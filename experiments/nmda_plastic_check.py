"""
nmda_plastic_check.py -- first stability/gating check of the Yang-faithful NMDA-plastic
synapse (context_circuit(nmda_plastic=True), 2026-11-02).

Versions: legacy (w scales AMPA only, rho0 = 0.5) vs yang (w scales NMDA, AMPA off,
rho0 = 1/3 -> w = 1 -> 2.5 nS, Yang's pre-learning weight).
Protocols (16 epochs x 3 s, seeds 42-44):
  always   both inputs on; context A x 8 then B x 8 (gating ratio after A; retention after B)
  context  only the active context's input on; A x 8 then B x 8
Run:  <py> -I experiments/nmda_plastic_check.py [n_workers]
Out:  results/current/nmda_plastic_check.json
"""
import os, sys, json, time
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT]
OUT = os.path.join(PROOT, 'results', 'current', 'nmda_plastic_check.json')


def _job(ver, mode, s):
    from brian2 import prefs, nS
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol
    t0 = time.time()
    kw = dict(nmda_plastic=True, rho_init=1 / 3, param_overrides={'gAMPA': 0 * nS}) if ver == 'yang' else {}
    r = run_context_protocol([0] * 8 + [1] * 8, T=3.0, input_mode=mode, seed_val=s, **kw)
    tr = r['traj']
    return dict(ver=ver, mode=mode, seed=s, rho0=[t['rho0'] for t in tr], rho1=[t['rho1'] for t in tr],
                pyr=[t['pyr_hz'] for t in tr], wall_s=round(time.time() - t0, 1))


if __name__ == '__main__':
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    J = [(v, m, s) for v in ('legacy', 'yang') for m in ('always', 'context') for s in (42, 43, 44)]
    done = {}
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(_job, *j): j for j in J}
        for fu in as_completed(futs):
            j = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                print(j, 'ERROR', repr(e), flush=True); continue
            done['_'.join(map(str, j))] = r
            json.dump(done, open(OUT, 'w'), indent=1)
            print(f"{j}: end A rho0 {r['rho0'][7]:.3f} rho1 {r['rho1'][7]:.3f} | end B rho0 {r['rho0'][-1]:.3f} "
                  f"rho1 {r['rho1'][-1]:.3f} | retention {r['rho0'][-1] / max(r['rho0'][7], 1e-9):.3f} ({r['wall_s']} s)",
                  flush=True)
    print('done', flush=True)
