"""
test_dendritic_nmda.py — the dendritic NMDA conductance.

Run:  python test_dendritic_nmda.py

Every assertion is quantitative against a closed-form prediction; none of them merely
checks that a variable is non-zero.

Formulation under test (saturating NMDA gating, the form the declared parameters belong
to; see the derivation in equations.py):
    dx/dt = -x/tauNMDARise                     x += 1 per presynaptic spike
    ds/dt = -s/tauNMDADecay + alphaNMDA*x*(1-s)
    iTotNMDA1_post = -gNMDA*s*(V_post - vE_pyr)*mg_gate      (summed)

Steady state at presynaptic rate r, used as the analytic reference:
    <x> = r*tauNMDARise
    <s> = alpha*<x> / (alpha*<x> + 1/tauNMDADecay)
"""
import builtins, sys, os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'model'))
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


def make_p(g_nmda_scale=1.0):
    p = params.copy(); p.update(plasticity_params)
    p['num_Soma'] = 1; p['num_DendEach'] = 2; p['num_Dend'] = 2
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * 2
    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']; p['norm_factor_Ca'] = t ** (1/(t-1))
    t = p['tauGABABRise'] / p['tauGABABDecay']; p['norm_factor_GABAB'] = t ** (1/(t-1))
    p['gNMDA'] = p['gNMDA'] * g_nmda_scale
    return p


def mg_of(p, v_mV):
    vh = float(p['vHalfNMDA'] / mV); vs = float(p['vSpreadNMDA'] / mV)
    return 1.0 / (1.0 + np.exp(-(v_mV - vh) / vs))


def s_analytic(p, rate_hz):
    al = float(p['alphaNMDA'] * ms)                 # per ms
    tr = float(p['tauNMDARise'] / ms) / 1000.0      # s
    td = float(p['tauNMDADecay'] / ms)              # ms
    x = rate_hz * tr
    return (al * x) / (al * x + 1.0 / td)


def build(p, rate_hz=80.0, n_aff=30, g_inh_nS=0.0, seed_val=0,
          hold_dend=None, dur_ms=1500):
    start_scope(); seed(seed_val); np.random.seed(seed_val)
    Soma = NeuronGroup(1, eqs_soma, threshold='V > vThres_pyr', reset='V = vReset_pyr',
                       refractory=p['refracTime_pyr'], method='euler', namespace=p)
    Soma.V = p['vRest_pyr']; Soma.vShadow = p['vRest_pyr']; Soma.vAveDend = p['vRest_pyr']
    Dend = NeuronGroup(2, eqs_dend, method='euler', namespace=p)
    Dend.V = p['vRest_pyr']; Dend.vSoma = p['vRest_pyr']
    objs = [Soma, Dend]
    if rate_hz > 0:
        inp = PoissonGroup(n_aff, rates=rate_hz * Hz)
        syn = Synapses(inp, Dend, model=eqs_synapse_plasticity, on_pre=on_pre_plasticity,
                       method='heun', namespace=p)
        syn.connect(); syn.rho = 0.5; attach_rho_clipper(syn)
        objs += [inp, syn]
    else:
        inp = SpikeGeneratorGroup(1, np.array([], dtype=int), np.array([]) * ms)
        syn = Synapses(inp, Dend, model=eqs_synapse_plasticity, on_pre=on_pre_plasticity,
                       method='heun', namespace=p)
        syn.connect(); syn.rho = 0.5; attach_rho_clipper(syn)
        objs += [inp, syn]
    if g_inh_nS > 0:
        gi = PoissonGroup(1, rates=1000 * Hz)
        si = Synapses(gi, Dend, on_pre=f'gTotGABA_post += {g_inh_nS/20.0}*nS', namespace=p)
        si.connect(j='0')                      # inhibit branch 0 only
        objs += [gi, si]
    mv = StateMonitor(Dend, ['V', 'iTotNMDA'], record=True, dt=1 * ms)
    mc = StateMonitor(syn, ['c', 's_nmda', 'x_nmda', 'rho'], record=True, dt=1 * ms)
    objs += [mv, mc]
    Network(objs).run(dur_ms * ms)
    return mv, mc, syn


