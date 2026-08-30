"""
phase1_ggaba_sweep.py -- Sweep 2 (Step 2d follow-up)
=====================================================
Holds SOM at Yang's actual rate (bias=20.04 pA -> ~10.1 Hz measured) and sweeps
the SOM->dendrite per-synapse GABA conductance (gGABA_nS) from the current
Yang-matched value (4.0 nS/synapse, 10 cells = 40 nS total) up to 6x that
(24.0 nS/synapse, 240 nS total). At each point, runs the full 15-epoch
analytical Phase-1 protocol and records the gating ratio + both branches'
final rho.

Goal: does ANY gGABA value recover gating (ratio > 2) at Yang's 10 Hz SOM rate?

Two points are already computed (reused, not rerun):
  - gGABA=4.0 nS  -> ratio=1.02  (docs/phase1_som10hz_run.log, Step 2d)
  - gGABA=10.0 nS -> ratio=1.11  (docs/gbarI_10_run.log)

Output: docs/gbar_I_sweep_results.json, docs/gbar_I_sweep_table.csv,
figures/gbar_I_sweep.png
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

RESULTS_PATH = os.path.join(PROOT, 'docs', 'gbar_I_sweep_results.json')
TABLE_PATH = os.path.join(PROOT, 'docs', 'gbar_I_sweep_table.csv')
FIG_PATH = os.path.join(PROOT, 'figures', 'gbar_I_sweep.png')

SOM_BIAS_PA = 20.04  # Yang's ~10 Hz operating point (measured 10.14-10.15 Hz)

# Reused points -- already run under the identical protocol (15 epochs, T=3s,
# exc=80Hz, post=10Hz, g_c=0.8nS, som_bias=20.04pA, seed 42). Not rerun.
REUSED = [
    dict(gGABA_nS=4.0, som_rate_hz=10.14, rho0=0.910, rho1=0.924, ratio=1.02,
         source='docs/phase1_som10hz_run.log (Step 2d)'),
    dict(gGABA_nS=10.0, som_rate_hz=10.15, rho0=0.829, rho1=0.923, ratio=1.11,
         source='docs/gbarI_10_run.log'),
]

# 4.0 nS is Yang's matched value (40 nS total across 10 SOM cells); 6x = 24.0 nS.
ALL_GGABA = np.linspace(4.0, 24.0, 11)
NEW_GGABA = [float(g) for g in ALL_GGABA if round(g, 4) not in (4.0, 10.0)]


def load_results():
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH) as f:
            return json.load(f)
    return list(REUSED)


def save_results(results):
    with open(RESULTS_PATH, 'w') as f:
        json.dump(results, f, indent=2)


def make_table(results):
    rows = sorted(results, key=lambda r: r['gGABA_nS'])
    with open(TABLE_PATH, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['gGABA_nS', 'gGABA_total_nS', 'measured_som_rate_hz', 'rho0_inhib', 'rho1_free', 'ratio'])
        for r in rows:
            w.writerow([r['gGABA_nS'], r['gGABA_nS'] * 10, round(r['som_rate_hz'], 2),
                        round(r['rho0'], 3), round(r['rho1'], 3), round(r['ratio'], 3)])
    return rows


def make_figure(rows):
    g = np.array([r['gGABA_nS'] for r in rows])
    ratio = np.array([r['ratio'] for r in rows])
    rho0 = np.array([r['rho0'] for r in rows])
    rho1 = np.array([r['rho1'] for r in rows])

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    ax[0].plot(g, ratio, marker='o', lw=2, color='C3')
    ax[0].axhline(2.0, color='red', ls='--', lw=1, label='crossover criterion (ratio=2)')
    ax[0].axvline(4.0, color='gray', ls=':', lw=1, label="Yang-matched (4.0 nS/40 nS total)")
    ax[0].set_xlabel('gGABA per synapse (nS)  [total = 10x this]')
    ax[0].set_ylabel('gating ratio (free/inhib)')
    ax[0].set_title("Sweep 2: gGABA vs gating ratio\n(SOM held at Yang's ~10 Hz)")
    ax[0].legend(fontsize=8)

    ax[1].plot(g, rho1, marker='o', lw=2, color='C1', label='free (branch 1)')
    ax[1].plot(g, rho0, marker='s', lw=2, color='C0', label='inhibited (branch 0)')
    ax[1].axhline(0.5, color='k', ls=':', lw=1)
    ax[1].set_xlabel('gGABA per synapse (nS)')
    ax[1].set_ylabel('final rho (epoch 15)')
    ax[1].set_title('Final rho per branch vs gGABA')
    ax[1].legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(FIG_PATH, dpi=130)
    print(f'Wrote {FIG_PATH}')


if __name__ == '__main__':
    results = load_results()
    done_g = {round(r['gGABA_nS'], 4) for r in results}
    todo = [g for g in NEW_GGABA if round(g, 4) not in done_g]
    print(f"=== Sweep 2: gGABA sweep -- {len(todo)} new point(s) to run "
          f"(of {len(NEW_GGABA)} planned, {len(REUSED)} reused) ===", flush=True)

    for i, g in enumerate(todo):
        print(f"\n--- point {i+1}/{len(todo)}: gGABA_nS={g:.3f} ---", flush=True)
        res = run_gating_analytical(n_epochs=15, som_bias_pA=SOM_BIAS_PA, gGABA_nS=g,
                                     run_tag=f'ggabasweep_{g:.3f}'.replace('.', 'p'))
        entry = dict(gGABA_nS=g, som_rate_hz=res['som_rate_hz'],
                     rho0=res['rho0'], rho1=res['rho1'], ratio=res['ratio'],
                     source='sweep run')
        results.append(entry)
        save_results(results)
        print(f"  -> measured {res['som_rate_hz']:.2f} Hz, ratio={res['ratio']:.3f}, "
              f"rho0={res['rho0']:.3f}, rho1={res['rho1']:.3f}", flush=True)

    rows = make_table(results)
    make_figure(rows)

    print("\n=== Sweep 2 complete ===")
    for r in sorted(results, key=lambda r: r['gGABA_nS']):
        flag = 'PASS' if r['ratio'] > 2 else 'fail'
        print(f"  gGABA={r['gGABA_nS']:5.1f} nS  ratio={r['ratio']:.3f}  [{flag}]")
