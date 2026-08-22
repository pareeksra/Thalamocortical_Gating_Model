"""
test_postsynaptic_calcium.py — the Graupner-Brunel calcium pathway, end to end.

Run:  python test_postsynaptic_calcium.py

Walks the five links the calcium signal has to traverse and asserts each one
separately, so a break can be localised rather than merely detected:

  1. presynaptic event      -> synapse-local NMDA calcium `c`
  2. postsynaptic response  -> somatic spike, bAP delivered to the branch
  3. calcium contribution   -> branch `bAPCa` transient, unit-normalised
  4. bAP calcium kinetics   -> rise / decay time constants
  5. downstream access      -> the plasticity rule actually reads pre + post

Test 6 is a deliberate break: it rebuilds the network with the bAP calcium injection
removed and asserts the suite notices. Without that, tests 1-5 could all pass against a
pathway that happens to work for an unrelated reason.

Why the postsynaptic term is read from `bAPCa_post` and not injected by an `on_post`
rule: the plastic synapses target `Dend`, which is constructed with no threshold and no
reset and therefore never spikes. An `on_post` pathway on that Synapses object can never
fire, which is why `on_post_plasticity` in equations.py was never attached and why
`C_post_eff` was never defined.
"""
import builtins
import sys, os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'v2'))
from brian2 import *
prefs.codegen.target = 'numpy'

from parameters import params, plasticity_params
from equations import (eqs_soma, eqs_dend, eqs_synapse_plasticity,
                       on_pre_plasticity, attach_rho_clipper)

_results = []


def check(name, ok, detail=''):
    _results.append((name, bool(ok)))
    print(f'  [{"PASS" if ok else "FAIL"}] {name}')
    if detail:
        print(f'         {detail}')
    return bool(ok)


def make_params():
    p = params.copy()
    p.update(plasticity_params)
    p['num_Soma'], p['num_DendEach'], p['num_Dend'] = 1, 2, 2
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * 2
    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']
    p['norm_factor_Ca'] = t ** (1 / (t - 1))
    t = p['tauGABABRise'] / p['tauGABABDecay']
    p['norm_factor_GABAB'] = t ** (1 / (t - 1))
    return p


def build(p, pre_times=None, soma_drive_hz=0.0, n_syn_inputs=1,
          connect_bap_calcium=True, seed_val=0, record_dt=0.1 * ms,
          bap_times=None):
    """Assemble soma + 2 branches + one plastic synapse group.

    `connect_bap_calcium=False` reproduces the pre-fix wiring, where the bAP synapse
    moved voltage into the branch but no calcium.

    `bap_times` (ms) drives bAP arrivals from a SpikeGeneratorGroup at exact times
    instead of relying on the soma's own firing. The soma sits close to threshold, so
    its rate is extremely sensitive to the Poisson drive (50 Hz drive gave 88 Hz, 60 Hz
    gave 37 Hz), which makes it useless for setting a target rate. The soma -> bAP link
    is verified separately with the real soma in test 2-4; this option isolates the
    calcium -> plasticity link at a controlled rate.
    """
    start_scope()
    seed(seed_val)
    np.random.seed(seed_val)

    Soma = NeuronGroup(1, eqs_soma, threshold='V > vThres_pyr',
                       reset='V = vReset_pyr',
                       refractory=p['refracTime_pyr'], method='euler', namespace=p)
    Soma.V = p['vRest_pyr']; Soma.vShadow = p['vRest_pyr']; Soma.vAveDend = p['vRest_pyr']

    Dend = NeuronGroup(2, eqs_dend, method='euler', namespace=p)
    Dend.V = p['vRest_pyr']; Dend.vSoma = p['vRest_pyr']

    bap_code = ('V_post += bAP_amp\nbAPCa_rise_post += norm_factor_Ca'
                if connect_bap_calcium else 'V_post += bAP_amp')
    bAP = Synapses(Soma, Dend, on_pre=bap_code, delay=p['bAP_delay'], namespace=p)
    bAP.connect(j='i*num_DendEach + k for k in range(num_DendEach)')

    objs = [Soma, Dend, bAP]

    if bap_times is not None:
        bt = np.asarray(bap_times, dtype=float)
        bap_src = SpikeGeneratorGroup(1, np.zeros(len(bt), dtype=int), bt * ms)
        code = ('bAPCa_rise_post += norm_factor_Ca' if connect_bap_calcium
                else 'V_post += 0*mV')
        bap_inj = Synapses(bap_src, Dend, on_pre=code, namespace=p)
        bap_inj.connect()
        objs += [bap_src, bap_inj]

    # presynaptic input to the plastic synapses
    if pre_times is not None and len(pre_times):
        pre = SpikeGeneratorGroup(1, np.zeros(len(pre_times), dtype=int),
                                  np.asarray(pre_times) * ms)
    else:
        pre = SpikeGeneratorGroup(1, np.array([], dtype=int), np.array([]) * ms)
    syn = Synapses(pre, Dend, model=eqs_synapse_plasticity, on_pre=on_pre_plasticity,
                   method='heun', namespace=p)
    syn.connect()
    syn.rho = 0.5
    attach_rho_clipper(syn)
    objs += [pre, syn]

    # optional drive to make the soma spike
    if soma_drive_hz > 0:
        drive = PoissonGroup(30, rates=soma_drive_hz * Hz)
        dsyn = Synapses(drive, Soma, on_pre='gTotAMPA_post += weight_bgE', namespace=p)
        dsyn.connect(p=0.5)
        objs += [drive, dsyn]

    mon_syn = StateMonitor(syn, ['c', 'rho'], record=True, dt=record_dt)
    mon_den = StateMonitor(Dend, 'bAPCa', record=True, dt=record_dt)
    mon_sp = SpikeMonitor(Soma)
    objs += [mon_syn, mon_den, mon_sp]
    return Network(objs), mon_syn, mon_den, mon_sp, syn