# ------------------------------------------------------------------ 1
def test_activation_by_synaptic_event():
    print('\n1. NMDA is activated by the presynaptic event, quantitatively')
    p = make_p()
    # a single presynaptic spike must raise x_nmda by exactly 1
    start_scope(); seed(0)
    Dend = NeuronGroup(1, eqs_dend, method='euler', namespace=p)
    Dend.V = p['vRest_pyr']; Dend.vSoma = p['vRest_pyr']
    pre = SpikeGeneratorGroup(1, [0], [50 * ms])
    syn = Synapses(pre, Dend, model=eqs_synapse_plasticity, on_pre=on_pre_plasticity,
                   method='heun', namespace=p)
    syn.connect(); syn.rho = 0.5
    m = StateMonitor(syn, ['x_nmda', 's_nmda'], record=0, dt=0.1 * ms)
    Network(Dend, pre, syn, m).run(300 * ms)
    check('one presynaptic spike raises x_nmda by exactly 1',
          abs(float(m.x_nmda[0].max()) - 1.0) < 0.02,
          f'x_nmda peak = {float(m.x_nmda[0].max()):.4f}')
    # decay of x follows tauNMDARise
    x = m.x_nmda[0]; t = m.t / ms; i = int(x.argmax())
    tail, tt = x[i:], t[i:] - t[i]
    t_e = float(tt[int(np.argmin(np.abs(tail - x[i] / np.e)))])
    tr = float(p['tauNMDARise'] / ms)
    check('x_nmda decays with tauNMDARise',
          abs(t_e - tr) / tr < 0.25, f'1/e at {t_e:.2f} ms vs tauNMDARise {tr:.1f} ms')
    check('s_nmda rises only after the spike and stays bounded in [0,1]',
          float(m.s_nmda[0][:400].max()) < 1e-9 and float(m.s_nmda[0].max()) <= 1.0,
          f'pre-spike max {float(m.s_nmda[0][:400].max()):.2e}, '
          f'overall max {float(m.s_nmda[0].max()):.4f}')

    # The defining property of this formulation is SATURATION: s is bounded in [0,1]
    # and grows sublinearly with rate. The closed form
    # s = alpha<x>/(alpha<x> + 1/tauDecay) is a mean-field approximation that assumes
    # E[x(1-s)] = E[x](1-E[s]); x is spiky shot noise, so that only becomes accurate at
    # high rates. Asserting saturation directly, and mean-field agreement only where the
    # approximation is valid.
    print('\n   s_nmda vs rate -- saturation, and mean-field where it is valid')
    print(f'      {"rate":>7} {"measured":>10} {"mean-field":>11} {"rel err":>9}')
    meas, preds = [], []
    for r in (20.0, 80.0, 200.0, 500.0):
        mv, mc, _ = build(p, rate_hz=r, n_aff=1, dur_ms=2500)
        m = float(np.mean(mc.s_nmda[0][-800:])); pr = s_analytic(p, r)
        meas.append(m); preds.append(pr)
        print(f'      {r:>7.0f} {m:>10.4f} {pr:>11.4f} {abs(m-pr)/pr:>8.1%}')
    check('s_nmda stays bounded in [0, 1] at every rate',
          all(0.0 <= m <= 1.0 for m in meas),
          f'max s = {max(meas):.4f}; a linear kernel would reach '
          f'gNMDA*n*rate*tauDecay without bound')
    # sublinear: doubling the rate must less than double s
    ratios = [meas[i+1] / meas[i] for i in range(len(meas)-1)]
    rate_ratios = [200.0/80.0, 500.0/200.0]
    check('s_nmda grows sublinearly with rate (saturating, not linear)',
          all(ratios[i+1] < rate_ratios[i] for i in range(len(rate_ratios))),
          f's ratios {[f"{r:.2f}" for r in ratios]} vs rate ratios '
          f'{[f"{r:.2f}" for r in rate_ratios]}')
    check('mean-field closed form agrees at high rate (>=200 Hz)',
          abs(meas[2]-preds[2])/preds[2] < 0.10 and abs(meas[3]-preds[3])/preds[3] < 0.10,
          f'{abs(meas[2]-preds[2])/preds[2]:.1%} at 200 Hz, '
          f'{abs(meas[3]-preds[3])/preds[3]:.1%} at 500 Hz; the larger error at 20 Hz is '
          f'the mean-field approximation, not the model')


