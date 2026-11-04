"""
robustness_r4_learning.py -- R4 of docs/reports/PLAN_robustness.md, the functional test of
gap G1: Yang 2016 Fig. 7c-e, "learning to gate specific pathways" (2026-11-04).

Yang's protocol, mapped onto our 2-branch context circuit:
  * both pathways initially target every dendrite with equal weights:
    input_mode='patterns', overlap 0, every afferent synapses on both branches.
  * learning: context A (MD_0 opens branch 0) with pattern A on, then context B (MD_1 opens
    branch 1) with pattern B on; N_EP epochs each, 3 s, pinned 10 Hz bAPs (Yang: post rate
    fixed at 10 Hz). Pattern rate 50 Hz (Yang) unless overridden.
  * readout (learning frozen, soma free with the balanced drive, bAPs from the soma):
    gating selectivity S = (r_on - r_off)/(r_on + r_off) of the soma rate, pattern A
    presented with gate A vs gate B open (and B likewise), baseline-corrected; before
    learning (initial weights) and after learning (learned weights).
  Yang equalised total drive before vs after by activating 8 vs 5 of 15 synapses; here
  the readout rate is the same before and after and both are reported.
Yang (Fig. 7d,e): before learning, no preference for the open gate (S ~ 0); after
learning, strong pathway-specific gating.
Prediction: synapse 'yang' -> S_after >> S_before; synapse 'ampa' -> S_after ~ S_before,
because learning changes only AMPA.
Run:  <py> -I experiments/robustness_r4_learning.py [n_workers]
Out:  results/current/robustness_r4_learning.json, figures/robustness_r4_learning.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
OUT = os.path.join(PROOT, 'results', 'current', 'robustness_r4_learning.json')
SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
N_EP = 8
LEARN_HZ = 50.0
READ_HZ = 50.0
# readout epochs: (context, pattern); None = no pattern (baseline)
READ = [(0, None), (1, None), (0, 0), (1, 0), (1, 1), (0, 1)]


def S_from(rates):
    base = {0: rates[0], 1: rates[1]}
    r = {(c, s): max(rates[i] - base[c], 0.0) for i, (c, s) in enumerate(READ) if s is not None}
    S = []
    for k in (0, 1):
        on, off = r[(k, k)], r[(1 - k, k)]
        S.append((on - off) / (on + off) if on + off > 0 else float('nan'))
    return float(np.nanmean(S)), S


def _job(syn, seed):
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA
    t0 = time.time()
    learn = run_context_protocol([0] * N_EP + [1] * N_EP, T=3.0, input_mode='patterns', overlap=0.0,
                                 exc_rate=LEARN_HZ, seed_val=seed, synapse=syn)
    tr = learn['traj']
    init = None
    rho0 = (1 / 3) if syn == 'yang' else 0.5
    n_aff = len(tr[-1]['rho0_syn'])
    states = {'before': ([rho0] * n_aff, [rho0] * n_aff), 'after': (tr[-1]['rho0_syn'], tr[-1]['rho1_syn'])}
    out = dict(syn=syn, seed=seed, idx_A=learn['idx_A'], idx_B=learn['idx_B'],
               learned=dict(rho0=tr[-1]['rho0_syn'], rho1=tr[-1]['rho1_syn']))
    for name, st in states.items():
        r = run_context_protocol([c for c, _ in READ], T=5.0, input_mode='patterns', overlap=0.0,
                                 stim=[s for _, s in READ], plastic=False, rho_init_syn=st, exc_rate=READ_HZ,
                                 bap_source='soma', seed_val=seed, synapse=syn,
                                 param_overrides={'gGABA_pv2soma': BALANCED_SOMA_G_PV2SOMA}, **BALANCED_SOMA_KW)
        rates = [t['pyr_hz'] for t in r['traj']]
        S, Sk = S_from(rates)
        out[name] = dict(rates=rates, S=S, S_k=Sk)
    out['wall_s'] = round(time.time() - t0, 1)
    return out


def main(nw):
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    J = [(syn, s) for syn in ('yang', 'ampa') for s in SEEDS if f'{syn}_{s}' not in done]
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
            print(j, f"S before {r['before']['S']:.2f}  after {r['after']['S']:.2f}  rates after "
                  + ' '.join(f'{v:.1f}' for v in r['after']['rates']) + f"  ({r['wall_s']} s)", flush=True)
    summ = {}
    for syn in ('yang', 'ampa'):
        rs = [r for r in done.values() if r['syn'] == syn]
        b = [r['before']['S'] for r in rs]; a = [r['after']['S'] for r in rs]
        summ[syn] = dict(n=len(rs), S_before=[float(np.nanmean(b)), float(np.nanstd(b))],
                         S_after=[float(np.nanmean(a)), float(np.nanstd(a))])
        print(syn, summ[syn])
    json.dump(dict(summary=summ, runs=done), open(OUT, 'w'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    for i, syn in enumerate(('yang', 'ampa')):
        rs = [r for r in done.values() if r['syn'] == syn]
        for r in rs:
            ax[0].plot([i * 3, i * 3 + 1], [r['before']['S'], r['after']['S']], '-', color='0.75', lw=1)
        m = summ[syn]
        ax[0].errorbar([i * 3, i * 3 + 1], [m['S_before'][0], m['S_after'][0]],
                       yerr=[m['S_before'][1], m['S_after'][1]], fmt='o-', color=['#0072B2', '#D55E00'][i], lw=2, capsize=4)
    ax[0].set_xticks([0, 1, 3, 4], ['before', 'after\nYang synapse', 'before', 'after\nold (AMPA) synapse'])
    ax[0].set_ylabel('gating selectivity S (soma output)'); ax[0].axhline(0, color='0.85', lw=1)
    ax[0].set_title('Yang Fig. 7d,e analogue: does learning create gating?', fontsize=10)
    rs = [r for r in done.values() if r['syn'] == 'yang']
    A = np.array(rs[0]['idx_A']); B = np.array(rs[0]['idx_B'])
    w = lambda r, b, ix: np.mean(np.array(r['learned'][f'rho{b}'])[ix])
    lab = ['A on branch 0', 'A on branch 1', 'B on branch 0', 'B on branch 1']
    vals = [[w(r, 0, A), w(r, 1, A), w(r, 0, B), w(r, 1, B)] for r in rs]
    ax[1].bar(lab, np.mean(vals, 0), yerr=np.std(vals, 0), color=['#0072B2', '#9ecae1', '#fdae6b', '#D55E00'], capsize=4)
    ax[1].axhline(1 / 3, color='k', ls='--', lw=1, label='initial ρ = 1/3')
    ax[1].set_ylabel('learned ρ (Yang synapse)'); ax[1].legend(frameon=False, fontsize=8)
    ax[1].set_title('excitation aligns with disinhibition (Yang Fig. 7c)', fontsize=10)
    for a in ax:
        a.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'robustness_r4_learning.png')
    fig.savefig(fp, dpi=150, facecolor='white'); print('saved', fp)


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 11)
