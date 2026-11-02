"""
alternation_experiment.py -- repeated A/B alternation with overlapping inputs
(plan: docs/reports/PLAN_alternation.md).

32 epochs (T = 3 s) alternating context A (MD_0, pattern A) and B (MD_1, pattern B) in blocks
of L epochs. MD gating x f {0,.25,.5,.75,1} x L {1,4} x seeds 42-46, plus a no-gating
control (f {0,.5,1}, L = 4). Fresh process per run.

Run:     <py> -I experiments/alternation_experiment.py run [n_workers]
Analyse: <py> -I experiments/alternation_experiment.py analyse
Out:     results/current/alternation_experiment.json, figures/alternation_experiment.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
OUT = os.path.join(PROOT, 'results', 'current', 'alternation_experiment.json')
OVERLAPS = [0.0, 0.25, 0.5, 0.75, 1.0]
SEEDS = [42, 43, 44, 45, 46]
BLOCKS = [1, 4]
N_TOT = 32


def schedule(L):
    return [(e // L) % 2 for e in range(N_TOT)]


def jobs():
    J = [('md', f, L, s) for f in OVERLAPS for L in BLOCKS for s in SEEDS]
    J += [('none', f, 4, s) for f in (0.0, 0.5, 1.0) for s in SEEDS]
    return J


def key(g, f, L, s):
    return f'{g}_f{f}_L{L}_s{s}'


def classes(A, B):
    A, B = np.asarray(A), np.asarray(B)
    return dict(Aonly=np.setdiff1d(A, B), shared=np.intersect1d(A, B), Bonly=np.setdiff1d(B, A))


def class_traj(r):
    """Mean rho per afferent class per branch per epoch; nan for empty classes."""
    C = classes(r['idx_A'], r['idx_B'])
    out = {}
    for b in (0, 1):
        R = np.array(r[f'rho{b}_syn'])          # epochs x afferents
        for c, ix in C.items():
            out[f'{c}_b{b}'] = (R[:, ix].mean(1) if len(ix) else np.full(len(R), np.nan)).tolist()
    return out


def _job(g, f, L, s):
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol
    from overlap_experiment import metrics
    t0 = time.time()
    sch = schedule(L)
    r = run_context_protocol(sch, T=3.0, input_mode='patterns', overlap=f,
                             inhibition=(g == 'md'), seed_val=s)
    tr = r['traj']
    rho0 = [t['rho0_syn'] for t in tr]; rho1 = [t['rho1_syn'] for t in tr]
    # per-epoch discriminability (metrics() needs rho at a reference "end of A"; reuse current)
    disc = [metrics(np.array(rho0[e]), np.array(rho1[e]), np.array(rho0[e]), np.array(rho1[e]),
                    r['idx_A'], r['idx_B'])['discrim'] for e in range(N_TOT)]
    return dict(gating=g, overlap=f, L=L, seed=s, schedule=sch, idx_A=r['idx_A'], idx_B=r['idx_B'],
                rho0_syn=rho0, rho1_syn=rho1, discrim=disc,
                som0=[t['som0_hz'] for t in tr], som1=[t['som1_hz'] for t in tr],
                wall_s=round(time.time() - t0, 1))


def run(nw):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    J = [j for j in jobs() if key(*j) not in done]
    print(f'{len(J)} jobs ({len(done)} done), {nw} workers', flush=True)
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(_job, *j): j for j in J}
        for fu in as_completed(futs):
            j = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                print(f'  {key(*j)}: ERROR {e!r}', flush=True); continue
            done[key(*j)] = r
            json.dump(done, open(OUT, 'w'))
            ends = [e for e in range(N_TOT) if e == N_TOT - 1 or r['schedule'][e + 1] != r['schedule'][e]]
            print(f"  {key(*j):<22} discrim at block ends: " +
                  ' '.join(f'{r["discrim"][e]:+.2f}' for e in ends[-4:]) + f"  ({r['wall_s']} s)", flush=True)
    print('done', flush=True)


def steady(r):
    """Steady-state numbers from the last cycle (last A block end, last B block end)."""
    sch = r['schedule']; L = r['L']
    eA = N_TOT - 1 - L          # last epoch of the final A block
    eB = N_TOT - 1              # last epoch of the final B block
    assert sch[eA] == 0 and sch[eB] == 1 and sch[eA + 1] == 1
    ct = class_traj(r)
    A, B = np.asarray(r['idx_A']), np.asarray(r['idx_B'])
    r0, r1 = np.array(r['rho0_syn']), np.array(r['rho1_syn'])
    return dict(
        shared_b0_endA=ct['shared_b0'][eA], shared_b0_endB=ct['shared_b0'][eB],
        shared_b1_endA=ct['shared_b1'][eA], shared_b1_endB=ct['shared_b1'][eB],
        Aonly_b0_endB=ct['Aonly_b0'][eB], Bonly_b1_endB=ct['Bonly_b1'][eB],
        ret_A=float(r0[eB, A].mean() / r0[eA, A].mean()),
        discrim_endA=r['discrim'][eA], discrim_endB=r['discrim'][eB],
        # per-pattern branch preference P_X = mean rho(X on its own branch) - mean rho(X on the
        # other branch). Shared afferents cancel in `discrim`, so it is blind to recency; P_A and
        # P_B are not (discrim = (P_A + P_B) / 2 at any instant).
        P_A_endA=float(r0[eA, A].mean() - r1[eA, A].mean()), P_B_endA=float(r1[eA, B].mean() - r0[eA, B].mean()),
        P_A_endB=float(r0[eB, A].mean() - r1[eB, A].mean()), P_B_endB=float(r1[eB, B].mean() - r0[eB, B].mean()),
        # convergence: shared_b0 at end of A blocks, cycle by cycle
        shared_b0_Aends=[ct['shared_b0'][e] for e in range(N_TOT)
                         if sch[e] == 0 and (e == N_TOT - 1 or sch[e + 1] == 1)],
    )


def analyse():
    d = json.load(open(OUT))
    conds = sorted({(r['gating'], r['overlap'], r['L']) for r in d.values()})
    keys = ['shared_b0_endA', 'shared_b0_endB', 'shared_b1_endA', 'shared_b1_endB',
            'Aonly_b0_endB', 'Bonly_b1_endB', 'ret_A', 'discrim_endA', 'discrim_endB',
            'P_A_endA', 'P_B_endA', 'P_A_endB', 'P_B_endB']
    S = {}
    print(f"{'g':<4} {'f':>4} {'L':>2} | shared b0 endA/endB | shared b1 endA/endB | Aonly_b0 | ret_A | "
          f"discrim endA / endB | P_A,P_B endA | P_A,P_B endB | shared_b0 at A-ends | n")
    for c in conds:
        rs = [steady(r) for r in d.values() if (r['gating'], r['overlap'], r['L']) == c]
        v = {k: (float(np.nanmean([x[k] for x in rs])), float(np.nanstd([x[k] for x in rs]))) for k in keys}
        ae = np.nanmean([x['shared_b0_Aends'] for x in rs], 0)
        S[c] = dict(v, shared_b0_Aends=ae.tolist(), n=len(rs))
        print(f"{c[0]:<4} {c[1]:>4} {c[2]:>2} | {v['shared_b0_endA'][0]:.3f} / {v['shared_b0_endB'][0]:.3f} | "
              f"{v['shared_b1_endA'][0]:.3f} / {v['shared_b1_endB'][0]:.3f} | {v['Aonly_b0_endB'][0]:.3f} | "
              f"{v['ret_A'][0]:.3f}±{v['ret_A'][1]:.3f} | {v['discrim_endA'][0]:+.3f} / {v['discrim_endB'][0]:+.3f} | "
              f"{v['P_A_endA'][0]:+.2f},{v['P_B_endA'][0]:+.2f} | {v['P_A_endB'][0]:+.2f},{v['P_B_endB'][0]:+.2f} | "
              + ' '.join(f'{a:.2f}' for a in ae[-6:]) + f" | {len(rs)}")
    json.dump({f'{g}_f{f}_L{L}': v for (g, f, L), v in S.items()},
              open(OUT.replace('.json', '_summary.json'), 'w'), indent=1)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 3, figsize=(15, 8))
    ep = np.arange(1, N_TOT + 1)
    # row 0: class trajectories for MD f = 0.5, L = 4 and L = 1, and no-gating f = 0.5
    for a, c, t in ((ax[0, 0], ('md', 0.5, 4), 'MD gating, f = 0.5, blocks of 4'),
                    (ax[0, 1], ('md', 0.5, 1), 'MD gating, f = 0.5, alternate every epoch'),
                    (ax[0, 2], ('none', 0.5, 4), 'no gating, f = 0.5, blocks of 4')):
        rs = [r for r in d.values() if (r['gating'], r['overlap'], r['L']) == c]
        if not rs:
            continue
        cts = [class_traj(r) for r in rs]
        sch = rs[0]['schedule']
        for e in range(N_TOT):
            if sch[e] == 1:
                a.axvspan(e + 0.5, e + 1.5, color='0.93', lw=0)
        for k, col, ls in (('Aonly_b0', '#0072B2', '-'), ('shared_b0', '#0072B2', '--'),
                           ('Bonly_b1', '#D55E00', '-'), ('shared_b1', '#D55E00', '--')):
            a.plot(ep, np.mean([x[k] for x in cts], 0), ls, color=col, label=k.replace('_', ' on '))
        a.set_ylim(0, 1.02); a.set_title(t, fontsize=10); a.set_xlabel('epoch (grey = context B)')
    ax[0, 0].set_ylabel('mean ρ'); ax[0, 0].legend(frameon=False, fontsize=8)
    # row 1: steady-state summaries vs f
    for L, ls in ((4, '-'), (1, ':')):
        cs = [('md', f, L) for f in OVERLAPS if ('md', f, L) in S]
        fs = [c[1] for c in cs]
        ax[1, 0].plot(fs, [S[c]['ret_A'][0] for c in cs], 'o' + ls, color='#0072B2', label=f'MD, L={L}')
        ax[1, 1].plot(fs, [S[c]['P_A_endA'][0] for c in cs], 'o' + ls, color='#0072B2', label=f'recent pattern (A after A), L={L}')
        ax[1, 1].plot(fs, [S[c]['P_B_endA'][0] for c in cs], 's' + ls, color='#CC79A7', label=f'older pattern (B after A), L={L}')
        ax[1, 2].plot(fs, [S[c]['shared_b0_endA'][0] for c in cs], 'o' + ls, color='#0072B2', label=f'end of A, L={L}')
        ax[1, 2].plot(fs, [S[c]['shared_b0_endB'][0] for c in cs], 's' + ls, color='#CC79A7', label=f'end of B, L={L}')
    cs = [c for c in S if c[0] == 'none']
    ax[1, 0].plot([c[1] for c in cs], [S[c]['ret_A'][0] for c in cs], 'o-', color='#D55E00', label='no gating')
    ax[1, 1].plot([c[1] for c in cs], [S[c]['P_A_endA'][0] for c in cs], 'o-', color='#D55E00', label='no gating')
    ax[1, 1].axhline(0, color='0.7', lw=1)
    ax[1, 0].set_title('steady-state retention of A across a B block', fontsize=10)
    ax[1, 1].set_title('branch preference of each pattern, end of A block\n(own branch − other branch, mean ρ)', fontsize=10)
    ax[1, 2].set_title('shared afferents on branch 0 (steady state)', fontsize=10)
    ax[1, 0].set_ylim(0, 1.1)
    for a in ax[1]:
        a.set_xlabel('input overlap f'); a.legend(frameon=False, fontsize=7)
    for a in ax.flat:
        a.spines[['top', 'right']].set_visible(False)
    fig.suptitle('Repeated A/B alternation (5 seeds, mean)', fontsize=11)
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'alternation_experiment.png')
    fig.savefig(fp, dpi=150, facecolor='white')
    print('saved', fp)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(int(sys.argv[2]) if len(sys.argv) > 2 else 10)
    else:
        analyse()
