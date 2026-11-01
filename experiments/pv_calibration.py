"""
pv_calibration.py -- recalibrate the PV arm (open item from docs/AUDIT_2026-11-01.md, P8).

Problem. PV's background drive (rate_bg_pv = 500 Hz, weight_bg_pv = 0.25 nS) was calibrated
BEFORE SOM->PV was wired (2026-08-27: p = 0.8, gGABA_pv = 2.0 nS) and never re-tuned.
With ~16 active SOM inputs at 30 Hz, the mean SOM->PV shunt is ~16 * 30 Hz * 2 nS * 10 ms
~ 9.6 nS -- ~10x PV's 1 nS leak -- so PV is silent whenever SOM is active, and MD->PV
(Zhang's MD^GRIK4 gain arm) is inert.

Source constraints (Yang 2016 Methods, p. 11-12): PV are linear rate units, f-I slope
220 Hz/nA, "their activities never reach zero in our model"; P_SOM->PV = 0.8 but the
SOM->PV strength is a FREE parameter Yang varies (Fig. 6b). So gGABA_pv is ours to set;
p_som2pv, and MD->PV (p_md2pv, n_md, gAMPA_pv) stay untouched.

Targets (stated before running):
  T1 baseline   MD 0 Hz, SOM active (30 Hz):  5 <= PV <= 10 Hz   (project's prior 7.5 Hz)
  T2 MD gain    SOM active, MD 0->40 Hz: monotonic, PV(40)/PV(0) >= 3, and no single
                MD step (5 / 10 Hz increments) adds more than 40% of the total rise
  T3 release    MD 0, SOM silenced:  PV(SOM off) > PV(SOM on), and <= 60 Hz

Harness: one Brian 2 network holding an independent 20-cell PV population per grid point
(its own background, MD Poisson pool and random SOM->PV connectivity), all reading one
shared, desynchronised 20-cell SOM population (som_phase='random', 21.32 pA -> 30 Hz).
SOM-silenced conditions get no SOM input. 3 s per run, rates from the last 2.5 s.

Run:  <venv>/python -I experiments/pv_calibration.py [seed]
Out:  docs/audit/pv_calibration_seed<seed>.json
"""
import os, sys, json, itertools
import numpy as np
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT]
from brian2 import (NeuronGroup, PoissonGroup, Synapses, SpikeMonitor, Network, seed, prefs,
                    second, ms, nS, pA, Hz)
prefs.codegen.target = 'cython'
from parameters import params, pv_params, som_params, md_params
from equations import eqs_pv, eqs_som
from circuit_helpers import som_initial_voltages

W_BG = [0.20, 0.25, 0.30, 0.35, 0.40]            # nS, background weight per input
G_SOMPV = [0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.0]   # nS, SOM->PV per-synapse
MD_RATES = [0, 5, 10, 20, 30, 40]
SOM_ON = [True, False]
N_PV = 20
T_RUN, T_SKIP = 3.0, 0.5


