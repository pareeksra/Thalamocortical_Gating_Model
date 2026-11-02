"""
som_async_sweep.py -- audit Problem 1 (2026-11-01): does SOM *synchrony* explain the
SOM-rate divergence from Yang 2016 and the 25 Hz seed-44/53 failures?

Every result before 2026-11-01 ran the SOM population in perfect lockstep (identical
bias, identical vRest start, no other input), i.e. one giant GABA volley per cycle.
This script re-runs the key gating measurements with the SOM cells desynchronised
(som_phase='random', model/circuit_helpers.py) next to the legacy lockstep ('sync').

Modes
  reduced   Phase-1 reduced circuit (run_gating_analytical, 10 SOM -> branch 0),
            SOM-rate sweep x {sync, random} x seeds. The basis of FINDING_som_rate_divergence.
  full      Full circuit (build_gating_circuit, md=0, noise=0), 20 seeds at a given SOM
            rate x {sync, random}. The basis of the 25 Hz / 30 Hz reliability claims.
  tau       Reduced circuit, tau_GABA,dend sweep at a fixed low SOM rate, random phase.

Each job runs in its OWN fresh process (max_tasks_per_child=1): Brian 2 PoissonGroup
streams are reproducible per seed only across processes.

Run:  <venv>/python -I experiments/som_async_sweep.py reduced|full|tau [n_workers]
Out:  results/current/som_async_<mode>.json (checkpointed per job; safe to re-launch)
"""
import os, sys, json, time
from concurrent.futures import ProcessPoolExecutor, as_completed

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
OUT = os.path.join(PROOT, 'results', 'current')
os.makedirs(OUT, exist_ok=True)

# Bias (pA) -> exact free-running SOM rate (Hz), from the LIF period formula
# (circuit_helpers.som_period_and_vinf, solved with brentq).
BIAS_FOR_RATE = {5: 20.000251, 7.5: 20.007042, 10: 20.037512, 12.5: 20.103301,
                 15: 20.20522, 20: 20.498844, 25: 20.879369, 30: 21.319034}


def _job(spec):
    from brian2 import ms
    t0 = time.time()
    if spec['circuit'] == 'reduced':
        from phase1_analytical import run_gating_analytical
        po = {'tauGABA': spec['tau_ms'] * ms} if spec.get('tau_ms', 20.0) != 20.0 else None
        r = run_gating_analytical(n_epochs=15, som_bias_pA=spec['bias'], seed_val=spec['seed'],
                                  gGABA_nS=spec.get('gGABA'),
                                  verbose=False, resume=False,
                                  run_tag=f"audit_{spec['key']}", param_overrides=po,
                                  som_phase=spec['phase'])
        try:
            os.remove(os.path.join(PROOT, 'results', 'pre_audit', f"phase1_analytical_state_audit_{spec['key']}.json"))
        except OSError:
            pass
        res = dict(r0=r['rho0'], r1=r['rho1'], ratio=r['ratio'], som_rate=r['som_rate_hz'])
    else:
        from full_circuit import build_gating_circuit
        r = build_gating_circuit(T=3.0, md_signal_rate=0.0, noise_level=0.0, n_epochs=15,
                                 seed_val=spec['seed'], som_bias_pA=spec['bias'],
                                 som_phase=spec['phase'])
        res = dict(r0=r['r0'], r1=r['r1'], ratio=r['ratio'], som_rate=r['som_rate'])
    res['gated'] = bool(res['r1'] > 0.65 and res['r0'] < 0.5 and res['ratio'] >= 2.0)
    res['wall_s'] = round(time.time() - t0, 1)
    return {**spec, **res}


def jobs_for(mode):
    J = []
    if mode == 'reduced':
        for rate in (5, 7.5, 10, 12.5, 15, 20, 30):
            for phase in ('random', 'sync'):
                for s in (42, 43, 44):
                    J.append(dict(circuit='reduced', rate=rate, bias=BIAS_FOR_RATE[rate],
                                  phase=phase, seed=s, key=f'red_{rate}_{phase}_{s}'))
    elif mode == 'full':
        for rate, phases in ((25, ('random', 'sync')), (15, ('random',)), (30, ('random',))):
            for phase in phases:
                for s in range(40, 60):
                    J.append(dict(circuit='full', rate=rate, bias=BIAS_FOR_RATE[rate],
                                  phase=phase, seed=s, key=f'full_{rate}_{phase}_{s}'))
    elif mode == 'mech':
        # Mechanism test at Yang's 10 Hz: if desynchronised inhibition acts through its MEAN
        # conductance (~ N * g * rate * tau), raising g or tau must rescue gating at 10 Hz
        # with random phases -- but NOT in lockstep, where the uncovered inter-volley gap
        # (~100 ms at 10 Hz) is unchanged by g. (The legacy gGABA sweep at 10 Hz found
        # 6x g only reached ratio 1.45 -- in lockstep.)
        for phase in ('random', 'sync'):
            for g in (6.0, 8.0, 12.0):
                J.append(dict(circuit='reduced', rate=10, bias=BIAS_FOR_RATE[10], gGABA=g,
                              phase=phase, seed=42, key=f'mech_g{g}_{phase}'))
            for tau in (30.0, 40.0):
                J.append(dict(circuit='reduced', rate=10, bias=BIAS_FOR_RATE[10], tau_ms=tau,
                              phase=phase, seed=42, key=f'mech_tau{tau}_{phase}'))
    else:
        raise SystemExit(f'unknown mode {mode}')
    return J


def main():
    mode = sys.argv[1]
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    path = os.path.join(OUT, f'som_async_{mode}.json')
    done = json.load(open(path)) if os.path.exists(path) else {}
    todo = [j for j in jobs_for(mode) if j['key'] not in done]
    print(f'{mode}: {len(todo)} jobs to run ({len(done)} already done), {nw} workers', flush=True)
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(_job, j): j for j in todo}
        for f in as_completed(futs):
            j = futs[f]
            try:
                r = f.result()
            except Exception as e:
                print(f"  {j['key']}: ERROR {e!r}", flush=True)
                continue
            done[j['key']] = r
            json.dump(done, open(path, 'w'), indent=1)
            print(f"  {j['key']:<26} SOM {r['som_rate']:6.2f} Hz  r0 {r['r0']:.3f}  r1 {r['r1']:.3f}  "
                  f"ratio {r['ratio']:6.2f}  {'GATED' if r['gated'] else 'not gated'}  ({r['wall_s']} s)",
                  flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
