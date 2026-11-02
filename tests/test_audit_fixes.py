"""
test_audit_fixes.py -- regression tests for the 2026-11-01 audit-repair pass
(docs/reports/AUDIT_2026-11-01.md). Fast tests run by default; `--slow` adds the full-circuit
legacy-equivalence check (~2 min).

Run:  /home/raghav/myenv/bin/python tests/test_audit_fixes.py [--slow]
"""
import os, sys
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model')); sys.path.insert(0, PROOT)
sys.path.insert(0, os.path.join(PROOT, 'experiments'))

import numpy as np
from brian2 import (NeuronGroup, SpikeMonitor, Network, PoissonGroup, Synapses, start_scope,
                    seed, second, ms, pA, mV, Hz, prefs)
prefs.codegen.target = 'numpy'
from parameters import params, som_params, md_params
from equations import eqs_som
from circuit_helpers import som_initial_voltages, som_period_and_vinf

FAILS = []


def check(name, cond, detail=''):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")
    if not cond:
        FAILS.append(name)


def _som_run(mode, n=20, bias=21.32, seed_val=44, T=1.0):
    start_scope(); seed(seed_val)
    p = dict(params); p.update(som_params)
    G = NeuronGroup(n, eqs_som, threshold='V>vThres_som', reset='V=vReset_som',
                    refractory=p['refrac_som'], method='euler', namespace=p)
    G.V = som_initial_voltages(n, p, bias, mode, seed_val); G.iBaseline_som = bias * pA
    m = SpikeMonitor(G); net = Network(G, m); net.run(T * second)
    t = np.round(np.asarray(m.t / ms), 4)
    return t, np.asarray(m.i), len(t) / T / n


def test_som_phase_modes():
    print('\n[1] SOM phase initialisation')
    t_sync, _, r_sync = _som_run('sync')
    t_rand, i_rand, r_rand = _som_run('random')
    t_even, _, r_even = _som_run('even')
    period, _ = som_period_and_vinf({**params, **som_params}, 21.32)
    check('analytic period matches ~30 Hz', abs(1 / period - 30.0) < 0.5, f'{1/period:.2f} Hz')
    check('sync: all 20 cells spike at identical times (legacy lockstep reproduced)',
          len(np.unique(t_sync)) * 20 == len(t_sync), f'{len(t_sync)} spikes / {len(np.unique(t_sync))} times')
    check('random: spike times are (almost) all distinct', len(np.unique(t_rand)) > 0.9 * len(t_rand),
          f'{len(np.unique(t_rand))}/{len(t_rand)} unique')
    check('even: spike times all distinct', len(np.unique(t_even)) == len(t_even))
    # steady-state per-cell rate unchanged by the phase (only the first cycle differs;
    # sync starts at vRest so its first spike is late -- compare median ISIs instead)
    ut = np.unique(t_sync); isi_s = np.median(np.diff(ut))
    isi_r = np.median([np.median(np.diff(t_rand[i_rand == k])) for k in range(20)])
    check('steady-state rate preserved (median ISI random vs sync < 0.1 ms apart)',
          abs(isi_s - isi_r) < 0.1, f'sync ISI {isi_s:.2f} ms, random ISI {isi_r:.2f} ms')
    # largest population-level gap: sync = one full period; random ~ few ms
    gaps_sync = np.diff(np.unique(t_sync[t_sync > 50])).max()
    gaps_rand = np.diff(np.unique(t_rand[t_rand > 50])).max()
    check('random: max population inter-spike gap << sync gap', gaps_rand < 0.5 * gaps_sync,
          f'sync max gap {gaps_sync:.1f} ms, random {gaps_rand:.1f} ms')
    # reproducible per seed, different across seeds
    t2, _, _ = _som_run('random')
    t3, _, _ = _som_run('random', seed_val=45)
    check('random phases reproducible for the same seed', np.array_equal(t_rand, t2))
    check('random phases differ across seeds', not np.array_equal(t_rand, t3))


def test_phase_init_does_not_touch_brian_rng():
    """som_initial_voltages must not consume Brian 2's / numpy's global RNG, otherwise
    switching sync->random would silently change connectivity and Poisson inputs."""
    print('\n[2] Phase init leaves the global RNG stream untouched')
    out = []
    for mode in ('sync', 'random'):
        start_scope(); seed(42)
        p = dict(params); p.update(som_params)
        _ = som_initial_voltages(20, p, 21.32, mode, 42)
        a = NeuronGroup(20, 'v:1'); b = NeuronGroup(2, 'v:1')
        s = Synapses(a, b); s.connect(p=0.5)
        out.append((np.asarray(s.i[:]).copy(), np.asarray(s.j[:]).copy(), np.random.rand()))
    check('identical connectivity after sync vs random init',
          np.array_equal(out[0][0], out[1][0]) and np.array_equal(out[0][1], out[1][1]))
    check('identical next global numpy draw', out[0][2] == out[1][2])


def test_subrheobase_and_bad_mode():
    print('\n[3] Edge cases')
    p = dict(params); p.update(som_params)
    v = som_initial_voltages(10, p, 15.0, 'random', 1)   # below rheobase (20 pA)
    check('sub-rheobase: voltages finite and below threshold',
          np.all(np.isfinite(v / mV)) and np.all(v < p['vThres_som']))
    try:
        som_initial_voltages(5, p, 21.32, 'bogus', 0); ok = False
    except ValueError:
        ok = True
    check('unknown mode raises ValueError', ok)