def run(seed_val=42, w_bg=W_BG, g_sompv=G_SOMPV, md_rates=MD_RATES, som_on=SOM_ON):
    seed(seed_val)
    p = dict(params); p.update(pv_params); p.update(som_params); p.update(md_params)
    conds = list(itertools.product(w_bg, g_sompv, md_rates, som_on))
    nc = len(conds); n_md = p['n_md']
    p['n_pv_c'] = N_PV; p['n_md_c'] = n_md
    PV = NeuronGroup(nc * N_PV, eqs_pv, threshold='V>vThres_pv', reset='V=vReset_pv',
                     refractory=p['refrac_pv'], method='euler', namespace=p)
    PV.V = p['vRest_pv']
    cid = np.arange(nc * N_PV) // N_PV
    # background: one Poisson source per PV cell, per-cell weight
    BG = PoissonGroup(nc * N_PV, rates=p['rate_bg_pv'])
    sbg = Synapses(BG, PV, model='wbg : siemens', on_pre='gTotAMPA_post += wbg', namespace=p)
    sbg.connect(j='i'); sbg.wbg = np.array([conds[c][0] for c in cid]) * nS
    # MD: own 50-cell pool per condition, Zhang/parameters.py MD->PV (p, g untouched)
    MD = PoissonGroup(nc * n_md, rates=np.repeat([conds[c][2] for c in range(nc)], n_md) * Hz)
    smd = Synapses(MD, PV, on_pre='gTotAMPA_post += gAMPA_pv', namespace=p)
    smd.connect(condition='i // n_md_c == j // n_pv_c', p=p['p_md2pv'])
    # SOM: one shared desynchronised 30 Hz population
    n_som = p['n_som_spike']
    SOM = NeuronGroup(n_som, eqs_som, threshold='V>vThres_som', reset='V=vReset_som',
                      refractory=p['refrac_som'], method='euler', namespace=p)
    SOM.V = som_initial_voltages(n_som, p, 21.32, 'random', seed_val); SOM.iBaseline_som = 21.32 * pA
    on_mask = np.array([conds[c][3] for c in range(nc)])
    p['som_on_c'] = on_mask.astype(float)
    ssp = Synapses(SOM, PV, model='gsp : siemens', on_pre='gTotGABA_post += gsp', namespace=p)
    targets_on = np.where(on_mask[cid])[0]
    pre, post = np.nonzero(np.random.rand(n_som, len(targets_on)) < p['p_som2pv'])
    ssp.connect(i=pre, j=targets_on[post])
    ssp.gsp = np.array([conds[cid[j]][1] for j in np.asarray(ssp.j[:])]) * nS
    mpv = SpikeMonitor(PV); msom = SpikeMonitor(SOM)
    net = Network(PV, BG, sbg, MD, smd, SOM, ssp, mpv, msom)
    net.run(T_RUN * second)
    t = np.asarray(mpv.t / second); i = np.asarray(mpv.i)
    keep = t >= T_SKIP
    counts = np.bincount(cid[i[keep]], minlength=nc)
    rate = counts / (T_RUN - T_SKIP) / N_PV
    som_rate = msom.num_spikes / T_RUN / n_som
    return conds, rate, som_rate


def evaluate(conds, rate):
    """Collapse to per-(w_bg, g) curves and score the three targets."""
    R = {c: r for c, r in zip(conds, rate)}
    out = []
    for wb in sorted({c[0] for c in conds}):
        for g in sorted({c[1] for c in conds}):
            on = np.array([R[(wb, g, m, True)] for m in MD_RATES])
            off0 = R[(wb, g, 0, False)]
            base = on[0]
            rise = on[-1] - on[0]
            steps = np.diff(on)
            t1 = bool(5.0 <= base <= 10.0)
            t2 = bool(np.all(steps >= -1.0) and base > 0 and on[-1] / base >= 3.0
                      and (rise > 0 and steps.max() <= 0.4 * rise))
            t3 = bool(off0 > base and off0 <= 60.0)
            out.append(dict(w_bg_nS=float(wb), gGABA_pv_nS=float(g), pv_vs_md_som_on=on.tolist(),
                            pv_md0_som_off=float(off0), T1=t1, T2=t2, T3=t3,
                            all=bool(t1 and t2 and t3)))
    return out


W_BG_FINE = [0.28, 0.29, 0.30, 0.31, 0.32, 0.33, 0.34]
G_SOMPV_FINE = [0.03, 0.05, 0.075, 0.1, 0.125, 0.15]


def main():
    sd = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    fine = len(sys.argv) > 2 and sys.argv[2] == 'fine'
    if fine:
        conds, rate, som_rate = run(sd, w_bg=W_BG_FINE, g_sompv=G_SOMPV_FINE)
    else:
        conds, rate, som_rate = run(sd)
    ev = evaluate(conds, rate)
    print(f'SOM rate {som_rate:.2f} Hz (target 30)')
    print(f"{'w_bg':>5} {'g_sp':>5} | PV vs MD {MD_RATES} (SOM on) | SOM off | T1 T2 T3")
    for e in ev:
        print(f"{e['w_bg_nS']:>5.2f} {e['gGABA_pv_nS']:>5.2f} | "
              + ' '.join(f'{x:6.1f}' for x in e['pv_vs_md_som_on'])
              + f" | {e['pv_md0_som_off']:6.1f} | {'Y' if e['T1'] else '.'}  {'Y' if e['T2'] else '.'}  "
              f"{'Y' if e['T3'] else '.'} {'<== ALL' if e['all'] else ''}")
    os.makedirs(os.path.join(PROOT, 'docs', 'audit'), exist_ok=True)
    json.dump(dict(seed=sd, som_rate=som_rate, md_rates=MD_RATES, grid=ev),
              open(os.path.join(PROOT, 'docs', 'audit', f"pv_calibration_{'fine_' if fine else ''}seed{sd}.json"), 'w'), indent=1)


if __name__ == '__main__':
    main()
