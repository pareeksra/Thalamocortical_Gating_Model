"""
robustness_r4_readout.py -- second diagnosis of the failed R4 learning test (2026-11-10).

robustness_r4_shunting.py rejected the shunting hypothesis: after learning, with the WRONG
gate open, the learned (strong) branch stays mostly inhibited (plateau 7%) but the open
branch plateaus 98% of the time even though its synapses are weak (w ~ 0.93). At the R4
readout drive (20 synapses x 50 Hz) both weak and strong branches are far above the
plateau threshold, so the open gate decides and learning cannot show.
Yang (Methods, Fig. 7d,e) read out with 8/15 synapses before and 5/15 after learning
(equal total conductance), i.e. a drive between the weak- and strong-branch thresholds.

Hypothesis (written before running): there is a readout drive window in which, after
learning, the strong branch plateaus when its gate is open but the weak branch does NOT
plateau when its gate is open -> S_after > 0.3 while S_before ~ 0.
Test: reuse the learned weights saved by robustness_r4_shunting.py (gGABA x1, seeds
42-48); readout only (plasticity frozen), pattern rate swept. Before-learning readout at
the same rates for comparison.
Contrast (argument 'ampa'): the same readout on the OLD synapse's learned weights
(robustness_r4_learning.json, synapse='ampa', rho0 0.5), rates 5-20 Hz, 10 seeds.
Prediction: S_after ~ S_before (learning changes only AMPA), unlike the Yang synapse.
Run:  <py> -I experiments/robustness_r4_readout.py [n_workers] [ampa]
Out:  results/current/robustness_r4_readout.json, figures/robustness_r4_readout.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
SRC = os.path.join(PROOT, 'results', 'current', 'robustness_r4_shunting.json')
OUT = os.path.join(PROOT, 'results', 'current', 'robustness_r4_readout.json')
RATES = [5.0, 10.0, 15.0, 20.0, 30.0, 50.0]
SYN = 'ampa' if 'ampa' in sys.argv[1:] else 'yang'
if SYN == 'ampa':
    SRC = os.path.join(PROOT, 'results', 'current', 'robustness_r4_learning.json')
    OUT = os.path.join(PROOT, 'results', 'current', 'robustness_r4_readout_ampa.json')
    RATES = [5.0, 10.0, 15.0, 20.0]


def _job(state, rate, seed, rho0, rho1):
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA
    import functools; run_context_protocol = functools.partial(run_context_protocol, som_baseline='bias', bap_ca_scale=1.0)  # pre-2026-11-10 SOM baseline and bAP calcium: reproduces the committed results
    from robustness_r4_learning import READ, S_from
    t0 = time.time()
    r = run_context_protocol([c for c, _ in READ], T=5.0, input_mode='patterns', overlap=0.0,
                             stim=[s for _, s in READ], plastic=False, rho_init_syn=(rho0, rho1), exc_rate=rate,
                             bap_source='soma', seed_val=seed, record_dend=True, synapse=SYN,
                             param_overrides={'gGABA_pv2soma': BALANCED_SOMA_G_PV2SOMA}, **BALANCED_SOMA_KW)
    rates = [t['pyr_hz'] for t in r['traj']]
    S, Sk = S_from(rates)
    return dict(state=state, rate=rate, seed=seed, rates=rates, S=S, S_k=Sk,
                plat=[[t['plat0'], t['plat1']] for t in r['traj']], wall_s=round(time.time() - t0, 1))


def main(nw):
    src = json.load(open(SRC))['runs']
    if SYN == 'ampa':
        learned = {r['seed']: (r['learned']['rho0'], r['learned']['rho1']) for r in src.values() if r['syn'] == 'ampa'}
    else:
        learned = {r['seed']: (r['learned']['rho0'], r['learned']['rho1']) for r in src.values() if r['scale'] == 1.0}
    rho_b = 0.5 if SYN == 'ampa' else 1 / 3
    n_aff = len(next(iter(learned.values()))[0])
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    J = []
    for seed, (r0, r1) in sorted(learned.items()):
        for rate in RATES:
            J.append(('after', rate, seed, r0, r1))
            J.append(('before', rate, seed, [rho_b] * n_aff, [rho_b] * n_aff))
    J = [j for j in J if f'{j[0]}_{j[1]}_{j[2]}' not in done]
    print(len(J), 'jobs', flush=True)
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(_job, *j): j for j in J}
        for fu in as_completed(futs):
            j = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                print(j[:3], 'ERROR', repr(e), flush=True); continue
            done[f'{j[0]}_{j[1]}_{j[2]}'] = r
            json.dump(done, open(OUT, 'w'))
            print(j[:3], f"S {r['S']:.2f}  rates " + ' '.join(f'{v:.1f}' for v in r['rates']), flush=True)
    analyse(done)


def analyse(done=None):
    done = done or json.load(open(OUT))
    summ = {}
    for st in ('before', 'after'):
        for rate in RATES:
            rs = [r for r in done.values() if r['state'] == st and r['rate'] == rate]
            S = [r['S'] for r in rs]
            P = np.array([r['plat'] for r in rs]).mean(0)
            R = np.array([r['rates'] for r in rs]).mean(0)
            summ[f'{st}_{rate}'] = dict(S=[float(np.nanmean(S)), float(np.nanstd(S))], n=len(rs), plat=P.tolist(), rates=R.tolist())
            # plateau of the pattern's own branch with its gate open vs the other branch with the wrong gate open
            print(f"{st:<6} {rate:>4} Hz: S {np.nanmean(S):+.2f}±{np.nanstd(S):.2f} | A, gate A: b0 plat {P[2][0]:.2f} | "
                  f"A, gate B: b1 plat {P[3][1]:.2f}, b0 {P[3][0]:.2f} | rates " + ' '.join(f'{v:.1f}' for v in R))
    json.dump(dict(summary=summ, runs=done), open(OUT, 'w'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    for st, c in (('before', '#999999'), ('after', '#0072B2')):
        ax[0].errorbar(RATES, [summ[f'{st}_{r}']['S'][0] for r in RATES], yerr=[summ[f'{st}_{r}']['S'][1] for r in RATES],
                       fmt='o-', color=c, lw=2, capsize=3, label=f'{st} learning')
        ax[1].plot(RATES, [summ[f'{st}_{r}']['plat'][2][0] for r in RATES], 'o-', color=c, lw=2,
                   label=f'{st}: own branch, its gate open')
        ax[1].plot(RATES, [summ[f'{st}_{r}']['plat'][3][1] for r in RATES], 's--', color=c, lw=2,
                   label=f'{st}: other branch, its gate open')
    ax[0].axhline(0, color='0.85', lw=1)
    ax[0].set(xlabel='readout input rate per synapse (Hz)', ylabel='gating selectivity S', title='Learned gating vs readout drive')
    ax[1].set(xlabel='readout input rate per synapse (Hz)', ylabel='plateau fraction (pattern A presented)',
              title='Is there a window where only the learned branch plateaus?')
    for a in ax:
        a.legend(frameon=False, fontsize=8); a.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'robustness_r4_readout' + ('_ampa' if SYN == 'ampa' else '') + '.png')
    fig.savefig(fp, dpi=150, facecolor='white'); print('saved', fp)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'analyse':
        analyse()
    else:
        main(int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 11)
