"""
pv_calibration_verify.py -- after the 2026-11-02 PV recalibration (weight_bg_pv 0.25 -> 0.29
nS, gGABA_pv 2.0 -> 0.05 nS), check (fresh process per run):

  A. gating unchanged: full circuit (md = 0, desynchronised SOM 30 Hz), seeds 40-59.
     Compare with results/current/som_async_full.json (pre-recalibration: 20/20).
  B. MD-driven retention unchanged: context circuit, 'both' and 'inhibonly', seeds 42-44.
  C. PV arm now reaches plasticity through somatic bAPs: context circuit,
     bap_source='soma', soma drive 100 x 10 Hz x 0.2 nS, input on both branches,
     MD->PV scale x0, x0.5, x1, x2, x3 -- PV rate, soma rate, gated/free rho.
  D. PV is graded inside the context circuit: PV rate per epoch in context A.

Run:  <venv>/python -I experiments/pv_calibration_verify.py [n_workers]
Out:  results/current/pv_calibration_verify.json
"""
import os, sys, json
from concurrent.futures import ProcessPoolExecutor
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT]
OUT = os.path.join(PROOT, 'results', 'current', 'pv_calibration_verify.json')


def _job(spec):
    from brian2 import prefs, nS
    prefs.codegen.target = 'cython'
    k = spec['kind']
    if k == 'A':
        from full_circuit import build_gating_circuit
        r = build_gating_circuit(T=3.0, md_signal_rate=0.0, noise_level=0.0, n_epochs=15,
                                 seed_val=spec['seed'])
        return {**spec, 'r0': r['r0'], 'r1': r['r1'], 'gated': r['gated'], 'pv': r['pv_rate'],
                'som': r['som_rate']}
    from context_circuit import run_context_protocol
    import functools; run_context_protocol = functools.partial(run_context_protocol, synapse='ampa')  # pre-2026-11-04 synapse: reproduces the committed results
    if k == 'B':
        mode = 'context' if spec['cond'] == 'both' else 'always'
        r = run_context_protocol([0] * 8 + [1] * 8, T=3.0, input_mode=mode, seed_val=spec['seed'])
        a, b = r['traj'][7], r['traj'][-1]
        return {**spec, 'rho0_endA': a['rho0'], 'rho0_endB': b['rho0'], 'rho1_endB': b['rho1'],
                'retention': b['rho0'] / a['rho0'], 'pv_A': a['pv_hz']}
    if k == 'C':
        r = run_context_protocol([0] * 8, T=3.0, input_mode='always', seed_val=42, bap_source='soma',
                                 soma_drive_hz=10.0, soma_drive_nS=0.2,
                                 param_overrides={'gAMPA_pv': 0.12 * spec['pv_scale'] * nS})
        tr = r['traj']
        return {**spec, 'pv': sum(t['pv_hz'] for t in tr) / 8, 'pyr': sum(t['pyr_hz'] for t in tr) / 8,
                'rho_free': tr[-1]['rho0'], 'rho_gated': tr[-1]['rho1'],
                'ad_gated': tr[-1]['ad1'], 'ap_free': tr[-1]['ap0']}
    raise ValueError(k)


def main():
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    J = [dict(kind='A', seed=s) for s in range(40, 60)]
    J += [dict(kind='B', cond=c, seed=s) for c in ('both', 'inhibonly') for s in (42, 43, 44)]
    J += [dict(kind='C', pv_scale=x) for x in (0.0, 0.5, 1.0, 2.0, 3.0)]
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        res = list(ex.map(_job, J))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, 'w'), indent=1, default=float)
    A = [r for r in res if r['kind'] == 'A']
    print(f"A: {sum(r['gated'] for r in A)}/20 gated; r0 {min(r['r0'] for r in A):.3f}-{max(r['r0'] for r in A):.3f}, "
          f"r1 {min(r['r1'] for r in A):.3f}-{max(r['r1'] for r in A):.3f}; PV {sum(r['pv'] for r in A)/20:.1f} Hz, "
          f"SOM {sum(r['som'] for r in A)/20:.1f} Hz; fails {[r['seed'] for r in A if not r['gated']]}")
    for r in res:
        if r['kind'] == 'B':
            print(f"B: {r['cond']:<9} seed {r['seed']}: retention {r['retention']:.3f}  (B-end rho1 {r['rho1_endB']:.3f}; "
                  f"PV in context A {float(r['pv_A']):.1f} Hz)")
    for r in res:
        if r['kind'] == 'C':
            print(f"C: MD->PV x{r['pv_scale']:<3g} PV {float(r['pv']):6.1f} Hz  soma {float(r['pyr']):5.1f} Hz | "
                  f"free {r['rho_free']:.3f}  gated {r['rho_gated']:.3f} (gated ad {r['ad_gated']:.2f})")


if __name__ == '__main__':
    main()
