"""
pv_soma_calibration.py -- calibrate the OUTPUT side of the PV arm (PV -> soma), after the
2026-11-02 input-side recalibration (pv_calibration.py).

Problem. gGABA_pv2soma = 5 nS was never tested with PV actually active against SOM. With
PV now at ~50 Hz in a context (MD 25 Hz), ~12 PV->soma synapses x 5 nS x 10 ms give ~32 nS
of mean somatic shunt (~13x the 2.5 nS somatic leak): the soma is silenced outright for
every somatic drive tested, so with somatic bAPs (context_circuit bap_source='soma') PV
acts as an on/off switch, not Yang's graded somatic inhibition (Yang Fig. 6: a uniform
increase in somatic inhibition improves gating selectivity; Eq. 29-30 linear PV).

This only matters when bAPs come from the soma; with the canonical Poisson bAP source the
somatic rate cannot change plasticity (verified: results/current/pv_calibration_verify.json A).

Targets (stated before running), context circuit, context A (MD_0 at 25 Hz), seed 42:
  S1  soma rate 5-15 Hz at MD->PV x1 (Yang's ~10 Hz postsynaptic rate)
  S2  divisive, not switch-like: soma(x0) > soma(x1) > soma(x3) > 0 (x3 >= 1 Hz),
      and 1.5 <= soma(x0)/soma(x1) <= 5
Knobs: gGABA_pv2soma (PV->soma per-synapse) x soma_drive_nS (the somatic Poisson drive
introduced for bap_source='soma'; 100 inputs at 10 Hz). p_pv2soma = 0.6 (Yang) untouched.

Run:  <venv>/python -I experiments/pv_soma_calibration.py [n_workers]
Out:  results/current/pv_soma_calibration.json
"""
import os, sys, json, itertools
from concurrent.futures import ProcessPoolExecutor
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT]
G_PV2SOMA = [0.25, 0.5, 1.0, 2.0, 5.0]
DRIVE = [0.2, 0.25, 0.3, 0.4, 0.5]
PV_SCALE = [0.0, 1.0, 3.0]


def _run(g, w, x):
    from brian2 import prefs, nS
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol
    r = run_context_protocol([0], T=3.0, input_mode='always', seed_val=42, bap_source='soma',
                             soma_drive_hz=10.0, soma_drive_nS=w,
                             param_overrides={'gAMPA_pv': 0.12 * x * nS, 'gGABA_pv2soma': g * nS})
    t = r['traj'][0]
    return dict(g=g, w=w, x=x, pyr=float(t['pyr_hz']), pv=float(t['pv_hz']))


def main():
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    jobs = list(itertools.product(G_PV2SOMA, DRIVE, PV_SCALE))
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        res = list(ex.map(_run, *zip(*jobs)))
    R = {(r['g'], r['w'], r['x']): r for r in res}
    rows = []
    print(f"{'g_pv2s':>6} {'drive':>5} | soma @ PV x0  x1  x3 (PV Hz at x1) | S1 S2")
    for g in G_PV2SOMA:
        for w in DRIVE:
            s0, s1, s3 = (R[(g, w, x)]['pyr'] for x in PV_SCALE)
            S1 = 5.0 <= s1 <= 15.0
            S2 = s0 > s1 > s3 >= 1.0 and 1.5 <= s0 / max(s1, 1e-9) <= 5.0
            rows.append(dict(g=g, w=w, soma=[s0, s1, s3], pv_x1=R[(g, w, 1.0)]['pv'], S1=S1, S2=S2))
            print(f"{g:>6} {w:>5} | {s0:7.1f} {s1:6.1f} {s3:6.1f}   ({R[(g, w, 1.0)]['pv']:5.1f}) | "
                  f"{'Y' if S1 else '.'}  {'Y' if S2 else '.'} {'<== BOTH' if S1 and S2 else ''}")
    os.makedirs(os.path.join(PROOT, 'results', 'current'), exist_ok=True)
    json.dump(dict(raw=res, grid=rows), open(os.path.join(PROOT, 'results', 'current', 'pv_soma_calibration.json'), 'w'),
              indent=1, default=float)


if __name__ == '__main__':
    main()