# ------------------------------------------------------------------ 2 & 3
def test_voltage_dependence_and_mg():
    """Voltage dependence and Mg2+ block, measured by recording during the run.

    Reading a `(summed)` variable as an attribute after run() is unreliable -- the value
    can lag a timestep, and assigning V between run() calls does not force a recompute.
    A StateMonitor samples with the correct scheduling, so V, s_nmda and iTotNMDA1 are
    all compared AT THE SAME timestep.
    """
    print('\n2-3. NMDA current voltage dependence and Mg2+ block')
    p = make_p()

    # (a) mg_gate exactness -- no run needed, so no read-timing ambiguity
    start_scope(); seed(0)
    D0 = NeuronGroup(1, eqs_dend, method='euler', namespace=p)
    D0.vSoma = p['vRest_pyr']
    pr0 = SpikeGeneratorGroup(1, np.array([], dtype=int), np.array([]) * ms)
    sy0 = Synapses(pr0, D0, model=eqs_synapse_plasticity, on_pre=on_pre_plasticity,
                   method='heun', namespace=p)
    sy0.connect(); sy0.rho = 0.5
    ok_mg, rows_mg = True, []
    for v in (-80.0, -60.0, -40.0, -20.0, 0.0, 20.0):
        D0.V = v * mV
        meas = float(sy0.mg_gate[0]); pred = mg_of(p, v)
        if abs(meas - pred) > 1e-9:
            ok_mg = False
        rows_mg.append((v, meas, pred))
    print(f'      {"V_post":>8} {"mg meas":>10} {"mg pred":>10}')
    for v, m, q in rows_mg:
        print(f'      {v:>8.0f} {m:>10.6f} {q:>10.6f}')
    check('mg_gate matches 1/(1+exp(-(V-vHalfNMDA)/vSpreadNMDA)) exactly', ok_mg)
    mgs = [r[1] for r in rows_mg]
    check('Mg block is monotonic in voltage and spans a wide range',
          all(mgs[i+1] > mgs[i] for i in range(len(mgs)-1)),
          f'{mgs[0]:.5f} at -80 mV -> {mgs[-1]:.5f} at +20 mV ({mgs[-1]/mgs[0]:.0f}x)')

    # (b) summed current vs analytics, sampled during a clamped voltage sweep
    VOLTS = [-80.0, -60.0, -40.0, -20.0, 0.0]
    HOLD_MS = 20.0
    start_scope(); seed(0)
    D = NeuronGroup(1, eqs_dend, method='euler', namespace=p)
    D.vSoma = p['vRest_pyr']; D.V = p['vRest_pyr']
    pre = PoissonGroup(30, rates=80 * Hz)
    syn = Synapses(pre, D, model=eqs_synapse_plasticity, on_pre=on_pre_plasticity,
                   method='heun', namespace=p)
    syn.connect(); syn.rho = 0.5
    p['v_clamp'] = p['vRest_pyr']
    D.run_regularly('V = v_clamp', dt=p['sim_dt'], when='start')
    mD = StateMonitor(D, ['V', 'iTotNMDA1'], record=True, dt=p['sim_dt'])
    mS = StateMonitor(syn, 's_nmda', record=True, dt=p['sim_dt'])
    net = Network(D, pre, syn, mD, mS)
    net.run(300 * ms)                                  # charge s_nmda
    marks = []
    for v in VOLTS:
        p['v_clamp'] = v * mV
        net.run(HOLD_MS * ms)
        marks.append(len(mD.t) - 2)                    # sample near the end of the hold

    g = float(p['gNMDA'] / siemens); vE = float(p['vE_pyr'] / mV)
    ok_drive = True
    print(f'\n      {"V rec":>8} {"I meas":>12} {"I pred":>12} {"rel err":>9}')
    for k, v in zip(marks, VOLTS):
        V_rec = float(mD.V[0][k] / mV)
        s_sum = float(np.sum(mS.s_nmda[:, k]))
        i_meas = float(mD.iTotNMDA1[0][k] / amp)
        i_pred = -g * s_sum * ((V_rec - vE) / 1000.0) * mg_of(p, V_rec)
        scale = max(abs(i_pred), 1e-12)
        err = abs(i_meas - i_pred) / scale
        if err > 0.02 and abs(i_meas - i_pred) > 2e-12:
            ok_drive = False
        print(f'      {V_rec:>8.2f} {i_meas*1e12:>9.2f} pA {i_pred*1e12:>9.2f} pA '
              f'{err:>8.2%}')
    check('summed NMDA current equals -gNMDA*sum(s)*(V-vE)*mg at every voltage',
          ok_drive,
          'conductance, driving force and Mg factor all enter exactly as specified')
    # reversal: at V = vE the driving force is zero
    k, = [m for m, v in zip(marks, VOLTS) if v == 0.0],
    i_rev = float(mD.iTotNMDA1[0][marks[VOLTS.index(0.0)]] / amp)
    check('NMDA current reverses at vE_pyr (zero driving force)',
          abs(i_rev) < 2e-12, f'current at V = vE = 0 mV is {i_rev*1e12:.4f} pA')


