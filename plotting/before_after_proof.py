"""
before_after_proof.py -- consolidated before->after proof for the 2026-10-14/15 session.
=========================================================================================
Three findings, each as a before/after pair, from committed data:

  1. Gating reliability: 25 Hz N=20 baseline 18/20 -> N=100 (variance-reduced) 20/20.
     (docs/full_circuit_reliability_25hz_results.json ; docs/n_som_reliability_n100_results.json)
  2. SOM-rate divergence: critical SOM rate vs tau_GABA,dend -- "before" the model needed
     ~2x Yang's 10 Hz at tau=20 ms; "after" (understanding duty cycle) it recovers Yang's
     ~10 Hz regime at tau=40 ms. (docs/tau_gaba_duty_cycle_results.json)
  3. No catastrophic forgetting: inhibition-only context switch 30% retention (before) ->
     input-gated 100% retention (after).
     (docs/retention_results_{inhibonly,inputgated}.json)

Run: <venv>/python -I plotting/before_after_proof.py -> figures/before_after_proof.png
"""
import os, sys, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(PROOT, 'docs')
BEFORE = '#D55E00'   # vermillion = the broken / baseline state
AFTER = '#009E73'    # green = the resolved state


def load(path):
    return json.load(open(os.path.join(DOCS, path)))


def main():
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))

    # ---- Panel 1: gating reliability ----
    b = load('full_circuit_reliability_25hz_results.json')
    n = load('n_som_reliability_n100_results.json')
    b_pass = 100 * sum(r['passed'] for r in b) / len(b)
    n_pass = 100 * sum(r['passed'] for r in n) / len(n)
    ax = axes[0]
    bars = ax.bar([0, 1], [b_pass, n_pass], width=0.6, color=[BEFORE, AFTER],
                  edgecolor='white', linewidth=1.5, zorder=3)
    ax.text(0, b_pass + 1.5, f"{sum(r['passed'] for r in b)}/{len(b)}", ha='center',
            fontsize=12, fontweight='bold', color=BEFORE)
    ax.text(1, n_pass + 1.5, f"{sum(r['passed'] for r in n)}/{len(n)}", ha='center',
            fontsize=12, fontweight='bold', color=AFTER)
    ax.text(0, 46, 'fails\n44, 53', ha='center', va='center', color='white',
            fontsize=9, fontweight='bold')
    ax.axhline(100, color='0.75', ls=':', lw=1)
    ax.set_xticks([0, 1]); ax.set_xticklabels(['BEFORE\nN=20 (25 Hz)', 'AFTER\nN=100'])
    ax.set_ylim(0, 110); ax.set_ylabel('seeds gating correctly (%)')
    ax.set_title('1  Gating reliability\n(small-N disinhibition variance)', fontsize=10.5, loc='left')
    ax.spines[['top', 'right']].set_visible(False)

    # ---- Panel 2: SOM-rate divergence (critical rate vs tau) ----
    d = load('tau_gaba_duty_cycle_results.json')
    taus = sorted(float(k) for k in d)
    crit = [d[str(t)]['crossover_rate_hz'] for t in taus]
    ax = axes[1]
    ax.plot(taus, crit, '-o', color='0.35', lw=2, ms=7, zorder=3)
    # mark Yang's tau=20 (BEFORE: model needs ~18 Hz, 2x Yang's 10) and tau=40 (AFTER: ~12 Hz, ~Yang)
    i20 = taus.index(20.0); i40 = taus.index(40.0)
    ax.plot(20.0, crit[i20], 'o', color=BEFORE, ms=12, zorder=4, markeredgecolor='white', markeredgewidth=1.3)
    ax.plot(40.0, crit[i40], 'o', color=AFTER, ms=12, zorder=4, markeredgecolor='white', markeredgewidth=1.3)
    ax.axhline(10.0, color='0.5', ls=':', lw=1.2)
    ax.text(41, 10.0, "Yang's ~10 Hz", fontsize=8.5, color='0.4', ha='right', va='bottom')
    ax.annotate(f"BEFORE: τ=20 ms\nneeds {crit[i20]:.0f} Hz (~2× Yang)", (20, crit[i20]),
                xytext=(21, crit[i20] + 8), fontsize=8.5, color=BEFORE,
                arrowprops=dict(arrowstyle='->', color=BEFORE))
    ax.annotate(f"AFTER: τ=40 ms\nrecovers {crit[i40]:.0f} Hz (~Yang)", (40, crit[i40]),
                xytext=(26, crit[i40] - 6), fontsize=8.5, color=AFTER,
                arrowprops=dict(arrowstyle='->', color=AFTER))
    ax.set_xlabel('τ_GABA,dend (ms)'); ax.set_ylabel('critical SOM rate (Hz)')
    ax.set_title('2  SOM-rate divergence\n(gating tracks rate × τ coverage)', fontsize=10.5, loc='left')
    ax.set_xlim(7, 44); ax.set_ylim(5, 42)
    ax.spines[['top', 'right']].set_visible(False)

    # ---- Panel 3: catastrophic forgetting ----
    di = load('retention_results_inhibonly.json')
    dg = load('retention_results_inputgated.json')
    ax = axes[2]
    for d2, color, lab in [(di, BEFORE, 'BEFORE: inhibition-only'),
                           (dg, AFTER, 'AFTER: input-gated')]:
        t = d2['traj']
        ax.plot(t['epoch'], t['rho0'], '-o', color=color, lw=2, ms=3.5, label=lab)
    nA = di['n_epochs_per_phase']
    ax.axvline(nA, color='0.5', ls='--', lw=1)
    ax.text(nA/2, 1.03, 'learn A', ha='center', fontsize=8.5, color='0.4')
    ax.text(nA*1.5, 1.03, 'learn B', ha='center', fontsize=8.5, color='0.4')
    ax.annotate(f"{di['rho0_retention_frac']*100:.0f}% retained", (16, di['traj']['rho0'][-1]),
                xytext=(9, 0.33), fontsize=9, color=BEFORE, fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=BEFORE))
    ax.annotate(f"{dg['rho0_retention_frac']*100:.0f}% retained", (16, dg['traj']['rho0'][-1]),
                xytext=(9, 1.0), fontsize=9, color=AFTER, fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=AFTER))
    ax.set_xlabel('epoch'); ax.set_ylabel("branch-0 (context A) rho")
    ax.set_ylim(0, 1.12)
    ax.set_title('3  No catastrophic forgetting\n(needs context-specific input)', fontsize=10.5, loc='left')
    ax.legend(frameon=False, fontsize=8.5, loc='center left')
    ax.spines[['top', 'right']].set_visible(False)

    fig.suptitle('Thalamocortical gating model — before → after (2026-10-14/15 session)',
                 fontsize=13, fontweight='bold', y=1.03)
    fig.tight_layout()
    out = os.path.join(PROOT, 'figures', 'before_after_proof.png')
    fig.savefig(out, dpi=150, bbox_inches='tight', facecolor='white')
    print(f'Saved {out}')
    print(f"  1 reliability: {sum(r['passed'] for r in b)}/{len(b)} -> {sum(r['passed'] for r in n)}/{len(n)}")
    print(f"  2 SOM crit rate: tau20={crit[i20]:.1f}Hz -> tau40={crit[i40]:.1f}Hz (Yang 10Hz)")
    print(f"  3 retention: {di['rho0_retention_frac']*100:.0f}% -> {dg['rho0_retention_frac']*100:.0f}%")


if __name__ == '__main__':
    main()
