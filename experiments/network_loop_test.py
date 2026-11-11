"""
network_loop_test.py -- step 3b (2026-11-11): the MD context signal produced by a PFC <-> MD
loop (model/md_loop.py) instead of fixed Poisson rates, in the step-3a network
(model/network_circuit.py, 20 canonical cells, Zhang E->all recurrence at gain 0.35).

Protocol and measures as network_test.py: learn A 8 x 3 s then B 8 x 3 s at 50 Hz; after A:
rho_free, rho_inh, fraction of cells gated; ret_A; frozen 10 Hz readout -> S_learn; plus the
MD rate of each channel in each phase (own = the cued context's channel).
Conditions (5 seeds):
  poisson            fixed Poisson MD 25 / 0 Hz (step-3a reference at gain 0.35)
  amp                loop amplifies a held context cue (loop gain 0.4)
  persist            self-sustained loop (gain 2), cue only for the first 0.5 s of each epoch
  persist_weakcomp   self-sustained loop with gain 3, competition too weak for it
  amp_em_w           amp + feedback of the plastic E cells' rate to BOTH MD channels, w_em = w
  persist_em_w       persist + the same feedback
  amp_cross_x        amp, a fraction x of the loop drive reaches the other channel
  persist_cross_x    persist, the same
Prediction (written before the network runs, from the standalone loop, md_loop.loop_steady):
  - amp and persist reproduce the poisson result (MD 25 / 0 Hz, switches with the cue).
  - persist_weakcomp keeps both MD channels on after the first switch to B: B is learned on
    both branches (A's branch 0 is disinhibited during B), so A's branch-0 memory stays but
    B's synapses also potentiate on branch 0 and the readout of B loses selectivity.
  - E->MD feedback is not context-specific: at E ~ 11 Hz the OFF channel gets M = w_em * r_E
    (amp; 0.25 -> ~3 Hz, 0.5 -> ~5.5 Hz, 1 -> ~11 Hz). From step 1, MD->VIP spill-over of
    ~25% of the ON drive breaks gating, so amp fails from w_em ~ 0.5. In persist the OFF
    loop ignites (both channels at 25 Hz) from w_em ~ 1.
  - Loop cross-talk: amp degrades gradually (10%: 21 / 2 Hz); persist collapses after the
    cue (the self-sustained state needs a specific loop): MD 0 / 0 for most of each epoch,
    so learning slows sharply.
Result (2026-11-11):
  - amp and persist match Poisson MD (S_learn 0.93 / 0.92).
  - persist_weakcomp: MD 25 / 25 in B, S_learn -0.03.
  - amp + E->MD passes up to w_em 1 (OFF MD 6 Hz; the prediction said it fails from 0.5).
  - persist + E->MD: 0.5 is partial (2/5 seeds re-ignite the old loop); 1 fails (both loops on).
  - Cross-talk: amp passes to 0.1 and gives 87% gated at 0.25; persist passes at 0.05 and
    collapses at 0.1 (ON MD 7 Hz).
  - ret_A 1.000 everywhere.
Run:     <py> -I experiments/network_loop_test.py run [n_workers]
Analyse: <py> -I experiments/network_loop_test.py analyse
Out:     results/current/network_loop_test.json, _summary.json, figures/network_loop_test.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
OUT = os.path.join(PROOT, 'results', 'current', 'network_loop_test.json')
SEEDS = [42, 43, 44, 45, 46]
REC_GAIN = 0.35
N_EP = 8
W_EM = [0.1, 0.25, 0.5, 1.0]
CROSS = [0.05, 0.1, 0.25]


def conditions():
    P = dict(regime='persist', cue_s=0.5)
    C = {'poisson': None, 'amp': dict(regime='amp'), 'persist': P,
         'persist_weakcomp': dict(regime='persist_weakcomp', cue_s=0.5)}
    for w in W_EM:
        C[f'amp_em_{w}'] = dict(regime='amp', w_em=w)
        C[f'persist_em_{w}'] = dict(P, w_em=w)
    for x in CROSS:
        C[f'amp_cross_{x}'] = dict(regime='amp', loop_cross=x)
        C[f'persist_cross_{x}'] = dict(P, loop_cross=x)
    return C


def _job(name, seed):
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    from network_circuit import run_network_protocol
    from network_test import readout
    t0 = time.time()
    kw = dict(rec_gain=REC_GAIN, md_loop=conditions()[name])
    out = dict(cond=name, seed=seed)
    lt = run_network_protocol([0] * N_EP + [1] * N_EP, T=3.0, exc_rate=50.0, seed_val=seed, **kw)
    tr = lt['traj']; iA = np.array(lt['idx_A']); iB = np.array(lt['idx_B'])
    a, b = tr[N_EP - 1], tr[-1]
    f0 = np.array(a['rho0_syn'])[:, iA].mean(1); f1 = np.array(a['rho1_syn'])[:, iA].mean(1)
    out['rho_free'], out['rho_inh'] = float(f0.mean()), float(f1.mean())
    out['frac_gated'] = float(np.mean((f0 > 0.65) & (f1 < 0.5)))
    out['ret_A'] = float(np.array(b['rho0_syn'])[:, iA].mean() / f0.mean())
    out['rhoB_b0'] = float(np.array(b['rho0_syn'])[:, iB].mean())   # B's synapses on A's branch
    out['rhoB_b1'] = float(np.array(b['rho1_syn'])[:, iB].mean())
    for ph, sl, own in (('A', tr[:N_EP], 0), ('B', tr[N_EP:], 1)):
        out[f'md_own_{ph}'] = float(np.mean([t[f'md{own}_hz'] for t in sl]))
        out[f'md_other_{ph}'] = float(np.mean([t[f'md{1 - own}_hz'] for t in sl]))
        out[f'som_own_{ph}'] = float(np.mean([t[f'som{own}_hz'] for t in sl]))
        out[f'som_other_{ph}'] = float(np.mean([t[f'som{1 - own}_hz'] for t in sl]))
    out['E_hz'] = float(np.mean([t['pyr_hz'] for t in tr[:N_EP]]))
    out['S_learn'], out['read_rates'] = readout(kw, seed, (b['rho0_syn'], b['rho1_syn']))
    out['wall_s'] = round(time.time() - t0, 1)
    return out


def run(nw):
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    J = [(c, s) for c in conditions() for s in SEEDS if f'{c}_s{s}' not in done]
    print(f'{len(J)} jobs ({len(done)} done), {nw} workers', flush=True)
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(_job, *j): j for j in J}
        for fu in as_completed(futs):
            j = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                print(j, 'ERROR', repr(e), flush=True); continue
            done[f'{j[0]}_s{j[1]}'] = r
            json.dump(done, open(OUT, 'w'))
            print(f"{j[0]:<18} s{j[1]} free {r['rho_free']:.3f} inh {r['rho_inh']:.3f} gated {r['frac_gated']:.2f} "
                  f"MD A {r['md_own_A']:4.1f}/{r['md_other_A']:4.1f} B {r['md_own_B']:4.1f}/{r['md_other_B']:4.1f} "
                  f"rhoB b0/b1 {r['rhoB_b0']:.3f}/{r['rhoB_b1']:.3f} E {r['E_hz']:4.1f} S_learn {r['S_learn']:+.2f} "
                  f"ret_A {r['ret_A']:.3f} ({r['wall_s']} s)", flush=True)
    print('done', flush=True)


KEYS = ['rho_free', 'rho_inh', 'frac_gated', 'ret_A', 'rhoB_b0', 'rhoB_b1', 'md_own_A', 'md_other_A',
        'md_own_B', 'md_other_B', 'som_own_A', 'som_other_A', 'E_hz', 'S_learn']


def analyse():
    d = json.load(open(OUT))
    rows = {}
    for c in conditions():
        rs = [r for r in d.values() if r['cond'] == c]
        if not rs:
            continue
        row = {k: float(np.nanmean([r[k] for r in rs])) for k in KEYS}
        row['S_learn_sd'] = float(np.nanstd([r['S_learn'] for r in rs])); row['n'] = len(rs)
        row['pass'] = bool(row['frac_gated'] >= 0.9 and row['S_learn'] > 0.5)
        rows[c] = row
    json.dump(rows, open(OUT.replace('.json', '_summary.json'), 'w'), indent=1)
    print(f"{'condition':<18} | free   inh  gated | MD A own/oth  B own/oth | SOM A own/oth | rhoB b0/b1  | E    | S_learn    | ret_A | pass")
    for c, r in rows.items():
        print(f"{c:<18} | {r['rho_free']:.3f} {r['rho_inh']:.3f} {r['frac_gated']:.2f} | {r['md_own_A']:4.1f}/{r['md_other_A']:4.1f} "
              f"{r['md_own_B']:4.1f}/{r['md_other_B']:4.1f} | {r['som_own_A']:4.1f}/{r['som_other_A']:4.1f} | "
              f"{r['rhoB_b0']:.3f}/{r['rhoB_b1']:.3f} | {r['E_hz']:4.1f} | {r['S_learn']:+.2f}±{r['S_learn_sd']:.2f} | "
              f"{r['ret_A']:.3f} | {'Y' if r['pass'] else '.'}")
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.2))
    base = [c for c in ('poisson', 'amp', 'persist', 'persist_weakcomp') if c in rows]
    x = np.arange(len(base))
    axs[0].bar(x - 0.2, [rows[c]['S_learn'] for c in base], 0.4, label='S after learning')
    axs[0].bar(x + 0.2, [rows[c]['frac_gated'] for c in base], 0.4, label='fraction of cells gated')
    axs[0].set_xticks(x); axs[0].set_xticklabels(base, fontsize=8); axs[0].axhline(0.5, color='grey', lw=0.6, ls=':')
    axs[0].set_title('MD source'); axs[0].legend(fontsize=7)
    for reg, mk in (('amp', 'o-'), ('persist', 's-')):
        ws = [w for w in W_EM if f'{reg}_em_{w}' in rows]
        axs[1].plot([0] + ws, [rows[reg]['S_learn']] + [rows[f'{reg}_em_{w}']['S_learn'] for w in ws], mk, label=f'{reg}: S_learn')
        axs[1].plot([0] + ws, [rows[reg]['md_other_A'] / 25] + [rows[f'{reg}_em_{w}']['md_other_A'] / 25 for w in ws],
                    mk.replace('-', '--'), alpha=0.6, label=f'{reg}: OFF-channel MD / 25 Hz')
        xs = [v for v in CROSS if f'{reg}_cross_{v}' in rows]
        axs[2].plot([0] + xs, [rows[reg]['S_learn']] + [rows[f'{reg}_cross_{v}']['S_learn'] for v in xs], mk, label=f'{reg}: S_learn')
        axs[2].plot([0] + xs, [rows[reg]['md_own_A'] / 25] + [rows[f'{reg}_cross_{v}']['md_own_A'] / 25 for v in xs],
                    mk.replace('-', '--'), alpha=0.6, label=f'{reg}: ON-channel MD / 25 Hz')
    axs[1].set_xlabel('E → MD feedback weight (both channels)'); axs[1].set_title('non-specific PFC → MD feedback')
    axs[2].set_xlabel('loop cross-talk fraction'); axs[2].set_title('PFC ↔ MD loop specificity')
    for ax in axs[1:]:
        ax.axhline(0.5, color='grey', lw=0.6, ls=':'); ax.legend(fontsize=7)
    fig.suptitle('Step 3b: MD from a PFC↔MD loop (20-cell network, recurrence gain 0.35), 5 seeds')
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'network_loop_test.png')
    fig.savefig(fp, dpi=130); print('saved', fp)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(int(sys.argv[2]) if len(sys.argv) > 2 else 11)
    else:
        analyse()
