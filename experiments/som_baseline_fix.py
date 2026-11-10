"""
som_baseline_fix.py -- the SOM-bias knife-edge of docs/reports/PLAN_robustness.md (R3),
2026-11-10.

Problem (R3): SOM's baseline comes from a noiseless bias current, 21.32 pA, just above the
20 pA rheobase of the SOM LIF. x0.75 silences SOM (gating lost), x1.25 gives 76 Hz.
Gating itself holds for SOM rates of ~15-112 Hz, so the fragility is in how the baseline
rate is produced, not in the gating mechanism.
Fix tested (calibration only, no new mechanism; SOM_NOISY_KW in model/context_circuit.py):
a sub-rheobase bias (6 pA) plus independent Poisson excitation onto every SOM cell
(60 Hz x 2 nS), which gives the same ~30 Hz baseline, irregular, with a smooth f-I curve.
Isolated SOM (scratch scan): bias x0.5-1.5 -> 23-40 Hz; input rate or weight x0.75/1.25 ->
17-19 / 42 Hz (bias-only: 0 / 76 Hz).
Per (variant, parameter, factor, seed) the R3 metrics plus the R4 learning test:
  gating   always-on inputs, A x 8: rho_free, rho_inh;  then B x 8: ret_always
  ret_ctx  context inputs, A x 8 then B x 8: retention of A with silent inputs
  S        Fig. 5 gating selectivity (learning frozen, balanced soma), default wiring
  S_learn  R4: learn A/B in 'patterns' mode (overlap 0), read out at 10 Hz/synapse
  som_base SOM rate of the channel whose MD is silent (during A); som_off: MD-on channel
Pass (stated before running), seed means, at x0.75 and x1.25 of each SOM drive parameter:
  gated (rho_free > 0.65, rho_inh < 0.5, ratio >= 2), S > 0.5, ret_ctx >= 0.9,
  S_learn > 0.5, som_base within 15-112 Hz. Baseline: 10 seeds, >= 9/10 gated.
Run with bAP calcium x1.0 (the model at the time); the canonical bAP x0.2 model's SOM-drive
robustness is in experiments/robustness_r3.py canonical.
Run:     <py> -I experiments/som_baseline_fix.py run [n_workers]
Analyse: <py> -I experiments/som_baseline_fix.py analyse
Out:     results/current/som_baseline_fix.json, figures/som_baseline_fix.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
OUT = os.path.join(PROOT, 'results', 'current', 'som_baseline_fix.json')
FACTORS = [0.5, 0.75, 1.25, 1.5]
SEEDS = [42, 43, 44, 45, 46]
BASE_SEEDS = list(range(42, 52))
PARAMS = {'noisy': ['som_bias_pA', 'som_bg_E_hz', 'som_bg_nS'], 'bias': ['som_bias_pA']}
READ_HZ = 10.0


def base_kw(variant):
    from context_circuit import SOM_NOISY_KW
    return dict(SOM_NOISY_KW, som_baseline='noisy', bap_ca_scale=1.0) if variant == 'noisy' else dict(som_bias_pA=21.32, som_baseline='bias', bap_ca_scale=1.0)


def _job(variant, param, f, seed):
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA
    from gating_selectivity_fig5 import selectivity, CTX, STIM
    from robustness_r4_learning import READ, S_from, N_EP
    t0 = time.time()
    kw = base_kw(variant)
    if param != 'baseline':
        kw[param] = kw[param] * f
    out = dict(variant=variant, param=param, f=f, seed=seed, kw=kw)
    for mode in ('always', 'context'):
        tr = run_context_protocol([0] * 8 + [1] * 8, T=3.0, input_mode=mode, seed_val=seed, **kw)['traj']
        out[mode] = dict(rho0=[t['rho0'] for t in tr], rho1=[t['rho1'] for t in tr],
                         som=[[t['som0_hz'], t['som1_hz']] for t in tr])
    a, c = out['always'], out['context']
    out['rho_free'], out['rho_inh'] = a['rho0'][7], a['rho1'][7]
    out['ret_always'] = a['rho0'][-1] / a['rho0'][7]
    out['ret_ctx'] = c['rho0'][-1] / c['rho0'][7]
    out['som_base'] = float(np.mean([s[1] for s in a['som'][:8]]))
    out['som_off'] = float(np.mean([s[0] for s in a['som'][:8]]))
    sk = dict(BALANCED_SOMA_KW)
    ov = {'gGABA_pv2soma': BALANCED_SOMA_G_PV2SOMA}
    r = run_context_protocol(CTX, T=5.0, input_mode='context', stim=STIM, plastic=False, bap_source='soma',
                             seed_val=seed, param_overrides=ov, **sk, **kw)
    out['S'], _ = selectivity([t['pyr_hz'] for t in r['traj']])
    learn = run_context_protocol([0] * N_EP + [1] * N_EP, T=3.0, input_mode='patterns', overlap=0.0,
                                 exc_rate=50.0, seed_val=seed, **kw)['traj'][-1]
    st = (learn['rho0_syn'], learn['rho1_syn'])
    r = run_context_protocol([c for c, _ in READ], T=5.0, input_mode='patterns', overlap=0.0,
                             stim=[s for _, s in READ], plastic=False, rho_init_syn=st, exc_rate=READ_HZ,
                             bap_source='soma', seed_val=seed, param_overrides=ov, **sk, **kw)
    out['S_learn_rates'] = [t['pyr_hz'] for t in r['traj']]
    out['S_learn'], _ = S_from(out['S_learn_rates'])
    out['wall_s'] = round(time.time() - t0, 1)
    return out


def key(v, p, f, s):
    return f'{v}_{p}_{f}_{s}'


def jobs():
    J = [('noisy', 'baseline', 1.0, s) for s in BASE_SEEDS]
    J += [('bias', 'baseline', 1.0, s) for s in SEEDS]
    for v, ps in PARAMS.items():
        J += [(v, p, f, s) for p in ps for f in FACTORS for s in SEEDS]
    return J


def run(nw):
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
                print(j, 'ERROR', repr(e), flush=True); continue
            done[key(*j)] = r
            json.dump(done, open(OUT, 'w'))
            print(f"{key(*j):<32} SOM {r['som_base']:5.1f}/{r['som_off']:4.1f} Hz free {r['rho_free']:.3f} "
                  f"inh {r['rho_inh']:.3f} S {r['S']:.2f} S_learn {r['S_learn']:.2f} ret ctx {r['ret_ctx']:.3f} "
                  f"alw {r['ret_always']:.3f} ({r['wall_s']} s)", flush=True)
    print('done', flush=True)


def summarise(d):
    rows = {}
    conds = [(v, 'baseline', 1.0) for v in PARAMS] + [(v, p, f) for v, ps in PARAMS.items() for p in ps for f in FACTORS]
    for v, p, f in conds:
        rs = [r for r in d.values() if r['variant'] == v and r['param'] == p and r['f'] == f]
        if not rs:
            continue
        m = lambda k: float(np.nanmean([r[k] for r in rs]))
        free, inh = m('rho_free'), m('rho_inh')
        row = dict(n=len(rs), som_base=m('som_base'), som_off=m('som_off'), rho_free=free, rho_inh=inh,
                   ratio=free / max(inh, 1e-9), S=m('S'), S_learn=m('S_learn'),
                   S_learn_sd=float(np.nanstd([r['S_learn'] for r in rs])),
                   ret_ctx=m('ret_ctx'), ret_always=m('ret_always'),
                   gated_seeds=sum(r['rho_free'] > 0.65 and r['rho_inh'] < 0.5 and
                                   r['rho_free'] / max(r['rho_inh'], 1e-9) >= 2 for r in rs))
        row['pass'] = dict(gating=free > 0.65 and inh < 0.5 and row['ratio'] >= 2, S=row['S'] > 0.5,
                           ret=row['ret_ctx'] >= 0.9, S_learn=row['S_learn'] > 0.5,
                           som=15 <= row['som_base'] <= 112)
        rows[f'{v}|{p}|{f}'] = row
    return rows


def analyse():
    d = json.load(open(OUT))
    rows = summarise(d)
    print(f"{'variant|param|x':<26} | {'SOM':>5} {'off':>4} | {'free':>5} {'inh':>5} {'ratio':>5} {'seeds':>5} | "
          f"{'S':>5} {'S_lrn':>5} | {'ret_c':>5} {'ret_a':>5} | pass G S R L som")
    for k, r in rows.items():
        P = r['pass']
        print(f"{k:<26} | {r['som_base']:5.1f} {r['som_off']:4.1f} | {r['rho_free']:.3f} {r['rho_inh']:.3f} "
              f"{r['ratio']:5.2f} {r['gated_seeds']:>2}/{r['n']:<2} | {r['S']:5.2f} {r['S_learn']:5.2f} | "
              f"{r['ret_ctx']:5.3f} {r['ret_always']:5.3f} | " + ' '.join('Y' if P[x] else '.' for x in
                                                                     ('gating', 'S', 'ret', 'S_learn', 'som')))
    knife = {v: sorted({k.split('|')[1] for k, r in rows.items() if k.startswith(v + '|')
                        and k.split('|')[2] in ('0.75', '1.25') and not all(r['pass'].values())})
             for v in PARAMS}
    print('knife-edge at +/-25%:', knife)
    json.dump(dict(rows=rows, knife_edge_25=knife), open(OUT.replace('.json', '_summary.json'), 'w'), indent=1)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    xs = [0.5, 0.75, 1.0, 1.25, 1.5]
    lines = [('bias', 'som_bias_pA', 'bias only: bias current (old)', '#999999', '--'),
             ('noisy', 'som_bias_pA', 'noisy: bias current', '#0072B2', '-'),
             ('noisy', 'som_bg_E_hz', 'noisy: Poisson input rate', '#D55E00', '-'),
             ('noisy', 'som_bg_nS', 'noisy: Poisson input weight', '#009E73', '-')]
    mets = [('som_base', 'SOM baseline rate (Hz); gating window 15–112 Hz', (0, 120)),
            ('ratio', 'gating ratio ρ_free/ρ_inh (pass ≥ 2)', (0, 4)),
            ('S', 'gating selectivity S, Fig. 5 (pass > 0.5)', (-0.2, 1.05)),
            ('S_learn', 'S after learning, 10 Hz readout (pass > 0.5)', (-0.2, 1.05))]
    fig, ax = plt.subplots(1, 4, figsize=(18, 4.2))
    for a, (mk, title, yl) in zip(ax, mets):
        for v, p, lab, col, ls in lines:
            ys = [rows.get(f'{v}|{p}|{x}' if x != 1.0 else f'{v}|baseline|1.0', {}).get(mk, np.nan) for x in xs]
            a.plot(xs, ys, 'o', ls=ls, color=col, lw=1.8, ms=4, label=lab)
        if mk == 'som_base':
            a.axhspan(15, 112, color='#e8f4e8', zorder=0)
        a.axvspan(0.75, 1.25, color='0.93', zorder=0)
        a.set(title=title, xlabel='scale factor', ylim=yl, xticks=xs)
        a.title.set_fontsize(9.5)
        a.spines[['top', 'right']].set_visible(False)
    ax[0].legend(fontsize=7.5, frameon=False)
    fig.suptitle('SOM baseline: bias-only (old) vs fluctuation-driven (noisy); 5 seeds, mean; grey = ±25%', fontsize=11)
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'som_baseline_fix.png')
    fig.savefig(fp, dpi=150, facecolor='white')
    print('saved', fp)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(int(sys.argv[2]) if len(sys.argv) > 2 else 11)
    else:
        analyse()
