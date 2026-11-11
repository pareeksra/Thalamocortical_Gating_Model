"""
zhang_wiring_test.py -- step 2 after the 2026-11-10 verdict: add the two interneuron
connections of Zhang 2025's mask that the canonical model lacks, SOM -> VIP and PV -> PV,
and ask whether MD-gated learning survives.

Zhang 2025 is a rate RNN: it gives signs, not conductances, and does not say which SOM
cells inhibit which VIP cells. So:
  som2vip  weight 0.01-0.5 nS (p 0.5) x wiring
             'uniform'  every SOM -> every VIP channel
             'own'      SOM_k -> VIP_k (mutual inhibition inside a channel)
             'cross'    SOM_k -> VIP_j, j != k (the inactive context's SOM brakes VIP_k)
           at MD 25 Hz; 'uniform' also at MD 50 Hz (can stronger MD compensate?)
  pv2pv    weight 0.05-1 nS (p 0.5, no autapses)
Scale: mean SOM->VIP conductance ~ 20 inputs x 30 Hz x w x 20 ms = 12 w nS (w in nS),
vs MD -> VIP ~0.4 nS at 25 Hz; so w ~ 0.03 nS already matches the MD drive.
Per condition, 5 seeds, specificity_test.measure: gating (rho_free, rho_inh), VIP/SOM/PV
rates in context A, S (Fig. 5, frozen), S_learn (learn A then B, 10 Hz readout), ret_A.

Prediction (written before running; smoke test: uniform 1 nS at MD 25 Hz -> VIP 0 Hz,
SOM_k 29 Hz, no gating):
  - SOM->VIP abolishes gating above a weight of order 0.03-0.1 nS (comparable to the MD
    drive); 'cross' and 'uniform' worst, 'own' less (once VIP_k wins it silences its own
    SOM_k, a bistable switch).
  - MD 50 Hz moves the failure point up by about x2.
  - PV->PV lowers PV rates and changes nothing about gating, learning or retention (PV
    acts on the soma only).
Run:     <py> -I experiments/zhang_wiring_test.py run [n_workers]
Analyse: <py> -I experiments/zhang_wiring_test.py analyse
Out:     results/current/zhang_wiring_test.json, _summary.json, figures/zhang_wiring_test.png
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
OUT = os.path.join(PROOT, 'results', 'current', 'zhang_wiring_test.json')
SEEDS = [42, 43, 44, 45, 46]
W_SV = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5]
W_PP = [0.05, 0.1, 0.2, 0.5, 1.0]


def conditions():
    C = {'canonical': {}, 'canonical_md50': dict(md_on_rate=50.0)}
    for wir in ('uniform', 'own', 'cross'):
        for w in W_SV:
            C[f'som2vip_{wir}_{w}'] = dict(som2vip_nS=w, som2vip_wiring=wir)
    for w in W_SV:
        C[f'som2vip_uniform_{w}_md50'] = dict(som2vip_nS=w, som2vip_wiring='uniform', md_on_rate=50.0)
    for w in W_PP:
        C[f'pv2pv_{w}'] = dict(pv2pv_nS=w)
    return C


def _job(name, seed):
    from specificity_test import measure
    out = measure(conditions()[name], seed)
    out['cond'] = name
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
            print(f"{j[0]:<28} s{j[1]} free {r['rho_free']:.3f} inh {r['rho_inh']:.3f} VIP {r['vip_A'][0]:5.1f} "
                  f"SOM {r['som_A'][0]:4.1f}/{r['som_A'][1]:4.1f} PV {r['pv_A']:5.1f} S {r['S']:+.2f} "
                  f"S_learn {r['S_learn']:+.2f} ret_A {r['ret_A']:.3f} ({r['wall_s']} s)", flush=True)
    print('done', flush=True)


def summarise(d):
    rows = {}
    for c in conditions():
        rs = [r for r in d.values() if r['cond'] == c]
        if not rs:
            continue
        m = lambda k: float(np.nanmean([r[k] for r in rs]))
        sd = lambda k: float(np.nanstd([r[k] for r in rs]))
        row = dict(n=len(rs), rho_free=m('rho_free'), rho_inh=m('rho_inh'),
                   vip_on=float(np.mean([r['vip_A'][0] for r in rs])),
                   som_on=float(np.mean([r['som_A'][0] for r in rs])), som_off=float(np.mean([r['som_A'][1] for r in rs])),
                   pv=m('pv_A'), S=m('S'), S_sd=sd('S'), S_learn=m('S_learn'), S_learn_sd=sd('S_learn'), ret_A=m('ret_A'))
        row['gated_seeds'] = sum(r['rho_free'] > 0.65 and r['rho_inh'] < 0.5 and r['rho_free'] / max(r['rho_inh'], 1e-9) >= 2 for r in rs)
        row['pass'] = bool(row['gated_seeds'] == len(rs) and row['S'] > 0.5 and row['S_learn'] > 0.5)
        rows[c] = row
    return rows


def analyse():
    d = json.load(open(OUT))
    rows = summarise(d)
    json.dump(rows, open(OUT.replace('.json', '_summary.json'), 'w'), indent=1)
    print(f"{'condition':<28} | free   inh  gated | VIP_on SOM on/off   PV | {'S':>10} | {'S_learn':>10} | ret_A | pass")
    for c, r in rows.items():
        print(f"{c:<28} | {r['rho_free']:.3f} {r['rho_inh']:.3f} {r['gated_seeds']}/{r['n']} | {r['vip_on']:6.1f} "
              f"{r['som_on']:4.1f}/{r['som_off']:4.1f} {r['pv']:5.1f} | {r['S']:+.2f}±{r['S_sd']:.2f} | "
              f"{r['S_learn']:+.2f}±{r['S_learn_sd']:.2f} | {r['ret_A']:.3f} | {'Y' if r['pass'] else '.'}")
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(14, 4))
    base = rows.get('canonical')
    for wir, mk in (('uniform', 'o-'), ('own', 's-'), ('cross', '^-'), ('uniform_md50', 'o--')):
        names = [f'som2vip_uniform_{w}_md50' if wir == 'uniform_md50' else f'som2vip_{wir}_{w}' for w in W_SV]
        rs = [rows[n] for n in names if n in rows]
        ws = [w for w, n in zip(W_SV, names) if n in rows]
        lab = 'uniform, MD 50 Hz' if wir == 'uniform_md50' else wir
        axs[0].plot(ws, [r['S_learn'] for r in rs], mk, label=lab)
        axs[1].plot(ws, [r['som_on'] for r in rs], mk, label=lab)
    for ax in axs[:2]:
        ax.set_xscale('log'); ax.set_xlabel('SOM→VIP weight (nS)')
    if base:
        axs[0].axhline(base['S_learn'], color='k', lw=0.8, ls=':', label='canonical (no SOM→VIP)')
    axs[0].axhline(0.5, color='grey', lw=0.6, ls=':')
    axs[0].set_ylabel('S after learning (10 Hz readout)'); axs[0].legend(fontsize=7)
    axs[1].set_ylabel("SOM rate on the context's own channel (Hz)")
    rs = [rows[f'pv2pv_{w}'] for w in W_PP if f'pv2pv_{w}' in rows]
    ws = [w for w in W_PP if f'pv2pv_{w}' in rows]
    axs[2].plot(ws, [r['S_learn'] for r in rs], 'o-', label='S after learning')
    axs[2].plot(ws, [r['S'] for r in rs], 's-', label='S before (Fig. 5)')
    ax2 = axs[2].twinx(); ax2.plot(ws, [r['pv'] for r in rs], 'k^--', label='PV rate'); ax2.set_ylabel('PV rate (Hz)')
    axs[2].set_xscale('log'); axs[2].set_xlabel('PV→PV weight (nS)'); axs[2].legend(fontsize=7, loc='lower left')
    fig.suptitle("Zhang 2025's SOM→VIP and PV→PV added to the canonical model (5 seeds)")
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'zhang_wiring_test.png')
    fig.savefig(fp, dpi=130); print('saved', fp)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(int(sys.argv[2]) if len(sys.argv) > 2 else 11)
    else:
        analyse()
