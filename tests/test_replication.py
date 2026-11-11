"""
test_replication.py -- R5 of docs/reports/PLAN_robustness.md: the replication numbers of the
canonical model frozen as automated checks with tolerances (2026-11-10).

Canonical model = model/context_circuit.py defaults: Yang NMDA-plastic synapse,
fluctuation-driven SOM baseline, bAP calcium x0.2 (Yang's in-vivo recalibration). Each check names the result it freezes; tolerances are
set from the multi-seed spread recorded there, not from one lucky run.

Fast (default, ~5 min on 8 cores):
  F1 SOM baseline rate and its robustness to +/-25% of each drive parameter (isolated SOM)
     -- results/current/som_baseline_fix.json
  F2 dendrite I/O half-activation vs Yang's g_1/2 = 5.56 (4 + g_inh), canonical synapse
     -- results/current/v1_dendrite_io_yang.json
  F3 branch gating, seed 42 (always-on inputs, A x 8) -- robustness_r2.json (20/20 seeds)
  F4 retention of A with silent inputs (context inputs, A x 8 then B x 8) -- robustness_r3.json
  F5 Fig. 5 gating selectivity S at the default wiring, seed 42 -- som_baseline_fix.json
  F6 plasticity rule and audit fixes -- tests/test_audit_fixes.py (run as a subprocess)
Slow (--slow, ~25 min on 8 cores):
  S1 learning creates gating (Yang Fig. 7d,e): S after learning at a 10 Hz readout,
     seeds 42-44, and S before learning ~ 0 at equal drive -- robustness_r4_readout.json
  S2 dt convergence: |rho(dt 0.05) - rho(dt 0.1)| < 0.01 -- robustness_r2.json
  S3 Yang Fig. 7b regimes: free branch LTP at high rate, inhibited branch LTD at the same
     rate, no change at 2 Hz -- paper_comparison.json
  S4 MD control (Zhang wiring): VIP silences its SOM channel, PV rises with MD. MD 25 Hz = the canonical context rate (was 20 Hz until VIP->SOM x0.25 became canonical; at 20 Hz own SOM is now 3 Hz)
     -- paper_comparison.json
  S5 epoch-length independence: learn A, then a 300-s idle phase (A silent) applied as ONE
     epoch keeps A (retention >= 0.98) -- epoch_length_check.json (bAP x1.0 gave 0.12)
Run:  <py> -I tests/test_replication.py [--slow] [n_workers]
Exit code 0 iff every check passes; one PASS/FAIL line per check.
"""
import os, sys, subprocess, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]


def _cy():
    from brian2 import prefs
    prefs.codegen.target = 'cython'


# ---------------------------------------------------------------- simulation jobs
def j_som_isolated():
    _cy()
    from brian2 import NeuronGroup, PoissonGroup, Synapses, SpikeMonitor, Network, seed, start_scope, \
        pA, nS, Hz, second, BrianLogger
    BrianLogger.log_level_error()
    from parameters import som_params
    from equations import eqs_som
    from context_circuit import SOM_NOISY_KW
    p = dict(som_params); p.pop('iBaseline_som')

    def rate(bias, R, w, n=40, T=6.0):
        start_scope(); seed(3)
        G = NeuronGroup(n, eqs_som, threshold='V>vThres_som', reset='V=vReset_som',
                        refractory=p['refrac_som'], method='euler', namespace=p)
        G.V = p['vRest_som']; G.iBaseline_som = bias * pA
        B = PoissonGroup(n, rates=R * Hz)
        S = Synapses(B, G, on_pre=f'gTotAMPA_post += {w}*nS'); S.connect(j='i')
        M = SpikeMonitor(G); Network(G, B, S, M).run(T * second)
        return M.num_spikes / T / n
    b, R, w = SOM_NOISY_KW['som_bias_pA'], SOM_NOISY_KW['som_bg_E_hz'], SOM_NOISY_KW['som_bg_nS']
    out = dict(base=rate(b, R, w))
    for f in (0.75, 1.25):
        out[f'bias_{f}'] = rate(b * f, R, w)
        out[f'rate_{f}'] = rate(b, R * f, w)
        out[f'w_{f}'] = rate(b, R, w * f)
    return out


def j_v1():
    _cy()
    sys.argv = ['x', 'yang']
    import v1_dendrite_io_measured as v1
    combos, V, gE, _ = v1.measure()
    out = {}
    for g in (0.0, 2.0, 6.0):
        idx = [k for k, c in enumerate(combos) if c[0] == g]
        out[g] = v1.half_point(gE[idx], V[idx])[0]
    return out


