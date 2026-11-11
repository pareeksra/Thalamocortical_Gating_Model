# Model status: do we have a robust, well-tested model of Yang 2016 + Zhang 2025 combined?

*2026-11-04. Covers everything up to commit `504daac` plus the Yang Fig. 2 / Supp. Fig. 1
notebook. Evidence for every claim is in the file named beside it.*

> **Update 2026-11-11** (`docs/reports/PLAN_robustness.md`, Step 1–3a).
> - Canonical VIP→SOM weight is now ×0.25. All checks were re-run on it: R2 20/20; R3 has no
>   knife-edge at ±25% and its weakest S_learn rises from 0.51 to 0.64; R5 19/19; Yang Fig. 7b
>   regimes hold. A/B conclusions are unchanged.
> - G2 (branch specificity): MD→VIP must respect the channel; VIP→SOM tolerates ≈ 7.5% and
>   SOM→dendrite 20% cross-talk.
> - Zhang's SOM→VIP is tolerated when weak or within-channel; PV→PV is inert.
> - G4 (scale): a 20-cell network with Zhang's E→all recurrence keeps gating and learning up
>   to a stability limit. It then fails abruptly, as the inactive channel's VIP ignites.
>   Step 3b: MD from a PFC↔MD rate loop works. A self-sustaining loop needs competition,
>   ≤ 5% loop cross-talk and weak non-context E→MD feedback.
>
> **Update 2026-11-10** (`docs/reports/PLAN_robustness.md`, Results).
> - **Later on 2026-11-10: canonical model changed again** (Yang synapse + noisy SOM baseline +
>   bAP calcium ×0.2; see PLAN_robustness.md and `docs/reports/PAPER_COMPARISON.md`). This
>   supersedes the two caveats below:
>   - the SOM knife-edge is fixed: canonical R3 has no knife-edge at ±25% on 14 parameters,
>     including learning (S_learn 0.88);
>   - silent-input retention is 1.000 at any epoch length.
>   - Still not robust: erasure with active inputs, 0.69 ± 0.26 and bimodal over 10 seeds.
>   - A/B results with a 10 Hz recall readout: MD gating is needed for any recall. The old memory
>     survives only at low overlap (f = 0: S 0.92; f ≥ 0.5: lost). Alternating 12-s blocks recall
>     both contexts at f ≤ 0.25. MD→PV sets output gain, not storage.
> - **G1 closed.** With Yang's NMDA-plastic synapse (now canonical), learning creates
>   pathway-specific output gating: S rises from ≈ 0 before learning to 0.86–0.89 after,
>   for readout drive ≤ 15 Hz per synapse. This is Yang Fig. 7d,e. The old AMPA-only
>   synapse learns nothing functional.
> - Numerics robust (20/20 seeds, dt-converged).
> - Gating robust to ±25% on 11 of 12 parameters. The exception is the SOM bias current,
>   which sits near rheobase.
> - New caveat: erasure of memories whose inputs stay active is parameter-dependent
>   (0.40–1.00) with the new synapse, so it is not a robust claim.

## Short answer

**Partly.** The *single-neuron mechanism* is robust and well tested: Yang's dendritic
NMDA nonlinearity and its gating by inhibition, Yang's calcium plasticity rule, and Zhang's
MD→VIP→SOM / MD→PV wiring grafted onto it. MD selects which branch learns, and this holds
across seeds, integration steps and processes.

What we do **not** yet have is a validated model of the *combined hypothesis* (MD gating
gives context-specific learning without forgetting):

1. In the canonical synapse, what is learned has no effect on the cell's output.
2. The key wiring that makes MD branch-specific is an assumption, not data.
3. Every result is from one neuron with two branches.

The sections below separate the two.

## 1. What is robust and tested

