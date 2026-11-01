"""
retention_pv_arm.py -- does MD->PV (Zhang's MD^GRIK4 arm) protect learned memories by
lowering somatic firing, hence bAP calcium, on idle branches? (2026-11-02)

Background. docs/AUDIT_2026-11-01.md P3: with the idle context's input still active,
SOM gating of a branch pushes its calcium into the LTD band (part of it bAP calcium) and
the memory is erased (retention 32-40%). bAPs come from somatic spikes; PV inhibits the
soma. If MD->PV lowers the somatic rate in a graded way, it lowers bAP calcium and should
reduce that LTD -- giving MD a protective role through PV.

Protocol: model/context_circuit.py, context A x 8 epochs then context B x 8 (T = 3 s),
input_mode='always' (the forgetting case), MD->PV scale x0, x0.5, x1, x2, x3, seeds 42-46.
  soma   bap_source='soma' with the calibrated balanced somatic drive (CLI args)
  pinned bap_source='poisson' (Yang's 10 Hz pinned bAPs) -- CONTROL: PV cannot change the
         bAP rate, so any MD->PV effect on retention must be absent here
Reference: input_mode='context' at x1 (soma), the input-sparse case that retains.

Run:  <py> -I experiments/retention_pv_arm.py <gI> <e_scale> <g_pv2soma> [n_workers]
Out:  docs/audit/retention_pv_arm.json
"""
import os, sys, json, time
from concurrent.futures import ProcessPoolExecutor
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
OUT = os.path.join(PROOT, 'docs', 'audit', 'retention_pv_arm.json')
PV_X = [0.0, 0.5, 1.0, 2.0, 3.0]
SEEDS = [42, 43, 44, 45, 46]
N_EP = 8


def _job(spec):
    from brian2 import prefs, nS
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol
    from soma_balanced_calibration import drive
    t0 = time.time()
    kw = dict(T=3.0, input_mode=spec['input_mode'], seed_val=spec['seed'],
              param_overrides={'gAMPA_pv': 0.12 * spec['x'] * nS,
                               'gGABA_pv2soma': spec['g_pv2soma'] * nS})
    if spec['bap'] == 'soma':
        r_e, r_i = drive(spec['gi'], spec['es'])
        kw.update(bap_source='soma', soma_drive_hz=r_e, soma_drive_nS=0.5,
                  soma_inh_hz=r_i, soma_inh_nS=1.0)
    else:
        kw.update(bap_source='poisson')
    r = run_context_protocol([0] * N_EP + [1] * N_EP, **kw)
    tr = r['traj']; a, b = tr[N_EP - 1], tr[-1]
    mean = lambda k, ep: sum(t[k] for t in ep) / len(ep)
    return {**spec, 'rho0_endA': a['rho0'], 'rho1_endA': a['rho1'], 'rho0_endB': b['rho0'],
            'rho1_endB': b['rho1'], 'retention': b['rho0'] / a['rho0'] if a['rho0'] > 1e-6 else None,
            'pyr_A': float(mean('pyr_hz', tr[:N_EP])), 'pyr_B': float(mean('pyr_hz', tr[N_EP:])),
            'pv_A': float(mean('pv_hz', tr[:N_EP])), 'ad0_B': float(mean('ad0', tr[N_EP:])),
            'ap0_B': float(mean('ap0', tr[N_EP:])), 'traj': tr, 'wall_s': round(time.time() - t0, 1)}


def main():
    gi, es, g = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
    nw = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    base = dict(gi=gi, es=es, g_pv2soma=g)
    J = [dict(base, bap=b, input_mode='always', x=x, seed=s)
         for b in ('soma', 'pinned') for x in PV_X for s in SEEDS]
    J += [dict(base, bap='soma', input_mode='context', x=1.0, seed=s) for s in SEEDS]
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    key = lambda j: f"{j['bap']}_{j['input_mode']}_x{j['x']}_s{j['seed']}"
    todo = [j for j in J if key(j) not in done]
    print(f'{len(todo)} jobs ({len(done)} done), {nw} workers', flush=True)
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        for j, r in zip(todo, ex.map(_job, todo)):
            done[key(j)] = r
            json.dump(done, open(OUT, 'w'), indent=1, default=float)
            print(f"  {key(j):<26} retention {r['retention']:.3f} | endA rho0 {r['rho0_endA']:.3f} "
                  f"rho1 {r['rho1_endA']:.3f} | endB rho1 {r['rho1_endB']:.3f} | soma A {r['pyr_A']:5.1f} "
                  f"B {r['pyr_B']:5.1f} Hz | PV {r['pv_A']:6.1f} | ad0_B {r['ad0_B']:.2f}  ({r['wall_s']} s)",
                  flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
