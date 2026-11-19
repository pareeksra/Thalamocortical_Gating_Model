"""
robustness_claims.py -- does the main A/B-alternation claim survive +/-25% parameter changes?
(2026-11-19, step 1 of the robustness push after the network alternation run.)

R3 (robustness_r3.py) showed that gating, S and learned S have no knife-edge at +/-25% for 16
parameters. It did not test the headline claim of the alternation experiment:
    "with 12-s blocks (L = 4) both contexts are recalled at overlap f = 0.25, and the previous
     context is lost at f = 0.5."
Here each of the 16 R3 parameters is scaled by x0.75 and x1.25 and the canonical alternation
protocol (32 x 3-s epochs, L = 4, learning at 80 Hz, plasticity frozen readout at 10 Hz) is run at
f = 0.25 and f = 0.5, 5 seeds (42-46). The readout uses the same perturbed model.

Prediction (written before running): the claim holds at every +/-25% perturbation:
  S_previous(f = 0.25) > 0.5 and S_current(f = 0.25) > 0.5, and S_previous(f = 0.5) < 0.5.
The parameters most likely to move the boundary are those that set how fast the shared
afferents swing between branches: gNMDA, exc_rate, bap_ca_scale.

Run:     <py> -I experiments/robustness_claims.py run [n_workers]
Analyse: <py> -I experiments/robustness_claims.py analyse
Out:     results/current/robustness_claims{,_summary}.json, figures/robustness_claims.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
OUT = os.path.join(PROOT, 'results', 'current', 'robustness_claims.json')
FACTORS = [0.75, 1.25]
OVERLAPS = [0.25, 0.5]
SEEDS = [42, 43, 44, 45, 46]
L, N_TOT = 4, 32
PARAMS = ['gNMDA', 'gLDend_pyr', 'gGABA', 'tauGABA', 'couple', 'som_bias', 'md_rate',
          'gAMPA_vip', 'p_vip2som_spike', 'pv_pair', 'soma_bg', 'exc_rate',
          'som_bg_E_hz', 'som_bg_nS', 'bap_ca_scale', 'vip2som_scale']
LABEL = {'gNMDA': 'NMDA conductance', 'gLDend_pyr': 'dendritic leak', 'gGABA': 'SOM→dend GABA',
         'tauGABA': 'dend GABA decay', 'couple': 'soma–dend coupling', 'som_bias': 'SOM bias current',
         'md_rate': 'MD rate', 'gAMPA_vip': 'MD→VIP weight', 'p_vip2som_spike': 'P(VIP→SOM)',
         'pv_pair': 'PV bg + SOM→PV', 'soma_bg': 'soma background', 'exc_rate': 'learning input rate',
         'som_bg_E_hz': 'SOM Poisson rate', 'som_bg_nS': 'SOM Poisson weight',
         'bap_ca_scale': 'bAP calcium', 'vip2som_scale': 'VIP→SOM weight'}


def kwargs_for(param, f):
    """Same perturbations as robustness_r3.kwargs_for in canonical mode."""
    from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
    P = dict(params)
    for d in (plasticity_params, pv_params, som_params, vip_params, md_params):
        P.update(d)
    ov, kw, soma_scale = {}, {}, 1.0
    if param in ('gNMDA', 'gLDend_pyr', 'gGABA', 'tauGABA', 'gAMPA_vip', 'p_vip2som_spike'):
        ov[param] = P[param] * f
    elif param == 'pv_pair':
        ov['weight_bg_pv'] = P['weight_bg_pv'] * f; ov['gGABA_pv'] = P['gGABA_pv'] * f
    elif param == 'couple':
        kw['gcouple_nS'] = 0.8 * f
    elif param == 'som_bias':
        kw['som_bias_pA'] = 6.0 * f
    elif param == 'som_bg_E_hz':
        kw['som_bg_E_hz'] = 60.0 * f
    elif param == 'som_bg_nS':
        kw['som_bg_nS'] = 2.0 * f
    elif param == 'md_rate':
        kw['md_on_rate'] = 25.0 * f
    elif param == 'exc_rate':
        kw['exc_rate'] = 80.0 * f
    elif param == 'soma_bg':
        soma_scale = f
    elif param == 'bap_ca_scale':
        kw['bap_ca_scale'] = 0.2 * f
    elif param == 'vip2som_scale':
        kw['vip2som_scale'] = 0.25 * f
    return ov, kw, soma_scale


def _job(param, fac, ov_f, seed):
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA
    from robustness_r4_learning import READ, S_from
    t0 = time.time()
    ov, kw, ss = kwargs_for(param, fac)
    sch = [(e // L) % 2 for e in range(N_TOT)]
    r = run_context_protocol(sch, T=3.0, input_mode='patterns', overlap=ov_f, seed_val=seed,
                             param_overrides=dict(ov) or None, **kw)
    tr = r['traj']
    rho0 = [t['rho0_syn'] for t in tr]; rho1 = [t['rho1_syn'] for t in tr]
    sk = dict(BALANCED_SOMA_KW); sk['soma_drive_hz'] *= ss; sk['soma_inh_hz'] *= ss
    ov2 = dict(ov); ov2['gGABA_pv2soma'] = BALANCED_SOMA_G_PV2SOMA
    kr = {k: v for k, v in kw.items() if k != 'exc_rate'}   # exc_rate perturbs learning only

    def readout(e):
        rr = run_context_protocol([c for c, _ in READ], T=5.0, input_mode='patterns', overlap=ov_f,
                                  stim=[s_ for _, s_ in READ], plastic=False, rho_init_syn=(rho0[e], rho1[e]),
                                  exc_rate=10.0, bap_source='soma', seed_val=seed, param_overrides=ov2, **sk, **kr)
        rates = [t['pyr_hz'] for t in rr['traj']]
        S, (SA, SB) = S_from(rates)
        return dict(S=S, S_A=SA, S_B=SB, rates=rates)

    end = readout(N_TOT - 1)
    # S of the current context (B at the end) and of the previous one (A, read at the end)
    cur_ctx = sch[-1]
    S_cur = end['S_B'] if cur_ctx == 1 else end['S_A']
    S_prev = end['S_A'] if cur_ctx == 1 else end['S_B']
    return dict(param=param, f=fac, overlap=ov_f, seed=seed, S_current=S_cur, S_previous=S_prev,
                readout_end=end, rho0_end=rho0[-1], rho1_end=rho1[-1],
                idx_A=r['idx_A'], idx_B=r['idx_B'], wall_s=round(time.time() - t0, 1))


def key(p, fac, f, s):
    return f'{p}_{fac}_f{f}_s{s}'


def jobs():
    J = [('baseline', 1.0, f, s) for f in OVERLAPS for s in SEEDS]
    J += [(p, fac, f, s) for p in PARAMS for fac in FACTORS for f in OVERLAPS for s in SEEDS]
    return J


def run(nw):
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    J = [j for j in jobs() if key(*j) not in done]
    # slowest first is unknown; interleave overlaps so both finish together
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
            print(f"{key(*j):<30} S cur {r['S_current']:+.2f} prev {r['S_previous']:+.2f} ({r['wall_s']} s)", flush=True)
    print('done', flush=True)


def analyse():
    d = json.load(open(OUT))
    rows = {}
    conds = [('baseline', 1.0)] + [(p, fac) for p in PARAMS for fac in FACTORS]
    for p, fac in conds:
        row = {}
        for f in OVERLAPS:
            rs = [r for r in d.values() if r['param'] == p and r['f'] == fac and r['overlap'] == f]
            if not rs:
                continue
            for m in ('S_current', 'S_previous'):
                v = [r[m] for r in rs]
                row[f'{m}_f{f}'] = float(np.nanmean(v)); row[f'{m}_f{f}_sd'] = float(np.nanstd(v))
            row[f'n_f{f}'] = len(rs)
        if 'S_previous_f0.25' in row and 'S_previous_f0.5' in row:
            row['both_recalled_f0.25'] = row['S_previous_f0.25'] > 0.5 and row['S_current_f0.25'] > 0.5
            row['prev_lost_f0.5'] = row['S_previous_f0.5'] < 0.5
            row['claim_holds'] = row['both_recalled_f0.25'] and row['prev_lost_f0.5']
        rows[f'{p}_{fac}'] = row
    print(f"{'param':<16} {'x':>5} | f=0.25 cur   prev  | f=0.5 cur   prev  | claim")
    for k, r in rows.items():
        p, fac = k.rsplit('_', 1)
        if 'claim_holds' not in r:
            print(f'{p:<16} {fac:>5} | incomplete'); continue
        print(f"{p:<16} {fac:>5} | {r['S_current_f0.25']:+.2f} {r['S_previous_f0.25']:+.2f}±{r['S_previous_f0.25_sd']:.2f} | "
              f"{r['S_current_f0.5']:+.2f} {r['S_previous_f0.5']:+.2f}±{r['S_previous_f0.5_sd']:.2f} | "
              f"{'holds' if r['claim_holds'] else ('f0.25 FAILS' if not r['both_recalled_f0.25'] else 'f0.5 previous KEPT')}")
    broken = [k for k, r in rows.items() if r.get('claim_holds') is False]
    print('claim broken at:', broken or 'none')
    json.dump(dict(rows=rows, broken=broken), open(OUT.replace('.json', '_summary.json'), 'w'), indent=1)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(14, 6.5), sharey=True)
    base = rows['baseline_1.0']
    for a, f in zip(ax, OVERLAPS):
        y = np.arange(len(PARAMS))
        for fac, mk, c in ((0.75, 'v', '#0B62A4'), (1.25, '^', '#C2510B')):
            xp = [rows.get(f'{p}_{fac}', {}).get(f'S_previous_f{f}', np.nan) for p in PARAMS]
            xe = [rows.get(f'{p}_{fac}', {}).get(f'S_previous_f{f}_sd', np.nan) for p in PARAMS]
            a.errorbar(xp, y + (-0.15 if fac < 1 else 0.15), xerr=xe, fmt=mk, color=c, ms=7, capsize=2, lw=1,
                       label=f'×{fac} (previous context)')
            xc = [rows.get(f'{p}_{fac}', {}).get(f'S_current_f{f}', np.nan) for p in PARAMS]
            a.plot(xc, y + (-0.15 if fac < 1 else 0.15), mk, mfc='none', color=c, ms=7, label=f'×{fac} (current context)')
        a.axvline(base[f'S_previous_f{f}'], color='k', lw=1.2, label='baseline, previous')
        a.axvline(base[f'S_current_f{f}'], color='k', lw=1.2, ls=':', label='baseline, current')
        a.axvline(0.5, color='0.6', ls='--', lw=1)
        a.set(yticks=y, yticklabels=[LABEL[p] for p in PARAMS], xlim=(-0.6, 1.05),
              xlabel='recall S at the end of the run', title=f'overlap f = {f}, 12-s blocks')
        a.spines[['top', 'right']].set_visible(False)
        a.invert_yaxis()
    ax[0].legend(fontsize=8, frameon=False, loc='lower left')
    fig.suptitle('Is the alternation claim robust? Each parameter ×0.75 and ×1.25 (5 seeds, mean ± sd).\n'
                 'Claim: previous context kept at f = 0.25 (S > 0.5), lost at f = 0.5', fontsize=11)
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'robustness_claims.png')
    fig.savefig(fp, dpi=150, facecolor='white'); print('saved', fp)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(int(sys.argv[2]) if len(sys.argv) > 2 else 38)
    else:
        analyse()