def j_gating(seed=42, dt_ms=None):
    _cy()
    from brian2 import defaultclock, ms
    if dt_ms:
        defaultclock.dt = dt_ms * ms
    from context_circuit import run_context_protocol
    tr = run_context_protocol([0] * 8, T=3.0, input_mode='always', seed_val=seed)['traj']
    return dict(rho_free=tr[-1]['rho0'], rho_inh=tr[-1]['rho1'], som_base=np.mean([t['som1_hz'] for t in tr]),
                som_off=np.mean([t['som0_hz'] for t in tr]))


def j_retention(seed=42):
    _cy()
    from context_circuit import run_context_protocol
    tr = run_context_protocol([0] * 8 + [1] * 8, T=3.0, input_mode='context', seed_val=seed)['traj']
    return tr[-1]['rho0'] / tr[7]['rho0']


def j_fig5(seed=42):
    _cy()
    from context_circuit import run_context_protocol, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA
    from gating_selectivity_fig5 import selectivity, CTX, STIM
    r = run_context_protocol(CTX, T=5.0, input_mode='context', stim=STIM, plastic=False, bap_source='soma',
                             seed_val=seed, param_overrides={'gGABA_pv2soma': BALANCED_SOMA_G_PV2SOMA},
                             **BALANCED_SOMA_KW)
    return selectivity([t['pyr_hz'] for t in r['traj']])[0]


