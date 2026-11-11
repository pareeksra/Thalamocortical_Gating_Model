"""
specificity_test.py -- step 1 after the 2026-11-10 verdict: how much does the canonical
model depend on the branch-specific MD_k -> VIP_k -> SOM_k -> branch k channels (assumption
G2)? Zhang 2025 shows MD -> VIP -> SOM disinhibition but not that it is branch-specific.

Three ways to mix the channels, each from specific (0) to uniform; total drive held constant:
  md_vip_frac     q: MD_k targets a fraction q of ALL VIP cells (0.5 = own channel only,
                  1 = all VIP cells, weight x 0.5/q)
  p_vip2som_cross VIP_k -> SOM_j (j != k) probability, 0 .. 0.6 (= own probability);
                  VIP->SOM weight x p_own/(p_own + p_cross)
  som2dend_cross  SOM_k -> other branch fraction, 0 .. 0.5 (synapse counts kept)
Per level, 5 seeds (42-46), canonical model:
  gating  -- 'always' mode, 8 x 3 s in context A: rho_free (branch 0), rho_inh (branch 1);
             SOM rate per channel in context A
  S       -- Yang Fig. 5 protocol, plasticity frozen (gating_selectivity_fig5)
  S_learn -- learn A (context A) then B (context B), 'patterns' mode, overlap 0, 8 x 3 s each
             at 50 Hz; frozen readout at 10 Hz/synapse (experiments/readout.py)
  ret_A   -- mean rho of A's synapses on branch 0 after B / after A (A silent during B)
Pass (as R3): gating (free > 0.65, inh < 0.5, ratio >= 2), S > 0.5, S_learn > 0.5.

Prediction (written before running): all three measures fall monotonically with mixing and
reach ~0 at uniform wiring (Yang Fig. 5: selectivity collapses with non-specific control).
Expected tolerance: S_learn > 0.5 up to about 25% of a SOM cell's VIP input from the wrong
channel (p_vip2som_cross ~0.15-0.2), md_vip_frac <= ~0.625, som2dend_cross <= ~0.1-0.15.
ret_A should stay ~1 at every level (A's inputs are silent during B).

Run:     <py> -I experiments/specificity_test.py run [n_workers]
Analyse: <py> -I experiments/specificity_test.py analyse
Out:     results/current/specificity_test.json, _summary.json, figures/specificity_test.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
OUT = os.path.join(PROOT, 'results', 'current', 'specificity_test.json')
SEEDS = [42, 43, 44, 45, 46]
AXES = {
    'md_vip_frac': [0.5, 0.625, 0.75, 0.875, 1.0],
    'p_vip2som_cross': [0.0, 0.075, 0.15, 0.3, 0.45, 0.6],
    'som2dend_cross': [0.0, 0.05, 0.1, 0.2, 0.3, 0.5],
}
SPECIFIC = {'md_vip_frac': 0.5, 'p_vip2som_cross': 0.0, 'som2dend_cross': 0.0}
LABEL = {'md_vip_frac': 'MD→VIP: fraction of all VIP targeted (0.5 = own channel)',
         'p_vip2som_cross': 'VIP→SOM cross-channel probability (0.6 = uniform)',
         'som2dend_cross': 'SOM→dendrite cross-branch fraction (0.5 = uniform)'}
N_EP = 8


def _job(axis, x, seed):
    out = measure({axis: x}, seed)
    out.update(axis=axis, x=x)
    return out


def measure(kw, seed):
    """Gating, S (Fig. 5, frozen), S_learn and ret_A of the canonical model with run_context_protocol
    keyword overrides kw (also used by zhang_wiring_test.py)."""
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA
    from gating_selectivity_fig5 import selectivity, CTX, STIM
    from readout import readout_S
    t0 = time.time()
    out = dict(seed=seed, kw={k: (v if isinstance(v, (int, float, str)) else repr(v)) for k, v in kw.items()})
    kw = dict(kw); kw_ov = kw.pop('param_overrides', None) or {}
    kw.setdefault('vip2som_scale', 1.0)   # these sweeps were run at VIP->SOM x1 (before x0.25 became canonical)

    def run_context_protocol(*a, _run=run_context_protocol, **c):   # kw + caller's call; param_overrides merged
        ov = {**kw_ov, **(c.pop('param_overrides', None) or {})}
        return _run(*a, param_overrides=ov or None, **{**kw, **c})
    tr = run_context_protocol([0] * N_EP, T=3.0, input_mode='always', seed_val=seed)['traj']
    out['rho_free'], out['rho_inh'] = tr[-1]['rho0'], tr[-1]['rho1']
    out['som_A'] = [float(np.mean([t['som0_hz'] for t in tr])), float(np.mean([t['som1_hz'] for t in tr]))]
    out['vip_A'] = [float(np.mean([t['vip0_hz'] for t in tr])), float(np.mean([t['vip1_hz'] for t in tr]))]
    out['pv_A'] = float(np.mean([t['pv_hz'] for t in tr]))
    r = run_context_protocol(CTX, T=5.0, input_mode='context', stim=STIM, plastic=False, bap_source='soma',
                             seed_val=seed, param_overrides={'gGABA_pv2soma': BALANCED_SOMA_G_PV2SOMA},
                             **BALANCED_SOMA_KW)
    out['S_rates'] = [t['pyr_hz'] for t in r['traj']]
    out['S'], _ = selectivity(out['S_rates'])
    lt = run_context_protocol([0] * N_EP + [1] * N_EP, T=3.0, input_mode='patterns', overlap=0.0,
                              exc_rate=50.0, seed_val=seed)
    a, b = lt['traj'][N_EP - 1], lt['traj'][-1]
    iA = np.array(lt['idx_A'])
    out['rhoA_b0_afterA'] = float(np.mean(np.asarray(a['rho0_syn'])[iA]))
    out['rhoA_b1_afterA'] = float(np.mean(np.asarray(a['rho1_syn'])[iA]))
    out['ret_A'] = float(np.mean(np.asarray(b['rho0_syn'])[iA]) / out['rhoA_b0_afterA'])
    rd = readout_S(b['rho0_syn'], b['rho1_syn'], 0.0, seed, run=run_context_protocol)
    out['S_learn'], out['S_learn_rates'] = rd['S'], rd['rates']
    out['wall_s'] = round(time.time() - t0, 1)
    return out


# Follow-up (written after the first run, which showed the VIP stage tolerates < 11% cross-talk
# while the other channel's SOM is silenced -- prediction: VIP->SOM is far stronger than needed,
# so a weaker VIP->SOM weight keeps gating at x1 and widens the cross-talk tolerance).
WEAK_G = [0.1, 0.25, 0.5]   # x gGABA_som (VIP->SOM, 3 nS)
WEAK_X = [('p_vip2som_cross', 0.0), ('p_vip2som_cross', 0.075), ('p_vip2som_cross', 0.15), ('md_vip_frac', 0.625)]


def _weak_job(g, axis, x, seed):
    from parameters import som_params
    kw = {'param_overrides': {'gGABA_som': som_params['gGABA_som'] * g}}
    if not (axis == 'p_vip2som_cross' and x == 0.0):
        kw[axis] = x
    out = measure(kw, seed)
    out.update(axis=f'weak{g}_{axis}', x=x, g=g)
    return out


def run_weak(nw):
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    J = [(g, a, x, s) for g in WEAK_G for a, x in WEAK_X for s in SEEDS if f'weak{g}_{a}_{x}_{s}' not in done]
    print(f'{len(J)} follow-up jobs, {nw} workers', flush=True)
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(_weak_job, *j): j for j in J}
        for fu in as_completed(futs):
            j = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                print(j, 'ERROR', repr(e), flush=True); continue
            done[f'weak{j[0]}_{j[1]}_{j[2]}_{j[3]}'] = r
            json.dump(done, open(OUT, 'w'))
            print(f"weak{j[0]} {j[1]} {j[2]} s{j[3]}: free {r['rho_free']:.3f} inh {r['rho_inh']:.3f} "
                  f"SOM {r['som_A'][0]:.1f}/{r['som_A'][1]:.1f} S {r['S']:.2f} S_learn {r['S_learn']:.2f} ({r['wall_s']} s)", flush=True)
    print('done', flush=True)


def key(a, x, s):
    return f'{a}_{x}_{s}'


def jobs():
    """The fully specific wiring (the canonical default) is shared by all axes: run once as 'specific'."""
    return [('specific', 0.0, s) for s in SEEDS] + [(a, x, s) for a, xs in AXES.items() for x in xs
                                                    if x != SPECIFIC[a] for s in SEEDS]


def run(nw):
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    J = [j for j in jobs() if key(*j) not in done]
    print(f'{len(J)} jobs ({len(done)} done), {nw} workers', flush=True)
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {}
        for j in J:
            a, x, s = j
            futs[ex.submit(_job, 'som2dend_cross' if a == 'specific' else a, 0.0 if a == 'specific' else x, s)] = j
        for fu in as_completed(futs):
            j = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                print(j, 'ERROR', repr(e), flush=True); continue
            r['axis'], r['x'] = j[0], j[1]
            done[key(*j)] = r
            json.dump(done, open(OUT, 'w'))
            print(f"{key(*j):<26} free {r['rho_free']:.3f} inh {r['rho_inh']:.3f} SOM {r['som_A'][0]:.1f}/{r['som_A'][1]:.1f} "
                  f"S {r['S']:.2f} S_learn {r['S_learn']:.2f} ret_A {r['ret_A']:.3f} ({r['wall_s']} s)", flush=True)
    print('done', flush=True)


def summarise(d):
    spec = [r for r in d.values() if r['axis'] == 'specific']
    rows = {}
    for a, xs in AXES.items():
        for x in xs:
            rs = spec if x == SPECIFIC[a] else [r for r in d.values() if r['axis'] == a and r['x'] == x]
            if not rs:
                continue
            m = lambda k: float(np.nanmean([r[k] for r in rs]))
            row = dict(axis=a, x=x, n=len(rs), rho_free=m('rho_free'), rho_inh=m('rho_inh'),
                       som_on=float(np.mean([r['som_A'][0] for r in rs])), som_off=float(np.mean([r['som_A'][1] for r in rs])),
                       S=m('S'), S_sd=float(np.nanstd([r['S'] for r in rs])),
                       S_learn=m('S_learn'), S_learn_sd=float(np.nanstd([r['S_learn'] for r in rs])),
                       ret_A=m('ret_A'), rhoA_b1=m('rhoA_b1_afterA'))
            row['gated_seeds'] = sum(r['rho_free'] > 0.65 and r['rho_inh'] < 0.5 and r['rho_free'] / max(r['rho_inh'], 1e-9) >= 2 for r in rs)
            row['pass'] = bool(row['gated_seeds'] == len(rs) and row['S'] > 0.5 and row['S_learn'] > 0.5)
            rows[f'{a}_{x}'] = row
    return rows


def analyse():
    d = json.load(open(OUT))
    rows = summarise(d)
    json.dump(rows, open(OUT.replace('.json', '_summary.json'), 'w'), indent=1)
    print(f"{'axis':<16} {'x':>6} | {'free':>5} {'inh':>5} gated | SOM on/off | {'S':>10} | {'S_learn':>10} | ret_A | pass")
    for r in rows.values():
        print(f"{r['axis']:<16} {r['x']:6.3f} | {r['rho_free']:.3f} {r['rho_inh']:.3f} {r['gated_seeds']}/{r['n']}   | "
              f"{r['som_on']:4.1f}/{r['som_off']:4.1f} | {r['S']:+.2f}±{r['S_sd']:.2f} | {r['S_learn']:+.2f}±{r['S_learn_sd']:.2f} | "
              f"{r['ret_A']:.3f} | {'Y' if r['pass'] else '.'}")
    weak = {}
    for g in WEAK_G:
        for a, x in WEAK_X:
            rs = [r for r in d.values() if r['axis'] == f'weak{g}_{a}' and r['x'] == x]
            if rs:
                m = lambda k: float(np.nanmean([r[k] for r in rs]))
                gs = sum(r['rho_free'] > 0.65 and r['rho_inh'] < 0.5 and r['rho_free'] / max(r['rho_inh'], 1e-9) >= 2 for r in rs)
                weak[f'weak{g}_{a}_{x}'] = w = dict(g=g, axis=a, x=x, n=len(rs), rho_free=m('rho_free'), rho_inh=m('rho_inh'),
                    som_on=float(np.mean([r['som_A'][0] for r in rs])), som_off=float(np.mean([r['som_A'][1] for r in rs])),
                    S=m('S'), S_learn=m('S_learn'), gated_seeds=gs)
                w['pass'] = bool(gs == len(rs) and w['S'] > 0.5 and w['S_learn'] > 0.5)
    if weak:
        print('\nfollow-up: weaker VIP->SOM (x gGABA_som)')
        for w in weak.values():
            print(f"x{w['g']:<5} {w['axis']:<16} {w['x']:6.3f} | {w['rho_free']:.3f} {w['rho_inh']:.3f} {w['gated_seeds']}/{w['n']} | "
                  f"{w['som_on']:4.1f}/{w['som_off']:4.1f} | S {w['S']:+.2f} | S_learn {w['S_learn']:+.2f} | {'Y' if w['pass'] else '.'}")
        rows['followup_weak_vip2som'] = weak
        json.dump(rows, open(OUT.replace('.json', '_summary.json'), 'w'), indent=1)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
    for ax, (a, xs) in zip(axs, AXES.items()):
        rs = [rows[f'{a}_{x}'] for x in xs if f'{a}_{x}' in rows]
        xx = [r['x'] for r in rs]
        ax.errorbar(xx, [r['S'] for r in rs], [r['S_sd'] for r in rs], marker='o', capsize=3, label='S, before learning (Fig. 5)')
        ax.errorbar(xx, [r['S_learn'] for r in rs], [r['S_learn_sd'] for r in rs], marker='s', capsize=3, label='S after learning (10 Hz readout)')
        ax.plot(xx, [r['rho_free'] - r['rho_inh'] for r in rs], 'k^--', label='ρ_free − ρ_inh')
        ax.axhline(0.5, color='grey', lw=0.8, ls=':')
        ax.axhline(0, color='grey', lw=0.5)
        ax.set_xlabel(LABEL[a], fontsize=8); ax.set_title(a)
    axs[0].set_ylabel('selectivity / ρ difference'); axs[0].legend(fontsize=7)
    fig.suptitle('Branch specificity of MD→VIP→SOM→dendrite (canonical model, 5 seeds; left end = specific)')
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'specificity_test.png')
    fig.savefig(fp, dpi=130); print('saved', fp)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(int(sys.argv[2]) if len(sys.argv) > 2 else 11)
    elif sys.argv[1] == 'weak':
        run_weak(int(sys.argv[2]) if len(sys.argv) > 2 else 11)
    else:
        analyse()
