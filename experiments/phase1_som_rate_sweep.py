"""
phase1_som_rate_sweep.py -- Sweep 1 (Step 2d follow-up)
========================================================
Holds gGABA at Yang's matched value (10 SOM cells x 4.0 nS = 40 nS total,
i.e. gGABA_nS=None -> parameters.py default) and sweeps the SOM->dendrite
firing rate (via som_bias_pA) from ~10 Hz to ~65 Hz. At each point, runs the
full 15-epoch analytical Phase-1 protocol (phase1_analytical.run_gating_analytical)
and records the gating ratio + both branches' final rho.

Goal: find the crossover SOM rate below which gating (ratio > 2) fails.

Two endpoints are already computed (reused, not rerun):
  - bias=20.04 pA -> ~10.14 Hz, ratio=1.02  (docs/phase1_som10hz_run.log, Step 2d)
  - bias=25.00 pA -> ~63.3  Hz, ratio=2.81  (docs/phase1_analytical_run.log, Step 2c)

Output: docs/som_rate_sweep_results.json, docs/som_rate_sweep_table.csv,
figures/som_rate_sweep.png
"""
import sys, os, json, csv
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'experiments'))
sys.path.insert(0, PROOT)
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from phase1_analytical import run_gating_analytical

RESULTS_PATH = os.path.join(PROOT, 'docs', 'som_rate_sweep_results.json')
TABLE_PATH = os.path.join(PROOT, 'docs', 'som_rate_sweep_table.csv')
FIG_PATH = os.path.join(PROOT, 'figures', 'som_rate_sweep.png')

# Reused points -- already run under the identical protocol (15 epochs, T=3s,
# exc=80Hz, post=10Hz, g_c=0.8nS, gGABA=4.0nS default, seed 42). Not rerun.
REUSED = [
    dict(som_bias_pA=20.04, gGABA_nS=4.0, som_rate_hz=10.14, rho0=0.910, rho1=0.924,
         ratio=1.02, source='docs/phase1_som10hz_run.log (Step 2d)'),
    dict(som_bias_pA=25.00, gGABA_nS=4.0, som_rate_hz=63.30, rho0=0.329, rho1=0.924,
         ratio=2.81, source='docs/phase1_analytical_run.log (Step 2c)'),
]

# New bias points spanning the same range as the reused endpoints (20.04, 25.00 pA).
# NOT evenly spaced: a 1-epoch smoke test showed the rate is extremely sensitive to
# bias near the low end (20.04 -> 21.0 pA took the rate from ~10 Hz to ~26 Hz), so an
# even grid would miss the actual crossover. Denser sampling below 22 pA.
NEW_BIAS = [20.3, 20.6, 20.9, 21.2, 21.6, 22.2, 23.0, 24.0]


def load_results():
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH) as f:
            return json.load(f)
    return list(REUSED)


def save_results(results):
    with open(RESULTS_PATH, 'w') as f:
        json.dump(results, f, indent=2)


def make_table(results):
    rows = sorted(results, key=lambda r: r['som_rate_hz'])
    with open(TABLE_PATH, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['som_bias_pA', 'measured_som_rate_hz', 'gGABA_nS', 'rho0_inhib', 'rho1_free', 'ratio'])
        for r in rows:
            w.writerow([r['som_bias_pA'], round(r['som_rate_hz'], 2), r['gGABA_nS'],
                        round(r['rho0'], 3), round(r['rho1'], 3), round(r['ratio'], 3)])
    return rows


def make_figure(rows):
    rate = np.array([r['som_rate_hz'] for r in rows])
    ratio = np.array([r['ratio'] for r in rows])
    rho0 = np.array([r['rho0'] for r in rows])
    rho1 = np.array([r['rho1'] for r in rows])

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    ax[0].plot(rate, ratio, marker='o', lw=2, color='C2')
    ax[0].axhline(2.0, color='red', ls='--', lw=1, label='crossover criterion (ratio=2)')
    ax[0].axvline(10.0, color='gray', ls=':', lw=1, label="Yang's SOM rate (~10 Hz)")
    ax[0].set_xlabel('measured SOM firing rate (Hz)')
    ax[0].set_ylabel('gating ratio (free/inhib)')
    ax[0].set_title('Sweep 1: SOM rate vs gating ratio\n(gGABA held at Yang-matched 40 nS total)')
    ax[0].legend(fontsize=8)

    ax[1].plot(rate, rho1, marker='o', lw=2, color='C1', label='free (branch 1)')
    ax[1].plot(rate, rho0, marker='s', lw=2, color='C0', label='inhibited (branch 0)')
    ax[1].axhline(0.5, color='k', ls=':', lw=1)
    ax[1].set_xlabel('measured SOM firing rate (Hz)')
    ax[1].set_ylabel('final rho (epoch 15)')
    ax[1].set_title('Final rho per branch vs SOM rate')
    ax[1].legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(FIG_PATH, dpi=130)
    print(f'Wrote {FIG_PATH}')


if __name__ == '__main__':
    results = load_results()
    done_bias = {round(r['som_bias_pA'], 4) for r in results}
    todo = [b for b in NEW_BIAS if round(b, 4) not in done_bias]
    print(f"=== Sweep 1: SOM rate sweep -- {len(todo)} new point(s) to run "
          f"(of {len(NEW_BIAS)} planned, {len(REUSED)} reused) ===", flush=True)

    for i, bias in enumerate(todo):
        print(f"\n--- point {i+1}/{len(todo)}: som_bias_pA={bias:.3f} ---", flush=True)
        res = run_gating_analytical(n_epochs=15, som_bias_pA=bias, gGABA_nS=None,
                                     run_tag=f'somsweep_{bias:.3f}'.replace('.', 'p'))
        entry = dict(som_bias_pA=bias, gGABA_nS=4.0, som_rate_hz=res['som_rate_hz'],
                     rho0=res['rho0'], rho1=res['rho1'], ratio=res['ratio'],
                     source='sweep run')
        results.append(entry)
        save_results(results)
        print(f"  -> measured {res['som_rate_hz']:.2f} Hz, ratio={res['ratio']:.3f}, "
              f"rho0={res['rho0']:.3f}, rho1={res['rho1']:.3f}", flush=True)

    rows = make_table(results)
    make_figure(rows)

    print("\n=== Sweep 1 complete ===")
    for r in sorted(results, key=lambda r: r['som_rate_hz']):
        flag = 'PASS' if r['ratio'] > 2 else 'fail'
        print(f"  {r['som_rate_hz']:6.2f} Hz  ratio={r['ratio']:.3f}  [{flag}]")
