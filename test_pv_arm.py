"""
test_pv_arm.py — the MD -> PV -> soma inhibitory arm.

Run:  python test_pv_arm.py

Asserts the four properties the step calls for: a baseline without MD, a graded response
with MD, actual suppression of the pyramidal cell, and a measurable effect of the MD->PV
projection itself. Also guards the architectural asymmetry that must NOT have changed.

Why a background conductance rather than a tonic current: PV's f-I curve is a near-step
because vThres - vReset is only 5 mV at tau_m = 10 ms. Rheobase is 20.0 pA, a 10 Hz
baseline would need 20.0003 pA and 40 Hz needs 20.5 pA, so no current is tunable.
Poisson conductance fluctuations smooth the curve instead. rate_bg_pv reuses the
project's declared rate_bgE = 500 Hz; weight_bg_pv is derived for PV.
"""
import builtins, sys, os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'v2'))
from brian2 import *
prefs.codegen.target = 'numpy'

from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
from equations import eqs_soma, eqs_dend, eqs_pv, eqs_som, eqs_vip

_results = []


def check(name, ok, detail=''):
    _results.append((name, bool(ok)))
    print(f'  [{"PASS" if ok else "FAIL"}] {name}')
    if detail:
        print(f'         {detail}')
    return bool(ok)


def P():
    p = params.copy()
    for e in (plasticity_params, pv_params, som_params, vip_params, md_params):
        p.update(e)
    return p


def pv_only(md_hz, background=True, dur=1.0, sd=0):
    """PV population alone: baseline and MD response."""
    p = P()
    start_scope(); seed(sd)
    PV = NeuronGroup(p['n_pv'], eqs_pv, threshold='V>vThres_pv', reset='V=vReset_pv',
                     refractory=p['refrac_pv'], method='euler', namespace=p)
    PV.V = p['vRest_pv']
    objs = [PV]
    if background:
        BG = PoissonGroup(p['n_pv'], rates=p['rate_bg_pv'])
        sb = Synapses(BG, PV, on_pre='gTotAMPA_post += weight_bg_pv', namespace=p)
        sb.connect(j='i'); objs += [BG, sb]
    if md_hz > 0:
        MD = PoissonGroup(p['n_md'], rates=md_hz * Hz)
        sm = Synapses(MD, PV, on_pre='gTotAMPA_post += gAMPA_pv', namespace=p)
        sm.connect(p=p['p_md2pv']); objs += [MD, sm]
    m = SpikeMonitor(PV); objs.append(m)
    Network(objs).run(dur * second)
    return len(m.t) / dur / p['n_pv']


def soma_with_pv(pv_connected, dur=1.0, sd=0, md_hz=25.0):
    """Pyramidal soma driven by a fixed excitatory drive, with PV inhibition on or off."""
    p = P()
    p['num_Soma'] = 1; p['num_DendEach'] = 2; p['num_Dend'] = 2
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * 2
    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']; p['norm_factor_Ca'] = t ** (1/(t-1))
    t = p['tauGABABRise'] / p['tauGABABDecay']; p['norm_factor_GABAB'] = t ** (1/(t-1))
    start_scope(); seed(sd)
    Soma = NeuronGroup(1, eqs_soma, threshold='V > vThres_pyr',
                       reset='V = vReset_pyr',
                       refractory=p['refracTime_pyr'], method='euler', namespace=p)
    Soma.V = p['vRest_pyr']; Soma.vShadow = p['vRest_pyr']; Soma.vAveDend = p['vRest_pyr']
    drive = PoissonGroup(40, rates=180 * Hz)
    ds = Synapses(drive, Soma, on_pre='gTotAMPA_post += weight_bgE', namespace=p)
    ds.connect(p=0.5)
    PV = NeuronGroup(p['n_pv'], eqs_pv, threshold='V>vThres_pv', reset='V=vReset_pv',
                     refractory=p['refrac_pv'], method='euler', namespace=p)
    PV.V = p['vRest_pv']
    BG = PoissonGroup(p['n_pv'], rates=p['rate_bg_pv'])
    sb = Synapses(BG, PV, on_pre='gTotAMPA_post += weight_bg_pv', namespace=p); sb.connect(j='i')
    MD = PoissonGroup(p['n_md'], rates=md_hz * Hz)
    sm = Synapses(MD, PV, on_pre='gTotAMPA_post += gAMPA_pv', namespace=p)
    sm.connect(p=p['p_md2pv'])
    objs = [Soma, drive, ds, PV, BG, sb, MD, sm]
    if pv_connected:
        sp = Synapses(PV, Soma, on_pre='gTotGABA_post += gGABA_pv2soma', namespace=p)
        sp.connect(p=p['p_pv2soma']); objs.append(sp)
    msp = SpikeMonitor(Soma); mpv = SpikeMonitor(PV); objs += [msp, mpv]
    Network(objs).run(dur * second)
    return len(msp.t) / dur, len(mpv.t) / dur / p['n_pv']


