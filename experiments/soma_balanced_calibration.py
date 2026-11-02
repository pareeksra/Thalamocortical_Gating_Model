"""
soma_balanced_calibration.py -- calibrate a BALANCED, fluctuation-driven somatic drive and
the PV -> soma weight, so PV inhibition scales somatic firing gradually (Yang Fig. 6,
Eqs. 29-30) instead of switching it off (2026-11-02).

Why. With a purely excitatory, mean-driven somatic drive, PV -> soma is switch-like at
every weight tested (results/current/pv_soma_calibration.json): the soma is a threshold LIF and
PV spans ~30x (7 -> 220 Hz) over MD->PV x0..x3. A high-conductance, balanced drive (mean
voltage just under threshold, firing driven by fluctuations) is the standard way to make
inhibition act gradually on an integrate-and-fire neuron.

Drive design (soma: C 50 pF, gL 2.5 nS, Vth -50 mV, GABA reversal -70 mV):
  inhibitory background  100 x r_I Hz x 1.0 nS, tauGABA_soma 10 ms -> g_I = r_I nS
      levels g_I = 2.5 / 5 / 10 nS  (1x / 2x / 4x the leak)
  excitatory drive       100 x r_E Hz x 0.5 nS, tauAMPA 2 ms       -> g_E = 0.1 r_E nS
      base g_E = 0.4 (gL + g_I)  puts V_inf at threshold; scaled by E_SCALE
Grid: g_I level x E_SCALE x gGABA_pv2soma x MD->PV scale (x0, 0.5, 1, 2, 3).
Context circuit, context A (MD_0 25 Hz), bap_source='soma', input on both branches,
1 epoch x 3 s, seed 42; one fresh process per run.

Targets (stated before running):
  S1  soma 5-15 Hz at MD->PV x1 (Yang's ~10 Hz)
  S2  graded: soma decreases monotonically over x0 -> x3, soma(x3) >= 1 Hz,
      1.5 <= soma(x0)/soma(x1) <= 5
  S3  fluctuation-driven: ISI CV >= 0.7 at x1

Run:  <py> -I experiments/soma_balanced_calibration.py [n_workers] [seed]
Out:  results/current/soma_balanced_calibration_seed<seed>.json
"""
import os, sys, json, itertools
from concurrent.futures import ProcessPoolExecutor
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT]

G_I = [2.5, 5.0, 10.0]                      # nS mean inhibitory background
E_SCALE = [0.6, 0.7, 0.8, 0.9, 1.0, 1.1]
G_PV2SOMA = [0.1, 0.25, 0.5, 1.0, 2.0]
PV_X = [0.0, 0.5, 1.0, 2.0, 3.0]
GL = 2.5


def drive(gi, es):
    r_i = gi / 1.0                           # Hz per input (100 inputs x 1 nS x 10 ms)
    r_e = es * 0.4 * (GL + gi) / 0.1         # Hz per input (100 inputs x 0.5 nS x 2 ms)
    return r_e, r_i


def _run(gi, es, g, x, seed_val):
    from brian2 import prefs, nS
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol
    r_e, r_i = drive(gi, es)
    r = run_context_protocol([0], T=3.0, input_mode='always', seed_val=seed_val, bap_source='soma',
                             soma_drive_hz=r_e, soma_drive_nS=0.5, soma_inh_hz=r_i, soma_inh_nS=1.0,
                             param_overrides={'gAMPA_pv': 0.12 * x * nS, 'gGABA_pv2soma': g * nS})
    t = r['traj'][0]
    return dict(gi=gi, es=es, g=g, x=x, pyr=float(t['pyr_hz']), cv=float(t['pyr_cv']),
                pv=float(t['pv_hz']), rho0=t['rho0'], rho1=t['rho1'])


FINE = dict(G_I=[5.0, 7.5, 10.0], E_SCALE=[0.5, 0.55, 0.6, 0.65],
            G_PV2SOMA=[0.05, 0.075, 0.1, 0.15])   # refinement around the coarse passing corner


def main():
    global G_I, E_SCALE, G_PV2SOMA
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    fine = len(sys.argv) > 3 and sys.argv[3] == 'fine'
    if fine:
        G_I, E_SCALE, G_PV2SOMA = FINE['G_I'], FINE['E_SCALE'], FINE['G_PV2SOMA']
    jobs = [(gi, es, g, x, sd) for gi, es, g, x in itertools.product(G_I, E_SCALE, G_PV2SOMA, PV_X)]
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        res = list(ex.map(_run, *zip(*jobs)))
    R = {(r['gi'], r['es'], r['g'], r['x']): r for r in res}
    rows = []
    print(f"{'gI':>4} {'Escl':>5} {'gPVs':>5} | soma Hz @ PV x0 x0.5 x1 x2 x3 | CV@x1 | S1 S2 S3")
    for gi, es, g in itertools.product(G_I, E_SCALE, G_PV2SOMA):
        s = [R[(gi, es, g, x)]['pyr'] for x in PV_X]
        cv = R[(gi, es, g, 1.0)]['cv']
        S1 = 5.0 <= s[2] <= 15.0
        S2 = all(a > b for a, b in zip(s, s[1:])) and s[4] >= 1.0 and 1.5 <= s[0] / max(s[2], 1e-9) <= 5.0
        S3 = cv == cv and cv >= 0.7
        rows.append(dict(gi=gi, es=es, g=g, soma=s, cv_x1=cv, S1=S1, S2=S2, S3=S3, all=S1 and S2 and S3))
        print(f"{gi:>4} {es:>5} {g:>5} | " + ' '.join(f'{v:5.1f}' for v in s) + f" | {cv:5.2f} | "
              f"{'Y' if S1 else '.'}  {'Y' if S2 else '.'}  {'Y' if S3 else '.'} {'<== ALL' if S1 and S2 and S3 else ''}")
    os.makedirs(os.path.join(PROOT, 'results', 'current'), exist_ok=True)
    json.dump(dict(seed=sd, raw=res, grid=rows),
              open(os.path.join(PROOT, 'results', 'current', f"soma_balanced_calibration_{'fine_' if fine else ''}seed{sd}.json"), 'w'),
              indent=1, default=float)


if __name__ == '__main__':
    main()
