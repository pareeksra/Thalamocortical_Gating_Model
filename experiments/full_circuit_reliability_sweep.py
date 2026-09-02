"""
full_circuit_reliability_sweep.py -- multi-seed reliability test IN THE FULL CIRCUIT
======================================================================================
2026-09-01 decision (Raghav): the reduced-vs-full circuit mismatch in
phase1_reliability_sweep.py (seeds 0-9, reduced Phase-1 circuit) meant that sweep never
actually validated against the failure it was built to fix -- seed 44's collapse
(docs/phase2_snr_sweep_results.json, noise_level=0.0: ratio 1.015) was found in the FULL
circuit (model/full_circuit.py), a disjoint seed AND a disjoint circuit. Going forward,
all reliability/validation numbers cited in the Progress Report or to Raghav's PI must
come from the full circuit. phase1_reliability_sweep.py is retired as evidence (kept for
fast dev iteration only, not deleted) -- see docs/diag_seed44_results.json for the
reproduction that motivated this script.

Runs the exact Phase-2B baseline call (T=3.0, md_signal_rate=0, noise_level=0,
n_epochs=10 -- see experiments/phase2_snr_breakdown.py) across 20 seeds (40-59) at one
SOM rate, and reports whether every single seed passes (ratio > 2.0).

Bias currents reused from the 2026-08-31 reduced-circuit calibration (isolated-neuron
measurement, so portable to the SOM-active/md_signal_rate=0 condition tested here --
see model/full_circuit.py's build_gating_circuit docstring for the portability caveat):
  25 Hz -> 20.90 pA   28 Hz -> 21.20 pA   30 Hz -> 21.32 pA
  33 Hz -> 21.60 pA   35 Hz -> 21.80 pA

Usage: py experiments/full_circuit_reliability_sweep.py <rate_label> [n_workers]
  where rate_label is one of 25, 28, 30, 33, 35, and n_workers (default 8) is how many
  seeds run concurrently. Checkpoints per-seed to
  docs/full_circuit_reliability_<rate>hz_results.json -- safe to re-launch after a kill,
  already-done seeds are skipped (see experiments/diag_seed44.py's 2026-09-01 fix for
  why this matters: the original diag script lost 3 finished seeds to an unpersisted
  restart before this pattern was adopted everywhere).

2026-09-01 (Raghav asked to speed this up): parallelized across seeds with
ProcessPoolExecutor. Safe because each seed is a fully independent build_gating_circuit()
call -- own Network(), own seed(seed_val) -- and model/MultiCompartmentalModel.py sets
prefs.codegen.target='numpy', so there's no C++/Cython compile cache for concurrent
processes to race on (that's the usual multiprocessing+Brian2 footgun; doesn't apply
here). Only the main process touches the results JSON, so checkpointing stays
corruption-safe. Machine has 12 logical cores; default 8 workers leaves headroom for
everything else running. At ~15 min/seed serial, 20 seeds / 8 workers -> ~3 batches ->
~45 min instead of ~5h.
"""
import os, sys, json
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
from full_circuit import build_gating_circuit

BIAS_BY_RATE = {25: 20.90, 28: 21.20, 30: 21.32, 33: 21.60, 35: 21.80}
SEEDS = list(range(40, 60))  # 40-59, 20 seeds
T_SIM = 3.0
N_EPOCHS = 10
RESULTS_DIR = os.path.join(PROOT, 'docs')
DEFAULT_WORKERS = 8


def results_path(rate_label):
    return os.path.join(RESULTS_DIR, f'full_circuit_reliability_{rate_label}hz_results.json')


def load_results(rate_label):
    p = results_path(rate_label)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return []


def save_results(rate_label, results):
    # Sorted by seed since parallel completion order != submission order.
    with open(results_path(rate_label), 'w') as f:
        json.dump(sorted(results, key=lambda r: r['seed']), f, indent=2)


def _run_one_seed(rate_label, bias, seed_val):
    # Runs in a worker process (Windows spawn -- this module gets reimported there,
    # which is why build_gating_circuit is imported at module scope, not in here).
    r = build_gating_circuit(T=T_SIM, md_signal_rate=0.0, noise_level=0.0,
                              n_epochs=N_EPOCHS, seed_val=seed_val, som_bias_pA=bias)
    passed = r['ratio'] > 2.0
    return dict(seed=seed_val, bias_pA=bias, som_rate_hz=round(r['som_rate'], 3),
                r0=round(r['r0'], 4), r1=round(r['r1'], 4),
                ratio=round(r['ratio'], 4), passed=passed)


def run_rate(rate_label, n_workers=DEFAULT_WORKERS):
    bias = BIAS_BY_RATE[rate_label]
    results = load_results(rate_label)
    done_seeds = {r['seed'] for r in results}
    todo = [s for s in SEEDS if s not in done_seeds]
    print(f"=== Full-circuit reliability test: {rate_label} Hz (bias={bias} pA) -- "
          f"{len(done_seeds)}/20 already done, running {len(todo)} more across "
          f"{n_workers} worker processes ===", flush=True)

    if todo:
        with ProcessPoolExecutor(max_workers=n_workers) as ex:
            futures = {ex.submit(_run_one_seed, rate_label, bias, s): s for s in todo}
            for fut in as_completed(futures):
                s = futures[fut]
                try:
                    row = fut.result()
                except Exception as e:
                    print(f"  seed={s}: ERRORED -- {e}", flush=True)
                    continue
                results.append(row)
                save_results(rate_label, results)  # main process only -- no write races
                print(f"  seed={row['seed']}: ratio={row['ratio']:.4f}  "
                      f"r0(inhib)={row['r0']:.4f}  r1(free)={row['r1']:.4f}  "
                      f"SOM={row['som_rate_hz']:.2f} Hz  "
                      f"{'[PASS]' if row['passed'] else '[FAIL]'}", flush=True)

    n_pass = sum(1 for r in results if r['passed'])
    print(f"\n=== full_circuit_reliability {rate_label}Hz complete: "
          f"{n_pass}/{len(results)} passed (ratio>2.0) ===", flush=True)
    return n_pass, len(results)


if __name__ == '__main__':
    if len(sys.argv) < 2 or int(sys.argv[1]) not in BIAS_BY_RATE:
        raise SystemExit(f"Usage: py {sys.argv[0]} <rate_label> [n_workers]  "
                          f"(rate_label one of {sorted(BIAS_BY_RATE)}, "
                          f"n_workers default {DEFAULT_WORKERS})")
    n_workers = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_WORKERS
    run_rate(int(sys.argv[1]), n_workers)
