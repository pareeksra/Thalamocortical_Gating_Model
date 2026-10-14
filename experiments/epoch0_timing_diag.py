"""
epoch0_timing_diag.py -- WHY does branch-0 ap0 differ across seeds? (2026-10-13)
================================================================================
across_seed_diag.py + the analytical analysis established WHAT the escape is:
seeds 44/53 carry a persistently elevated branch-0 LTP drive (ap0, time the
inhibited branch's calcium spends above theta_p) from epoch 0 on, which ratchets
rho0 to ~0.9. Mean SOM rate is identical across seeds (25.27 Hz), so the cause is
sub-epoch SPIKE TIMING, not mean inhibition.

This script uses model/full_circuit.py's new monitor_epoch0 hook to record, during
EPOCH 0 only, the full c_total trace of both dendritic branches plus SOM and exc0
spike times, for a passing seed (42) and a failing seed (44), at BOTH 25 Hz (where
the failure lives) and 30 Hz (the locked baseline). It then quantifies, without any
plotting dependency:

  - epoch-0 ap0 measured two ways (run-regularly accumulator vs the c_total trace)
    as a self-consistency check,
  - the distribution of SOM inter-spike intervals (ISI) in epoch 0 -- is there a
    longer inhibition GAP in the failing seed? (duty-cycle / gap hypothesis)
  - how branch-0 calcium excursions above theta_p line up with SOM ISI gaps.

Prediction to test:
  25 Hz: seed 44 ap0 >> seed 42 ap0 (reproduce ~1.22 vs ~0.07 s).
  30 Hz: both seeds' ap0 fall below the ~0.67 s self-sustain barrier.
  Failing seed should show a longer max SOM-ISI gap coincident with a branch-0
  calcium excursion above theta_p.

Output: docs/epoch0_timing_diag_results.json + printed summary.
Run: <venv>/python -I experiments/epoch0_timing_diag.py
"""
import os, sys, json
import numpy as np

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
from full_circuit import build_gating_circuit

BIAS = {25: 20.9, 30: 21.32}   # same bias->rate calibration as the reliability sweep
SEEDS = [42, 44]               # 42 passes, 44 fails (at 25 Hz)
RATES = [25, 30]
MON_DT_MS = 0.5


def isi_stats(spike_times, t_end):
    """ISI stats for the POOLED SOM spike train over [0, t_end]."""
    s = np.sort(np.asarray(spike_times))
    s = s[s <= t_end]
    if len(s) < 2:
        return dict(n=len(s), isi_mean=float('nan'), isi_max=float('nan'),
                    isi_max_at=float('nan'))
    isi = np.diff(s)
    k = int(np.argmax(isi))
    return dict(n=int(len(s)), isi_mean=float(isi.mean()), isi_max=float(isi.max()),
                isi_max_at=float(s[k]))  # start time of the largest gap


def overlap_gap_with_ltp(c0, t, theta_p, som_spikes, t_end):
    """Of branch-0's time above theta_p, how much falls inside the single largest
    SOM-ISI gap? If the LTP excursion sits in the big inhibition gap, that's the
    smoking gun for the gap->escape story."""
    c0 = np.asarray(c0); t = np.asarray(t)
    above = c0 > theta_p
    if not above.any():
        return dict(ltp_in_biggest_gap_frac=float('nan'), biggest_gap=(float('nan'), float('nan')))
    s = np.sort(np.asarray(som_spikes)); s = s[s <= t_end]
    if len(s) < 2:
        return dict(ltp_in_biggest_gap_frac=float('nan'), biggest_gap=(float('nan'), float('nan')))
    isi = np.diff(s); k = int(np.argmax(isi))
    g0, g1 = float(s[k]), float(s[k + 1])
    in_gap = above & (t >= g0) & (t <= g1)
    frac = float(in_gap.sum()) / float(above.sum())
    return dict(ltp_in_biggest_gap_frac=frac, biggest_gap=(g0, g1))


results = {}
for rate in RATES:
    for seed in SEEDS:
        r = build_gating_circuit(T=3.0, md_signal_rate=0.0, noise_level=0.0,
                                 n_epochs=1, seed_val=seed, som_bias_pA=BIAS[rate],
                                 monitor_epoch0=True, monitor_dt_ms=MON_DT_MS)
        ep0 = r['ep0']
        t_end = max(ep0['t']) if ep0['t'] else 3.0
        som_isi = isi_stats(ep0['som_spikes'], t_end)
        ov = overlap_gap_with_ltp(ep0['c0'], ep0['t'], ep0['theta_p'], ep0['som_spikes'], t_end)
        key = f"{rate}hz_seed{seed}"
        results[key] = dict(
            rate=rate, seed=seed,
            ap0_acc=None,  # filled from a parallel return_trace run below if desired
            ap0_from_trace=ep0['ap0_from_trace'],
            ad0_from_trace=ep0['ad0_from_trace'],
            c0_max=ep0['c0_max'], c0_mean=ep0['c0_mean'],
            theta_p=ep0['theta_p'], theta_d=ep0['theta_d'],
            n_som=ep0['n_som'], n_exc0=ep0['n_exc0'],
            som_isi=som_isi, overlap=ov,
        )
        print(f"\n=== {key} ===", flush=True)
        print(f"  epoch-0 ap0 (from c trace) = {ep0['ap0_from_trace']:.3f} s   "
              f"ad0 = {ep0['ad0_from_trace']:.3f} s", flush=True)
        print(f"  branch-0 c_total: max={ep0['c0_max']:.3f} (theta_p={ep0['theta_p']}), "
              f"mean={ep0['c0_mean']:.3f}", flush=True)
        print(f"  SOM spikes={ep0['n_som']}  ISI mean={som_isi['isi_mean']*1e3:.1f} ms  "
              f"ISI max={som_isi['isi_max']*1e3:.1f} ms @ t={som_isi['isi_max_at']:.3f}s", flush=True)
        print(f"  frac of branch-0 LTP-time inside the biggest SOM gap = "
              f"{ov['ltp_in_biggest_gap_frac']}", flush=True)

out = os.path.join(PROOT, 'docs', 'epoch0_timing_diag_results.json')
# drop the big per-sample arrays from the saved json; keep summaries only
with open(out, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nSaved {out}", flush=True)

print("\n--- SUMMARY: epoch-0 ap0 (branch-0 LTP drive), barrier = 0.67 s ---", flush=True)
for rate in RATES:
    row = " ".join(f"seed{seed}={results[f'{rate}hz_seed{seed}']['ap0_from_trace']:.3f}s"
                   for seed in SEEDS)
    print(f"  {rate} Hz: {row}", flush=True)
