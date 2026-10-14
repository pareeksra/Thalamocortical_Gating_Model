"""
tau_gaba_duty_cycle_sweep.py -- resolve the SOM-rate divergence from Yang 2016.
================================================================================
Yang, Murray & Wang (2016) obtain pathway-specific gating with a SOM baseline of
~10 Hz (Methods: "firing of SOM neurons ~10 Hz as observed experimentally") and
tau_GABA,dend = 20 ms. This spiking reimplementation needs ~21 Hz at the SAME
tau = 20 ms (docs/som_rate_sweep_table.csv: fail at 16.9 Hz, pass at 21.5 Hz) --
2x the biologically observed, Yang-used rate. A reviewer will ask why.

Hypothesis (duty-cycle / inhibition coverage): what gates plasticity is not the
SOM rate per se but the fraction of each inter-spike interval the dendritic GABA
conductance keeps the branch shunted. That coverage is set by rate x tau_GABA,dend.
In a SPIKING model the dendritic calcium is driven by discrete NMDA events, so any
uncovered window within an ISI lets calcium cross theta_p (event-driven escape) --
a sensitivity a rate-averaged treatment smooths over. Prediction: the critical SOM
rate for gating scales INVERSELY with tau_GABA,dend. Doubling tau should roughly
halve the critical rate (toward Yang's 10 Hz).

Smoke test already confirmed the qualitative effect (2026-10-14): at a FIXED 16.87
Hz SOM rate, tau=20 ms fails (ratio 1.04) but tau=40 ms passes (ratio 4.25) -- same
spike train, longer GABA tail rescues gating. This script quantifies the scaling.

Method: for each tau_GABA,dend, sweep som_bias_pA to find the fail->pass crossover
SOM rate (ratio crosses 2.0). Uses the same reduced Phase-1 analytical protocol as
docs/som_rate_sweep_table.csv (run_gating_analytical, 15 epochs, seed 42, gGABA
default), via its new param_overrides={'tauGABA': ...} hook. numpy codegen (set
below) so changing tau does NOT trigger a cython recompile each point.

Output: docs/tau_gaba_duty_cycle_results.json, docs/tau_gaba_duty_cycle_table.csv
Run: <venv>/python -I experiments/tau_gaba_duty_cycle_sweep.py
"""
import os, sys, json, csv

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'experiments'))
sys.path.insert(0, PROOT)

from brian2 import prefs, ms
prefs.codegen.target = 'numpy'   # avoid per-tau cython recompile; set BEFORE importing the model run
from phase1_analytical import run_gating_analytical

# tau values to test (ms). 20 = Yang/default; bracket it both ways.
TAUS = [10.0, 20.0, 30.0, 40.0]
# SOM bias grid (pA) -> rate; reuse the known-informative span from som_rate_sweep.
# Rate is very sensitive to bias at the low end, so sample densely there.
BIASES = [20.04, 20.3, 20.45, 20.6, 20.75, 20.9, 21.2, 21.6, 22.2, 23.0, 25.0]
N_EPOCHS = 15
RATIO_PASS = 2.0

RESULTS = os.path.join(PROOT, 'docs', 'tau_gaba_duty_cycle_results.json')
TABLE = os.path.join(PROOT, 'docs', 'tau_gaba_duty_cycle_table.csv')


def crossover_rate(points):
    """Linear-interp the SOM rate where ratio crosses RATIO_PASS, from (rate,ratio)
    points sorted by rate. Returns None if no crossing in range."""
    pts = sorted(points, key=lambda x: x[0])
    for (r0, g0), (r1, g1) in zip(pts, pts[1:]):
        if (g0 < RATIO_PASS) and (g1 >= RATIO_PASS):
            if g1 == g0:
                return r1
            frac = (RATIO_PASS - g0) / (g1 - g0)
            return r0 + frac * (r1 - r0)
    return None


def main():
    all_results = {}
    for tau in TAUS:
        pts = []
        print(f"\n=== tau_GABA,dend = {tau} ms ===", flush=True)
        for bias in BIASES:
            res = run_gating_analytical(
                n_epochs=N_EPOCHS, som_bias_pA=bias, seed_val=42,
                verbose=False, resume=False, run_tag=f'tau{int(tau)}_b{bias}',
                param_overrides={'tauGABA': tau * ms})
            rate = res['som_rate_hz']; ratio = res['ratio']
            pts.append((rate, ratio, bias, res['rho0'], res['rho1']))
            print(f"  bias {bias:>5} pA -> SOM {rate:6.2f} Hz  ratio {ratio:6.3f}  "
                  f"{'PASS' if ratio >= RATIO_PASS else 'fail'}", flush=True)
            # early stop once we're comfortably in the passing regime
            if ratio >= RATIO_PASS and rate > 0 and len([p for p in pts if p[1] >= RATIO_PASS]) >= 2:
                break
        xr = crossover_rate([(p[0], p[1]) for p in pts])
        all_results[str(tau)] = dict(tau_ms=tau, crossover_rate_hz=xr,
                                     points=[dict(som_rate_hz=p[0], ratio=p[1], bias_pA=p[2],
                                                  rho0=p[3], rho1=p[4]) for p in pts])
        print(f"  --> crossover SOM rate (ratio=2.0): "
              f"{xr:.2f} Hz" if xr else "  --> no crossover found in range", flush=True)

    with open(RESULTS, 'w') as f:
        json.dump(all_results, f, indent=2)
    with open(TABLE, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['tau_GABA_dend_ms', 'crossover_som_rate_hz', 'rate_x_tau_product_Hz_ms'])
        for tau in TAUS:
            xr = all_results[str(tau)]['crossover_rate_hz']
            prod = (xr * tau) if xr else ''
            w.writerow([tau, round(xr, 2) if xr else '', round(prod, 1) if xr else ''])
    print(f"\nSaved {RESULTS} and {TABLE}", flush=True)

    print("\n=== DUTY-CYCLE TEST: does critical rate scale ~1/tau? ===", flush=True)
    print(f"{'tau(ms)':>8} {'crit rate(Hz)':>14} {'rate*tau(Hz*ms)':>16}", flush=True)
    for tau in TAUS:
        xr = all_results[str(tau)]['crossover_rate_hz']
        if xr:
            print(f"{tau:>8} {xr:>14.2f} {xr*tau:>16.1f}", flush=True)
    print("If rate*tau is ~constant across tau, gating is set by inhibition COVERAGE "
          "(duty cycle), not rate -- this is the resolution of the Yang divergence.", flush=True)


if __name__ == '__main__':
    main()
