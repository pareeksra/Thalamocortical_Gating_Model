"""
dt_convergence_check.py -- audit (2026-11-01): every Model A result integrates at Brian 2's
DEFAULT 0.1 ms (defaultclock.dt is never set; parameters.py's sim_dt = 0.02 ms only ever
clocked the retired Python coupling operation, while docstrings claimed 0.02 ms). This
checks that the plasticity outcome is converged in dt: the reduced Phase-1 circuit, 15
epochs, seed 42, desynchronised SOM, at 0.1 ms vs 0.02 ms, at 30 Hz (baseline) and 15 Hz
(close to the gating threshold, i.e. the most dt-sensitive point).

Run:  <venv>/python -I experiments/dt_convergence_check.py [n_workers]
Out:  docs/audit/dt_convergence.json
"""
import os, sys, json
from concurrent.futures import ProcessPoolExecutor
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
BIAS = {30: 21.319034, 15: 20.20522}


def _run(dt_ms, rate):
    from brian2 import defaultclock, ms
    defaultclock.dt = dt_ms * ms
    from phase1_analytical import run_gating_analytical
    tag = f'dtconv_{dt_ms}_{rate}'
    r = run_gating_analytical(n_epochs=15, som_bias_pA=BIAS[rate], seed_val=42, verbose=False,
                              resume=False, run_tag=tag)
    try:
        os.remove(os.path.join(PROOT, 'docs', f'phase1_analytical_state_{tag}.json'))
    except OSError:
        pass
    return dict(dt_ms=dt_ms, som_hz_target=rate, som_rate=r['som_rate_hz'], r0=r['rho0'],
                r1=r['rho1'], ratio=r['ratio'], ap0=r['traj']['ap0'][-1], ad0=r['traj']['ad0'][-1],
                ap1=r['traj']['ap1'][-1], ad1=r['traj']['ad1'][-1])


def main():
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    jobs = [(dt, r) for r in (30, 15) for dt in (0.1, 0.02)]
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        res = list(ex.map(_run, [j[0] for j in jobs], [j[1] for j in jobs]))
    for r in res:
        print(f"  SOM {r['som_hz_target']} Hz  dt {r['dt_ms']} ms: r0 {r['r0']:.3f}  r1 {r['r1']:.3f}  "
              f"ratio {r['ratio']:.2f}  (inh ap/ad {r['ap0']:.2f}/{r['ad0']:.2f}, free ap/ad {r['ap1']:.2f}/{r['ad1']:.2f})")
    os.makedirs(os.path.join(PROOT, 'docs', 'audit'), exist_ok=True)
    json.dump(res, open(os.path.join(PROOT, 'docs', 'audit', 'dt_convergence.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
