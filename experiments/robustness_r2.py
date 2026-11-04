"""
robustness_r2.py -- R2 of docs/reports/PLAN_robustness.md: numerical robustness of the
canonical (Yang NMDA-plastic) synapse, 2026-11-04.

  gating  input_mode='always' (both inputs on), context A x 8 epochs x 3 s, seeds 42-61.
          Branch 0 is free (MD_0), branch 1 inhibited. Pass: >= 19/20 seeds with
          rho_free > 0.65, rho_inh < 0.5, ratio >= 2.
  dt      the same protocol at dt 0.1 ms (default) vs 0.05 ms, seeds 42-44.
          Pass: |delta rho| < 0.01 on both branches.
  soma    balanced somatic drive preset (bap_source='soma', BALANCED_SOMA_KW, MD->PV x1),
          calibrated with the old synapse: does it still give 5-15 Hz, CV >= 0.7?
          2 epochs, seeds 42-44 (informational).
Run:  <py> -I experiments/robustness_r2.py [n_workers]
Out:  results/current/robustness_r2.json
"""
import os, sys, json, time
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT]
OUT = os.path.join(PROOT, 'results', 'current', 'robustness_r2.json')


def _job(kind, seed, dt_ms=0.1):
    from brian2 import prefs, defaultclock, ms
    prefs.codegen.target = 'cython'
    defaultclock.dt = dt_ms * ms
    from context_circuit import run_context_protocol, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA
    t0 = time.time()
    if kind == 'soma':
        r = run_context_protocol([0, 0], T=3.0, input_mode='always', seed_val=seed, bap_source='soma',
                                 param_overrides={'gGABA_pv2soma': BALANCED_SOMA_G_PV2SOMA}, **BALANCED_SOMA_KW)
        tr = r['traj']
        return dict(kind=kind, seed=seed, pyr=sum(t['pyr_hz'] for t in tr) / 2, cv=tr[-1]['pyr_cv'],
                    pv=sum(t['pv_hz'] for t in tr) / 2, rho0=tr[-1]['rho0'], rho1=tr[-1]['rho1'],
                    wall_s=round(time.time() - t0, 1))
    r = run_context_protocol([0] * 8, T=3.0, input_mode='always', seed_val=seed)
    tr = r['traj']
    return dict(kind=kind, seed=seed, dt_ms=dt_ms, rho_free=tr[-1]['rho0'], rho_inh=tr[-1]['rho1'],
                traj=[[t['rho0'], t['rho1']] for t in tr], som=[[t['som0_hz'], t['som1_hz']] for t in tr],
                wall_s=round(time.time() - t0, 1))


def main(nw):
    J = [('gating', s, 0.1) for s in range(42, 62)] + [('dt', s, 0.05) for s in (42, 43, 44)] + \
        [('soma', s, 0.1) for s in (42, 43, 44)]
    res = {}
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(_job, *j): j for j in J}
        for fu in as_completed(futs):
            j = futs[fu]; r = fu.result(); res[f'{j[0]}_{j[1]}'] = r
            print(j, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k not in ('traj', 'som')}, flush=True)
    g = [res[f'gating_{s}'] for s in range(42, 62)]
    ok = [x['rho_free'] > 0.65 and x['rho_inh'] < 0.5 and x['rho_free'] / max(x['rho_inh'], 1e-9) >= 2 for x in g]
    dts = [max(abs(res[f'dt_{s}']['rho_free'] - res[f'gating_{s}']['rho_free']),
               abs(res[f'dt_{s}']['rho_inh'] - res[f'gating_{s}']['rho_inh'])) for s in (42, 43, 44)]
    soma = [res[f'soma_{s}'] for s in (42, 43, 44)]
    summ = dict(gated=f'{sum(ok)}/20', gating_pass=sum(ok) >= 19,
                rho_free=[x['rho_free'] for x in g], rho_inh=[x['rho_inh'] for x in g],
                dt_max_delta=dts, dt_pass=max(dts) < 0.01,
                soma_hz=[x['pyr'] for x in soma], soma_cv=[x['cv'] for x in soma],
                soma_pass=all(5 <= x['pyr'] <= 15 and x['cv'] >= 0.7 for x in soma))
    json.dump(dict(summary=summ, runs=res), open(OUT, 'w'), indent=1)
    print(json.dumps({k: v for k, v in summ.items() if k not in ('rho_free', 'rho_inh')}, indent=1))
    import numpy as np
    print('rho_free mean %.3f [%.3f, %.3f]  rho_inh mean %.3f [%.3f, %.3f]' % (
        np.mean(summ['rho_free']), min(summ['rho_free']), max(summ['rho_free']),
        np.mean(summ['rho_inh']), min(summ['rho_inh']), max(summ['rho_inh'])))


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 11)
