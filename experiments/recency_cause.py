"""
recency_cause.py -- why is the network more recency-biased than the single cell at high
overlap? (2026-11-19, step 2; open point of step 4a, PLAN_robustness.md.)

Step 4a (network_alternation.py, L = 4): at f = 1 the network gives S current / previous
0.41 / -0.41, the single cell 0.10 / -0.16. Three differences were not separated:
  (1) learning input rate: network 50 Hz, single cell 80 Hz;
  (2) recurrence (gain 0.35) and the PFC<->MD loop;
  (3) S averaged over 20 cells of one network vs over seeds of single cells.
Design: L = 4 (12-s blocks), 5 seeds (42-46), readout as in each reference run.
  cell50   single cell, learning at 50 Hz        f {0, .25, .5, .75, 1}   (vs cell at 80 Hz:
           alternation_experiment_canonical.json, same seeds)
  net0     network at recurrence gain 0, amp loop, 50 Hz   f {.25, .5, .75, 1}
  net80    network at gain 0.35, amp loop, learning at 80 Hz   f {.5, .75, 1}
           (vs network at 50 Hz: network_alternation.json)
Reading the result:
  cell50 ~ network(50 Hz)                 -> the learning rate explains it;
  net0 ~ network(gain 0.35)               -> recurrence/loop do not; if also ~ cell50 then the
                                             20-cell average does not either;
  net80 ~ cell at 80 Hz                   -> confirms the rate.
Prediction (written before running): recurrence is minor (net0 ~ network at gain 0.35),
because step 3a found that gain 0.35 leaves single-cell learning intact. The gap then follows
the learning rate or the cell average. We have no confident prediction for the direction of
the rate effect: less drive per epoch at 50 Hz could make the shared afferents swing less, not
more.
Run:     <py> -I experiments/recency_cause.py run [n_workers]
Analyse: <py> -I experiments/recency_cause.py analyse
Out:     results/current/recency_cause{,_summary}.json, figures/recency_cause.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
OUT = os.path.join(PROOT, 'results', 'current', 'recency_cause.json')
SEEDS = [42, 43, 44, 45, 46]
L, N_TOT = 4, 32
OV = {'cell50': [0.0, 0.25, 0.5, 0.75, 1.0], 'net0': [0.25, 0.5, 0.75, 1.0], 'net80': [0.5, 0.75, 1.0]}


def schedule():
    return [(e // L) % 2 for e in range(N_TOT)]


def _job(cond, f, s):
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    t0 = time.time()
    sch = schedule()
    last = sch[-1]
    if cond == 'cell50':
        from context_circuit import run_context_protocol
        from readout import readout_S
        r = run_context_protocol(sch, T=3.0, input_mode='patterns', overlap=f, exc_rate=50.0, seed_val=s)
        tr = r['traj']
        ro = readout_S(tr[-1]['rho0_syn'], tr[-1]['rho1_syn'], f, s)
        A, B = np.array(r['idx_A']), np.array(r['idx_B'])
        sh = np.intersect1d(A, B)
        shared_b0 = [float(np.array(t['rho0_syn'])[sh].mean()) if len(sh) else float('nan') for t in tr]
        out = dict(S_current=ro['S_A' if last == 0 else 'S_B'], S_previous=ro['S_B' if last == 0 else 'S_A'],
                   shared_b0=shared_b0, rates=ro['rates'])
    else:
        from network_circuit import run_network_protocol
        from network_test import READ
        from network_alternation import S_cells
        gain = 0.0 if cond == 'net0' else 0.35
        rate = 50.0 if cond == 'net0' else 80.0
        kw = dict(rec_gain=gain, overlap=f, md_loop=dict(regime='amp'))
        lt = run_network_protocol(sch, T=3.0, exc_rate=rate, seed_val=s, **kw)
        tr = lt['traj']
        A, B = np.array(lt['idx_A']), np.array(lt['idx_B'])
        sh = np.intersect1d(A, B)
        shared_b0 = [float(np.array(t['rho0_syn'])[:, sh].mean()) if len(sh) else float('nan') for t in tr]
        r0, r1 = np.array(tr[-1]['rho0_syn']), np.array(tr[-1]['rho1_syn'])
        rd = run_network_protocol([c for c, _ in READ], T=5.0, stim=[x for _, x in READ], plastic=False,
                                  rho_init_syn=(r0, r1), exc_rate=10.0, seed_val=s, **kw)
        R = np.array([t['pyr_hz_cells'] for t in rd['traj']])
        SC = S_cells(R)
        out = dict(S_current=float(np.nanmean(SC[:, last])), S_previous=float(np.nanmean(SC[:, 1 - last])),
                   S_current_cells=SC[:, last].tolist(), S_previous_cells=SC[:, 1 - last].tolist(),
                   shared_b0=shared_b0, pyr_hz=[t['pyr_hz'] for t in tr])
    return dict(cond=cond, overlap=f, seed=s, wall_s=round(time.time() - t0, 1), **out)


def key(c, f, s):
    return f'{c}_f{f}_s{s}'


def run(nw):
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    # network jobs first (slower)
    J = [(c, f, s) for c in ('net80', 'net0', 'cell50') for f in OV[c] for s in SEEDS]
    J = [j for j in J if key(*j) not in done]
    print(f'{len(J)} jobs ({len(done)} done), {nw} workers', flush=True)
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(_job, *j): j for j in J}
        for fu in as_completed(futs):
            j = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                print(key(*j), 'ERROR', repr(e), flush=True); continue
            done[key(*j)] = r
            json.dump(done, open(OUT, 'w'))
            print(f"{key(*j):<18} S cur {r['S_current']:+.2f} prev {r['S_previous']:+.2f} ({r['wall_s']} s)", flush=True)
    print('done', flush=True)


def _ref():
    """Reference runs, same seeds and L = 4: single cell at 80 Hz, network at 50 Hz (gain 0.35, amp)."""
    ref = {}
    cell = json.load(open(os.path.join(PROOT, 'results', 'current', 'alternation_experiment_canonical.json')))
    for f in OV['cell50']:
        rs = [r for r in cell.values() if r['gating'] == 'md' and r['overlap'] == f and r['L'] == L
              and r['seed'] in SEEDS and 'readout_end' in r]
        cur = [r['readout_end']['S_A' if r['readout_end_ctx'] == 0 else 'S_B'] for r in rs]
        prv = [r['readout_end']['S_B' if r['readout_end_ctx'] == 0 else 'S_A'] for r in rs]
        ref[f'cell80_f{f}'] = dict(S_current=float(np.nanmean(cur)), S_previous=float(np.nanmean(prv)),
                                   S_current_sd=float(np.nanstd(cur)), S_previous_sd=float(np.nanstd(prv)), n=len(rs))
    net = json.load(open(os.path.join(PROOT, 'results', 'current', 'network_alternation.json')))
    for f in OV['cell50']:
        rs = [r for r in net.values() if r['gating'] == 'amp' and r['overlap'] == f and r['L'] == L]
        ref[f'net50_f{f}'] = dict(S_current=float(np.mean([r['S_current'] for r in rs])),
                                  S_previous=float(np.mean([r['S_previous'] for r in rs])),
                                  S_current_sd=float(np.std([r['S_current'] for r in rs])),
                                  S_previous_sd=float(np.std([r['S_previous'] for r in rs])), n=len(rs))
    return ref


def analyse():
    d = json.load(open(OUT))
    rows = _ref()
    for c in OV:
        for f in OV[c]:
            rs = [r for r in d.values() if r['cond'] == c and r['overlap'] == f]
            if rs:
                rows[f'{c}_f{f}'] = dict(S_current=float(np.nanmean([r['S_current'] for r in rs])),
                                         S_previous=float(np.nanmean([r['S_previous'] for r in rs])),
                                         S_current_sd=float(np.nanstd([r['S_current'] for r in rs])),
                                         S_previous_sd=float(np.nanstd([r['S_previous'] for r in rs])), n=len(rs))
    conds = [('cell80', 'single cell, 80 Hz learning'), ('cell50', 'single cell, 50 Hz'),
             ('net50', 'network gain 0.35, 50 Hz (step 4a)'), ('net0', 'network gain 0, 50 Hz'),
             ('net80', 'network gain 0.35, 80 Hz')]
    print('S current / previous, L = 4')
    print(f"{'f':>5} | " + ' | '.join(f'{c:>13}' for c, _ in conds))
    for f in OV['cell50']:
        cells = []
        for c, _ in conds:
            r = rows.get(f'{c}_f{f}')
            cells.append(f"{r['S_current']:+.2f}/{r['S_previous']:+.2f}" if r else '      -      ')
        print(f'{f:>5} | ' + ' | '.join(f'{x:>13}' for x in cells))
    json.dump(rows, open(OUT.replace('.json', '_summary.json'), 'w'), indent=1)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    sty = {'cell80': ('#555555', 'o', '-'), 'cell50': ('#555555', 's', '--'), 'net50': ('#0B62A4', 'o', '-'),
           'net0': ('#0B62A4', 'D', ':'), 'net80': ('#C2510B', 's', '--')}
    for a, m, t in ((ax[0], 'S_current', 'current context'), (ax[1], 'S_previous', 'previous context')):
        for c, lab in conds:
            fs = [f for f in OV['cell50'] if f'{c}_f{f}' in rows]
            col, mk, ls = sty[c]
            a.errorbar(fs, [rows[f'{c}_f{f}'][m] for f in fs], yerr=[rows[f'{c}_f{f}'][m + '_sd'] for f in fs],
                       color=col, marker=mk, ls=ls, lw=1.8, capsize=2, label=lab)
        a.axhline(0, color='0.85', lw=1); a.axhline(0.5, color='0.7', ls='--', lw=1)
        a.set(xlabel='overlap f', title=f'Recall of the {t} (12-s blocks)', xticks=OV['cell50'])
        a.spines[['top', 'right']].set_visible(False)
    ax[0].set_ylabel('recall S at the end of the run')
    ax[1].legend(fontsize=8, frameon=False, loc='lower left')
    fig.suptitle('What makes the network more recency-biased? learning rate vs recurrence (5 seeds, mean ± sd)', fontsize=11)
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'recency_cause.png')
    fig.savefig(fp, dpi=150, facecolor='white'); print('saved', fp)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(int(sys.argv[2]) if len(sys.argv) > 2 else 38)
    else:
        analyse()