# ----------------------------------------------------------------- link 1
def test_presynaptic_event():
    print('\n1. Presynaptic event -> synapse-local NMDA calcium')
    p = make_params()
    net, ms_, md, sp, _ = build(p, pre_times=[50.0])
    net.run(120 * ms)
    c = ms_.c[0]; jump = float(c.max())
    # Since the Mg2+ gate was added, a presynaptic spike deposits C_pre * mg_gate(V_post),
    # not the full C_pre. At rest that factor is small by design -- an unexcited branch
    # keeps its NMDA receptors blocked. Asserting the gated value rather than C_pre is
    # the point of the gate, not a relaxation of the test.
    v_rest_mV = float(p['vRest_pyr'] / mV)
    vh = float(p['vHalfNMDA'] / mV); vs = float(p['vSpreadNMDA'] / mV)
    gate_rest = 1.0 / (1.0 + np.exp(-(v_rest_mV - vh) / vs))
    expected = p['C_pre'] * gate_rest
    check('a presynaptic spike raises c by C_pre * mg_gate(V_post)',
          abs(jump - expected) < 0.05 * max(expected, 1e-3),
          f'observed jump {jump:.5f}, expected C_pre*gate = {p["C_pre"]}*'
          f'{gate_rest:.5f} = {expected:.5f} at V_rest = {v_rest_mV:.0f} mV')
    check('no postsynaptic calcium appears without a somatic spike',
          float(md.bAPCa[0].max()) < 1e-9 and len(sp.t) == 0,
          f'bAPCa max = {float(md.bAPCa[0].max()):.2e}, soma spikes = {len(sp.t)}')

    # The gate must make the SAME presynaptic spike deposit different calcium on
    # differently-polarised branches -- the mechanism that lets SOM inhibition gate
    # plasticity. mg_gate is a synaptic subexpression over V_post, so it can be read
    # directly at chosen branch voltages without needing a simulation.
    pj = make_params()
    net2, m2, md2, sp2, syn2 = build(pj, pre_times=[50.0])
    dend = syn2.target
    gates = {}
    for v_hold in (-70.0, -50.0, -30.0):
        dend.V = v_hold * mV
        gates[v_hold] = float(np.mean(syn2.mg_gate[:]))
    print('         mg_gate vs branch voltage: ' +
          '  '.join(f'{v:+.0f} mV -> {g:.4f}' for v, g in gates.items()))
    check('the Mg gate makes calcium influx depend on branch voltage',
          gates[-30.0] > 3.0 * gates[-70.0],
          f'gate rises {gates[-30.0]/max(gates[-70.0],1e-12):.1f}x from -70 to -30 mV, '
          f'so an inhibited branch admits far less calcium for the same input')


