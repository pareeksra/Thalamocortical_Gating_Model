"""
phase2_snr_breakdown.py
========================
Phase 2B of the roadmap: sweep biological noise in the full MD -> PV / MD -> VIP ->
SOM disinhibition circuit (model/full_circuit.py) and measure the point at which
branch-specific gating breaks down.

Protocol: MD drive is held at md_signal_rate=0 Hz throughout (the network's resting
state -- SOM receives no VIP-mediated suppression, so its ~22 pA baseline current
drives it to fire and tonically inhibit dendritic branch 0, while branch 1 is
structurally never inhibited). This is the same "SOM-active" condition validated in
Phase 1 (free/inhibited ratio ~43-65) and Section 2.3 of docs/Validation_Report.docx,
now reproduced through the full circuit instead of a hand-set SOM bias.

`noise_level` (model/full_circuit.py) jointly scales three biologically distinct
noise sources introduced in Phase 2A:
  1. MD noise Poisson input (independent of the md_signal_rate=0 signal channel)
  2. vesicle-release variance on the plastic NMDA pathway (CV up to 0.30)
  3. background membrane-potential fluctuation on SOM and VIP

Gating Selectivity is defined as ratio = rho_free / rho_inhibited (branch 1 / branch
0), matching Section 2.3's definition. A value near 1 means the two branches are
statistically indistinguishable -- the network has stopped gating.
"""
import os
import sys

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
FIGROOT = os.path.join(PROOT, 'figures')

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from full_circuit import build_gating_circuit

NOISE_LEVELS = [0.0, 0.25, 0.30, 0.35, 0.40, 0.45, 0.5, 0.75, 1.0, 1.5, 2.0]
N_SEEDS = 3
T_SIM = 3.0


def sweep():
    records = []
    for nl in NOISE_LEVELS:
        ratios, r0s, r1s, som_rates = [], [], [], []
        for s in range(N_SEEDS):
            out = build_gating_circuit(T=T_SIM, md_signal_rate=0.0, noise_level=nl,
                                        seed_val=42 + s)
            ratios.append(out['ratio'])
            r0s.append(out['r0']); r1s.append(out['r1'])
            som_rates.append(out['som_rate'])
        rec = dict(noise_level=nl, ratio_mean=float(np.mean(ratios)),
                   ratio_sem=float(np.std(ratios, ddof=1) / np.sqrt(N_SEEDS)),
                   r0_mean=float(np.mean(r0s)), r1_mean=float(np.mean(r1s)),
                   som_rate_mean=float(np.mean(som_rates)))
        records.append(rec)
        print(f"noise_level={nl:.2f}  ratio={rec['ratio_mean']:.2f}+/-{rec['ratio_sem']:.2f}  "
              f"rho0={rec['r0_mean']:.3f}  rho1={rec['r1_mean']:.3f}  "
              f"SOM={rec['som_rate_mean']:.1f} Hz", flush=True)
    return records


def find_breaking_point(records, threshold=1.5):
    """First noise_level at which mean ratio drops below `threshold`."""
    for rec in records:
        if rec['ratio_mean'] < threshold:
            return rec['noise_level']
    return None


def find_transition_zone(records, cv_threshold=0.5):
    """Noise-level range over which the across-seed coefficient of variation of the
    ratio exceeds cv_threshold -- i.e. where individual runs disagree on whether
    gating held or failed, rather than the population mean smoothly declining."""
    unstable = [r['noise_level'] for r in records
                if r['ratio_mean'] > 0 and (r['ratio_sem'] * np.sqrt(N_SEEDS)) / r['ratio_mean'] > cv_threshold]
    if not unstable:
        return None
    return min(unstable), max(unstable)


def plot(records, out_path):
    nl = [r['noise_level'] for r in records]
    ratio = [r['ratio_mean'] for r in records]
    sem = [r['ratio_sem'] for r in records]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.errorbar(nl, ratio, yerr=sem, fmt='o-', color='#1565C0', lw=2, capsize=3,
                label=f'Gating selectivity ($n={N_SEEDS}$ seeds/point)')
    ax.axhline(1.0, color='gray', ls='--', lw=1, label='No gating (ratio = 1)')
    zone = find_transition_zone(records)
    if zone is not None:
        ax.axvspan(zone[0], zone[1], color='#C62828', alpha=0.15,
                   label=f'Unstable transition zone: noise = {zone[0]:.2f}-{zone[1]:.2f}')
    bp = find_breaking_point(records)
    if bp is not None:
        ax.axvline(bp, color='#C62828', ls=':', lw=1.5,
                   label=f'Gating collapses (ratio < 1.5): noise = {bp:.2f}')
    ax.set_xlabel('Noise level (joint scale of MD noise, vesicle CV, background conductance)')
    ax.set_ylabel(r'Gating selectivity ($\rho_{free} / \rho_{inhibited}$)')
    ax.set_title('Branch-specific gating selectivity under biological noise')
    ax.legend(fontsize=8, loc='best')
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Saved {out_path}")


if __name__ == '__main__':
    print("=== Phase 2B: SNR / noise-robustness sweep ===")
    records = sweep()
    zone = find_transition_zone(records)
    bp = find_breaking_point(records)
    if zone is not None:
        print(f"\nUnstable transition zone (seeds disagree on pass/fail): "
              f"noise_level = {zone[0]:.2f}-{zone[1]:.2f}")
    if bp is not None:
        print(f"Gating selectivity falls and stays below 1.5 from noise_level={bp:.2f} onward")
    else:
        print("\nGating selectivity remained >= 1.5 across the full sweep range.")
    os.makedirs(FIGROOT, exist_ok=True)
    plot(records, os.path.join(FIGROOT, 'phase2_snr_curve.png'))
