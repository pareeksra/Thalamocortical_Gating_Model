"""
phase1_reliability_finalize.py -- merge phase1_reliability_sweep.py's per-rate results,
find the lowest 10/10-pass SOM rate, and write the table + figure.

Usage: python phase1_reliability_finalize.py
Requires all five docs/som_reliability_<rate>hz_results.json files to have 10 seeds each.
"""
import os, sys, json, csv
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(PROOT, 'docs')
FIG = os.path.join(PROOT, 'figures')

RATES = [25, 28, 30, 33, 35]
DUTY_CYCLE_THRESHOLD_HZ = 21.0  # Sweep 1 fail->pass step: 16.87 Hz fail, 21.49 Hz pass


def load_all():
    by_rate = {}
    for r in RATES:
        p = os.path.join(DOCS, f'som_reliability_{r}hz_results.json')
        with open(p) as f:
            entries = json.load(f)
        if len(entries) != 10:
            raise SystemExit(f"{p} has {len(entries)} seeds, expected 10 -- not finished yet")
        by_rate[r] = sorted(entries, key=lambda e: e['seed'])
    return by_rate


def find_robust_rate(by_rate):
    for r in RATES:
        n_pass = sum(1 for e in by_rate[r] if e['passed'])
        if n_pass == 10:
            return r
    return None


def write_table(by_rate):
    path = os.path.join(DOCS, 'som_reliability_table.csv')
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['rate_label_Hz', 'bias_pA', 'seed', 'measured_som_rate_hz',
                    'rho0', 'rho1', 'ratio', 'passed'])
        for r in RATES:
            for e in by_rate[r]:
                w.writerow([r, e['bias_pA'], e['seed'], round(e['som_rate_hz'], 2),
                            round(e['rho0'], 3), round(e['rho1'], 3),
                            round(e['ratio'], 3), e['passed']])
    print(f"Wrote {path}")
    return path


def write_figure(by_rate, robust_rate):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=(8, 5.5))
    for r in RATES:
        ratios = [e['ratio'] for e in by_rate[r]]
        xs = [r] * len(ratios)
        colors = ['#2E7D32' if e['passed'] else '#C62828' for e in by_rate[r]]
        ax.scatter(xs, ratios, c=colors, s=50, zorder=3,
                   edgecolors='k', linewidths=0.5)
        n_pass = sum(1 for e in by_rate[r] if e['passed'])
        ax.text(r, max(ratios) + 0.3, f'{n_pass}/10', ha='center', fontsize=9)

    ax.axhline(2.0, color='0.4', ls='--', lw=1, label='pass criterion (ratio = 2.0)')
    ax.axvline(DUTY_CYCLE_THRESHOLD_HZ, color='red', ls=':', lw=1.5,
               label=f'duty-cycle cliff (~{DUTY_CYCLE_THRESHOLD_HZ:.0f} Hz, Sweep 1)')
    if robust_rate is not None:
        ax.axvline(robust_rate, color='#1565C0', ls='-', lw=1.5, alpha=0.7,
                   label=f'chosen default ({robust_rate} Hz, 10/10 seeds pass)')
    ax.set_xlabel('SOM firing rate (Hz)')
    ax.set_ylabel('gating ratio (free/inhibited), one dot per seed (10 seeds)')
    ax.set_title('Multi-seed reliability: gating ratio vs. SOM rate\n'
                 'green = pass (ratio > 2.0), red = fail')
    ax.legend(fontsize=8, loc='lower right')
    fig.tight_layout()
    path = os.path.join(FIG, 'som_rate_reliability.png')
    fig.savefig(path, dpi=140)
    print(f"Wrote {path}")
    return path


if __name__ == '__main__':
    by_rate = load_all()
    print("Pass counts:")
    for r in RATES:
        n_pass = sum(1 for e in by_rate[r] if e['passed'])
        ratios = [round(e['ratio'], 2) for e in by_rate[r]]
        print(f"  {r:3d} Hz: {n_pass}/10 pass  ratios={ratios}")
    robust_rate = find_robust_rate(by_rate)
    if robust_rate is None:
        print("\nNo rate in the tested range achieved 10/10 -- need to extend the sweep higher.")
    else:
        margin = robust_rate - DUTY_CYCLE_THRESHOLD_HZ
        print(f"\nLowest 10/10-pass rate: {robust_rate} Hz "
              f"({margin:.0f} Hz margin above the ~{DUTY_CYCLE_THRESHOLD_HZ:.0f} Hz cliff)")
    write_table(by_rate)
    write_figure(by_rate, robust_rate)
