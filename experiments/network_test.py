"""
network_test.py -- step 3a (2026-11-10): does MD-gated, branch-specific learning survive in a
small recurrent network with Zhang 2025's E -> {E, SOM, VIP, PV} recurrence?
Model: model/network_circuit.py (N_E = 20 canonical cells, shared canonical interneurons).

Per condition and seed (42-46):
  learn   'patterns' mode, overlap 0: A in context A for 8 x 3 s, then B in context B
          8 x 3 s, at 50 Hz, plastic. After A (mean over cells, A's synapses):
          rho_free (branch 0), rho_inh (branch 1), fraction of cells gated
          (free > 0.65, inh < 0.5); after B: ret_A (A's branch-0 rho after B / after A).
          Rates over phase A: E mean / max cell, SOM own/other, VIP own/other, PV.
  readout plasticity frozen, Yang's READ protocol at 10 Hz/synapse (as R4):
          S_learn (mean of per-cell S) after learning, S_before with rho = 1/3.
Conditions: all recurrence x rec_gain {0, 0.05, 0.1, 0.2, 0.35, 0.5, 1}; one pathway at a
time (E->E, E->SOM, E->VIP, E->PV) x {0.25, 0.5, 1}. Gain 1 = REC_REF in network_circuit.

Smoke test (before the sweep, seed 42, 4 epochs of A): gain 0 gates like the single cell
(free 0.924, inh 0.333, E 11 Hz); gain 1 runs away (E 113 Hz, VIP 211 / 137 Hz in BOTH
channels, both SOM channels silent, both branches potentiate).
Prediction (written before the sweep):
  - gating and S_learn survive weak recurrence (gain <= ~0.1-0.2), with E < ~20 Hz;
  - the failure is driven by E -> VIP (not channel-specific: excites the other channel's
    VIP, silencing the other SOM and opening the other branch) and by E -> E (runaway);
  - E -> SOM raises SOM in both channels, slowing LTP on the free branch;
  - E -> PV lowers E rates and is harmless to gating.
Result (2026-11-11, plus follow-up gains 0.6-0.9 for all / E / VIP):
  - all: passes to gain 0.6; at 0.7, 80% of cells are gated; at 1.0, 20%. The other VIP
    channel ignites, a cliff not a slope.
  - E->E alone passes to 0.6 (E 50 Hz); it runs away from 0.7.
  - E->VIP alone passes to 0.7; 40% gated at 0.8, none at 0.9.
  - E->SOM and E->PV are harmless up to gain 1.
  - Prediction right on which pathways break it; threshold ~3x higher than predicted;
    E->SOM does not slow LTP.
Run:     <py> -I experiments/network_test.py run [n_workers]
Analyse: <py> -I experiments/network_test.py analyse
Out:     results/current/network_test.json, _summary.json, figures/network_test.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
OUT = os.path.join(PROOT, 'results', 'current', 'network_test.json')
SEEDS = [42, 43, 44, 45, 46]
GAINS = [0.0, 0.05, 0.1, 0.2, 0.35, 0.5, 1.0]
SINGLE = ['E', 'SOM', 'VIP', 'PV']
SINGLE_GAINS = [0.25, 0.5, 1.0]
FINE = [0.6, 0.7, 0.8, 0.9]          # follow-up: locate the cliff between 0.5 and 1
FINE_TARGETS = ['all', 'E', 'VIP']
N_EP = 8
READ = [(0, None), (1, None), (0, 0), (1, 0), (1, 1), (0, 1)]


def conditions():
    C = {f'all_{g}': dict(rec_gain=g) for g in GAINS}
    for t in SINGLE:
        for g in SINGLE_GAINS:
            C[f'{t}_{g}'] = dict(rec_gain=g, rec_targets=(t,))
    for t in FINE_TARGETS:
        for g in FINE:
            C[f'{t}_{g}'] = dict(rec_gain=g) if t == 'all' else dict(rec_gain=g, rec_targets=(t,))
    return C


def S_cell(rates):
    """Yang Eq. 1 per cell from the six READ epochs (baseline-corrected, clipped at 0)."""
    base = {0: rates[0], 1: rates[1]}
    r = {(c, s): max(rates[i] - base[c], 0.0) for i, (c, s) in enumerate(READ) if s is not None}
    S = []
    for k in (0, 1):
        on, off = r[(k, k)], r[(1 - k, k)]
        S.append((on - off) / (on + off) if on + off > 0 else np.nan)
    return float(np.nanmean(S)) if not np.all(np.isnan(S)) else np.nan


def readout(kw, seed, rho):
    from network_circuit import run_network_protocol
    r = run_network_protocol([c for c, _ in READ], T=5.0, stim=[s for _, s in READ], plastic=False,
                             rho_init_syn=rho, exc_rate=10.0, seed_val=seed, **kw)
    R = np.array([t['pyr_hz_cells'] for t in r['traj']])          # (6 epochs, N_E)
    S = [S_cell(R[:, c]) for c in range(R.shape[1])]
    return float(np.nanmean(S)) if not np.all(np.isnan(S)) else float('nan'), R.mean(1).tolist()


def _job(name, seed):
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    from network_circuit import run_network_protocol
    t0 = time.time()
    kw = conditions()[name]
    out = dict(cond=name, seed=seed)
    lt = run_network_protocol([0] * N_EP + [1] * N_EP, T=3.0, exc_rate=50.0, seed_val=seed, **kw)
    tr = lt['traj']; iA = np.array(lt['idx_A'])
    a, b = tr[N_EP - 1], tr[-1]
    f0 = np.array(a['rho0_syn'])[:, iA].mean(1); f1 = np.array(a['rho1_syn'])[:, iA].mean(1)
    out['rho_free'], out['rho_inh'] = float(f0.mean()), float(f1.mean())
    out['frac_gated'] = float(np.mean((f0 > 0.65) & (f1 < 0.5)))
    out['ret_A'] = float(np.array(b['rho0_syn'])[:, iA].mean() / f0.mean())
    ph = tr[:N_EP]
    out['E_hz'] = float(np.mean([t['pyr_hz'] for t in ph]))
    out['E_max_hz'] = float(np.max([max(t['pyr_hz_cells']) for t in ph]))
    out['som_own'], out['som_other'] = float(np.mean([t['som0_hz'] for t in ph])), float(np.mean([t['som1_hz'] for t in ph]))
    out['vip_own'], out['vip_other'] = float(np.mean([t['vip0_hz'] for t in ph])), float(np.mean([t['vip1_hz'] for t in ph]))
    out['pv_hz'] = float(np.mean([t['pv_hz'] for t in ph]))
    out['S_learn'], out['read_rates_learn'] = readout(kw, seed, (b['rho0_syn'], b['rho1_syn']))
    n_aff = lt['n_aff']; N = lt['N_E']
    flat = np.full((N, n_aff), 1 / 3)
    out['S_before'], out['read_rates_before'] = readout(kw, seed, (flat, flat))
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
            print(f"{j[0]:<10} s{j[1]} free {r['rho_free']:.3f} inh {r['rho_inh']:.3f} gated {r['frac_gated']:.2f} "
                  f"E {r['E_hz']:5.1f} (max {r['E_max_hz']:5.1f}) SOM {r['som_own']:4.1f}/{r['som_other']:4.1f} "
                  f"VIP {r['vip_own']:5.1f}/{r['vip_other']:5.1f} PV {r['pv_hz']:5.1f} S_learn {r['S_learn']:+.2f} "
                  f"S_before {r['S_before']:+.2f} ret_A {r['ret_A']:.3f} ({r['wall_s']} s)", flush=True)
    print('done', flush=True)


KEYS = ['rho_free', 'rho_inh', 'frac_gated', 'ret_A', 'E_hz', 'E_max_hz', 'som_own', 'som_other',
        'vip_own', 'vip_other', 'pv_hz', 'S_learn', 'S_before']


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
    print(f"{'condition':<10} | free   inh  gated | E (max)        | SOM own/oth | VIP own/oth  |   PV  | S_learn     S_bef | ret_A | pass")
    for c, r in rows.items():
        print(f"{c:<10} | {r['rho_free']:.3f} {r['rho_inh']:.3f} {r['frac_gated']:.2f} | {r['E_hz']:5.1f} ({r['E_max_hz']:5.1f}) | "
              f"{r['som_own']:4.1f}/{r['som_other']:4.1f} | {r['vip_own']:5.1f}/{r['vip_other']:5.1f} | {r['pv_hz']:5.1f} | "
              f"{r['S_learn']:+.2f}±{r['S_learn_sd']:.2f} {r['S_before']:+.2f} | {r['ret_A']:.3f} | {'Y' if r['pass'] else '.'}")
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.2))
    gs = sorted(g for g in GAINS + FINE if f'all_{g}' in rows)
    A = [rows[f'all_{g}'] for g in gs]
    axs[0].plot(gs, [r['S_learn'] for r in A], 'o-', label='S after learning')
    axs[0].plot(gs, [r['S_before'] for r in A], 's--', label='S before learning')
    axs[0].plot(gs, [r['frac_gated'] for r in A], 'k^-', label='fraction of cells gated')
    axs[0].axhline(0.5, color='grey', lw=0.6, ls=':')
    axs[0].set_xlabel('recurrence gain (all E→ pathways)'); axs[0].set_title('learning and gating'); axs[0].legend(fontsize=7)
    for k, lab in (('E_hz', 'E'), ('som_own', 'SOM own'), ('som_other', 'SOM other'), ('vip_other', 'VIP other'), ('pv_hz', 'PV')):
        axs[1].plot(gs, [r[k] for r in A], 'o-', label=lab)
    axs[1].set_yscale('symlog', linthresh=1); axs[1].set_xlabel('recurrence gain'); axs[1].set_ylabel('rate (Hz)')
    axs[1].set_title('rates in context A'); axs[1].legend(fontsize=7)
    for t, mk in zip(SINGLE, 'osd^'):
        g2 = sorted(g for g in SINGLE_GAINS + FINE if f'{t}_{g}' in rows)
        axs[2].plot(g2, [rows[f'{t}_{g}']['S_learn'] for g in g2], mk + '-', label=f'E→{t} only')
    axs[2].axhline(0.5, color='grey', lw=0.6, ls=':')
    axs[2].set_xlabel('gain of the single pathway'); axs[2].set_ylabel('S after learning'); axs[2].legend(fontsize=7)
    axs[2].set_title('which recurrent pathway breaks it')
    fig.suptitle('Recurrent network (20 canonical cells, Zhang E→all recurrence), 5 seeds')
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'network_test.png')
    fig.savefig(fp, dpi=130); print('saved', fp)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(int(sys.argv[2]) if len(sys.argv) > 2 else 11)
    else:
        analyse()
