# γ/τ units analysis: does canonical Graupner-Brunel (2012) gate at its own timescale?

**Status: open. Result is a partial confirmation, not a clean pass or fail. Do not
proceed to Step 2 (permanent equation fix + recalibration) until this is resolved.**

**Update:** The continuous ODE timescale question (§1) is superseded by the switch to
Yang's analytical epoch-based update (§2b), which does not depend on simulation
duration for convergence.

## 1. The math

Graupner & Brunel (2012), the calcium-based synaptic plasticity model this project's
`drho/dt` is derived from, divides the *entire* right-hand side by the time constant τ:

```
τ dρ/dt = -ρ(1-ρ)(0.5-ρ) + γ_p(1-ρ)H(c-θ_p) - γ_d ρ H(c-θ_d) + σ√τ ξ(t)√(H_p+H_d)
```

where `H(·)` is a dimensionless 0/1 indicator ("currently above threshold"). Dividing
through by τ:

```
dρ/dt = [-ρ(1-ρ)(0.5-ρ) + γ_p(1-ρ)H_p - γ_d ρ H_d] / τ + σ√(1/τ) ξ(t)√(H_p+H_d)
```

`model/equations.py:199`, as committed, instead reads:

```python
ind_p = int(c_total > theta_p) : 1
ind_d = int(c_total > theta_d) : 1
rate_p = ind_p * 1/second : Hz
rate_d = ind_d * 1/second : Hz
drho/dt = -rho*(1-rho)*(0.5-rho)/tau + gamma_p*(1-rho)*rate_p - gamma_d*rho*rate_d \
          + sigma*sqrt(1.0*(ind_p + ind_d))*sqrt(1/tau)*xi : 1 (clock-driven)
```

Only the double-well term is divided by τ. The γ terms use `ind_p`/`ind_d` multiplied by
a bare `1/second` instead of divided by τ, so their contribution is
`γ·H·(1/second)` instead of the canonical `γ·H/τ`. Ratio of the two:
`(1/second) / (1/τ) = τ = 346.36` (τ_rho in `plasticity_params`). This matches the
codebase's own pre-existing comment at that line almost exactly ("346x stronger"),
independently re-derived here.

## 2. Why this matters for timescale, not just amplitude

With τ = 346.36 s, canonical GB2012 dynamics are slow: the double-well restoring force
and the γ-driven potentiation/depression both operate on a multi-minute timescale. This
project's Phase-1 protocol runs 3 simulated seconds. The 346x term is what makes 3-second
runs show any ρ separation at all — dividing by τ correctly, as GB2012 do, should need
run durations comparable to τ (hundreds of seconds) to see the same effect, if it exists
at all with these γ_p/γ_d/θ_p/θ_d values.

## 3. Step 1 test: does canonical GB2012 gate, given enough time?

