"""
robustness_r4_shunting.py -- diagnose the failed R4 learning test (2026-11-10).

R4 (robustness_r4_learning.py, Yang Fig. 7d,e analogue) failed: weights aligned exactly
as in Yang (A->own branch 0.925, A->other branch 0.31) but the soma output did not gate
(pattern A: 12.8 Hz with gate A open vs 13.0 Hz with gate B open).

Hypothesis (written before running): our dendrite is shunted less by inhibition than
Yang's (V1: -23 vs -54 mV at 10 nS; Yang's 10 Hz regime needs ~1.5x gGABA). After
learning, potentiated synapses (w ~ 2.8, ~7 nS NMDA each) drive a plateau even on a
gated-off (inhibited) branch, so both branches respond whichever gate is open.
Predictions: (1) at x1, the closed-gate branch carrying the learned pattern plateaus in
the readout; (2) scaling the SOM->dendrite conductance gGABA by x1.5-x2 suppresses that
plateau and gating selectivity after learning becomes clearly positive (S_after > 0.3)
while S_before stays ~0; (3) learning itself still aligns the weights at x1.5-x2.
If (2) fails, shunting is not the explanation and the cause lies elsewhere (e.g. the
readout protocol or too little LTD on inhibited branches).

Same protocol as robustness_r4_learning.py (Yang synapse only), plus record_dend in the
readout. gGABA scaled in both learning and readout.
Run:  <py> -I experiments/robustness_r4_shunting.py [n_workers]
Out:  results/current/robustness_r4_shunting.json, figures/robustness_r4_shunting.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
OUT = os.path.join(PROOT, 'results', 'current', 'robustness_r4_shunting.json')
SCALES = [1.0, 1.5, 2.0]
SEEDS = [42, 43, 44, 45, 46, 47, 48]


def _job(scale, seed):
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA
    import functools; run_context_protocol = functools.partial(run_context_protocol, som_baseline='bias', bap_ca_scale=1.0)  # pre-2026-11-10 SOM baseline and bAP calcium: reproduces the committed results
    from parameters import params
    from robustness_r4_learning import READ, S_from, N_EP, LEARN_HZ, READ_HZ
    t0 = time.time()
    g = params['gGABA'] * scale
    learn = run_context_protocol([0] * N_EP + [1] * N_EP, T=3.0, input_mode='patterns', overlap=0.0,
                                 exc_rate=LEARN_HZ, seed_val=seed, param_overrides={'gGABA': g})
    tr = learn['traj']
    n_aff = len(tr[-1]['rho0_syn'])
    states = {'before': ([1 / 3] * n_aff, [1 / 3] * n_aff), 'after': (tr[-1]['rho0_syn'], tr[-1]['rho1_syn'])}
    out = dict(scale=scale, seed=seed, idx_A=learn['idx_A'], idx_B=learn['idx_B'],
               learned=dict(rho0=tr[-1]['rho0_syn'], rho1=tr[-1]['rho1_syn']),
               som_learn=[[t['som0_hz'], t['som1_hz']] for t in tr])
    for name, st in states.items():
        r = run_context_protocol([c for c, _ in READ], T=5.0, input_mode='patterns', overlap=0.0,
                                 stim=[s for _, s in READ], plastic=False, rho_init_syn=st, exc_rate=READ_HZ,
                                 bap_source='soma', seed_val=seed, record_dend=True,
                                 param_overrides={'gGABA': g, 'gGABA_pv2soma': BALANCED_SOMA_G_PV2SOMA},
                                 **BALANCED_SOMA_KW)
        rates = [t['pyr_hz'] for t in r['traj']]
        S, Sk = S_from(rates)
        out[name] = dict(rates=rates, S=S, S_k=Sk, plat=[[t['plat0'], t['plat1']] for t in r['traj']],
                         dV=[[t['dV0'], t['dV1']] for t in r['traj']])
    out['wall_s'] = round(time.time() - t0, 1)
    return out


def main(nw):
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    J = [(sc, s) for sc in SCALES for s in SEEDS if f'{sc}_{s}' not in done]
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(_job, *j): j for j in J}
        for fu in as_completed(futs):
            j = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                print(j, 'ERROR', repr(e), flush=True); continue
            done[f'{j[0]}_{j[1]}'] = r
            json.dump(done, open(OUT, 'w'))
            print(j, f"S before {r['before']['S']:.2f} after {r['after']['S']:.2f} ({r['wall_s']} s)", flush=True)
    analyse(done)


def analyse(done=None):
    done = done or json.load(open(OUT))
    from robustness_r4_learning import READ
    print('readout epochs:', READ, '(context, pattern)')
    summ = {}
    for sc in SCALES:
        rs = [r for r in done.values() if r['scale'] == sc]
        if not rs:
            continue
        A, B = np.array(rs[0]['idx_A']), np.array(rs[0]['idx_B'])
        w = np.array([[np.mean(np.array(r['learned']['rho0'])[A]), np.mean(np.array(r['learned']['rho1'])[A])] for r in rs])
        sb = [r['before']['S'] for r in rs]; sa = [r['after']['S'] for r in rs]
        pa = np.array([r['after']['plat'] for r in rs]).mean(0); pb = np.array([r['before']['plat'] for r in rs]).mean(0)
        ra = np.array([r['after']['rates'] for r in rs]).mean(0); rb = np.array([r['before']['rates'] for r in rs]).mean(0)
        som = np.array([r['som_learn'] for r in rs]).mean(0)
        summ[sc] = dict(n=len(rs), S_before=[float(np.nanmean(sb)), float(np.nanstd(sb))],
                        S_after=[float(np.nanmean(sa)), float(np.nanstd(sa))],
                        rhoA_own=float(w[:, 0].mean()), rhoA_other=float(w[:, 1].mean()),
                        plat_before=pb.tolist(), plat_after=pa.tolist(), rates_before=rb.tolist(),
                        rates_after=ra.tolist(), som_inhibited_learning=float(som[:8, 1].mean()))
        print(f"gGABA x{sc}: S before {np.nanmean(sb):+.2f}±{np.nanstd(sb):.2f}  after {np.nanmean(sa):+.2f}±{np.nanstd(sa):.2f} | "
              f"rho A own {w[:, 0].mean():.3f} other {w[:, 1].mean():.3f}")
        print('   rates before', rb.round(1), ' after', ra.round(1))
        print('   plateau frac [b0,b1] after, per readout epoch:', [[round(x, 2) for x in e] for e in pa])
    json.dump(dict(summary={str(k): v for k, v in summ.items()}, runs=done), open(OUT, 'w'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    scs = list(summ)
    for k, c in (('S_before', '#999999'), ('S_after', '#0072B2')):
        ax[0].errorbar(scs, [summ[s][k][0] for s in scs], yerr=[summ[s][k][1] for s in scs], fmt='o-', capsize=4,
                       color=c, lw=2, label=k.replace('S_', '').replace('before', 'before learning').replace('after', 'after learning'))
    ax[0].axhline(0, color='0.85', lw=1); ax[0].set(xlabel='SOM→dendrite conductance gGABA (× default)', ylabel='gating selectivity S',
                                                   title='Does stronger dendritic shunting restore learned gating?', xticks=scs)
    ax[0].legend(frameon=False)
    # closed-gate branch plateau when the learned pattern is presented: epoch (1,0) = pattern A with gate B open -> branch 0 closed
    ax[1].bar([f'×{s}' for s in scs], [summ[s]['plat_after'][3][0] for s in scs], color='#D55E00', label='A presented, gate B open: branch 0 (A\'s, closed)')
    ax[1].bar([f'×{s}' for s in scs], [summ[s]['plat_after'][3][1] for s in scs], bottom=[summ[s]['plat_after'][3][0] for s in scs],
              color='#9ecae1', label='… branch 1 (open, weak A synapses)')
    ax[1].set(ylabel='fraction of time in plateau (stacked)', title='After learning: where does pattern A plateau\nwhen the WRONG gate is open?')
    ax[1].legend(frameon=False, fontsize=8)
    for a in ax:
        a.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'robustness_r4_shunting.png')
    fig.savefig(fp, dpi=150, facecolor='white'); print('saved', fp)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'analyse':
        analyse()
    else:
        main(int(sys.argv[1]) if len(sys.argv) > 1 else 11)
