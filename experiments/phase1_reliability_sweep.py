"""
phase1_reliability_sweep.py -- multi-seed reliability test (2026-08-31)
========================================================================
RETIRED AS EVIDENCE (2026-09-01, Raghav's decision): this sweep tests the REDUCED
Phase-1 circuit (seeds 0-9), which is disjoint in both seed range AND circuit from
where seed 44 actually collapsed (the FULL circuit, model/full_circuit.py). Its 10/10
pass results therefore never validated the failure mode it was built to check. Kept
for fast dev iteration only -- do NOT cite its results as reliability evidence in the
Progress Report or to Raghav's PI. See experiments/full_circuit_reliability_sweep.py
for the full-circuit replacement (seeds 40-59, matches the Phase-2B harness exactly).

The 2026-08-30 SOM-rate sweep (docs/som_rate_sweep_table.csv) picked 25.29 Hz as the
"best" SOM baseline from a SINGLE seed (42) per rate. Phase 2's rerun then showed that
choice fails at zero added noise in 1/3 seeds (docs/phase2_snr_sweep_results.json,
noise_level=0.0: seeds 42/43 ratio 4.07/4.81, seed 44 ratio 1.015 -- complete collapse).
25 Hz sits too close to Sweep 1's ~21 Hz duty-cycle cliff for ordinary Poisson trial-to-
trial variability to be safe.

This script runs the full 15-epoch analytical Phase-1 protocol at each of five SOM
rates, across 10 seeds (0-9) per rate, and finds the lowest rate where every single seed
passes (ratio > 2.0). Bias currents were calibrated against the real eqs_som equation in
an isolated-neuron test (not the analytic LIF formula, which is off by ~1 Hz here due to
the refractory period):
  25 Hz -> 20.90 pA (reused from the Sweep 1 data, measured 25.29 Hz there)
  28 Hz -> 21.20 pA (reused from Sweep 1, measured 28.80 Hz there)
  30 Hz -> 21.32 pA (newly calibrated, isolated-neuron measured 30.05 Hz)
  33 Hz -> 21.60 pA (reused from Sweep 1, measured 33.09 Hz there)
  35 Hz -> 21.80 pA (newly calibrated, isolated-neuron measured 35.05 Hz)

Usage: python phase1_reliability_sweep.py <rate_label>
  where rate_label is one of 25, 28, 30, 33, 35 -- runs ONE rate's 10 seeds so multiple
  rates can run as separate parallel background processes.
"""
import sys, os, json
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'experiments'))
sys.path.insert(0, PROOT)
from phase1_analytical import run_gating_analytical

BIAS_BY_RATE = {25: 20.90, 28: 21.20, 30: 21.32, 33: 21.60, 35: 21.80}
SEEDS = list(range(10))
N_EPOCHS = 15
RESULTS_DIR = os.path.join(PROOT, 'docs')


def results_path(rate_label):
    return os.path.join(RESULTS_DIR, f'som_reliability_{rate_label}hz_results.json')


def load_results(rate_label):
    p = results_path(rate_label)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return []


def save_results(rate_label, results):
    with open(results_path(rate_label), 'w') as f:
        json.dump(results, f, indent=2)


def run_rate(rate_label):
    bias = BIAS_BY_RATE[rate_label]
    results = load_results(rate_label)
    done_seeds = {r['seed'] for r in results}
    todo = [s for s in SEEDS if s not in done_seeds]
    print(f"=== Reliability test: {rate_label} Hz (bias={bias} pA) -- "
          f"{len(todo)} seed(s) to run (of {len(SEEDS)}, {len(results)} done) ===",
          flush=True)
    for s in todo:
        res = run_gating_analytical(n_epochs=N_EPOCHS, som_bias_pA=bias, seed_val=s,
                                     run_tag=f'reliability_{rate_label}hz_seed{s}')
        entry = dict(rate_label=rate_label, bias_pA=bias, seed=s,
                     som_rate_hz=res['som_rate_hz'], rho0=res['rho0'], rho1=res['rho1'],
                     ratio=res['ratio'], passed=bool(res['ratio'] > 2.0))
        results.append(entry)
        results.sort(key=lambda r: r['seed'])
        save_results(rate_label, results)
        print(f"  seed={s}: ratio={res['ratio']:.3f} rho0={res['rho0']:.3f} "
              f"rho1={res['rho1']:.3f} SOM={res['som_rate_hz']:.2f} Hz "
              f"[{'PASS' if entry['passed'] else 'FAIL'}]", flush=True)
    n_pass = sum(1 for r in results if r['passed'])
    print(f"\n=== Reliability test {rate_label} Hz complete: {n_pass}/{len(results)} "
          f"seeds passed ===")
    return results


if __name__ == '__main__':
    rate_label = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    if rate_label not in BIAS_BY_RATE:
        raise SystemExit(f"rate_label must be one of {sorted(BIAS_BY_RATE)}")
    run_rate(rate_label)
