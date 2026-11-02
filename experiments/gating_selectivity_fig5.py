"""
gating_selectivity_fig5.py -- Yang 2016 Fig. 5 analogue: gating selectivity measured from
the soma's OUTPUT firing, vs how specific the MD control signal is (2026-11-02).

Gating selectivity (Yang Eq. 1): S = (r_on - r_off) / (r_on + r_off), with baseline-corrected
soma rates: r_on = rate(pathway k on, context k) - rate(no input, context k);
r_off = rate(pathway k on, context j) - rate(no input, context j); clipped at 0; S averaged
over k = 0, 1. Plasticity frozen (pre-learning weights), soma fires freely (calibrated
balanced drive, PV->soma 0.1 nS), bAPs from the soma. 6 readout epochs x 5 s per run.

Our circuit has 2 branches with one VIP->SOM->branch channel each, so Yang's random-wiring
axes are mapped onto channel specificity:
  b  md_vip_frac q: MD_k targets a fraction q of ALL VIP cells, own channel first
     (q > 0.5 spills into the other channel); total control drive held constant
  c  p_vip2som_cross: VIP_k -> SOM_j (j != k) probability, 0 (specific) .. 0.6 (= own, uniform);
     total VIP inhibition per SOM held constant
  e  scheme 2: VIP->SOM uniform (cross = 0.6) and MD_k also excites a fraction of the OTHER
     channel's SOM cells (md2som 2.25 nS: restores ~30 Hz SOM at full targeting)
  f  scheme 2: md2som_frac = 1, VIP->SOM cross-probability swept
Synapse versions: old (w scales AMPA, rho 0.5) and yang (w scales NMDA, AMPA off, w = 1).
Run:     <py> -I experiments/gating_selectivity_fig5.py run [n_workers]
Analyse: <py> -I experiments/gating_selectivity_fig5.py analyse
Out:     results/current/gating_selectivity_fig5.json, figures/gating_selectivity_fig5.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT]
OUT = os.path.join(PROOT, 'results', 'current', 'gating_selectivity_fig5.json')
SEEDS = [42, 43, 44, 45, 46]
VERS = ['old', 'yang']
MD2SOM_NS = 2.25
PANELS = {
    'b': ('md_vip_frac', [0.05, 0.1, 0.25, 0.5, 0.75, 1.0], {}),
    'c': ('p_vip2som_cross', [0.0, 0.15, 0.3, 0.45, 0.6], {}),
    'e': ('md2som_frac', [0.0, 0.25, 0.5, 0.75, 1.0], {'p_vip2som_cross': 0.6}),
    'f': ('p_vip2som_cross', [0.0, 0.15, 0.3, 0.45, 0.6], {'md2som_frac': 1.0}),
}
CTX = [0, 1, 0, 0, 1, 1]
STIM = [None, None, 0, 1, 1, 0]


def selectivity(rates):
    base = {0: rates[0], 1: rates[1]}
    r = {(c, s): max(rates[i] - base[c], 0.0) for i, (c, s) in enumerate(zip(CTX, STIM)) if s is not None}
    S = []
    for k in (0, 1):
        on, off = r[(k, k)], r[(1 - k, k)]
        S.append((on - off) / (on + off) if on + off > 0 else float('nan'))
    return float(np.nanmean(S)) if not all(np.isnan(S)) else float('nan'), S


def _job(panel, ver, x, seed):
    from brian2 import prefs, nS
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA
    t0 = time.time()
    key, _, fixed = PANELS[panel]
    ov = {'gGABA_pv2soma': BALANCED_SOMA_G_PV2SOMA}
    kw = dict(rho_init=0.5)
    if ver == 'yang':
        ov['gAMPA'] = 0 * nS; kw = dict(rho_init=1 / 3, nmda_plastic=True)
    kw.update(fixed); kw[key] = x
    if kw.get('md2som_frac', 0) > 0:
        kw['md2som_nS'] = MD2SOM_NS
    r = run_context_protocol(CTX, T=5.0, input_mode='context', stim=STIM, plastic=False, bap_source='soma',
                             seed_val=seed, param_overrides=ov, **BALANCED_SOMA_KW, **kw)
    rates = [t['pyr_hz'] for t in r['traj']]
    S, Sk = selectivity(rates)
    return dict(panel=panel, ver=ver, x=x, seed=seed, rates=rates, S=S, S_k=Sk,
                som=[[t['som0_hz'], t['som1_hz']] for t in r['traj']], pv=[t['pv_hz'] for t in r['traj']],
                wall_s=round(time.time() - t0, 1))


def run(nw):
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    J = [(pn, v, x, s) for pn, (_, xs, _) in PANELS.items() for v in VERS for x in xs for s in SEEDS]
    J = [j for j in J if '_'.join(map(str, j)) not in done]
    print(f'{len(J)} jobs ({len(done)} done), {nw} workers', flush=True)
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(_job, *j): j for j in J}
        for fu in as_completed(futs):
            j = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                print(j, 'ERROR', repr(e), flush=True); continue
            done['_'.join(map(str, j))] = r
            json.dump(done, open(OUT, 'w'))
            print(f"{j}: S {r['S']:.3f}  rates " + ' '.join(f'{v:.1f}' for v in r['rates']) + f"  ({r['wall_s']} s)", flush=True)
    print('done', flush=True)


def analyse():
    d = json.load(open(OUT))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    col = {'old': '#D55E00', 'yang': '#0072B2'}
    lab = {'old': 'old synapse (w scales AMPA)', 'yang': 'Yang synapse (w scales NMDA)'}
    titles = {'b': 'b  MD → VIP only:\nproportion of VIP targeted by control',
              'c': 'c  MD → VIP only:\nVIP→SOM cross-channel probability',
              'e': 'e  MD → VIP + SOM (VIP→SOM uniform):\nproportion of other-channel SOM targeted',
              'f': 'f  MD → VIP + SOM (all SOM targeted):\nVIP→SOM cross-channel probability'}
    xl = {'b': 'proportion of VIP neurons targeted by control', 'c': 'P(VIP→SOM, cross-channel)',
          'e': 'proportion of SOM neurons targeted by control', 'f': 'P(VIP→SOM, cross-channel)'}
    fig, ax = plt.subplots(2, 2, figsize=(10, 8))
    summ = {}
    for a, pn in zip(ax.flat, ['b', 'c', 'e', 'f']):
        _, xs, _ = PANELS[pn]
        for v in VERS:
            M, SD = [], []
            for x in xs:
                ss = [r['S'] for r in d.values() if r['panel'] == pn and r['ver'] == v and r['x'] == x]
                M.append(np.nanmean(ss) if ss else np.nan); SD.append(np.nanstd(ss) if ss else np.nan)
            M, SD = np.array(M), np.array(SD)
            summ[f'{pn}_{v}'] = dict(x=xs, mean=M.tolist(), sd=SD.tolist())
            a.plot(xs, M, 'o-', color=col[v], label=lab[v], lw=2)
            a.fill_between(xs, M - SD, M + SD, color=col[v], alpha=0.15, lw=0)
        a.set_ylim(-0.2, 1.05); a.set_xlabel(xl[pn]); a.set_ylabel('gating selectivity')
        a.set_title(titles[pn], fontsize=10, loc='left'); a.spines[['top', 'right']].set_visible(False)
        a.axhline(0, color='0.85', lw=1, zorder=0)
    ax[0, 0].legend(frameon=False, fontsize=9, loc='lower left')
    fig.suptitle('Gating selectivity from soma output, (r_on − r_off)/(r_on + r_off): Yang 2016 Fig. 5 analogue\n'
                 '(2-branch spiking circuit, learning frozen, 5 seeds, mean ± SD)', fontsize=11)
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'gating_selectivity_fig5.png')
    fig.savefig(fp, dpi=150, facecolor='white')
    json.dump(summ, open(OUT.replace('.json', '_summary.json'), 'w'), indent=1)
    for k, v in summ.items():
        print(k, ' '.join(f'{x}:{m:.2f}±{s:.2f}' for x, m, s in zip(v['x'], v['mean'], v['sd'])))
    print('saved', fp)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(int(sys.argv[2]) if len(sys.argv) > 2 else 10)
    else:
        analyse()
