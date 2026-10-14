"""
n_som_variance_figure.py -- figure for the small-N disinhibition-variance finding.
=================================================================================
Two panels:
  (A) Per-seed branch-0 GABA conductance (gGABA0) at N=20 vs N=100 (weight-
      compensated, mean inhibition held constant). Shows the distribution NARROWS
      with N and lifts off the ~12 nS failure floor. The two baseline-failing seeds
      (44, 53) sit on that floor at N=20 and are pulled into the safe band at N=100.
  (B) Reliability: fraction of the 20 canonical seeds (40-59) that gate (ratio>2.0),
      full 10-epoch protocol. Baseline N=20 @25Hz = 18/20; N=100 (comp.) = 20/20.

Panel A uses the epoch-0 gGABA0 measurements (1-epoch probe, docs embedded below so
the figure is self-contained from committed data). Panel B reads the committed full
10-epoch sweeps:
  docs/full_circuit_reliability_25hz_results.json   (baseline N=20)
  docs/n_som_reliability_n100_results.json          (N=100, this work)

Run: <venv>/python -I plotting/n_som_variance_figure.py
Out: figures/n_som_disinhibition_variance.png
"""
import os, sys, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG_DIR = os.path.join(PROOT, 'figures')
DOCS = os.path.join(PROOT, 'docs')

# --- CVD-safe categorical pair (Okabe-Ito: blue #0072B2, vermillion #D55E00) -----
C_N20 = '#D55E00'   # baseline, the fragile condition
C_N100 = '#0072B2'  # enlarged pool, the fix
C_FAIL = '#D55E00'
GABA_FLOOR = 12.0   # nS: empirical failure floor (~6 SOM->Dend[0] synapses)

# --- Panel A data: epoch-0 branch-0 gGABA (nS) per seed, 1-epoch probe -----------
# (measured 2026-10-13/14; weight-compensated so expected mean inhibition is equal.)
SEEDS = [40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 53]
GGABA = {
    20:  {40:25.802, 41:17.863, 42:27.787, 43:19.848, 44:11.909, 45:19.848,
          46:23.817, 47:19.848, 48:21.832, 49:21.832, 50:23.817, 53:11.909},
    100: {40:19.054, 41:13.496, 42:22.229, 43:17.863, 44:18.657, 45:20.245,
          46:22.229, 47:17.863, 48:15.878, 49:19.451, 50:22.229, 53:21.038},
}
BASE_FAILS = {44, 53}


def load_reliability(path):
    d = json.load(open(path))
    npass = sum(1 for r in d if r['passed'])
    fails = sorted(r['seed'] for r in d if not r['passed'])
    return npass, len(d), fails


def main():
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(11, 4.6),
                                   gridspec_kw={'width_ratios': [1.6, 1]})

    # ---------- Panel A: gGABA distribution, N=20 vs N=100 ----------
    rng = np.random.default_rng(0)
    for xpos, N, color, lab in [(0, 20, C_N20, 'N = 20'), (1, 100, C_N100, 'N = 100')]:
        vals = np.array([GGABA[N][s] for s in SEEDS])
        jit = (rng.random(len(vals)) - 0.5) * 0.18
        # mark the two baseline-failing seeds distinctly in both conditions
        for s, v, j in zip(SEEDS, vals, jit):
            is_fail_seed = s in BASE_FAILS
            axA.scatter(xpos + j, v, s=70 if is_fail_seed else 46,
                        facecolor=color if not is_fail_seed else 'none',
                        edgecolor=color, linewidth=1.8 if is_fail_seed else 0.6,
                        marker='D' if is_fail_seed else 'o', zorder=3,
                        alpha=0.95)
        # mean bar
        axA.plot([xpos - 0.22, xpos + 0.22], [vals.mean()] * 2, color=color,
                 lw=2.4, zorder=4)
        axA.text(xpos, vals.max() + 1.4, lab, ha='center', va='bottom',
                 fontsize=11, color=color, fontweight='bold')
        # CV annotation
        cv = 100 * vals.std() / vals.mean()
        axA.text(xpos, 7.2, f'CV {cv:.0f}%', ha='center', va='top',
                 fontsize=9.5, color=color)

    axA.axhspan(0, GABA_FLOOR, color='0.90', zorder=0)
    axA.axhline(GABA_FLOOR, color='0.55', lw=1.1, ls='--', zorder=1)
    axA.text(1.46, GABA_FLOOR - 0.4, 'gating-failure floor\n(~6 SOM→branch-0 syn)',
             ha='right', va='top', fontsize=8.5, color='0.4')
    # annotate the rescued seeds
    axA.annotate('seeds 44, 53\n(baseline failures)',
                 xy=(0.0, 11.9), xytext=(0.30, 5.2), fontsize=8.5, color=C_FAIL,
                 ha='left', va='center',
                 arrowprops=dict(arrowstyle='->', color=C_FAIL, lw=1.0))
    axA.set_xlim(-0.5, 1.6); axA.set_ylim(4, 30)
    axA.set_xticks([0, 1]); axA.set_xticklabels(['N = 20\n(g 4.0 nS)', 'N = 100\n(g 0.8 nS)'])
    axA.set_ylabel('branch-0 GABA conductance  gGABA$_0$  (nS)')
    axA.set_title('A   Disinhibition variance shrinks with SOM pool size',
                  fontsize=11, loc='left')
    axA.spines[['top', 'right']].set_visible(False)

    # ---------- Panel B: reliability bars ----------
    base = load_reliability(os.path.join(DOCS, 'full_circuit_reliability_25hz_results.json'))
    n100 = load_reliability(os.path.join(DOCS, 'n_som_reliability_n100_results.json'))
    conds = [('N = 20\n(baseline)', base, C_N20), ('N = 100\n(this work)', n100, C_N100)]
    for i, (lab, (npass, ntot, fails), color) in enumerate(conds):
        frac = 100 * npass / ntot
        axB.bar(i, frac, width=0.6, color=color, zorder=3,
                edgecolor='white', linewidth=1.5)
        axB.text(i, frac + 1.5, f'{npass}/{ntot}', ha='center', va='bottom',
                 fontsize=12, fontweight='bold', color=color)
        if fails:
            axB.text(i, 50, 'fails:\n' + ', '.join(map(str, fails)), ha='center',
                     va='center', fontsize=9, color='white', fontweight='bold')
    axB.axhline(100, color='0.7', lw=1.0, ls=':', zorder=1)
    axB.set_ylim(0, 108); axB.set_xticks([0, 1])
    axB.set_xticklabels([c[0] for c in conds])
    axB.set_ylabel('seeds gating correctly  (%, ratio > 2.0)')
    axB.set_title('B   Reliability at 25 Hz\n(20 seeds, 10-epoch protocol)',
                  fontsize=11, loc='left')
    axB.spines[['top', 'right']].set_visible(False)

    fig.suptitle('25 Hz gating failure is a small-N disinhibition-variance artifact, '
                 'not a firing-rate problem', fontsize=12.5, fontweight='bold', y=1.02)
    fig.tight_layout()
    out = os.path.join(FIG_DIR, 'n_som_disinhibition_variance.png')
    fig.savefig(out, dpi=150, bbox_inches='tight', facecolor='white')
    print(f'Saved {out}')
    print(f'  baseline N=20: {base[0]}/{base[1]} pass, fails {base[2]}')
    print(f'  N=100        : {n100[0]}/{n100[1]} pass, fails {n100[2]}')


if __name__ == '__main__':
    main()