def _fresh(code):
    """Run `code` in a FRESH interpreter (Brian 2 PoissonGroup streams are only
    reproducible per seed across processes, not across builds in one process)."""
    import subprocess, json
    pre = (f"import sys,json; sys.path[:0]={[os.path.join(PROOT,'model'), PROOT, os.path.join(PROOT,'experiments')]!r}\n")
    out = subprocess.run([sys.executable, '-c', pre + code], capture_output=True, text=True, cwd=PROOT)
    line = [l for l in out.stdout.splitlines() if l.startswith('RESULT ')]
    if not line:
        raise RuntimeError(out.stderr[-2000:])
    return json.loads(line[-1][7:])


def test_full_circuit_legacy_equivalence():
    """Compiled coupling + som_phase='sync' must reproduce the legacy build exactly."""
    print('\n[4] (slow) full circuit: compiled coupling == legacy Python coupling (fresh processes)')
    res = {}
    for c in ('python', 'compiled'):
        res[c] = _fresh(
            "from full_circuit import build_gating_circuit\n"
            f"r=build_gating_circuit(T=1.0, md_signal_rate=0.0, noise_level=0.0, n_epochs=2, seed_val=44, som_phase='sync', coupling='{c}')\n"
            "print('RESULT '+json.dumps({k:r[k] for k in ('r0','r1','som_rate','pv_rate','pyr_rate')}))")
    a, b = res['python'], res['compiled']
    check('identical r0/r1/rates', a == b, f"python {a} | compiled {b}")


def test_plasticity_update():
    print('\n[5] Analytical plasticity update (src/v2/plasticity.py)')
    from src.v2.plasticity import yang_synapse_update as up
    r = up(0.0, 0.0, 0.73)
    check('silent synapse (alpha=0) holds rho exactly', r['rho_new'] == 0.73 and r['U'] == 0 and r['D'] == 0)
    # w0 = 0: general form == Yang's printed form
    for (ad, ap, rho) in [(0.9751, 0.0, 0.5), (2.9693, 2.8637, 0.5), (1.5, 0.4, 0.8), (3.0, 0.0, 0.92)]:
        r = up(ad, ap, rho)
        w_pre = 3.0 * rho
        printed = (w_pre * (1 - r['D']) + (3.0 - w_pre) * r['U']) / 3.0
        check(f'w0=0 matches Yang printed form (ad={ad}, ap={ap}, rho={rho})', abs(r['rho_new'] - printed) < 1e-12)
    # w0 != 0: rho_new must not depend on the weight scale
    a = up(1.5, 0.4, 0.8); b = up(1.5, 0.4, 0.8, w0=1.0, w1=4.0)
    check('rho update invariant to (w0, w1) when w0 != 0', abs(a['rho_new'] - b['rho_new']) < 1e-12,
          f"{a['rho_new']:.6f} vs {b['rho_new']:.6f}")
    check('w_post = w0 + (w1-w0) rho_new', abs(b['w_post'] - (1.0 + 3.0 * b['rho_new'])) < 1e-12)
    # pure depression drives rho down, potentiation-dominated drives it up
    check('depression-only lowers rho', up(3.0, 0.0, 0.9)['rho_new'] < 0.9)
    check('potentiation-dominated raises rho', up(3.0, 2.9, 0.5)['rho_new'] > 0.5)


def test_balanced_soma_preset():
    """(slow) The calibrated balanced-soma preset fires near Yang's ~10 Hz irregularly, and
    PV (MD->PV x1 vs x3) lowers the somatic rate gradually rather than silencing it."""
    print('\n[6] (slow) balanced somatic drive preset (fresh processes)')
    res = {}
    for x in (1.0, 3.0):
        res[x] = _fresh(
            "from brian2 import prefs, nS; prefs.codegen.target='cython'\n"
            "from context_circuit import run_context_protocol, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA\n"
            f"r=run_context_protocol([0,0], T=3.0, input_mode='always', seed_val=43, bap_source='soma', **BALANCED_SOMA_KW, "
            f"param_overrides={{'gAMPA_pv': 0.12*{x}*nS, 'gGABA_pv2soma': BALANCED_SOMA_G_PV2SOMA}})\n"
            "t=r['traj']; print('RESULT '+json.dumps(dict(pyr=sum(e['pyr_hz'] for e in t)/2, cv=t[-1]['pyr_cv'], pv=sum(e['pv_hz'] for e in t)/2)))")
    a, b = res[1.0], res[3.0]
    check('soma fires 5-15 Hz at MD->PV x1', 5.0 <= a['pyr'] <= 15.0, f"{a['pyr']:.1f} Hz (PV {a['pv']:.0f} Hz)")
    check('irregular, fluctuation-driven firing (ISI CV >= 0.7)', a['cv'] >= 0.7, f"CV {a['cv']:.2f}")
    check('stronger MD->PV lowers somatic rate gradually (x3 < x1, not abolished to 0)',
          0.0 < b['pyr'] < a['pyr'], f"x1 {a['pyr']:.1f} Hz -> x3 {b['pyr']:.1f} Hz (PV {b['pv']:.0f} Hz)")


if __name__ == '__main__':
    test_som_phase_modes()
    test_phase_init_does_not_touch_brian_rng()
    test_subrheobase_and_bad_mode()
    test_plasticity_update()
    if '--slow' in sys.argv:
        test_full_circuit_legacy_equivalence()
        test_balanced_soma_preset()
    print(f"\n{'ALL PASSED' if not FAILS else 'FAILED: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)
