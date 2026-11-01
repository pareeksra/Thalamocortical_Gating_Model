"""
retention_md_context.py -- audit Problem 3 (2026-11-01): the catastrophic-forgetting test
driven THROUGH MD, with the missing control, across seeds.

The original test (retention_catastrophic_forgetting.py) switched context with a hand-set
per-phase SOM gain in a reduced circuit, single seed, and never ran "idle input OFF but NO
inhibition". Since the analytical Yang update holds rho exactly when a synapse's calcium
never crosses theta_d (alpha_d = alpha_p = 0), silencing the idle input may protect the
memory by itself, which would make the "needs BOTH input and inhibition gating" claim
unsupported. This script runs the full 2x2:

    condition     idle input   SOM inhibition (via MD context)
    both          OFF          ON      (the original 'inputgated' claim)
    inhibonly     ON           ON      (the original 'inhibonly' -> forgot)
    inputonly     OFF          OFF     (the MISSING control)
    neither       ON           OFF     (no gating at all)

Protocol: model/context_circuit.py, 8 epochs context A (MD_0 on -> branch 0 free) then
8 epochs context B (MD_1 on -> branch 1 free), T = 3 s, seeds 42-46, each run in a fresh
process.

Run:  <venv>/python -I experiments/retention_md_context.py [n_workers]
Out:  docs/audit/retention_md_context.json
"""
import os, sys, json, time
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT]
OUT = os.path.join(PROOT, 'docs', 'audit', 'retention_md_context.json')
N_EP = 8
CONDS = {'both': ('context', True), 'inhibonly': ('always', True),
         'inputonly': ('context', False), 'neither': ('always', False)}
SEEDS = [42, 43, 44, 45, 46]


def _job(cond, seed_val):
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol
    t0 = time.time()
    input_mode, inhib = CONDS[cond]
    r = run_context_protocol([0] * N_EP + [1] * N_EP, T=3.0, input_mode=input_mode,
                             inhibition=inhib, seed_val=seed_val)
    tr = r['traj']
    a, b = tr[N_EP - 1], tr[-1]
    return dict(cond=cond, seed=seed_val, rho0_endA=a['rho0'], rho1_endA=a['rho1'],
                rho0_endB=b['rho0'], rho1_endB=b['rho1'],
                retention=b['rho0'] / a['rho0'] if a['rho0'] > 1e-6 else None,
                n_som_syn=r['n_som_syn_per_branch'], traj=tr, wall_s=round(time.time() - t0, 1))


def main():
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    todo = [(c, s) for c in CONDS for s in SEEDS if f'{c}_{s}' not in done]
    print(f'{len(todo)} jobs, {nw} workers', flush=True)
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(_job, c, s): (c, s) for c, s in todo}
        for f in as_completed(futs):
            c, s = futs[f]
            try:
                r = f.result()
            except Exception as e:
                print(f'  {c}_{s}: ERROR {e!r}', flush=True); continue
            done[f'{c}_{s}'] = r
            json.dump(done, open(OUT, 'w'), indent=1)
            print(f"  {c:<10} seed {s}: A-end rho0 {r['rho0_endA']:.3f} rho1 {r['rho1_endA']:.3f} | "
                  f"B-end rho0 {r['rho0_endB']:.3f} rho1 {r['rho1_endB']:.3f} | "
                  f"retention {r['retention']:.3f}  ({r['wall_s']} s)", flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
