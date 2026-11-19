"""
network_alternation.py -- step 4a (2026-11-12): the canonical alternation experiment
(experiments/alternation_experiment.py canonical) on the recurrent network of step 3
(model/network_circuit.py: 20 canonical cells, Zhang E->all recurrence at gain 0.35).

Protocol as the single cell: 32 x 3-s epochs at 50 Hz, alternating context A (pattern A,
MD_0) and B (pattern B, MD_1) in blocks of L epochs; patterns share a fraction f of their
afferents (all cells receive the same afferents). Recall at the end of the run: plasticity
frozen, READ protocol at 10 Hz (network_test.readout), per-cell S for pattern A and B,
averaged over cells; "current" = the pattern of the last block's context, "previous" = the
other one.
Conditions (seeds 42-46):
  amp       MD from the PFC<->MD loop, regime 'amp' (step 3b)  x f {0,.25,.5,.75,1} x L {1,4}
  poisson   fixed Poisson MD 25 / 0 Hz (step-3a network)        x f {0,.25,.5,.75,1} x L {1,4}
  none      no gating during learning (SOM -> dendrite 0 nS), Poisson MD, L = 4, f {0,.5,1};
            the readout is gated as for the other conditions (as in the single cell)
Single-cell reference (canonical, 10 seeds; PLAN_robustness.md), S current / previous:
  f      L = 1          L = 4
  0      0.94 / 0.95    0.94 / 0.95
  0.25   0.63 / 0.50    0.91 / 0.90
  0.5    0.28 / 0.12    0.82 / 0.11
  0.75   0.06 / -0.01   0.46 / -0.14
  1.0    0.02 / -0.05   0.10 / -0.16
  no gating ~0
Prediction (written before the run): at gain 0.35 each cell gates as the single cell (step 3,
100% gated, S_learn 0.93), and the amp loop switches within ~0.1 s, so the table is
reproduced within ~0.1 for f <= 0.25 and keeps its shape at higher f (current > previous,
L = 4 > L = 1; previous context lost from f = 0.5 with L = 4). amp = poisson within noise.
Possible network effect: with shared afferents every cell is driven by the same pattern, so
recurrence adds a common signal; if it changes anything it should raise E in the shared
afferents' epochs, not the branch assignment.
Result (2026-11-12, 115 runs on toothless, ~19 min each):
  - Prediction holds for f <= 0.5: network = single cell within ~0.05 (L = 1 and 4), e.g. f = 0.25,
    L = 4: 0.92 / 0.92 (single cell 0.91 / 0.90); f = 0.5, L = 4: 0.85 / 0.08 (0.82 / 0.11).
    amp loop = fixed Poisson MD within 0.01 everywhere. No gating: S 0.01-0.03. E 12-17 Hz.
  - New at high overlap with L = 4: the network is MORE recency-biased than the single cell.
    f = 0.75: 0.68 / -0.15 (single cell 0.46 / -0.14); f = 1: 0.41 / -0.41 (0.10 / -0.16). The
    shared afferents swing fully to the latest context's branch each block (shared on branch 0:
    0.93 at the end of A, 0.54 at the end of B, f = 1). Not separated: learning input rate
    (50 Hz here, 80 Hz in the single-cell runs), recurrence, and averaging S over 20 cells.
  - Conclusion unchanged: both contexts are recalled only for f <= 0.25 with 12-s blocks.
Run:     <py> -I experiments/network_alternation.py run [n_workers]
Analyse: <py> -I experiments/network_alternation.py analyse
Out:     results/current/network_alternation.json, _summary.json, figures/network_alternation.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
OUT = os.path.join(PROOT, 'results', 'current', 'network_alternation.json')
SEEDS = [42, 43, 44, 45, 46]
OVERLAPS = [0.0, 0.25, 0.5, 0.75, 1.0]
BLOCKS = [1, 4]
N_TOT = 32
REC_GAIN = 0.35
SINGLE_CELL = {  # canonical single cell, S current / previous (L1, L4)
    0.0: ((0.94, 0.95), (0.94, 0.95)), 0.25: ((0.63, 0.50), (0.91, 0.90)), 0.5: ((0.28, 0.12), (0.82, 0.11)),
    0.75: ((0.06, -0.01), (0.46, -0.14)), 1.0: ((0.02, -0.05), (0.10, -0.16))}


def schedule(L):
    return [(e // L) % 2 for e in range(N_TOT)]


def jobs():
    J = [(g, f, L, s) for g in ('amp', 'poisson') for f in OVERLAPS for L in BLOCKS for s in SEEDS]
    J += [('none', f, 4, s) for f in (0.0, 0.5, 1.0) for s in SEEDS]
    return J


def key(g, f, L, s):
    return f'{g}_f{f}_L{L}_s{s}'


def net_kw(g, f):
    """Network keywords shared by learning and readout (readout is always gated)."""
    kw = dict(rec_gain=REC_GAIN, overlap=f)
    if g == 'amp':
        kw['md_loop'] = dict(regime='amp')
    return kw


def S_cells(R):
    """Per-cell (S_A, S_B) from the six READ epochs; R: (6, N_E) rates."""
    from network_test import READ
    out = []
    for c in range(R.shape[1]):
        rates = R[:, c]
        base = {0: rates[0], 1: rates[1]}
        r = {(cx, s): max(rates[i] - base[cx], 0.0) for i, (cx, s) in enumerate(READ) if s is not None}
        S = []
        for k in (0, 1):
            on, off = r[(k, k)], r[(1 - k, k)]
            S.append((on - off) / (on + off) if on + off > 0 else np.nan)
        out.append(S)
    return np.array(out)


def _job(g, f, L, s):
    from brian2 import prefs, nS
    prefs.codegen.target = 'cython'
    from network_circuit import run_network_protocol
    from network_test import READ
    t0 = time.time()
    sch = schedule(L)
    kw = net_kw(g, f)
    lkw = dict(kw)
    if g == 'none':
        lkw['param_overrides'] = {'gGABA': 0 * nS}
    lt = run_network_protocol(sch, T=3.0, exc_rate=50.0, seed_val=s, **lkw)
    tr = lt['traj']
    A, B = np.array(lt['idx_A']), np.array(lt['idx_B'])
    C = dict(Aonly=np.setdiff1d(A, B), shared=np.intersect1d(A, B), Bonly=np.setdiff1d(B, A), A=A, B=B)
    ep = {}
    for b in (0, 1):
        for c, ix in C.items():
            ep[f'{c}_b{b}'] = [float(np.array(t[f'rho{b}_syn'])[:, ix].mean()) if len(ix) else float('nan') for t in tr]
    for k in ('md0_hz', 'md1_hz', 'som0_hz', 'som1_hz', 'vip0_hz', 'vip1_hz', 'pv_hz', 'pyr_hz'):
        ep[k] = [t[k] for t in tr]
    # per-cell branch preference at the end of the run
    r0, r1 = np.array(tr[-1]['rho0_syn']), np.array(tr[-1]['rho1_syn'])
    P_A_cells = (r0[:, A].mean(1) - r1[:, A].mean(1)).tolist()
    P_B_cells = (r1[:, B].mean(1) - r0[:, B].mean(1)).tolist()
    # recall readout at the end (gated, plasticity frozen, 10 Hz)
    rd = run_network_protocol([c for c, _ in READ], T=5.0, stim=[x for _, x in READ], plastic=False,
                              rho_init_syn=(r0, r1), exc_rate=10.0, seed_val=s, **kw)
    R = np.array([t['pyr_hz_cells'] for t in rd['traj']])
    SC = S_cells(R)
    last = sch[-1]
    return dict(gating=g, overlap=f, L=L, seed=s, schedule=sch, ep=ep, P_A_cells=P_A_cells, P_B_cells=P_B_cells,
                S_A_cells=SC[:, 0].tolist(), S_B_cells=SC[:, 1].tolist(),
                S_A=float(np.nanmean(SC[:, 0])), S_B=float(np.nanmean(SC[:, 1])),
                S_current=float(np.nanmean(SC[:, last])), S_previous=float(np.nanmean(SC[:, 1 - last])),
                end_ctx=int(last), read_rates=R.mean(1).tolist(), wall_s=round(time.time() - t0, 1))


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
            e = r['ep']
            print(f"  {key(*j):<22} S cur/prev {r['S_current']:+.2f}/{r['S_previous']:+.2f}  "
                  f"MD {np.mean(e['md0_hz']):4.1f}/{np.mean(e['md1_hz']):4.1f}  E {np.mean(e['pyr_hz']):4.1f} Hz  "
                  f"({r['wall_s']} s)", flush=True)
    print('done', flush=True)


def steady(r):
    """Numbers from the last cycle: end of the final A block (eA) and of the final B block (eB)."""
    e, L = r['ep'], r['L']
    eA, eB = N_TOT - 1 - L, N_TOT - 1
    return dict(
        shared_b0_endA=e['shared_b0'][eA], shared_b0_endB=e['shared_b0'][eB],
        ret_A=e['A_b0'][eB] / e['A_b0'][eA],
        P_A_endA=e['A_b0'][eA] - e['A_b1'][eA], P_B_endA=e['B_b1'][eA] - e['B_b0'][eA],
        P_A_endB=e['A_b0'][eB] - e['A_b1'][eB], P_B_endB=e['B_b1'][eB] - e['B_b0'][eB],
        S_current=r['S_current'], S_previous=r['S_previous'],
        E_hz=float(np.mean(e['pyr_hz'])), md_on=float(np.mean([e[f'md{c}_hz'][i] for i, c in enumerate(r['schedule'])])),
        md_off=float(np.mean([e[f'md{1 - c}_hz'][i] for i, c in enumerate(r['schedule'])])),
        som_off=float(np.mean([e[f'som{1 - c}_hz'][i] for i, c in enumerate(r['schedule'])])),
        frac_cells_both=float(np.mean((np.array(r['P_A_cells']) > 0.2) & (np.array(r['P_B_cells']) > 0.2))))


KEYS = ['S_current', 'S_previous', 'ret_A', 'P_A_endA', 'P_B_endA', 'P_A_endB', 'P_B_endB',
        'shared_b0_endA', 'shared_b0_endB', 'E_hz', 'md_on', 'md_off', 'som_off', 'frac_cells_both']


def analyse():
    d = json.load(open(OUT))
    conds = sorted({(r['gating'], r['overlap'], r['L']) for r in d.values()})
    S = {}
    print(f"{'g':<8} {'f':>4} {'L':>2} | S current      | S previous     | single cell cur/prev | ret_A | "
          f"P_A,P_B endB | shared_b0 endA/endB | E Hz | MD on/off | n")
    for c in conds:
        rs = [steady(r) for r in d.values() if (r['gating'], r['overlap'], r['L']) == c]
        v = {k: (float(np.nanmean([x[k] for x in rs])), float(np.nanstd([x[k] for x in rs]))) for k in KEYS}
        S[c] = dict(v, n=len(rs))
        sc = SINGLE_CELL.get(c[1], ((np.nan,) * 2,) * 2)[0 if c[2] == 1 else 1] if c[0] != 'none' else (np.nan, np.nan)
        print(f"{c[0]:<8} {c[1]:>4} {c[2]:>2} | {v['S_current'][0]:+.2f}±{v['S_current'][1]:.2f} | "
              f"{v['S_previous'][0]:+.2f}±{v['S_previous'][1]:.2f} | {sc[0]:+.2f} / {sc[1]:+.2f} | "
              f"{v['ret_A'][0]:.3f} | {v['P_A_endB'][0]:+.2f},{v['P_B_endB'][0]:+.2f} | "
              f"{v['shared_b0_endA'][0]:.3f} / {v['shared_b0_endB'][0]:.3f} | {v['E_hz'][0]:4.1f} | "
              f"{v['md_on'][0]:4.1f}/{v['md_off'][0]:4.1f} | {len(rs)}")
    json.dump({f'{g}_f{f}_L{L}': v for (g, f, L), v in S.items()},
              open(OUT.replace('.json', '_summary.json'), 'w'), indent=1)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
    sty = {'amp': ('#0072B2', 'o'), 'poisson': ('#009E73', 's')}
    for i, L in enumerate(BLOCKS):
        a = ax[i]
        for g, (col, mk) in sty.items():
            cs = [(g, f, L) for f in OVERLAPS if (g, f, L) in S]
            fs = [x[1] for x in cs]
            a.errorbar(fs, [S[x]['S_current'][0] for x in cs], [S[x]['S_current'][1] for x in cs], fmt=mk + '-',
                       color=col, capsize=2, label=f'network, {g}: current')
            a.errorbar(fs, [S[x]['S_previous'][0] for x in cs], [S[x]['S_previous'][1] for x in cs], fmt=mk + '--',
                       color=col, capsize=2, alpha=0.7, label=f'network, {g}: previous')
        a.plot(OVERLAPS, [SINGLE_CELL[f][i][0] for f in OVERLAPS], 'k-', lw=1, label='single cell: current')
        a.plot(OVERLAPS, [SINGLE_CELL[f][i][1] for f in OVERLAPS], 'k--', lw=1, label='single cell: previous')
        if L == 4:
            cs = [c for c in S if c[0] == 'none']
            a.plot([c[1] for c in cs], [S[c]['S_current'][0] for c in cs], 'x:', color='#D55E00', label='no gating: current')
        a.axhline(0, color='0.8', lw=0.8)
        a.set_ylim(-0.5, 1.05); a.set_xlabel('input overlap f'); a.set_ylabel('recall S at end of run')
        a.set_title(f'blocks of L = {L} epoch' + ('s' if L > 1 else ''), fontsize=10)
        a.legend(frameon=False, fontsize=6.5, loc='upper right' if L == 1 else 'center left')
    rs = [r for r in d.values() if (r['gating'], r['overlap'], r['L']) == ('amp', 0.5, 4)]
    if rs:
        a = ax[2]; ep = np.arange(1, N_TOT + 1); sch = rs[0]['schedule']
        for e in range(N_TOT):
            if sch[e] == 1:
                a.axvspan(e + 0.5, e + 1.5, color='0.93', lw=0)
        for k, col, ls in (('Aonly_b0', '#0072B2', '-'), ('shared_b0', '#0072B2', '--'),
                           ('Bonly_b1', '#D55E00', '-'), ('shared_b1', '#D55E00', '--')):
            a.plot(ep, np.mean([r['ep'][k] for r in rs], 0), ls, color=col, label=k.replace('_', ' on '))
        a.set_ylim(0, 1.02); a.set_xlabel('epoch (grey = context B)'); a.set_ylabel('mean ρ (cells, afferents)')
        a.set_title('network, amp loop, f = 0.5, L = 4', fontsize=10); a.legend(frameon=False, fontsize=7)
    for a in ax:
        a.spines[['top', 'right']].set_visible(False)
    fig.suptitle(f'A/B alternation on the 20-cell network (recurrence gain {REC_GAIN}), 5 seeds', fontsize=11)
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'network_alternation.png')
    fig.savefig(fp, dpi=140, facecolor='white')
    print('saved', fp)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(int(sys.argv[2]) if len(sys.argv) > 2 else 38)
    else:
        analyse()