def j_learn(seed):
    _cy()
    from context_circuit import run_context_protocol, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA
    from robustness_r4_learning import READ, S_from, N_EP
    tr = run_context_protocol([0] * N_EP + [1] * N_EP, T=3.0, input_mode='patterns', overlap=0.0,
                              exc_rate=50.0, seed_val=seed)['traj'][-1]
    out = {}
    n = len(tr['rho0_syn'])
    w_learned = 3 * np.mean(np.r_[np.array(tr['rho0_syn'])[:n // 2], np.array(tr['rho1_syn'])[n // 2:]])
    for name, st, rate in (('after', (tr['rho0_syn'], tr['rho1_syn']), 10.0),
                           ('before', ([1 / 3] * n, [1 / 3] * n), round(10.0 * w_learned, 1))):
        r = run_context_protocol([c for c, _ in READ], T=5.0, input_mode='patterns', overlap=0.0,
                                 stim=[s for _, s in READ], plastic=False, rho_init_syn=st, exc_rate=rate,
                                 bap_source='soma', seed_val=seed,
                                 param_overrides={'gGABA_pv2soma': BALANCED_SOMA_G_PV2SOMA}, **BALANCED_SOMA_KW)
        out[name] = S_from([t['pyr_hz'] for t in r['traj']])[0]
    return out


def j_idle(seed=42):
    _cy()
    from context_circuit import run_context_protocol
    tA = run_context_protocol([0] * 8, T=3.0, input_mode='patterns', overlap=0.0, seed_val=seed)['traj'][-1]
    tB = run_context_protocol([1], T=300.0, input_mode='patterns', overlap=0.0, seed_val=seed + 1000,
                              rho_init_syn=(tA['rho0_syn'], tA['rho1_syn']))['traj'][-1]
    return float(np.mean(tB['rho0_syn'][:20]) / np.mean(tA['rho0_syn'][:20]))


def j_v2(rate):
    import paper_comparison as pc
    return pc._v2(rate, 1.0, 42)


def j_v4(md):
    import paper_comparison as pc
    return pc._v4(md, 42)


# ---------------------------------------------------------------- checks
RESULTS = []


def check(name, cond, detail):
    RESULTS.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  ({detail})", flush=True)


def main(slow, nw):
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        F = dict(som=ex.submit(j_som_isolated), v1=ex.submit(j_v1), gate=ex.submit(j_gating),
                 ret=ex.submit(j_retention), fig5=ex.submit(j_fig5))
        if slow:
            F.update({f'learn{s}': ex.submit(j_learn, s) for s in (42, 43, 44)})
            F['dt'] = ex.submit(j_gating, 42, 0.05)
            F.update({f'v2_{r}': ex.submit(j_v2, r) for r in (2, 60)})
            F.update({f'v4_{m}': ex.submit(j_v4, m) for m in (0, 25, 40)})
            F['idle'] = ex.submit(j_idle)
        audit = subprocess.run([sys.executable, '-I', os.path.join(PROOT, 'tests', 'test_audit_fixes.py')],
                               capture_output=True, text=True)
        R = {k: f.result() for k, f in F.items()}

    print('\nFast checks')
    s = R['som']
    check('F1 SOM baseline 25-40 Hz', 25 <= s['base'] <= 40, f"{s['base']:.1f} Hz")
    lo = min(v for k, v in s.items() if k != 'base'); hi = max(v for k, v in s.items() if k != 'base')
    check('F1 SOM stays in the 15-112 Hz gating window at +/-25% of bias, input rate, input weight',
          lo >= 15 and hi <= 112, f'{lo:.1f}-{hi:.1f} Hz')
    for g, gh in R['v1'].items():
        y = 5.56 * (4 + g)
        check(f'F2 V1 g_1/2 within 20% of Yang at g_inh={g:g} nS', gh is not None and abs(gh - y) / y < 0.2,
              f'{gh:.1f} vs {y:.1f} nS' if gh else 'no half-point')
    g = R['gate']
    check('F3 gating: rho_free > 0.9', g['rho_free'] > 0.9, f"{g['rho_free']:.3f}")
    check('F3 gating: rho_inh 0.25-0.35', 0.25 <= g['rho_inh'] <= 0.35, f"{g['rho_inh']:.3f}")
    check('F3 MD-on SOM silenced (< 2 Hz), baseline SOM 25-40 Hz', g['som_off'] < 2 and 25 <= g['som_base'] <= 40,
          f"{g['som_off']:.1f} / {g['som_base']:.1f} Hz")
    check('F4 retention with silent inputs >= 0.99', R['ret'] >= 0.99, f"{R['ret']:.3f}")
    check('F5 Fig. 5 gating selectivity S > 0.8 (seed 42)', R['fig5'] > 0.8, f"{R['fig5']:.2f}")
    check('F6 tests/test_audit_fixes.py', audit.returncode == 0 and 'ALL PASSED' in audit.stdout,
          'ALL PASSED' if 'ALL PASSED' in audit.stdout else audit.stdout[-300:])
    if slow:
        print('\nSlow checks')
        a = [R[f'learn{s}']['after'] for s in (42, 43, 44)]
        b = [R[f'learn{s}']['before'] for s in (42, 43, 44)]
        check('S1 S after learning (10 Hz readout) > 0.7, mean of 3 seeds', np.mean(a) > 0.7,
              ' '.join(f'{x:.2f}' for x in a))
        check('S1 S before learning at equal drive |S| < 0.3', abs(np.nanmean(b)) < 0.3,
              ' '.join(f'{x:.2f}' for x in b))
        d = abs(R['dt']['rho_free'] - g['rho_free'])
        di = abs(R['dt']['rho_inh'] - g['rho_inh'])
        check('S2 dt 0.05 vs 0.1 ms: |d rho| < 0.01', max(d, di) < 0.01, f'{d:.4f} / {di:.4f}')
        v2lo, v2hi = R['v2_2'], R['v2_60']
        check('S3 Fig. 7b: no change at 2 Hz (|dw| < 0.05, both branches)',
              abs(v2lo['dw0']) < 0.05 and abs(v2lo['dw1']) < 0.05, f"{v2lo['dw0']:.3f} / {v2lo['dw1']:.3f}")
        check('S3 Fig. 7b: 60 Hz -> free branch LTP, inhibited branch LTD', v2hi['dw0'] > 0.5 and v2hi['dw1'] < 0,
              f"{v2hi['dw0']:.2f} / {v2hi['dw1']:.2f}")
        v4 = [R[f'v4_{m}'] for m in (0, 25, 40)]
        check('S4 MD on: VIP up, own SOM channel silenced, other channel unchanged',
              v4[1]['vip_on'] > 5 and v4[1]['som_on'] < 2 and abs(v4[1]['som_off'] - v4[0]['som_off']) < 5,
              f"VIP {v4[1]['vip_on']:.1f} Hz, SOM on/off {v4[1]['som_on']:.1f}/{v4[1]['som_off']:.1f} Hz")
        check('S4 PV rises monotonically with MD (0/25/40 Hz)', v4[0]['pv'] < v4[1]['pv'] < v4[2]['pv'],
              '/'.join(f"{x['pv']:.0f}" for x in v4))
        check('S5 300-s idle phase as one epoch keeps A (retention >= 0.98)', R['idle'] >= 0.98, f"{R['idle']:.3f}")
    n_fail = sum(not ok for _, ok in RESULTS)
    print(f'\n{len(RESULTS) - n_fail}/{len(RESULTS)} checks passed ({time.time() - t0:.0f} s)')
    return n_fail


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    sys.exit(1 if main('--slow' in sys.argv, int(args[0]) if args else 8) else 0)