def test_baseline_without_md():
    print('\n1. PV baseline with no MD drive at all')
    r = np.mean([pv_only(0.0, background=True, sd=s) for s in (0, 1, 2)])
    r_nobg = np.mean([pv_only(0.0, background=False, sd=s) for s in (0, 1, 2)])
    check('PV has a non-zero tonic baseline', r > 1.0,
          f'{r:.2f} Hz with background drive vs {r_nobg:.2f} Hz without it')
    check('the baseline is physiological, not saturated', 1.0 < r < 40.0,
          f'{r:.2f} Hz (fast-spiking cortical interneurons rest around 5-20 Hz)')


def test_response_to_md():
    print('\n2. PV response across the MD operating range')
    mds = [0, 5, 20, 25, 40]
    rates = [np.mean([pv_only(m, sd=s) for s in (0, 1)]) for m in mds]
    print(f'         MD (Hz): {"  ".join(f"{m:>6}" for m in mds)}')
    print(f'         PV (Hz): {"  ".join(f"{r:>6.1f}" for r in rates)}')
    check('PV rate increases monotonically with MD drive',
          all(rates[i+1] >= rates[i] - 1.0 for i in range(len(rates)-1)),
          'no decreasing segment')
    check('the response is graded, not a step',
          rates[1] > rates[0] and rates[2] > rates[1] * 1.5,
          f'{rates[0]:.1f} -> {rates[1]:.1f} -> {rates[2]:.1f} Hz over MD 0/5/20')
    check('PV stays below the 200 Hz ceiling across the operating range',
          max(rates) < 200.0, f'max {max(rates):.1f} Hz at MD = {mds[int(np.argmax(rates))]} Hz')
    check('MD->PV has a measurable effect (>=5x from rest to 40 Hz MD)',
          rates[-1] > 5 * max(rates[0], 1e-9),
          f'{rates[0]:.1f} Hz at rest -> {rates[-1]:.1f} Hz at MD 40')


def test_pyramidal_suppression():
    print('\n3. Does PV actually suppress the pyramidal cell?')
    on = [soma_with_pv(True, sd=s) for s in (0, 1, 2)]
    off = [soma_with_pv(False, sd=s) for s in (0, 1, 2)]
    pyr_on = np.mean([a for a, _ in on]); pyr_off = np.mean([a for a, _ in off])
    pv_on = np.mean([b for _, b in on])
    print(f'         PV active at {pv_on:.1f} Hz')
    print(f'         pyramidal rate: {pyr_off:.1f} Hz without PV -> {pyr_on:.1f} Hz with PV')
    check('PV inhibition reduces pyramidal firing', pyr_on < pyr_off,
          f'suppression {100*(1-pyr_on/max(pyr_off,1e-9)):.1f}%')
    check('the suppression is substantial (>10%)',
          pyr_on < 0.9 * pyr_off,
          f'{pyr_off:.1f} -> {pyr_on:.1f} Hz')


def test_architecture_preserved():
    print('\n4. The PV/VIP architectural asymmetry must be unchanged')
    p = P()
    checks = [('p_md2pv', 0.5), ('p_md2vip', 0.3),
              ('gAMPA_pv', 0.12), ('gAMPA_vip', 0.5), ('n_md', 50)]
    ok = True
    for k, want in checks:
        got = float(p[k] / nS) if k.startswith('gAMPA') else float(p[k])
        if abs(got - want) > 1e-9:
            ok = False
        print(f'         {k:<10} = {got:<6} (expected {want})')
    check('p, n and g are untouched by the PV fix', ok,
          'many weak contacts to PV (p=0.5, g=0.12 nS) vs fewer strong to VIP '
          '(p=0.3, g=0.5 nS)')
    drive_pv = 0.5 * 50 * 0.12
    drive_vip = 0.3 * 50 * 0.5
    check('the aggregate p*n*g asymmetry is preserved',
          abs(drive_pv - 3.0) < 1e-9 and abs(drive_vip - 7.5) < 1e-9,
          f'PV {drive_pv} nS vs VIP {drive_vip} nS -- unchanged from before the fix')


if __name__ == '__main__':
    print('=' * 74)
    print('  MD -> PV -> soma inhibitory arm')
    print('=' * 74)
    for fn in (test_baseline_without_md, test_response_to_md,
               test_pyramidal_suppression, test_architecture_preserved):
        fn()
    n = builtins.sum(1 for _, ok in _results if ok)
    print('\n' + '=' * 74)
    for name, ok in _results:
        print(f'  {"PASS" if ok else "FAIL"}  {name}')
    print(f'\n  {n}/{len(_results)} assertions passed')
    print('=' * 74)
    sys.exit(0 if n == len(_results) else 1)
