# Plan — repeated A/B alternation with overlapping inputs (2026-11-02)

Follow-up to `docs/reports/PLAN_overlapping_inputs.md`, which tested a single A→B sequence.

## Question

In that experiment, under MD gating, afferents shared by A and B lost ~60% of their
strength on A's branch during context B. Real contexts recur. **When A and B alternate
repeatedly, do the shared synapses reach a stable compromise? What does steady-state
separation and retention look like, and does block length matter?**

## Design

Same circuit and protocol as the overlap experiment: `context_circuit(input_mode='patterns')`,
analytical Yang plasticity, pinned 10 Hz bAPs, desynchronised SOM, calibrated PV, T = 3 s
epochs, ρ initialised at 0.5.

- **Schedule.** 32 epochs alternating in blocks of length L.
  - L = 4: (A×4, B×4) × 4 cycles.
  - L = 1: (A, B) × 16.
  - Both give 16 A and 16 B epochs in total.
- **Conditions.**
  - MD gating × f {0, 0.25, 0.5, 0.75, 1} × L {1, 4} × seeds 42–46 = 50 runs.
  - No gating × f {0, 0.5, 1} × L = 4 × seeds 42–46 = 15 runs (control).
  - Run locally, 10 workers, one fresh process per run.

## Metrics

All come from per-synapse ρ, recorded after every epoch.

- Trajectories of mean ρ for each afferent class (A-only, shared, B-only) on each branch.
- **Steady state**, taken from the last cycle:
  - ρ_shared on b0 and on b1, at the end of an A block and at the end of a B block.
  - Oscillation amplitude: the change in ρ_shared(b0) across one B block.
- `ret_A`: ρ(A→b0) at the end of the last B block ÷ ρ(A→b0) at the end of the last A block.
- `discrim` (same definition as the overlap experiment), at the end of the last A block
  and at the end of the last B block. The difference between the two is a recency bias.

## Predictions (written before running)

1. **Convergence.** Each block applies a fixed per-epoch map to a shared synapse: LTP on a
   free branch, LTD on a gated one. The composition of the two maps has a single stable
   cycle. So shared synapses settle into a **limit cycle** that does not depend on
   history, within 2–3 cycles for L = 4.
2. **Symmetry.** By the A↔B symmetry of the circuit, shared synapses on b0 and on b1 sit
   at the same cycle-averaged level. On average they therefore carry **no context
   information**.
   - Steady-state discriminability ≈ the unique-afferent part, 0.65·(1−f), plus a recency
     term: positive after A and negative for A after B.
   - The recency term should be larger for L = 4 than for L = 1.
3. **Retention.** It becomes cyclic, not cumulative: each A block restores what B eroded.
   Within-cycle `ret_A` ≈ 1 − f·(1 − ρ_low/ρ_high), with ρ_low and ρ_high the cycle extremes.
   For L = 1 the swing is smaller, so `ret_A` should be closer to 1 than for L = 4.
4. **No gating.** All active synapses potentiate on both branches; discriminability is 0
   at every f and L.
5. **f = 0 anchor.** Identical to the single A→B run: discriminability ≈ 0.65 at the end
   of every block, and retention 1.

If the f = 0 anchor or the no-gating control fails, stop and debug.

---

## Results (2026-11-02; 65 runs, run locally)

Data: `results/current/alternation_experiment.json` (summary: `_summary.json`). Figure:
`figures/alternation_experiment.png`. Code: `experiments/alternation_experiment.py`.

**Anchors pass.**
- f = 0: retention 1.000, discriminability 0.69 at every block end. The single A→B run
  gave 0.65; the gap comes from longer training, with Aonly_b0 0.924 in both.
- No gating: retention 1.000 and discriminability 0 at every f.

**Steady state** (last cycle, mean over seeds 42–46; SDs ≤ 0.04):

