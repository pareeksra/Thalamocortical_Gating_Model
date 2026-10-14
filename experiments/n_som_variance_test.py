"""
n_som_variance_test.py -- is the 25 Hz gating failure a small-N disinhibition-
variance artifact? (2026-10-13)
===================================================================================
Hypothesis (from epoch0_timing_diag.py): gating fails when the inhibited branch
draws too few SOM->Dend[0] synapses (p_som2dend_spike=0.5 over only n_som_spike=20),
so its GABA conductance is weak-and-noisy. Prediction: raising n_som_spike while
HOLDING the expected total branch-0 inhibition constant (scale gGABA ~ 1/n_som_spike)
should shrink the seed-to-seed gGABA variance and make the ~10% failures vanish --
WITHOUT adding mean inhibition (which would be a trivial "more GABA" rescue).

Run ONE seed per process from the shell wrapper (full StateMonitors are memory-heavy).
This module exposes run_one(seed, n_som, gGABA_nS) and prints one TSV row:
    n_som  gGABA_nS  seed  ratio  r0  r1  gGABA0_mean_nS  passed

Design:
  baseline  N=20  gGABA=4.0 nS   (expected total 20*0.5*4.0 = 40 nS)
  test      N=40  gGABA=2.0 nS   (same expected total, lower relative variance)
  test      N=100 gGABA=0.8 nS   (same expected total, lowest variance)
A WEIGHT-COMPENSATED raise is the controlled test. (An uncompensated raise would
also work but for the trivial reason.)

Note n_som_spike also sizes the SOM background Poisson (BG_som) and the SOM->PV and
VIP->SOM pathways; those scale naturally with the population and are part of what a
"bigger SOM pool" means. gGABA is the SOM->Dend weight only (parameters.py line 61),
so compensating it isolates the branch-0 inhibition budget without touching SOM->PV
(gGABA_pv) or the SOM firing itself.
"""
import os, sys
import numpy as np

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
from brian2 import nS
from full_circuit import build_gating_circuit


def run_one(seed, n_som, gGABA_nS, n_epochs=10):
    r = build_gating_circuit(
        T=3.0, md_signal_rate=0.0, noise_level=0.0, n_epochs=n_epochs,
        seed_val=seed, som_bias_pA=20.9,          # the 25 Hz condition
        monitor_epoch0=True, monitor_dt_ms=1.0,   # 1ms is enough; keeps memory lower
        param_overrides={'n_som_spike': int(n_som), 'gGABA': gGABA_nS * nS},
    )
    g0 = r['ep0']['gGABA0_mean_nS']
    passed = r['ratio'] > 2.0
    print(f"{n_som}\t{gGABA_nS:.3f}\t{seed}\t{r['ratio']:.3f}\t{r['r0']:.4f}\t"
          f"{r['r1']:.4f}\t{g0:.3f}\t{int(passed)}", flush=True)


if __name__ == '__main__':
    seed = int(sys.argv[1]); n_som = int(sys.argv[2]); gGABA_nS = float(sys.argv[3])
    ne = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    run_one(seed, n_som, gGABA_nS, ne)