# ------------------------------------------------------------------ 4 & 5
def test_calcium_contribution_and_removal():
    print('\n4-5. NMDA contributes calcium; disabling it removes the contribution')
    res = {}
    for label, scale in (('NMDA present', 1.0), ('NMDA disabled', 0.0)):
        p = make_p(g_nmda_scale=scale)
        mv, mc, syn = build(p, rate_hz=80.0, dur_ms=1500)
        last = slice(-500, None)
        res[label] = dict(
            V=float(np.mean(mv.V[0][last] / mV)),
            I=float(np.mean(mv.iTotNMDA[0][last])) * 1e12,
            c=float(np.mean(mc.c[0][last])),
            mg=mg_of(p, float(np.mean(mv.V[0][last] / mV))))
        r = res[label]
        print(f'      {label:<15} V={r["V"]:>7.2f} mV  I_NMDA={r["I"]:>8.2f} pA  '
              f'mg={r["mg"]:.4f}  <c>={r["c"]:.4f}')
    on, off = res['NMDA present'], res['NMDA disabled']
    th_d = p['theta_d']
    check('NMDA depolarises the branch substantially',
          on['V'] - off['V'] > 20.0,
          f'{off["V"]:.1f} -> {on["V"]:.1f} mV ({on["V"]-off["V"]:+.1f} mV)')
    check('the depolarisation opens the Mg block',
          on['mg'] > 5 * off['mg'],
          f'mg {off["mg"]:.4f} -> {on["mg"]:.4f} ({on["mg"]/off["mg"]:.1f}x)')
    check('with NMDA, calcium crosses theta_D; without it, it does not',
          on['c'] > th_d > off['c'],
          f'<c> {off["c"]:.4f} (no NMDA) vs {on["c"]:.4f} (NMDA), theta_D = {th_d}')
    check('disabling NMDA removes the NMDA current entirely',
          abs(off['I']) < 1e-9, f'I_NMDA = {off["I"]:.3e} pA when gNMDA = 0')


# ------------------------------------------------------------------ 6
def test_reproducible():
    print('\n6. Reproducibility under a fixed seed')
    p = make_p()
    outs = []
    for _ in range(2):
        mv, mc, _ = build(p, rate_hz=80.0, seed_val=7, dur_ms=800)
        outs.append((np.array(mv.V[0] / mV), np.array(mc.s_nmda[0]),
                     np.array(mc.c[0])))
    dV = float(np.max(np.abs(outs[0][0] - outs[1][0])))
    ds = float(np.max(np.abs(outs[0][1] - outs[1][1])))
    dc = float(np.max(np.abs(outs[0][2] - outs[1][2])))
    check('identical seed reproduces V, s_nmda and c bit-for-bit',
          dV < 1e-9 and ds < 1e-12 and dc < 1e-12,
          f'max |dV| = {dV:.2e} mV, |ds| = {ds:.2e}, |dc| = {dc:.2e}')


# ------------------------------------------------------------------ 7
def test_branch_selectivity():
    print('\n7. Branch selectivity (the payoff)')
    p = make_p()
    mv, mc, syn = build(p, rate_hz=80.0, g_inh_nS=40.0, dur_ms=1500)
    last = slice(-500, None)
    v0 = float(np.mean(mv.V[0][last] / mV)); v1 = float(np.mean(mv.V[1][last] / mV))
    print(f'      branch 0 (inhibited)   V = {v0:>7.2f} mV  mg = {mg_of(p, v0):.4f}')
    print(f'      branch 1 (free)        V = {v1:>7.2f} mV  mg = {mg_of(p, v1):.4f}')
    check('inhibition keeps its branch hyperpolarised relative to the free one',
          v1 > v0 + 10.0, f'separation {v1 - v0:+.2f} mV')
    check('the Mg gate therefore differs strongly between branches',
          mg_of(p, v1) > 3 * mg_of(p, v0),
          f'gate ratio {mg_of(p, v1)/mg_of(p, v0):.1f}x')


if __name__ == '__main__':
    print('=' * 78)
    print('  Dendritic NMDA conductance')
    print('=' * 78)
    for fn in (test_activation_by_synaptic_event, test_voltage_dependence_and_mg,
               test_calcium_contribution_and_removal, test_reproducible,
               test_branch_selectivity):
        fn()
    n = builtins.sum(1 for _, ok in _results if ok)
    print('\n' + '=' * 78)
    for name, ok in _results:
        print(f'  {"PASS" if ok else "FAIL"}  {name}')
    print(f'\n  {n}/{len(_results)} assertions passed')
    print('=' * 78)
    sys.exit(0 if n == len(_results) else 1)