**Protocol.** Isolated test (equations.py itself untouched): `eqs_synapse_plasticity_template`'s
`drho/dt` line swapped for the canonical form
`(-rho*(1-rho)*(0.5-rho) + gamma_p*(1-rho)*ind_p - gamma_d*rho*ind_d)/tau + sigma*sqrt(ind_p+ind_d)*sqrt(1/tau)*xi`,
run through `phase1_single_neuron_gating.py`'s exact reduced circuit (Soma + 2 dendritic
branches + 10 SOM cells inhibiting branch 0 only), same parameters as the validated run
(`exc_rate=80 Hz`, `post_rate=10 Hz`, `g_c=0.8 nS`, `som_bias_pA=25.0` — this project's
own "current" Phase-1 default, which measures at **63.3 Hz**, not ~40 Hz; the ~36-40 Hz
figure documented elsewhere in this repo comes from a different script convention
(22 pA), not Phase-1's own 25 pA default — noted for accuracy, not changed here). Seed
42. ρ initialized at 0.5 on both branches, reported every 30 s of simulated time.

**3-second reference points** (already reported):

| Form | ρ₀ (inhibited) | ρ₁ (free) | ratio |
|---|---|---|---|
| As-committed (346x term), T=3 s | 0.018 | 0.779 | 42.76 |
| Canonical (γ/τ), T=3 s | 0.424 | 0.638 | 1.51 |

**300-second trajectory** (canonical form, same seed/protocol, checkpointed every 30 s;
full precision in `docs/gamma_tau_300s_checkpoints.json`):

| t (s) | ρ₀ | ρ₁ | ratio |
|---|---|---|---|
| 30  | 0.409 | 0.746 | 1.82 |
| 60  | 0.337 | 0.727 | 2.16 |
| 90  | 0.311 | 0.640 | 2.06 |
| 120 | 0.261 | 0.740 | **2.83** (peak) |
| 150 | 0.292 | 0.705 | 2.42 |
| 180 | 0.298 | 0.744 | 2.49 |
| 210 | 0.407 | 0.728 | 1.79 |
| 240 | 0.464 | 0.689 | **1.49** (trough) |
| 270 | 0.321 | 0.718 | 2.24 |
| 300 | 0.278 | 0.651 | 2.34 |

Mean ratio over the 10 checkpoints: **2.16 ± 0.37** (SD). Wall-clock cost: ~6070 s
(~1.7 hours) for this single 300-second run at this network's compiled step rate.

## 4. Interpretation

This is **neither a clean pass nor a clean fail** against the criterion in the Step-1
instructions ("if the free branch potentiates and the inhibited branch stays low, it
confirms the equations are correct — they just need time"):

- **Directionally real.** ρ₁ (free) is above ρ₀ (inhibited) at every single checkpoint,
  10/10. The ratio never drops to 1 or below. This is a genuine, non-zero, canonical-form
  gating signal — the "equations are just slow" hypothesis is not falsified.
- **But weak and non-converged.** The ratio oscillates in a band of roughly [1.5, 2.8]
  with no visible trend toward a stable separation by t=300 s (0.87τ) — it peaks at
  t=120s (2.83) and *drops* by t=240s (1.49) before partially recovering. ρ₀ itself never
  approaches the ~0.01-0.02 the 346x-boosted model reaches in 3 seconds; it wanders
  between 0.26 and 0.46, closer to the shared 0.5 starting point than to either stable
  well minimum. This looks like a bistable system that has not yet settled from its
  symmetric initial condition — plausible given GB2012-style double-well systems
  typically need several τ (here, plausibly >1000-1700 s) to resolve fully under noise,
  and 300 s is well under one τ.
- **The achieved separation is an order of magnitude short of the validated result.**
  Best-case ratio here (2.83) vs. the as-committed model's 42.76 — even granting more
  time to settle, there is no evidence yet that canonical GB2012 with *these specific*
  γ_p/γ_d/θ_p/θ_d/τ values converges to anything resembling the reported Yang-replication
  numbers.

## 5. What this does NOT tell us yet

I have not run long enough to see whether the ratio keeps climbing toward something
comparable to 42.76 (would need multiple τ — several more hours of wall-clock at this
network's compile/step rate) or whether it plateaus around ~2 and stays there
permanently (a much weaker but stable form of gating). Those are different findings with
different implications for Step 2, and I don't want to guess which one is true.

## 6. Recommendation

I have **not** modified `equations.py` and have **not** proceeded to Step 2. Options,
roughly in order of cost:
1. Extend this specific run further (e.g. to 1000-1500 s, several more hours of
   wall-clock) to see if the ratio is still climbing or has plateaued.
2. Run a small batch of seeds at T=300s to see whether the oscillation is seed noise
   (would average out) or a structural non-convergence (would persist across seeds).
3. Decide now that ~2x ratio, even if it eventually stabilizes, is too weak to be the
   basis of the model's headline claim, and treat this as the negative result described
   in Step 3 of your instructions — proceed to figuring out the right path together
   (e.g., is the published γ/θ/τ combination even the right one for this protocol type,
   per the still-open provenance question in `REPAIR_LOG.md`: pairing vs.
   rate/Poisson-calibrated parameter sets).

I'd lean toward (2) before (1) if you want another data point cheaply, since seed noise
vs. structural non-convergence changes what "more time" would even buy us — but this is
your call.

---

# Step 2a — Diagnostic: Model C linear relaxation vs Yang 2016 Eqs. 32–35

**Status: complete.** This is the low-cost, high-information comparison requested before
committing to the full Eq. 32–35 implementation in Model A. It answers one question:
*was Model C's linearised `exp(-(Gp+Gd)/τ)` relaxation accidentally good enough, or is it
fundamentally different from Yang's real erf-based bistable switching formula?*

Scripts (both standalone, neither touches `equations.py`):
`docs/extract_phase1_alpha.py` (measures the real α operating points) and
`docs/formula_comparison.py` (the two-formula comparison, table, and figure).
Artifacts: `docs/phase1_alpha_operating_points.json`,
`docs/formula_comparison_table.csv`, `figures/formula_comparison.png`.

## 2a.1 The two formulas, on the same Yang parameters

Both are evaluated with Yang's **published** constants so the *only* thing that differs is
the formula, not the numbers: `w0=0, w1=3, ρ*=0.5, σ=3.35, τ=346.36 s, γ_d=39.949,
γ_p=177.552, θ_d=1.0, θ_p=2.78`. With `Gp=γ_p·α_p`, `Gd=γ_d·α_d`, `E=exp(-(Gp+Gd)/τ)`:

- **(C) Model C linear** (`numpy_models/*._synapse_change`, verified w/ W1=3 here, not its
  own W1=1.0): `ρ_new = ρ̄ + (ρ_init − ρ̄)·E`, where `ρ̄ = Gp/(Gp+Gd)`. No variance term.
- **(Y) Yang Eqs. 32–35** (Nat. Commun. 7:12815, Methods p.12, transcribed from the PDF,
  not the OCR):
  - Eq. 32 `ρ̄ = Gp/(Gp+Gd)`
  - Eq. 33 `σ_ρ² = σ²(α_p+α_d)/(Gp+Gd)`
  - Eq. 34 `U = ½(1 + erf( −(0.5 − ρ̄ + ρ̄·E) / √(σ_ρ²(1−E²)) ))`
  - Eq. 35 `D = ½(1 − erf( −(0.5 − ρ̄ + (ρ̄−1)·E) / √(σ_ρ²(1−E²)) ))`
  - `w_post = w_pre(1−D) + (w1−w_pre)U`, `w_pre = w0+(w1−w0)ρ_init`; reported as
    `ρ_new = (w_post−w0)/(w1−w0)` for a like-for-like comparison against (C).

## 2a.2 The α range Phase-1 actually produces (measured, not assumed)

`extract_phase1_alpha.py` reruns Phase-1's exact reduced circuit (Soma + 2 branches + 10
SOM onto branch 0 only; exc=80 Hz, post=10 Hz, g_c=0.8 nS, seed 42, T=3 s) and integrates
the `ind_d`/`ind_p` indicators from the plastic synapses' own calcium `c_total = c + bAPCa`.
Per-synapse means (20 synapses/branch):

| branch | α_d (s) | α_p (s) | c_total mean / max |
|---|---|---|---|
| inhibited (branch 0) | 0.975 ± 0.039 | **0.000** | 0.998 / 2.775 |
| free (branch 1)      | 2.969 ± 0.011 | 2.864 ± 0.071 | 3.540 / 5.570 |

So over T=3 s, α ∈ [0, 3] s; the inhibited branch never once crosses θ_p (α_p=0 exactly),
the free branch sits above θ_p for ~95% of the protocol. These are the two operating
points the formulas are anchored to; the sweep covers the whole [0,3]² plane between them.

## 2a.3 Result — the two formulas at Phase-1's operating points (ρ_init=0.5)

| branch | α_d | α_p | ρ_linear | ρ_Yang | U | D | Δρ = Yang−lin |
|---|---|---|---|---|---|---|---|
| inhibited | 0.975 | 0.000 | 0.4468 | **0.4959** | 0.0015 | 0.0096 | **+0.049** |
| free      | 2.969 | 2.864 | 0.7600 | **0.8604** | 0.7854 | 0.0647 | **+0.100** |

- **gating ratio (free/inhibited):** linear **1.70**, Yang **1.74** — essentially identical
  (same for ρ and for w, since w = 3ρ here).

## 2a.4 What the sweep shows (see `formula_comparison_table.csv`, `figures/formula_comparison.png`)

1. **For the headline gating *ratio*, Model C's approximation was accidentally good enough.**
   At Phase-1's operating points the single-epoch free/inhibited ratio is ~1.70 either way.
   If the ratio were the only quantity we cared about, the two formulas would be
   interchangeable *here*.

2. **But the two are a genuinely different function of (α_d, α_p), not a constant offset.**
   The difference `ρ_Yang − ρ_linear` changes sign across the plane (heatmap, panel C):
   strongly **negative** (down to −0.11) in the low-α_d / moderate-α_p corner, strongly
   **positive** (up to +0.11) along the high-α_p ridge where the free branch lives. The two
   curves cross near α_p ≈ 0.7 in the potentiation arm (panel A).

3. **The variance term Model C drops (Eq. 33) is large, not negligible.** σ_ρ ranges
   **0.25–0.53** across the grid — comparable to the entire [0,1] range of ρ. That is
   exactly why the erf-based switching probabilities depart from the deterministic
   relaxation: the distribution of the bistable state is broad relative to the 0.5 barrier.

4. **Two specific, systematic discrepancies that matter for a defensible claim:**
   - *Potentiation is under-estimated by the linear form.* Free branch: 0.76 (linear) vs
     0.86 (Yang) — Yang potentiates ~13% harder (U = 0.79, a high DOWN→UP switch prob).
   - *The linear form manufactures a spurious depression on the inhibited branch.* Linear
     says ρ: 0.5 → 0.447 (a 10.6% LTD); Yang says ρ: 0.5 → 0.496 — essentially **no change**
     (D = 0.96%). One 3-s epoch is far too short ((Gp+Gd)/τ = 0.11) for the synapse to
     actually flip DOWN, and Yang's formula reports that correctly. Yang's "inhibited branch
     stays put" is a **cleaner, more honest no-potentiation control** than linear's drift.

5. **Caveat — this is a single-epoch comparison.** Yang applies the update repeatedly
   (60 pairings in the in-vitro fit; many trial epochs in vivo). The ~0.10 per-epoch gap in
   the potentiation arm and the different barrier-crossing behaviour **compound** over
   epochs: the linear form relaxes deterministically toward ρ̄ every epoch, while Yang makes
   probabilistic, more nearly all-or-none jumps. Single-epoch agreement on the *ratio* does
   **not** guarantee multi-epoch agreement — another reason to implement the real formula
   rather than lean on the approximation.

## 2a.5 Verdict

Model C's linear relaxation is **coincidentally adequate for the coarse single-epoch gating
ratio at Phase-1's specific operating points, but quantitatively wrong on the individual
endpoints by up to ~0.10 in ρ (~13% relative), in a direction-dependent way, and it invents
a ~10% depression on the inhibited branch that the real formula says should not occur.**
This confirms the decision to implement the real Eq. 32–35: the approximation is not a
faithful stand-in, and the discrepancies are of a size and kind (potentiation magnitude +
control-branch stability + epoch-to-epoch compounding) that a PI or reviewer would care
about. Proceed to Step 2b.

*(Provenance preview for 2b: the PDF is unambiguous that `w1 = 3` is Yang's own value —
"we set the weight of DOWN state to w0 = 0 and the weight of UP state w1 = 3." Model C's
`W1 = 1.0` in `emergent_gating_mechanistic_model.py` is the outlier; Model B and Model A's
`parameters.py` already use 3.0. Full write-up in the Step 2b section.)*

---

# Step 2b — Analytical Yang plasticity in Model A

## 2b.1 W1 provenance — finding

**`w1 = 3` is Yang's actual, dimensionless value, and it is mandatory for the analytical
update; Model C's `W1 = 1.0` is a deliberate [0,1] display-normalisation of a *different*
quantity, not Yang's weight — correct for what Model C plots, but wrong if ever fed into
Eqs. 34–35.** Yang, Murray & Wang (2016), Nat. Commun. 7:12815, Methods p.12, states it
outright: *"For convenience, we set the weight of DOWN state to w0 = 0 and the weight of UP
state w1 = 3"*, and one paragraph later fixes the scale: *"Before the plasticity-inducing
experiment, we have w_pre = 1 that corresponds to g̃_NMDA = 2.5 nS … after learning, the
actual synaptic conductances are g̃_NMDA = w_post · 2.5 nS."* So `w` is a **dimensionless
multiplier** on a base conductance, spanning `w0 = 0` (DOWN) → `w1 = 3` (UP), with the naive
synapse at `w_pre = 1`; it is neither in nS nor normalised to [0,1]. It is inferred jointly
with the calcium/rate model from the Graupner–Brunel (2012, ref. 36) formalism, not from an
independent fit. Tracing the code path confirms two different conventions coexist: **(a)
Model A / Brian 2** (`equations.py:207` `w = w0 + (w1-w0)*clip(rho,0,1)`, consumed at
`equations.py:212` `gTotAMPA_post += w*gAMPA`, `gAMPA = 0.4 nS`) uses `w1 = 3.0`
(`parameters.py:82`), so `w ∈ [0,3]` genuinely scales a physical AMPA conductance — this is
Yang's convention and is already correct. **(b) Model C**
(`emergent_gating_mechanistic_model.py:81-82`, used at `:382`/`:451`
`W = W0 + (W1-W0)*rho`) sets `W1 = 1.0`, which makes `W ≡ rho ∈ [0,1]`; that `W` is only a
plotting/gating index (`W_history`, selectivity panels) and **never multiplies a conductance**,
so within Model C the 1.0 is an internally-consistent [0,1] normalisation, not a bug.
**However, it is the wrong constant for the analytical rule:** `w_post = w_pre(1−D) +
(w1−w_pre)U` needs `w1 = 3`, because with `w1 = 1` and a naive `w_pre = 1.5` (ρ=0.5) the
potentiation term `(w1−w_pre) = −0.5` flips sign and potentiation would *depress*.
**Decision: use `w1 = 3` everywhere in the analytical pipeline (matching Model A and Yang).**
Model C's `W1 = 1.0` is left as-is in its own file (it is correct there) but must never be
imported into the Eq. 34–35 path; `src/v2/plasticity.py` hard-defaults to `w1 = 3`.

## 2b.2 Implementation

- **`src/v2/plasticity.py`** — standalone `yang_synapse_update(alpha_d, alpha_p, rho_init,
  …)` implementing Eqs. 32–35 verbatim (erf-based U/D with the σ_ρ² variance term), plus
  `alpha_above_threshold()` and a `rho_new()` convenience wrapper. Docstring cites Yang 2016
  Methods p.12, Eqs. 32–35 and prints the exact equations. Returns U, D, ρ̄, σ_ρ², w_pre,
  w_post, and `rho_new = (w_post−w0)/(w1−w0)` (the exact inverse of Model A's ρ→w map, so
  it writes straight back into Brian 2). Silent/shunted synapse (Gp+Gd=0) ⇒ U=D=0,
  rho_new=rho_init (matches the old gated-noise "silent synapse holds still" behaviour).
  Smoke test reproduces §2a's operating-point numbers exactly (free ρ_new=0.860, inhib
  0.496).

- **`model/equations.py`** — the continuous `drho/dt` double-well ODE is **commented out,
  not deleted**, under the label *"Legacy continuous ODE — superseded by analytical epoch
  update per Yang 2016 Eqs. 32-35"* (with the `rate_p`/`rate_d` and gated-noise lines). `rho`
  is now a settable **parameter** (`rho : 1`); `w = w0+(w1-w0)*clip(rho,0,1)` and the
  `ind_p`/`ind_d` indicators are retained. **Downstream impact (flagged, not silently
  broken):** every script that relied on the ODE to *evolve* ρ now holds ρ static at its
  initialised 0.5 unless it adopts the epoch update — `validate_vs_papers.py`,
  `validate_model.py`, `demo_v2_zhang2025.py`, `sweep_phase_diagram.py`,
  `print_network_summary.py`, and `model/full_circuit.py` (Phase 2). These need the same
  epoch-runner wrapper to be migrated; out of scope for this step but listed here so the
  migration is explicit.

- **`experiments/phase1_analytical.py`** — the refactored Model-A plasticity pipeline. Builds
  Phase-1's exact reduced circuit once (ρ held as a parameter), then per epoch: run T=3 s →
  read per-synapse α_d/α_p from compiled `run_regularly` counters (`c_total>θ` integrated at
  the full 0.02 ms `sim_dt`, reset each epoch — O(1) memory, no StateMonitor) →
  `yang_synapse_update` per synapse → write ρ (hence w) back into Brian 2. Cython codegen;
  per-epoch state is checkpointed to `docs/phase1_analytical_state.json` and auto-resumed,
  so the multi-epoch run survives process/time limits (each 3 s epoch is ~74 s wall-clock,
  dominated by the Python soma-dendrite `Coupling` network_operation). Verified bit-identical
  between numpy and Cython targets and between the StateMonitor and counter α-extraction.

## 2c — Multi-epoch validation (15 × 3 s epochs, exc=80 Hz, post=10 Hz, g_c=0.8 nS, seed 42)

**Result: PASS.** Figure: `figures/analytical_plasticity_trajectory.png`.

| epoch | 0 | 1 | 2 | 3 | 5 | 8 | 11 | 13 | 15 |
|---|---|---|---|---|---|---|---|---|---|
| **free** ρ (branch 1) | 0.500 | 0.863 | 0.916 | 0.924 | 0.924 | 0.925 | 0.924 | 0.926 | **0.924** |
| **inhib** ρ (branch 0) | 0.500 | 0.476 | 0.471 | 0.460 | 0.419 | 0.392 | 0.367 | 0.341 | **0.329** |

Final: free **ρ = 0.924** (w = 2.771), inhibited **ρ = 0.329** (w = 0.986), **ratio = 2.81**.

- **Free branch compounds toward UP and plateaus.** It reaches ρ ≈ 0.92 by epoch 2–3 and
  holds — the analytical fixed point given its calcium drive (α_p ≈ 2.9 s, α_d ≈ 3.0 s, so
  ρ̄ ≈ 0.81 and per-epoch U ≈ 0.79). Well above the 0.7 pass line. ✔ (criterion: free ρ > 0.7)
- **Inhibited branch drifts monotonically toward DOWN.** It never crosses θ_p in any epoch
  (α_p ≈ 0.02 s), so it cannot potentiate; its α_d ≈ 1–2 s gives a weak but persistent LTD
  pull, and ρ falls 0.500 → 0.329 over 15 epochs, still declining. ✔ (criterion: inhib ρ ≤ 0.5)
- **Gating is real and grows with epochs** (ratio 1.8 → 2.8 as the inhibited branch
  separates), driven by an honest mechanism — the free branch's sustained calcium vs the
  inhibited branch's shunted calcium — not by the 346× units bug. **The 42.76 figure was not
  used as a criterion** (it came from that bug); this trajectory is the new honest baseline.

**Verdict: Step 2c PASSES.** Holding here before Step 2d (SOM baseline) per instruction.

---

# Step 2d — SOM baseline at Yang's ~10 Hz → **FAIL** (diagnostic, not reverted)

**Result: FAIL.** Lowering the SOM bias from Phase-1's 25 pA to the calibrated 20.04 pA
abolishes gating under the analytical plasticity. Figure:
`figures/analytical_plasticity_trajectory_som10hz.png`; log `docs/phase1_som10hz_run.log`.
Same 15-epoch analytical protocol, only `som_bias_pA` changed.

| quantity | 25 pA (Step 2c, PASS) | 20.04 pA (Step 2d, FAIL) |
|---|---|---|
| measured SOM rate | ~63 Hz (per §3) | **10.14 Hz** (SpikeMonitor) |
| inhibited branch α_p (final) | ~0.02 s | **2.59 s** |
| inhibited branch α_d (final) | ~1.3 s | 3.00 s |
| free branch α_p (final) | ~2.90 s | 2.90 s |
| inhibited ρ (final) | 0.329 | **0.910** |
| free ρ (final) | 0.924 | 0.924 |
| ratio | 2.81 | **1.02** |

**Answer to the diagnostic question — yes, the inhibited branch now has large α_p.** It rose
from ~0.02 s (25 pA) to **2.59 s** (20.04 pA): with only ~10 Hz of SOM drive the shunt no
longer holds the branch below the NMDA plateau, its calcium crosses θ_p for most of the
epoch, and it potentiates to ρ ≈ 0.91 — indistinguishable from the free branch (both curves
overlap in the figure). This is precisely the "both branches potentiate identically"
failure, but now it is a *calcium-availability* failure, not the old 346× artefact.

## 2d.1 Yang's SOM→dendrite conductances (Methods p.12, verified from PDF)

> "…the sum of conductances of all inhibitory synapses to be **G_SOM→dend = 40 nS**, each
> SOM neuron fires **∼10 Hz** before disinhibition, and **τ_GABA,dend = 20 ms**, the
> time-averaged conductance received by each dendrite in default is
> **ḡ_I = r_I · τ_GABA,dend · G_SOM→dend = 8.0 nS**. Therefore, by setting **g_I,th = 4.0 nS**,
> excitatory synapses only target dendrites that are at least disinhibited by half. …
> **g_E,max = 25 nS**."

## 2d.2 The key finding — the model ALREADY matches Yang's inhibition; the mismatch is elsewhere

The reduced Phase-1 circuit uses 10 SOM cells × `gGABA = 4.0 nS` = **40 nS** total onto
branch 0, with `tauGABA = 20 ms`. That is **exactly Yang's G_SOM→dend = 40 nS and
τ_GABA,dend = 20 ms.** At the measured 10.14 Hz, the model's time-averaged inhibition is

    ḡ_I = 10.14 Hz × 0.020 s × 40 nS ≈ 8.1 nS  ≈  Yang's 8.0 nS default.

**So the model reproduces Yang's dendritic-inhibition spec at 10 Hz and still fails to gate.**
This flips the naive reading of the failure: it is **not** that `gGABA` is too weak relative
to Yang. Conversely, Step 2c's PASS ran SOM at ~63 Hz (25 pA), i.e.
ḡ_I ≈ 63 × 0.02 × 40 ≈ **50 nS — roughly 6× Yang's 8 nS.** The model only gates when the
inhibited branch receives several times the inhibition Yang specifies.

**Interpretation.** The discrepancy lives in the **calcium/NMDA pathway sensitivity**, not in
the GABA conductance. At Yang's own 8 nS time-averaged inhibition, this spiking
multicompartment branch still reaches the NMDA plateau and integrates calcium above θ_p,
whereas Yang's *rate* model treats g_I,th = 4 nS as the disinhibition boundary. The calcium
scaling (`kappa_Ca_NMDA = 0.26/pA`, calibrated in Phase-1 at the 25 pA/63 Hz operating point),
`gNMDA`, and/or θ_p place the plateau threshold such that the branch needs ~6× more shunting
than Yang to stay sub-threshold. **This also means Step 2c's headline gating (ratio 2.81) was
obtained at ~6× Yang's inhibition — an important caveat for the project's baseline.**

## 2d.3 Proposed recalibration (NOT applied — reporting first, per instruction)

Raghav's hypothesis (bump per-synapse gGABA so 10 Hz delivers the same total inhibition) is a
valid *engineering* fix, but note it would push SOM→dend conductance **above** Yang's reported
40 nS, because the model already matches 40 nS. The options, honestly framed:

- **(A) Strengthen gGABA to the model's requirement.** Raise `gGABA` so 10 Hz SOM delivers the
  ~50 nS the model needs to gate (≈ 25 nS/synapse → 250 nS total, ~6× Yang's 40 nS). Restores
  gating at Yang's SOM rate, but the SOM→dend conductance then departs from Yang by ~6×; only
  defensible if explicitly labelled "the spiking model requires stronger unitary GABA than
  Yang's rate model."
- **(B) Reduce the branch's calcium sensitivity so 8 nS suffices.** Lower `kappa_Ca_NMDA`
  and/or `gNMDA`, or raise θ_p, so Yang's 8 nS inhibition keeps the branch below θ_p. This
  keeps SOM→dend at Yang's 40 nS but **re-opens the whole Phase-1 calcium calibration** — the
  free branch must still cross θ_p, so any change has to be re-validated against Step 2c.
- **(C) Document the discrepancy rather than force-fit.** Accept that this spiking
  implementation's faithful operating point is its own (SOM must supply ≳ g_I,th-equivalent
  shunting, which here needs ~40–63 Hz), and that Yang's exact 10 Hz / 8 nS does not transfer
  1:1 to the spiking model. Report it as a known calibration gap.

**Recommended next step before choosing A/B/C — a cheap, high-information diagnostic (à la
Step 2a):** sweep the SOM rate (equivalently ḡ_I from ~8 → ~55 nS) and locate the gating
threshold — the ḡ_I at which the inhibited branch's α_p collapses to ~0. That single curve
tells us whether the model's requirement is a modest ~2× over Yang (making (B) feasible
without breaking the free branch) or the full ~6× (favouring (A) with an explicit caveat, or
(C)). I have **not** changed `gGABA`, `kappa_Ca_NMDA`, or any parameter. Awaiting your call.
