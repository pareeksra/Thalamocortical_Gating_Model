"""
robustness_r3.py -- R3 of docs/reports/PLAN_robustness.md: one-at-a-time parameter
sensitivity of the canonical model (Yang NMDA-plastic synapse), 2026-11-04.

Each parameter is scaled by x0.5, x0.75, x1.25 and x1.5 (x1 = baseline), 5 seeds (42-46).
Per (parameter, factor, seed):
  always   both inputs on: context A x 8 then B x 8 (3 s epochs). After A: rho_free
           (branch 0), rho_inh (branch 1) -> metric 1 (gating). After B: retention of A
           with active inputs.
  context  only the active context's input on, A x 8 then B x 8 -> retention with silent
           inputs.
  S        gating selectivity from soma firing (Fig. 5 protocol, learning frozen,
           balanced soma, bAPs from the soma) at the default wiring.
Pass criteria (stated in the plan, before running), evaluated on the seed mean:
  gating: rho_free > 0.65, rho_inh < 0.5, ratio >= 2;  S > 0.5;  retention(context) >= 0.9.
  retention(always) is reported, not scored (baseline already varies by seed).
Run:     <py> -I experiments/robustness_r3.py run [n_workers] [canonical]
Analyse: <py> -I experiments/robustness_r3.py analyse [canonical]
'canonical' = model defaults since 2026-11-10 (noisy SOM baseline, bAP calcium x0.2); adds the
SOM Poisson-drive parameters and S_learn (R4 learning test, 10 Hz readout); outputs get a
_canonical suffix. Without it: the committed pre-2026-11-10 model.
Out:     results/current/robustness_r3.json, figures/robustness_r3.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
CANON = 'canonical' in sys.argv[1:]   # argument 'canonical': model defaults (2026-11-10); else the committed pre-2026-11-10 model
SOMB = 'noisy' if CANON else 'bias'
OUT = os.path.join(PROOT, 'results', 'current', 'robustness_r3' + ('_canonical' if CANON else '') + '.json')
FACTORS = [0.5, 0.75, 1.25, 1.5]
SEEDS = [42, 43, 44, 45, 46]
PARAMS = ['gNMDA', 'gLDend_pyr', 'gGABA', 'tauGABA', 'couple', 'som_bias', 'md_rate',
          'gAMPA_vip', 'p_vip2som_spike', 'pv_pair', 'soma_bg', 'exc_rate']
if CANON:
    PARAMS = PARAMS + ['som_bg_E_hz', 'som_bg_nS']
LABEL = {'gNMDA': 'NMDA conductance', 'gLDend_pyr': 'dendritic leak', 'gGABA': 'SOM→dend GABA',
         'tauGABA': 'dend GABA decay', 'couple': 'soma–dend coupling', 'som_bias': 'SOM bias current',
         'md_rate': 'MD rate (context on)', 'gAMPA_vip': 'MD→VIP weight', 'p_vip2som_spike': 'P(VIP→SOM)',
         'pv_pair': 'PV bg weight + SOM→PV', 'soma_bg': 'soma background (E and I)', 'exc_rate': 'input rate',
         'som_bg_E_hz': 'SOM Poisson input rate', 'som_bg_nS': 'SOM Poisson input weight'}


def kwargs_for(param, f):
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
        kw['som_bias_pA'] = (6.0 if CANON else 21.32) * f
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
    return ov, kw, soma_scale


def _job(param, f, seed):
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA
    if not CANON:   # committed results: bias-only SOM baseline, bAP calcium x1.0
        import functools; run_context_protocol = functools.partial(run_context_protocol, som_baseline='bias', bap_ca_scale=1.0)
    from gating_selectivity_fig5 import selectivity, CTX, STIM
    t0 = time.time()
    ov, kw, ss = kwargs_for(param, f)
    out = dict(param=param, f=f, seed=seed)
    for mode in ('always', 'context'):
        r = run_context_protocol([0] * 8 + [1] * 8, T=3.0, input_mode=mode, seed_val=seed,
                                 param_overrides=dict(ov) or None, **kw)
        tr = r['traj']
        out[mode] = dict(rho0=[t['rho0'] for t in tr], rho1=[t['rho1'] for t in tr],
                         som=[[t['som0_hz'], t['som1_hz']] for t in tr], pv=[t['pv_hz'] for t in tr])
    sk = dict(BALANCED_SOMA_KW); sk['soma_drive_hz'] *= ss; sk['soma_inh_hz'] *= ss
    ov2 = dict(ov); ov2['gGABA_pv2soma'] = BALANCED_SOMA_G_PV2SOMA
    r = run_context_protocol(CTX, T=5.0, input_mode='context', stim=STIM, plastic=False, bap_source='soma',
                             seed_val=seed, param_overrides=ov2, **sk, **kw)
    rates = [t['pyr_hz'] for t in r['traj']]
    out['S'], out['S_k'] = selectivity(rates)
    out['S_rates'] = rates
    a = out['always']
    out['rho_free'], out['rho_inh'] = a['rho0'][7], a['rho1'][7]
    out['ret_always'] = a['rho0'][-1] / a['rho0'][7]
    c = out['context']
    out['ret_context'] = c['rho0'][-1] / c['rho0'][7]
    if CANON:   # R4 learning test: learn A/B ('patterns', overlap 0), read out at 10 Hz/synapse
        from robustness_r4_learning import READ, S_from, N_EP
        lt = run_context_protocol([0] * N_EP + [1] * N_EP, T=3.0, input_mode='patterns', overlap=0.0,
                                  exc_rate=50.0 * (f if param == 'exc_rate' else 1.0), seed_val=seed,
                                  param_overrides=dict(ov) or None, **{k: v for k, v in kw.items() if k != 'exc_rate'})['traj'][-1]
        rr = run_context_protocol([c for c, _ in READ], T=5.0, input_mode='patterns', overlap=0.0,
                                  stim=[s_ for _, s_ in READ], plastic=False, rho_init_syn=(lt['rho0_syn'], lt['rho1_syn']),
                                  exc_rate=10.0, bap_source='soma', seed_val=seed, param_overrides=ov2,
                                  **sk, **{k: v for k, v in kw.items() if k != 'exc_rate'})
        out['S_learn_rates'] = [t['pyr_hz'] for t in rr['traj']]
        out['S_learn'], _ = S_from(out['S_learn_rates'])
    out['wall_s'] = round(time.time() - t0, 1)
    return out


def key(p, f, s):
    return f'{p}_{f}_{s}'


def run(nw):
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    J = [('baseline', 1.0, s) for s in SEEDS] + [(p, f, s) for p in PARAMS for f in FACTORS for s in SEEDS]
    J = [j for j in J if key(*j) not in done]
    print(f'{len(J)} jobs ({len(done)} done), {nw} workers', flush=True)
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(_job, *j): j for j in J}
        for fu in as_completed(futs):
            j = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                print(j, 'ERROR', repr(e), flush=True); continue
            done[key(*j)] = r
            json.dump(done, open(OUT, 'w'))
            print(f"{key(*j):<24} free {r['rho_free']:.3f} inh {r['rho_inh']:.3f} S {r['S']:.2f} "
                  f"ret ctx {r['ret_context']:.3f} always {r['ret_always']:.3f} ({r['wall_s']} s)", flush=True)
    print('done', flush=True)


def summarise(d):
    rows = {}
    conds = [('baseline', 1.0)] + [(p, f) for p in PARAMS for f in FACTORS]
    for p, f in conds:
        rs = [r for r in d.values() if r['param'] == p and r['f'] == f]
        if not rs:
            continue
        m = lambda k: float(np.nanmean([r[k] for r in rs]))
        sd = lambda k: float(np.nanstd([r[k] for r in rs]))
        free, inh = m('rho_free'), m('rho_inh')
        gated_seeds = sum(r['rho_free'] > 0.65 and r['rho_inh'] < 0.5 and r['rho_free'] / max(r['rho_inh'], 1e-9) >= 2 for r in rs)
        row = dict(n=len(rs), rho_free=free, rho_inh=inh, ratio=free / max(inh, 1e-9), gated_seeds=gated_seeds,
                   S=m('S'), S_sd=sd('S'), ret_context=m('ret_context'), ret_always=m('ret_always'),
                   ret_always_sd=sd('ret_always'))
        row['pass_gating'] = free > 0.65 and inh < 0.5 and row['ratio'] >= 2
        row['pass_S'] = row['S'] > 0.5
        row['pass_ret'] = row['ret_context'] >= 0.9
        if CANON:
            row['S_learn'] = m('S_learn'); row['S_learn_sd'] = sd('S_learn')
            row['pass_learn'] = row['S_learn'] > 0.5
        rows[f'{p}_{f}'] = row
    return rows


def analyse():
    d = json.load(open(OUT))
    rows = summarise(d)
    print(f"{'param':<16} {'x':>5} | {'free':>5} {'inh':>5} {'ratio':>5} {'seeds':>5} | {'S':>5} | "
          f"{'ret_ctx':>7} {'ret_alw':>7} | {'S_lrn':>5} | pass G S R L")
    for k, r in rows.items():
        p, f = k.rsplit('_', 1)
        print(f"{p:<16} {f:>5} | {r['rho_free']:.3f} {r['rho_inh']:.3f} {r['ratio']:5.2f} {r['gated_seeds']:>3}/{r['n']} | "
              f"{r['S']:5.2f} | {r['ret_context']:7.3f} {r['ret_always']:7.3f} | {r.get('S_learn', float('nan')):5.2f} | "
              f"{'Y' if r['pass_gating'] else '.'} {'Y' if r['pass_S'] else '.'} {'Y' if r['pass_ret'] else '.'} "
              f"{'Y' if r.get('pass_learn', True) else '.'}")
    knife = sorted({k.rsplit('_', 1)[0] for k, r in rows.items() if k.rsplit('_', 1)[1] in ('0.75', '1.25')
                    and not (r['pass_gating'] and r['pass_S'] and r['pass_ret'] and r.get('pass_learn', True))})
    print('knife-edge at +/-25%:', knife or 'none')
    json.dump(dict(rows=rows, knife_edge_25=knife), open(OUT.replace('.json', '_summary.json'), 'w'), indent=1)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    xs = [0.5, 0.75, 1.0, 1.25, 1.5]
    mets = [('ratio', 'gating ratio ρ_free/ρ_inh (pass ≥ 2)', 2.0, (0, 4)),
            ('S', 'gating selectivity S (pass > 0.5)', 0.5, (-0.2, 1.05)),
            ('ret_context', 'retention, idle inputs silent (pass ≥ 0.9)', 0.9, (0, 1.1)),
            ('ret_always', 'retention, inputs always on (reported)', None, (0, 1.1))]
    if CANON:
        mets.insert(2, ('S_learn', 'S after learning, 10 Hz readout (pass > 0.5)', 0.5, (-0.2, 1.05)))
        mets.append(('rho_inh', 'ρ_inh (inhibited branch after A)', None, (0, 1.0)))
    fig, ax = plt.subplots(2, len(mets) // 2, figsize=(7 * len(mets) // 2, 10))
    cmap = plt.get_cmap('tab20')
    for a, (mk, title, thr, yl) in zip(ax.flat, mets):
        for i, p in enumerate(PARAMS):
            ys = [rows.get(f'{p}_{x}' if x != 1.0 else 'baseline_1.0', {}).get(mk, np.nan) for x in xs]
            a.plot(xs, ys, 'o-', color=cmap(i), lw=1.5, ms=4, label=LABEL[p])
        if thr is not None:
            a.axhline(thr, color='k', ls='--', lw=1)
        a.axvspan(0.75, 1.25, color='0.92', zorder=0)
        a.set(title=title, xlabel='parameter scale factor', ylim=yl, xticks=xs)
        a.spines[['top', 'right']].set_visible(False)
    ax[0, 0].legend(fontsize=7.5, frameon=False, ncol=2, loc='lower left')
    fig.suptitle(f'R3 parameter sensitivity, Yang NMDA-plastic synapse, SOM baseline {SOMB} (5 seeds, mean; grey = ±25% band)', fontsize=12)
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'robustness_r3' + ('_canonical' if CANON else '') + '.png')
    fig.savefig(fp, dpi=150, facecolor='white')
    print('saved', fp)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 11)
    else:
        analyse()
