"""
n_som_reliability_sweep.py -- citable version of the N-size prediction test (2026-10-14)
========================================================================================
The 2026-10-13 fast proxy (experiments/n_som_variance_test.py, 1-epoch ap0>0.67, 12
seeds) showed the 25 Hz gating failure is a small-N disinhibition-VARIANCE artifact:
raising n_som_spike while HOLDING expected branch-0 inhibition constant (scale gGABA
~ 1/N) shrinks the seed-to-seed gGABA variance and removes the failures (N=100: 0/12).
This script is the full-rigor confirmation: a proper 10-epoch reliability sweep (same
protocol as full_circuit_reliability_sweep.py) over the canonical 20 seeds (40-59), at
the 25 Hz condition, for the N=100 weight-compensated population.

Controlled comparison (expected branch-0 inhibition = N * p_som2dend_spike * gGABA held
~constant at 40 nS, so any change is VARIANCE not mean):
    baseline  N=20   gGABA=4.0 nS   (the known 25 Hz condition: 18/20 pass, fails 44,53)
    test      N=100  gGABA=0.8 nS   (prediction: 20/20 pass)

Reuses the proven harness pattern: ProcessPoolExecutor across seeds, per-seed JSON
checkpointing (resume-safe after a kill -- already-done seeds are skipped), numpy
codegen (no C++ compile race). som_bias_pA=20.9 is the 25 Hz bias throughout; only N
and gGABA change via param_overrides.

Memory note (2026-10-13): N=100 circuits are ~5x the interneuron scale of baseline; on
the 14 GiB dev box keep workers low (default 4) so an overnight run does not OOM. No
StateMonitors here (monitor_epoch0 off), so each worker is far lighter than the epoch0
diagnostic.

Usage:
  <venv>/python -I experiments/n_som_reliability_sweep.py <config> [n_workers]
    config: 'baseline' (N=20,gGABA=4.0) or 'n100' (N=100,gGABA=0.8)
  Checkpoints to docs/n_som_reliability_<config>_results.json; safe to re-launch.
"""
import os, sys, json
from concurrent.futures import ProcessPoolExecutor, as_completed

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
sys.path.insert(0, PROOT)

from brian2 import nS
from full_circuit import build_gating_circuit

CONFIGS = {
    'baseline': dict(n_som=20, gGABA_nS=4.0),
    'n100':     dict(n_som=100, gGABA_nS=0.8),
}
SOM_BIAS_PA = 20.9        # 25 Hz condition
SEEDS = list(range(40, 60))   # canonical 20 seeds
T_SIM = 3.0
N_EPOCHS = 10
RESULTS_DIR = os.path.join(PROOT, 'docs')
DEFAULT_WORKERS = 4


def results_path(cfg):
    return os.path.join(RESULTS_DIR, f'n_som_reliability_{cfg}_results.json')


def load_results(cfg):
    p = results_path(cfg)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return []


def save_results(cfg, results):
    with open(results_path(cfg), 'w') as f:
        json.dump(sorted(results, key=lambda r: r['seed']), f, indent=2)


def _run_one_seed(cfg, seed_val):
    c = CONFIGS[cfg]
    r = build_gating_circuit(
        T=T_SIM, md_signal_rate=0.0, noise_level=0.0, n_epochs=N_EPOCHS,
        seed_val=seed_val, som_bias_pA=SOM_BIAS_PA,
        param_overrides={'n_som_spike': int(c['n_som']), 'gGABA': c['gGABA_nS'] * nS},
    )
    passed = r['ratio'] > 2.0
    return dict(seed=seed_val, n_som=c['n_som'], gGABA_nS=c['gGABA_nS'],
                som_rate_hz=round(r['som_rate'], 3),
                r0=round(r['r0'], 4), r1=round(r['r1'], 4),
                ratio=round(r['ratio'], 4), passed=passed)


def run_cfg(cfg, n_workers=DEFAULT_WORKERS):
    c = CONFIGS[cfg]
    results = load_results(cfg)
    done = {r['seed'] for r in results}
    todo = [s for s in SEEDS if s not in done]
    print(f"=== N-som reliability: cfg={cfg} (N={c['n_som']}, gGABA={c['gGABA_nS']} nS, "
          f"25 Hz bias {SOM_BIAS_PA} pA) -- {len(done)}/{len(SEEDS)} done, running "
          f"{len(todo)} across {n_workers} workers ===", flush=True)
    if todo:
        with ProcessPoolExecutor(max_workers=n_workers) as ex:
            futs = {ex.submit(_run_one_seed, cfg, s): s for s in todo}
            for fut in as_completed(futs):
                s = futs[fut]
                try:
                    row = fut.result()
                except Exception as e:
                    print(f"  seed={s}: ERRORED -- {e}", flush=True)
                    continue
                results.append(row)
                save_results(cfg, results)
                print(f"  seed={row['seed']}: ratio={row['ratio']:.4f}  "
                      f"r0={row['r0']:.4f}  r1={row['r1']:.4f}  "
                      f"SOM={row['som_rate_hz']:.2f}Hz  "
                      f"{'[PASS]' if row['passed'] else '[FAIL]'}", flush=True)
    n_pass = sum(1 for r in results if r['passed'])
    fails = sorted(r['seed'] for r in results if not r['passed'])
    print(f"\n=== cfg={cfg} complete: {n_pass}/{len(results)} passed (ratio>2.0); "
          f"fails={fails} ===", flush=True)
    return n_pass, len(results)


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in CONFIGS:
        raise SystemExit(f"Usage: python -I {sys.argv[0]} <config> [n_workers]  "
                         f"(config one of {sorted(CONFIGS)}, workers default {DEFAULT_WORKERS})")
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_WORKERS
    run_cfg(sys.argv[1], nw)
