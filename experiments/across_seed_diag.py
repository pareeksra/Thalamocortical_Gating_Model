"""
across_seed_diag.py -- hunt the culprit for the across-seed gating failure
==========================================================================
2026-09-03 (Raghav): at 25 Hz SOM baseline, most seeds gate fine but a few (44, 53)
collapse to ratio ~1.02 -- the inhibited branch (0) escapes SOM control and potentiates.
Mean SOM rate is identical across seeds, so it's not a rate-threshold effect. This script
tests the leading hypothesis:

  EARLY BISTABLE LOCK-IN. rho follows a bistable (double-well) update: once a synapse's
  rho crosses the 0.5 barrier, the analytical Yang update pulls it toward the UP state and
  it stays there. So if an early-epoch calcium fluctuation on branch 0 pushes its rho past
  0.5, the branch locks UP for the rest of the run -- a stochastic escape decided in the
  first epoch or two, not a gradual drift.

Uses the REAL model (model/full_circuit.py build_gating_circuit, return_trace=True) at the
25 Hz condition (som_bias_pA=20.9) where the failure was found, noise=0, 10 epochs. Logs,
per epoch, branch-0 and branch-1 mean rho (before/after the update) and the mean alpha_p /
alpha_d that drove it. Runs a passing seed (42) and the two failing seeds (44, 53).

Reads the trace to answer:
  - Does branch 0 cross rho=0.5 early in the failing seeds (lock-in), or climb slowly?
  - Is the escape driven by a large branch-0 alpha_p (calcium above LTP threshold) in a
    specific early epoch?

Output: results/pre_audit/across_seed_diag_results.json + printed per-epoch tables.
"""
import os, sys, json
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
from full_circuit import build_gating_circuit

SEEDS = [42, 44, 53]     # 42 passes; 44, 53 fail (results/pre_audit/full_circuit_reliability_25hz_results.json)
SOM_BIAS = 20.9          # the 25 Hz condition where the failure lives
N_EPOCHS = 10

results = {}
for s in SEEDS:
    r = build_gating_circuit(T=3.0, md_signal_rate=0.0, noise_level=0.0,
                             n_epochs=N_EPOCHS, seed_val=s, som_bias_pA=SOM_BIAS,
                             return_trace=True)
    results[s] = dict(ratio=round(r['ratio'], 4), r0=round(r['r0'], 4), r1=round(r['r1'], 4),
                      som_rate=round(r['som_rate'], 3), trace=r['trace'])
    verdict = 'PASS' if r['ratio'] > 2.0 else 'FAIL'
    print(f"\n=== seed {s}: ratio={r['ratio']:.3f}  r0(inhib)={r['r0']:.4f}  "
          f"r1(free)={r['r1']:.4f}  [{verdict}] ===", flush=True)
    print(f"{'ep':>3} | {'rho0_bef':>8} {'rho0_aft':>8} | {'ap0':>6} {'ad0':>6} | "
          f"{'rho1_aft':>8} | {'ap1':>6}", flush=True)
    first_cross = None
    for t in r['trace']:
        cross = ' <-- rho0 crosses 0.5' if (t['rho0_after'] >= 0.5 and first_cross is None) else ''
        if t['rho0_after'] >= 0.5 and first_cross is None:
            first_cross = t['epoch']
        print(f"{t['epoch']:>3} | {t['rho0_before']:>8.4f} {t['rho0_after']:>8.4f} | "
              f"{t['ap0']:>6.3f} {t['ad0']:>6.3f} | {t['rho1_after']:>8.4f} | "
              f"{t['ap1']:>6.3f}{cross}", flush=True)
    results[s]['first_epoch_rho0_over_0.5'] = first_cross

out = os.path.join(PROOT, 'results', 'pre_audit', 'across_seed_diag_results.json')
with open(out, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nSaved {out}", flush=True)

# Summary: for each seed, when (if ever) branch 0 crossed 0.5, and its epoch-1 alpha_p.
print("\n--- summary ---", flush=True)
for s in SEEDS:
    tr = results[s]['trace']
    ep0_ap0 = tr[0]['ap0'] if tr else float('nan')
    fc = results[s]['first_epoch_rho0_over_0.5']
    print(f"seed {s}: ratio={results[s]['ratio']:.3f}  branch-0 alpha_p in epoch0={ep0_ap0:.3f}s  "
          f"first epoch rho0>0.5={fc}", flush=True)
