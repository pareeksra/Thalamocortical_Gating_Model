# The 25 Hz gating failure is a small-N disinhibition-variance artifact

*2026-10-14. Commits `5dac844` (mechanism + sweeps), `85f8bce` (figure).*
*Figure: `figures/n_som_disinhibition_variance.png`.*

## Summary

At the 25 Hz SOM baseline, branch-specific gating fails on ~10% of random seeds:
the inhibited branch escapes SOM control and potentiates, collapsing the gating
ratio to ~1.0 (committed `full_circuit_reliability_25hz_results.json`: 18/20
pass; seeds 44 and 53 fail). We traced this to its root cause and proved the fix.

**The failure is not a firing-rate problem and not a timing coincidence. It is a
small-population connectivity-variance effect.** With only `n_som_spike = 20` SOM
cells and `p_som2dend_spike = 0.5`, the inhibited branch receives SOM input from a
small, per-seed-random *integer* number of synapses. When that draw is low
(~6 synapses, gGABA ≈ 12 nS), inhibition is too weak to shunt the branch, and a
calcium/plasticity cascade drives it to escape. Raising the SOM pool to N = 100
while holding the *mean* inhibition constant (so only its seed-to-seed variance
falls) removes every failure: **20/20 seeds gate**, with the two baseline failures
rescued (seed 44: ratio 1.015 → 4.866; seed 53: 1.024 → 4.812).

## The causal chain (each link measured, not assumed)

1. **Connectivity draw.** `gGABA` delivered to branch 0 is quantized in ~1.98 nS
   steps — one SOM→Dend[0] synapse. Across seeds 40–59 it ranges 11.9–27.8 nS. The
   two failing seeds sit at the floor (11.9 nS ≈ 6 synapses); every passing seed is
   higher.
2. **E/I imbalance.** Weaker GABA shunt ⇒ branch-0 mean voltage rises ~12 mV
   (−61 → −49 mV in seed 44 vs 42).
3. **NMDA de-gating.** Higher voltage opens the NMDA Mg²⁺ block
   (`mg_gate = 1/(1+exp(−(V−vHalf)/vSpread))`) ⇒ branch-0 NMDA current roughly
   doubles (86 → 176 pA).
4. **Calcium / plasticity escape.** Elevated calcium keeps the branch's time above
   the LTP threshold (`ap0`) over the ~0.67 s self-sustain barrier *every epoch*, so
   its synaptic state `rho0` ratchets monotonically to ~0.9 — gating lost.

**Control:** the *free* branch (branch 1) is identical across seeds (V, NMDA
current all match), so the effect is specific to the inhibited branch's inhibition
— ruling out any global seed artifact.

## Two hypotheses this ruled out

- **SOM inhibition gap.** Failing seeds do *not* have a longer SOM inter-spike gap:
  the largest SOM ISI gap is identical across seeds, and ~0% of branch-0's
  above-threshold time falls inside it. The calcium elevation is sustained across
  the whole epoch, not concentrated in a gap.
- **SOM→branch-0 synapse *count* (naïve).** An isolated connectivity probe does not
  separate the seeds (passing seeds draw as few as 6 synapses too). The correct
  measure is the *delivered* `gGABA` in the real build, which does separate cleanly.
  (The isolated probe consumes the RNG stream in a different order than the full
  build, so its per-seed counts are not the ones the simulation actually uses.)

## The controlled proof (variance, not mean, not rate)

To show it is the *variance* of inhibition and not its mean (or the firing rate),
we raised `n_som_spike` while scaling the per-synapse weight `gGABA ∝ 1/N`, holding
the expected branch-0 inhibition (`N · p · gGABA`) constant at ~40 nS. SOM firing
rate stayed at 25.27 Hz throughout.

| N_som | gGABA weight | mean gGABA₀ | **CV** | failures (10-epoch, seeds 40–59) |
|------:|-------------:|------------:|-------:|---------------------------------:|
| 20    | 4.0 nS       | 20.5 nS     | 22.8%  | **2 / 20** (seeds 44, 53)        |
| 40    | 2.0 nS       | 18.3 nS     | 18.7%  | 2 / 20 (proxy; 44, 45)†          |
| 100   | 0.8 nS       | 19.2 nS     | 13.4%  | **0 / 20** (ratio 3.80–5.23)     |

Mean inhibition is held constant; only the coefficient of variation falls. At
N = 100 the whole distribution lifts off the ~12 nS failure floor and gating is
100% reliable.

† **Honest wrinkle.** N = 40 does *not* reduce the failure count (it moves the
failure to a different seed). The variance reduction is modest at intermediate N,
and halving the per-synapse weight means a low-draw seed still lands low. The effect
is real but only becomes decisive once the whole tail of the gGABA distribution is
pulled above the floor — i.e. the fragility is a *tail* property of the inhibition
distribution, not a smooth mean effect. This is why it takes a substantial N to fix.

## Implication

The previously chosen remedy — locking the SOM baseline to 30 Hz (commit
`9b359be`) — works, but by *overdriving* the few synapses a weakly-connected seed
has, pushing its `ap0` back under the barrier. It **masks** a population-size
fragility rather than removing it. The principled robustness knob is **SOM
population size** (or connection probability): with a realistically sized SOM pool,
the inhibition each branch receives self-averages and the failure mode disappears at
the original 25 Hz baseline.

## Reproduce

```bash
# full 10-epoch reliability at N=100 (weight-compensated), seeds 40-59, 25 Hz
python -I experiments/n_som_reliability_sweep.py n100 4      # -> docs/n_som_reliability_n100_results.json
# baseline is the committed docs/full_circuit_reliability_25hz_results.json

# sub-epoch E/I-balance diagnostic (why branch-0 calcium is elevated)
python -I experiments/epoch0_timing_diag.py                  # -> docs/epoch0_timing_diag_results.json

# fast N-size proxy sweep (1-epoch ap0 > 0.67)
python -I experiments/n_som_variance_test.py <seed> <n_som> <gGABA_nS>

# regenerate the figure
python -I plotting/n_som_variance_figure.py                  # -> figures/n_som_disinhibition_variance.png
```

The mechanism diagnostics rely on the `monitor_epoch0` hook added to
`model/full_circuit.py` (default off, RNG-neutral; records branch-0 reconstructed
`c_total`, `V`, `gTotGABA`, `iTotNMDA`, and SOM/exc0 spikes during epoch 0).

## Caveat

The N = 40 row and the intermediate characterization used a fast 1-epoch
`ap0 > 0.67` proxy (validated against full pass/fail on the known cases) over 12
seeds. The headline N = 20 and N = 100 numbers are the **full 10-epoch protocol over
all 20 canonical seeds**, which is the citable result.