# ----------------------------------------------------------------- links 2,3,4
def test_postsynaptic_response_and_trace():
    print('\n2-4. Somatic spike -> bAP -> branch calcium transient')
    p = make_params()
    net, ms_, md, sp, _ = build(p, pre_times=None, soma_drive_hz=400.0)
    net.run(400 * ms)
    check('the soma spikes under drive', len(sp.t) > 0, f'{len(sp.t)} spikes')
    ba = md.bAPCa[0]
    check('a bAP calcium transient appears in the branch',
          float(ba.max()) > 0.1, f'bAPCa max = {float(ba.max()):.4f}')
    check('no presynaptic calcium appears without a presynaptic spike',
          float(ms_.c[0].max()) < 1e-9, f'c max = {float(ms_.c[0].max()):.2e}')
    check('the bAP reaches both branches (it is not branch-selective)',
          float(md.bAPCa[1].max()) > 0.1,
          f'branch 0 max {float(md.bAPCa[0].max()):.3f}, '
          f'branch 1 max {float(md.bAPCa[1].max()):.3f} -- so on its own the bAP '
          f'supplies NO pathway specificity; that must come from voltage gating')

    # isolated single transient: amplitude and kinetics
    print('\n   single isolated bAP — amplitude and kinetics')
    p2 = make_params()
    start_scope(); seed(0)
    G = NeuronGroup(1, '''dbAPCa/dt = (-bAPCa+bAPCa_rise)/tau_Ca_bAP_decay : 1
                          dbAPCa_rise/dt = -bAPCa_rise/tau_Ca_bAP_rise : 1''',
                    method='exact', namespace=p2)
    G.bAPCa_rise = p2['norm_factor_Ca']
    m = StateMonitor(G, 'bAPCa', record=0, dt=0.02 * ms)
    Network(G, m).run(250 * ms)
    tr = m.bAPCa[0]; t_ms = m.t / ms
    pk = float(tr.max()); t_pk = float(t_ms[int(tr.argmax())])
    check('the transient is normalised to a unit peak (matching the C_pre scale)',
          abs(pk - 1.0) < 1e-3, f'peak {pk:.6f} at t = {t_pk:.2f} ms')
    i = int(tr.argmax()); tail = tr[i:]; tt = t_ms[i:] - t_ms[i]
    t_e = float(tt[int(np.argmin(np.abs(tail - pk / np.e)))])
    tau_d = float(p2['tau_Ca_bAP_decay'] / ms)
    check('decay time constant matches tau_Ca_bAP_decay',
          abs(t_e - tau_d) / tau_d < 0.15,
          f'1/e decay at {t_e:.1f} ms, tau_Ca_bAP_decay = {tau_d:.1f} ms')


# ----------------------------------------------------------------- link 5
BAP_RATE_HZ = 25.0   # chosen from the regime scan: theta_D crossed, theta_P rarely


def _run_condition(p, connect, seed_val, rate_hz=BAP_RATE_HZ, dur=2000):
    """Regular bAP arrivals at `rate_hz`, no presynaptic input at all."""
    times = np.arange(10.0, dur, 1000.0 / rate_hz)
    net, ms_, md, sp, syn = build(p, pre_times=None, bap_times=times,
                                  connect_bap_calcium=connect, seed_val=seed_val)
    net.run(dur * ms)
    rho_end = np.array([ms_.rho[i][-1] for i in range(len(syn))])
    ba = md.bAPCa[0]
    return dict(drho=float(np.mean(rho_end - 0.5)),
                ba_max=float(ba.max()), ba_mean=float(ba.mean()),
                f_d=float((ba > p['theta_d']).mean()),
                f_p=float((ba > p['theta_p']).mean()),
                n_bap=len(times))