| Claim | Evidence | How it is tested |
|---|---|---|
| NMDA plateau with a sharp threshold in the number of synapses; inhibition gates NMDA input strongly and AMPA input weakly (Yang Fig. 2b,c, Supp. Fig. 1f–h) | `notebooks/yang_fig2_supp1.ipynb`, `figures/yang_supp1_fgh_model.png`, `figures/yang_fig2_model.png` | Run directly from `model/equations.py` + `parameters.py`; qualitative match |
| Pathway-specific gating of output firing, gate 1 vs gate 2 (Yang Fig. 2e–g) | same notebook: 27 vs 8 Hz at the preferred stimulus, S ≈ 0.6 | 1 seed per panel |
| Yang's calcium plasticity rule (Eqs. 32–35, closed-form epoch update) | `src/v2/plasticity.py` | Unit tests in `tests/test_audit_fixes.py` [5]: silent synapse holds, matches Yang's printed form, invariance to (w0, w1) |
| Free branch potentiates, inhibited branch does not (Yang Fig. 7) | V3 ratio 4.1 (0.925 / 0.227); `experiments/validate_vs_papers.py` | 1 seed; repeated in all later experiments |
| LTP threshold moves up with SOM inhibition | V2: 12 Hz free → 98 Hz (SOM 15 Hz) → >240 Hz (SOM 30 Hz) | 1 seed sweep |
| Gating is reliable in the full circuit | 20/20 seeds at 25 and 30 Hz SOM; `experiments/som_async_sweep.py` | 20 seeds |
| MD selects the branch (MD_k → VIP_k → SOM_k → branch k) | `model/context_circuit.py`, `experiments/demo_v2_zhang2025.py` | Used by every experiment since the audit, 5 seeds each |
| MD→PV gives graded somatic inhibition (Zhang's MD^GRIK4 arm) | PV 7 → 94 Hz over MD 0–40 Hz; `experiments/pv_calibration_verify.py` | `tests/test_pv_arm.py` 10/10; 3 seeds |
| Gating selectivity needs branch-specific control (Yang Fig. 5 logic) | S ≈ 0.96 by default; it collapses with VIP→SOM cross-wiring ≥ 0.15, and is restored by MD→SOM; `experiments/gating_selectivity_fig5.py` | 5 seeds × 2 synapse versions |
| Numerics | dt-converged (0.1 vs 0.02 ms); compiled coupling bit-identical to legacy; results deterministic per seed across processes | `experiments/dt_convergence_check.py`; `tests/test_audit_fixes.py --slow`; regression check run after every change |

## 2. What the combined model currently shows (each result is solid, but limited in scope)

| Finding | Evidence | Seeds |
|---|---|---|
| Retention comes from **input sparsity**. Inhibition alone erases a memory whose inputs stay active (32–38% kept). | `experiments/retention_md_context.py`, audit P3 | 5 |
| MD→PV does **not** protect memories (retention 0.37–0.39); the erasing LTD is NMDA-driven. | `experiments/retention_pv_arm.py` | 5 |
| With shared inputs, MD gating is the **only** source of context separation, and pays for it in retention (≈ 1 − 0.6·f). | `docs/reports/PLAN_overlapping_inputs.md` | 5 |
| Under repeated alternation the loss is cyclic. Shared inputs follow the most recent context; with long blocks and high overlap the older pattern prefers the wrong branch. | `docs/reports/PLAN_alternation.md` | 5 |

So the defensible claim today is: **"MD decides *where* learning happens; protection
against forgetting comes from input sparsity; overlap trades separation against
retention."** The original claim, "MD gating prevents forgetting", is **not** supported in
the current model.

## 3. Gaps that stop us calling it a validated combined model

**G1. Learned weights do not change what the neuron does (largest gap).**
- In the canonical synapse, learning scales only a small AMPA conductance (0.4 nS). The
  NMDA conductance that makes the plateaus is fixed.
- With learning frozen, the MD cue alone decides which branch plateaus, even with every
  weight at 0 (recall smoke test, 2026-11-02).
- Yang scales the NMDA conductance with the weight.
- The Yang form exists as an opt-in setting (`nmda_plastic=True`). Its first check was
  stable, with gating ratio ≈ 3 and always-on retention 0.43–0.98 versus 0.35–0.40, but
  that is 3 seeds and one protocol (`experiments/nmda_plastic_check.py`).
- Until one synapse is chosen as canonical and the key results are re-run with it, every
  learning result here is about synapse strengths, not behaviour.

**G2. The branch-specific VIP→SOM channels are an assumption.**
- Zhang 2025 gives cell-type wiring (MD→VIP, MD→PV), not a branch-level map. It has no
  direct MD→SOM projection.
- The Fig. 5 analogue shows selectivity collapses once VIP→SOM cross-wiring reaches 15%.
- Our MD selectivity therefore rests on wiring that neither paper supplies.

**G3. Quantitative mismatches with Yang, each absorbed by a calibration choice.**
- Our dendrite is shunted less than Yang's fit (V1: −23 vs −54 mV at 10 nS). Yang's 10 Hz
  regime needs ≈ 1.5× gGABA.
- Fig. 2 needed a 0.8 nS coupling for the clamped-soma panels and a 300 Hz soma background
  (Yang: 500 Hz).
- The Fig. 5 MD→SOM strength (2.25 nS) was set by hand.
- The PV calibration is a narrow ridge: `weight_bg_pv` and `gGABA_pv` must be changed
  together.
- None of these choices has had a sensitivity analysis.

**G4. Scale and scope.**
- Everything is one pyramidal cell, 2 branches, about 20 SOM / 20 VIP.
- Yang's network results (Figs. 3–4, 7d,e at scale) are not reproduced.
- Of Zhang 2025 we use only the cell-type wiring. Its main subject, MD regulating task
  uncertainty in a PFC–MD network, is not modelled at all.

**G5. Testing is thin outside the core.**
- `tests/test_audit_fixes.py` covers the audit fixes and the plasticity rule.
- The paper-replication numbers (V1–V4, Fig. 2, Fig. 5, the 20/20 reliability) are
  scripts, not automated checks with tolerances.
- `experiments/validate_model.py` is stale (last recorded 4/6), and one assertion in
  `tests/test_postsynaptic_calcium.py` is stale by design.
- There is no continuous integration (CI) running the tests automatically.
- Newer results use 3–5 seeds.
- Models B and C (NumPy) are inert; the decision to repair or retire them was never taken.

## 4. How to take the project further without building anything new

In priority order. None of these adds a mechanism; they are decisions, re-runs and
consolidation of what exists.

1. **Choose the canonical synapse (closes G1).**
   - Decide with the PI whether Yang's NMDA-plastic weight replaces the AMPA-only weight.
   - If yes, re-run the existing experiments with `nmda_plastic=True`: gating reliability,
     the forgetting 2×2, overlap, alternation, Fig. 5. Then run the recall test.
   - All the code exists; it is about 2–3 hours of compute locally.
   - This is the single step that turns weight-level results into functional ones.
2. **State the assumptions explicitly (G2, G3).**
   - Write one table for the PI: branch-specific VIP→SOM channels, dendrite shunting
     weaker than Yang's, clamped-soma coupling, soma background, MD→SOM strength, PV ridge.
   - For each: the source (paper, calibration or assumption) and what breaks if it changes.
   - Decide whether to refit the dendrite to Yang's shunting or keep and document the
     difference.
3. **Sensitivity of the headline results to those choices (G3).**
   - Use the existing sweep scripts (`gating_selectivity_fig5.py`, `som_async_sweep.py`,
     `pv_calibration.py`, the notebook parameters) to check whether the conclusions in §2
     survive, for example, ±50% on gGABA, coupling and background.
   - If they survive, the model is robust in the sense that matters.
4. **More seeds on the claims we would publish (G5).** Take the §2 findings and the Fig. 5
   panels from 5 seeds to 10–20 and report confidence intervals.
5. **Turn the replications into regression tests (G5).**
   - Freeze today's numbers (V1–V4, the Fig. 2 S value, Fig. 5 S at default, 20/20
     reliability) as tests with tolerances.
   - Retire or fix `validate_model.py`; retire Models B and C.
   - This is consolidation, not new science.
6. **Reframe the claim.** The supported story is the one in §2: MD selects where learning
   happens, input sparsity protects, overlap trades separation for retention, and
   alternation gives a recency-weighted code. Agree with the PI whether that is the paper,
   or whether the forgetting-protection claim must be rescued (that would need new
   mechanisms, which is a separate decision).
7. **Only then scale (G4).**
   - The network build (Phase 4) should start from the chosen synapse and the stated
     assumptions.
   - Keep input context-sparsity; it is the only protector in this model.

## Bottom line for the PI

The Yang mechanism with Zhang's wiring is implemented faithfully at the single-neuron
level and is numerically robust. MD selecting the learning branch is established.

Three things are not yet established:
- that the learned weights matter for the neuron's output;
- that the result holds without assuming branch-specific VIP→SOM wiring;
- that it holds at network scale.

The first is a decision plus re-runs with code that already exists, and it should come
first.
