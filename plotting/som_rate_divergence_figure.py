"""
som_rate_divergence_figure.py -- figure for the SOM-rate divergence resolution.
===============================================================================
Panel A: gating ratio vs SOM rate for three tau_GABA,dend values. The fail->pass
         crossover shifts to LOWER rate as tau grows -> gating tracks coverage
         (rate x tau), not rate. Yang's ~10 Hz marked; the model reaches it at tau=40ms.
Panel B: critical SOM rate vs tau, with the rate x tau product annotated (constant
         for 10->20 ms = the duty-cycle law).

Data from docs/tau_gaba_duty_cycle_results.json (reduced Phase-1, seed 42, 8 epochs).
Run: <venv>/python -I plotting/som_rate_divergence_figure.py
Out: figures/som_rate_divergence.png
"""
import os, sys, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(PROOT, 'docs', 'tau_gaba_duty_cycle_results.json')
OUT = os.path.join(PROOT, 'figures', 'som_rate_divergence.png')

# CVD-safe sequential-by-tau (Okabe-Ito ordered light->dark-ish)
TAU_COLOR = {10.0: '#E69F00', 20.0: '#0072B2', 40.0: '#009E73'}
RATIO_PASS = 2.0
YANG_RATE = 10.0


def main():
    d = json.load(open(RES))
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(11, 4.5),
                                   gridspec_kw={'width_ratios': [1.5, 1]})

    # Panel A: ratio vs rate per tau
    for tau in (10.0, 20.0, 40.0):
        pts = sorted(d[str(tau)]['points'], key=lambda p: p['som_rate_hz'])
        rates = [p['som_rate_hz'] for p in pts]
        ratios = [p['ratio'] for p in pts]
        c = TAU_COLOR[tau]
        axA.plot(rates, ratios, '-o', color=c, lw=2, ms=6, label=f'τ = {int(tau)} ms')
        xr = d[str(tau)]['crossover_rate_hz']
        axA.plot([xr], [RATIO_PASS], marker='v', color=c, ms=11, zorder=5,
                 markeredgecolor='white', markeredgewidth=1)
    axA.axhline(RATIO_PASS, color='0.5', ls='--', lw=1, zorder=1)
    axA.text(axA.get_xlim()[1] if False else 95, RATIO_PASS + 0.12, 'gating threshold (ratio 2.0)',
             ha='right', va='bottom', fontsize=8.5, color='0.4')
    axA.axvline(YANG_RATE, color='0.3', ls=':', lw=1.2)
    axA.text(YANG_RATE + 1, 5.3, "Yang's ~10 Hz\n(experimental)", fontsize=8.5, color='0.3',
             ha='left', va='top')
    axA.set_xlabel('SOM firing rate (Hz)')
    axA.set_ylabel('gating ratio  (rho_free / rho_inhib)')
    axA.set_title('A   Gating crossover shifts to lower rate as τ grows', fontsize=11, loc='left')
    axA.set_xlim(5, 72); axA.set_ylim(0.8, 5.6)
    axA.legend(frameon=False, loc='center right', fontsize=10)
    axA.spines[['top', 'right']].set_visible(False)

    # Panel B: critical rate vs tau + rate*tau product
    taus = [10.0, 20.0, 40.0]
    crit = [d[str(t)]['crossover_rate_hz'] for t in taus]
    prod = [d[str(t)]['rate_x_tau_Hz_ms'] for t in taus]
    for t, cr in zip(taus, crit):
        axB.plot([t], [cr], 'o', color=TAU_COLOR[t], ms=11, zorder=3,
                 markeredgecolor='white', markeredgewidth=1.2)
    # pure 1/tau reference anchored at tau=20
    tt = np.linspace(9, 42, 100)
    axB.plot(tt, crit[1] * 20.0 / tt, color='0.6', ls='--', lw=1.3, zorder=1,
             label='pure 1/τ (coverage law)')
    for t, cr, pr in zip(taus, crit, prod):
        axB.annotate(f'{cr:.0f} Hz\n(rate·τ={pr:.0f})', (t, cr), textcoords='offset points',
                     xytext=(8, 6), fontsize=8.5, color=TAU_COLOR[t])
    axB.set_xlabel('τ_GABA,dend (ms)')
    axB.set_ylabel('critical SOM rate (Hz)')
    axB.set_title('B   Critical rate ∝ 1/τ\n(duty-cycle law; saturates at long τ)',
                  fontsize=11, loc='left')
    axB.set_xlim(7, 44); axB.set_ylim(8, 40)
    axB.legend(frameon=False, fontsize=9, loc='upper right')
    axB.spines[['top', 'right']].set_visible(False)

    fig.suptitle('SOM-rate divergence resolved: gating tracks inhibition coverage '
                 '(rate × τ), not firing rate', fontsize=12.5, fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches='tight', facecolor='white')
    print(f'Saved {OUT}')


if __name__ == '__main__':
    main()
