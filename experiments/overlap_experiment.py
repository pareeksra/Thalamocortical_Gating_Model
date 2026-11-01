"""
overlap_experiment.py -- overlapping-inputs experiment (plan: docs/PLAN_overlapping_inputs.md).

Contexts A and B share a fraction f of their 20 afferents; every afferent has a plastic
synapse on both branches. Context A (MD_0 on, pattern A) x 8 epochs, then context B
(MD_1 on, pattern B) x 8 epochs. Gating {md: SOM inhibition on, none: inhibition off} x
f {0, .25, .5, .75, 1} x seeds 42-46. Fresh process per run.

Run:     <py> -I experiments/overlap_experiment.py run [n_workers]
Analyse: <py> -I experiments/overlap_experiment.py analyse
Out:     docs/audit/overlap_experiment.json, figures/overlap_experiment.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT]
OUT = os.path.join(PROOT, 'docs', 'audit', 'overlap_experiment.json')
OVERLAPS = [0.0, 0.25, 0.5, 0.75, 1.0]
GATING = ['md', 'none']
SEEDS = [42, 43, 44, 45, 46]
N_EP = 8
W1 = 3.0     # w = w0 + (w1 - w0) rho, w0 = 0


def metrics(r0A, r1A, r0B, r1B, A, B):
    """r{branch}{phase}: per-afferent rho after phase A / after phase B."""
    A, B = np.asarray(A), np.asarray(B)
    sh, Ao, Bo = np.intersect1d(A, B), np.setdiff1d(A, B), np.setdiff1d(B, A)
    m = lambda x, ix: float(np.mean(x[ix])) if len(ix) else float('nan')
    out = dict(
        ret_A=m(r0B, A) / m(r0A, A),
        ret_A_shared=(m(r0B, sh) / m(r0A, sh)) if len(sh) else float('nan'),
        ret_A_unique=(m(r0B, Ao) / m(r0A, Ao)) if len(Ao) else float('nan'),
        rhoA_b0_endA=m(r0A, A), rhoA_b0_endB=m(r0B, A),
        rhoB_b1_endB=m(r1B, B), rhoA_b1_endB=m(r1B, A), rhoB_b0_endB=m(r0B, B),
        sep_b0=(m(r0B, A) - m(r0B, Bo)) if len(Bo) else float('nan'),
        sep_b1=(m(r1B, B) - m(r1B, Ao)) if len(Ao) else float('nan'),
    )
    # pattern drive D(X, b) = sum of AMPA efficacies w over pattern-X afferents on branch b
    D = lambda r, ix: float(W1 * np.sum(r[ix]))
    out.update(D_A_b0=D(r0B, A), D_B_b0=D(r0B, B), D_A_b1=D(r1B, A), D_B_b1=D(r1B, B))
    # context discriminability of the whole cell: branch-specific drive contrast
    # (A should drive b0 more than B does, and B should drive b1 more than A does)
    out['discrim'] = ((out['D_A_b0'] - out['D_B_b0']) + (out['D_B_b1'] - out['D_A_b1'])) / (2 * W1 * len(A))
    return out


def _job(gating, f, seed_val):
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol
    t0 = time.time()
    r = run_context_protocol([0] * N_EP + [1] * N_EP, T=3.0, input_mode='patterns', overlap=f,
                             inhibition=(gating == 'md'), seed_val=seed_val)
    tr = r['traj']; a, b = tr[N_EP - 1], tr[-1]
    mt = metrics(np.array(a['rho0_syn']), np.array(a['rho1_syn']), np.array(b['rho0_syn']),
                 np.array(b['rho1_syn']), r['idx_A'], r['idx_B'])
    return dict(gating=gating, overlap=f, seed=seed_val, idx_A=r['idx_A'], idx_B=r['idx_B'],
                rho_endA=[a['rho0_syn'], a['rho1_syn']], rho_endB=[b['rho0_syn'], b['rho1_syn']],
                som_A=[a['som0_hz'], a['som1_hz']], som_B=[b['som0_hz'], b['som1_hz']],
                wall_s=round(time.time() - t0, 1), **mt)


def run(nw):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    J = [(g, f, s) for g in GATING for f in OVERLAPS for s in SEEDS if f'{g}_{f}_{s}' not in done]
    print(f'{len(J)} jobs ({len(done)} done), {nw} workers', flush=True)
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(_job, *j): j for j in J}
        for fu in as_completed(futs):
            g, f, s = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                print(f'  {g}_{f}_{s}: ERROR {e!r}', flush=True); continue
            done[f'{g}_{f}_{s}'] = r
            json.dump(done, open(OUT, 'w'), indent=1)
            print(f"  {g:<4} f={f:<4} seed {s}: ret_A {r['ret_A']:.3f} (shared {r['ret_A_shared']:.3f}) "
                  f"sep_b0 {r['sep_b0']:.3f} sep_b1 {r['sep_b1']:.3f} discrim {r['discrim']:.3f} ({r['wall_s']} s)",
                  flush=True)
    print('done', flush=True)


def analyse():
    d = json.load(open(OUT))
    keys = ['ret_A', 'ret_A_shared', 'ret_A_unique', 'sep_b0', 'sep_b1', 'discrim', 'rhoB_b1_endB']
    S = {}
    for g in GATING:
        for f in OVERLAPS:
            rs = [r for r in d.values() if r['gating'] == g and r['overlap'] == f]
            S[(g, f)] = {k: (np.nanmean([r[k] for r in rs]), np.nanstd([r[k] for r in rs]), len(rs)) for k in keys}
    print(f"{'gating':<5} {'f':>5} | {'ret_A':>13} {'ret_shared':>11} {'ret_unique':>11} | {'sep_b0':>7} {'sep_b1':>7} "
          f"{'discrim':>8} | rhoB_b1 | n")
    for (g, f), v in S.items():
        print(f"{g:<5} {f:>5} | {v['ret_A'][0]:.3f}±{v['ret_A'][1]:.3f} {v['ret_A_shared'][0]:>11.3f} "
              f"{v['ret_A_unique'][0]:>11.3f} | {v['sep_b0'][0]:>7.3f} {v['sep_b1'][0]:>7.3f} "
              f"{v['discrim'][0]:>8.3f} | {v['rhoB_b1_endB'][0]:.3f} | {v['ret_A'][2]}")
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.2))
    col = {'md': '#0072B2', 'none': '#D55E00'}
    lab = {'md': 'MD gating (SOM on)', 'none': 'no gating (SOM off)'}
    for g in GATING:
        for a, k, t in ((ax[0], 'ret_A', "A's memory retained after B (ret_A)"),
                        (ax[1], 'discrim', 'context discriminability'),
                        (ax[2], 'sep_b0', 'branch-0 separation (A - B-only)')):
            m = [S[(g, f)][k][0] for f in OVERLAPS]; sd = [S[(g, f)][k][1] for f in OVERLAPS]
            a.errorbar(OVERLAPS, m, yerr=sd, marker='o', capsize=3, color=col[g], label=lab[g])
            a.set_title(t, fontsize=10); a.set_xlabel('input overlap f')
    ax[0].plot(OVERLAPS, [1 - f for f in OVERLAPS], ':', color='0.6', label='1 - f')
    ax[0].set_ylim(0, 1.1); ax[0].legend(frameon=False, fontsize=8)
    for a in ax:
        a.axhline(0, color='0.85', lw=1, zorder=0); a.spines[['top', 'right']].set_visible(False)
    fig.suptitle('Overlapping inputs: what MD branch gating buys (5 seeds, mean ± SD)', fontsize=11)
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'overlap_experiment.png')
    fig.savefig(fp, dpi=150, facecolor='white')
    print('saved', fp)
    return S


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(int(sys.argv[2]) if len(sys.argv) > 2 else 10)
    else:
        analyse()
