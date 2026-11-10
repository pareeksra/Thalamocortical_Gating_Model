"""
bap_soma_coupling_test.py -- audit Problem 8 (2026-11-01): does the MD->PV (gain) arm
reach plasticity once bAPs come from the soma's own spikes?

In every canonical builder the dendritic bAPs come from an independent Poisson source at
post_rate (Yang's protocol pins the postsynaptic rate at 10 Hz). The soma's own spikes
never reach the dendrites, so the MD->PV->soma arm and somatic firing cannot affect
learning AT ALL in those runs -- a design limitation, not a bug, but it means no result so
far says anything about the PV arm's role in plasticity.

model/context_circuit.py now has bap_source='soma' plus an optional somatic Poisson drive.
This script:
  1. calibrates the somatic drive so the soma fires ~10 Hz in context A (MD_0 on);
  2. scales the MD->PV weight (x0, x1, x3, x6) and runs 8 epochs of context A with
     bap_source='soma' and, as a control, bap_source='poisson' (PV must then be inert);
  3. reports soma rate, PV rate, and final rho of the free (0) and gated (1) branch, with
     input on BOTH branches (input_mode='always') so the gated branch's LTD -- driven
     partly by bAP calcium -- is visible.

Run:  <venv>/python -I experiments/bap_soma_coupling_test.py [n_workers]
Out:  results/current/bap_soma_coupling.json
"""
import os, sys, json
from concurrent.futures import ProcessPoolExecutor
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT]
OUT = os.path.join(PROOT, 'results', 'current', 'bap_soma_coupling.json')
DRIVE_HZ = 10.0           # per input, 100 inputs
CAL_W = [0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.8]   # 2026-11-02: re-calibrated with PV active (PV recalibration)
PV_SCALE = [0.0, 0.5, 1.0, 2.0, 3.0]


def _run(kind, w, pv_scale, bap, n_ep):
    from brian2 import prefs, nS
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol
    import functools; run_context_protocol = functools.partial(run_context_protocol, synapse='ampa')  # pre-2026-11-04 synapse: reproduces the committed results
    r = run_context_protocol([0] * n_ep, T=3.0 if n_ep > 1 else 2.0, input_mode='always',
                             seed_val=42, bap_source=bap, soma_drive_hz=DRIVE_HZ, soma_drive_nS=w,
                             param_overrides={'gAMPA_pv': 0.12 * pv_scale * nS})
    tr = r['traj']
    return dict(kind=kind, w=w, pv_scale=pv_scale, bap=bap,
                pyr_hz=sum(t['pyr_hz'] for t in tr) / len(tr), pv_hz=sum(t['pv_hz'] for t in tr) / len(tr),
                rho0=tr[-1]['rho0'], rho1=tr[-1]['rho1'], ad1=tr[-1]['ad1'], ap1=tr[-1]['ap1'])


def main():
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        cal = list(ex.map(_run, ['cal'] * len(CAL_W), CAL_W, [1.0] * len(CAL_W),
                          ['soma'] * len(CAL_W), [1] * len(CAL_W)))
    for c in cal:
        print(f"  calib w={c['w']:.2f} nS -> soma {float(c['pyr_hz']):.1f} Hz, PV {float(c['pv_hz']):.1f} Hz")
    best = min(cal, key=lambda c: abs(float(c['pyr_hz']) - 10.0))
    w = best['w']
    print(f'chosen soma drive weight {w} nS ({float(best["pyr_hz"]):.1f} Hz)')
    jobs = [(b, s) for b in ('soma', 'poisson') for s in PV_SCALE]
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        res = list(ex.map(_run, ['test'] * len(jobs), [w] * len(jobs), [j[1] for j in jobs],
                          [j[0] for j in jobs], [8] * len(jobs)))
    for r in res:
        print(f"  bAP={r['bap']:<8} MD->PV x{r['pv_scale']:<3g}: soma {float(r['pyr_hz']):5.1f} Hz  "
              f"PV {float(r['pv_hz']):6.1f} Hz | free rho0 {r['rho0']:.3f}  gated rho1 {r['rho1']:.3f} "
              f"(gated ad={r['ad1']:.2f} ap={r['ap1']:.2f})")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(dict(calibration=cal, chosen_w_nS=w, results=res), open(OUT, 'w'), indent=1,
              default=float)


if __name__ == '__main__':
    main()