| f | L | shared b0, end A / end B | ret_A | discrim | P_A, P_B after A | P_A, P_B after B |
|---|---|---|---|---|---|---|
| 0 | 4 | — | 0.998 | 0.69 | +0.72, +0.66 | +0.72, +0.69 |
| 0.25 | 4 | 0.93 / 0.64 | 0.922 | 0.54 | +0.65, +0.43 | +0.49, +0.62 |
| 0.5 | 4 | 0.93 / 0.56 | 0.803 | 0.37 | +0.59, +0.15 | +0.19, +0.56 |
| 0.75 | 4 | 0.93 / 0.50 | 0.653 | 0.19 | +0.54, **−0.17** | **−0.13**, +0.51 |
| 1 | 4 | 0.93 / 0.46 | 0.493 | 0 | +0.49, **−0.49** | **−0.47**, +0.47 |
| 0.25 | 1 | 0.91 / 0.81 | 0.972 | 0.54 | +0.57, +0.50 | +0.52, +0.56 |
| 0.5 | 1 | 0.90 / 0.78 | 0.930 | 0.36 | +0.44, +0.29 | +0.30, +0.43 |
| 0.75 | 1 | 0.90 / 0.74 | 0.873 | 0.18 | +0.29, +0.06 | +0.06, +0.30 |
| 1 | 1 | 0.90 / 0.74 | 0.821 | 0 | +0.15, −0.15 | −0.16, +0.16 |

P_X = mean ρ of pattern X on its own branch minus on the other branch (branch preference).

**Prediction by prediction.**
1. **Convergence: confirmed, and faster than predicted.** Shared synapses re-potentiate to
   the ceiling (~0.93) within 1–2 epochs of a free-branch block, so the limit cycle is
   reached in the first cycle. LTP is fast and saturating; gated-branch LTD is slow
   (~0.1 ρ per epoch). The cycle is therefore pinned at the top and swings downward.
2. **Symmetry: confirmed.** Shared synapses on b0 at the end of A equal those on b1 at the
   end of B.
   - The prediction of recency in `discrim` failed for a reason in the metric. Shared
     afferents belong to both patterns, so they cancel exactly in the summed contrast:
     discrim = (P_A + P_B)/2. It stays at 0.69·(1−f) whatever the shared synapses do.
   - Recency is real and large in the per-pattern preferences P_A and P_B:
     - For L = 4 and f ≳ 0.6, the less recent pattern prefers the WRONG branch.
       After an A block, pattern B drives b0 more than b1 (P_B −0.17 at f = 0.75,
       −0.49 at f = 1).
     - Branch assignment of the older context is overwritten. It is not merely weakened.
     - L = 1 gives smaller swings: P_B after A is +0.06 at f = 0.75 and −0.15 at f = 1.
3. **Retention cyclic, not cumulative: confirmed.** Each A block fully restores what the
   B block eroded.
   - Within-cycle `ret_A` depends on the length of the B block. For L = 4, it is
     0.49–0.92 (cf. 0.365 at f = 1 after 8 B epochs).
   - For L = 1, it is 0.82–0.97.
   - Fast alternation protects better.
4. **No gating: confirmed.** Everything sits at the ceiling on both branches, and P = 0.
5. **f = 0 anchor: confirmed** (see above).

**Interpretation.** Under repeated alternation, gating does not destroy shared memories
permanently: fast, saturating LTP re-installs them on each return. What it produces is a
**recency-weighted** branch code.
- Shared afferents always side with the most recent context's branch.
- Only the unique afferents carry a stable context label.
- How much the code tilts towards the recent context depends on the block length and the
  overlap. With long blocks and high overlap, the older context's pattern is actively
  mis-assigned.
- Frequent switching keeps both contexts usable, at the cost of a smaller separation
  (P ≈ 0.15 at f = 1, L = 1).

**Caveats.**
- These are synaptic (ρ-level) readouts. A functional recall test, with plasticity frozen
  and branch plateaus measured, is still needed to show whether P < 0 actually flips the
  branch response.
- Pinned bAPs; 2 branches; 20-afferent patterns; equal A/B block lengths only.
- The asymmetry between LTP and LTD speed is a property of the Yang parameters at 80 Hz
  input. At other rates the cycle may not be pinned at the ceiling.