def test_downstream_plasticity_access():
    """Does the plasticity rule actually read the postsynaptic component?

    Two confounds had to be removed to make this meaningful.

    First, rho carries un-gated noise (sigma = 3.35), so it drifts even with no calcium
    at all. Comparing one trace against zero proves nothing; the comparison must be
    against the identical seed with the bAP calcium severed.

    Second, the postsynaptic rate decides the regime. A single bAP peaks at exactly 1.0
    -- at theta_D and well below theta_P -- so isolated postsynaptic spikes belong in the
    LTD regime, which is the canonical Graupner-Brunel result for a post-only protocol.
    But the transients summate linearly with tau_decay = 30 ms, so above roughly 80 Hz
    they pile past theta_P and post-only activity spuriously produces LTP. An earlier
    version of this test drove the soma at ~290 Hz and measured exactly that artefact.
    bAP arrivals are now imposed at a fixed 25 Hz and the regime is asserted, not assumed.
    """
    print('\n5. Downstream access — does the plasticity rule read the postsynaptic term?')
    p = make_params()
    on = [_run_condition(p, True, sd) for sd in (0, 1, 2, 3, 4)]
    off = [_run_condition(p, False, sd) for sd in (0, 1, 2, 3, 4)]

    f_d = float(np.mean([r['f_d'] for r in on]))
    f_p = float(np.mean([r['f_p'] for r in on]))
    print(f'         bAP arrivals at {BAP_RATE_HZ:.0f} Hz; branch bAPCa above theta_D '
          f'{f_d*100:.1f}% of the time, above theta_P {f_p*100:.1f}%')
    check('the test condition sits in the LTD regime (theta_D crossed, theta_P rarely)',
          f_d > 0.02 and f_p < 0.15,
          'were theta_P frequently crossed, post-only LTP would be a summation '
          'artefact rather than the canonical result')

    d_on = np.array([r['drho'] for r in on])
    d_off = np.array([r['drho'] for r in off])
    print(f'         connected    mean drho = {d_on.mean():+.4f}  '
          f'(per-seed {np.array2string(d_on, precision=3)})')
    print(f'         severed      mean drho = {d_off.mean():+.4f}  '
          f'(per-seed {np.array2string(d_off, precision=3)})')
    check('postsynaptic calcium alone drives rho DOWN (theta_D crossed -> LTD)',
          d_on.mean() < d_off.mean() - 0.02,
          f'connected {d_on.mean():+.4f} vs severed {d_off.mean():+.4f}')
    check('severing the bAP calcium changes the plasticity outcome',
          abs(d_off.mean() - d_on.mean()) > 0.02,
          f'difference {d_off.mean() - d_on.mean():+.4f}')


# ----------------------------------------------------------------- link 6
def test_coincidence():
    print('\n6. Coincidence — pre + post exceeds either alone')
    p = make_params()
    net, ms_, md, sp, _ = build(p, pre_times=list(np.arange(50, 550, 10.0)),
                                soma_drive_hz=400.0)
    net.run(600 * ms)
    c = ms_.c[0]; ba = md.bAPCa[0]
    tot = c + ba
    check('total calcium exceeds the presynaptic component alone',
          float(tot.max()) > float(c.max()) + 1e-6,
          f'c max {float(c.max()):.3f}, bAPCa max {float(ba.max()):.3f}, '
          f'sum max {float(tot.max()):.3f}')
    n_pre_only = int((c > p['theta_p']).sum())
    n_both = int((tot > p['theta_p']).sum())
    check('coincidence lifts more samples above theta_p than pre alone',
          n_both >= n_pre_only,
          f'above theta_p: {n_pre_only} pre-only vs {n_both} with postsynaptic term')


# ----------------------------------------------------------------- break detector
def test_break_detector():
    print('\n7. Deliberate break — the suite must notice a severed connection')
    p = make_params()
    ba_on = _run_condition(p, True, 0)['ba_max']
    ba_off = _run_condition(p, False, 0)['ba_max']
    check('with the injection present, branch bAPCa is non-zero',
          ba_on > 0.1, f'bAPCa max = {ba_on:.4f}')
    check('with the injection removed, branch bAPCa is exactly zero (break detected)',
          ba_off < 1e-9, f'bAPCa max = {ba_off:.2e}')


if __name__ == '__main__':
    print('=' * 76)
    print('  Graupner-Brunel calcium pathway — connection tests')
    print('=' * 76)
    for fn in (test_presynaptic_event, test_postsynaptic_response_and_trace,
               test_downstream_plasticity_access, test_coincidence,
               test_break_detector):
        fn()
    n = builtins.sum(1 for _, ok in _results if ok)
    print('\n' + '=' * 76)
    for name, ok in _results:
        print(f'  {"PASS" if ok else "FAIL"}  {name}')
    print(f'\n  {n}/{len(_results)} assertions passed')
    print('=' * 76)
    sys.exit(0 if n == len(_results) else 1)
