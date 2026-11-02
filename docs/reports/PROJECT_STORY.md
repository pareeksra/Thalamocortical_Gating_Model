# The project's story, start to now

One continuous narrative, in order, so you can read it front-to-back without jumping between
files. Same shape throughout: **what we were trying to do → what happened when we ran it → what
we concluded → what we changed → how we checked it actually worked.** Every number here is
sourced from the repo (mostly `scripts/build_progress_report.py`, `docs/reports/REPAIR_LOG.md`,
`docs/reports/gamma_tau_analysis.md`, and this session's own reliability-sweep results) — nothing new is
being asserted, this is the existing evidence retold as one story instead of nine report
sections. This document supersedes `docs/reports/NARRATIVE_WALKTHROUGH.md` for the "whole project" view;
that file still exists but everything in it is folded in here, plus the parts before and after it.

---

## 0. Where the idea came from

**The question:** can a single biological mechanism let the mediodorsal (MD) thalamus help
prefrontal cortex switch between contexts without erasing what it already learned? Concretely:
can MD activity control *which dendritic branch* of a pyramidal neuron is allowed to learn, so
different contexts write onto different physical branches instead of overwriting the same
synapses?

**Why two papers, grafted together:** neither paper alone answers this.
- **Yang, Murray & Wang (2016)** has the mechanism — a spiking, reduced-compartment pyramidal
  neuron with a dendritic disinhibitory circuit (VIP inhibits SOM, SOM inhibits the dendrite, PV
  inhibits the soma) and calcium-based Graupner-Brunel plasticity on the dendrite — but no
  thalamus. Just an abstract "control input."
- **Zhang et al. (2025)** has the thalamus — a trained rate RNN with an MD that projects to
  interneurons in a cell-type-specific way (MD's GRIK4 cells → PV, its DRD2 cells → VIP) — but no
  dendrites and no synaptic plasticity. It's a trained network, not a mechanistic one.

**The plan:** replicate Yang's single-neuron gating mechanism, graft on Zhang's MD→interneuron
wiring, see whether MD activity can control which branch gates. Worth being precise about scope
early, because it's easy to overstate: we borrow Zhang's *wiring labels* only — not its trained
task, its behavioral results, or its PFC↔MD feedback loop — and the model runs 1 soma / 2
dendrites / 20 interneurons per type, nowhere near Yang's own ~3,000-neuron network.

**Three implementations exist in the repo, and only one matters going forward:**

| Model | What it is | Status |
|---|---|---|
| A — Brian 2 spiking network | Full spiking circuit: multi-compartment pyramidal cell, PV/SOM/VIP as LIF interneurons, MD as Poisson input, native Brian 2 Graupner-Brunel synapses | **Working** — the only one whose plasticity actually functions |
| B — Phenomenological NumPy | Proof-of-concept, hardcoded dendritic inhibition instead of simulated interneurons | Inert (falls back to a random walk) |
| C — Emergent mechanistic NumPy | Inhibition emerges from noisy interneuron rates | Inert, same underlying reason |

Everything below is about Model A. B and C are frozen illustrative sketches and don't get
revisited.

---

## 1. Before Phase 1 even started: a structural repair pass

Before running any real gating experiment, an audit of the existing code (`docs/reports/REPAIR_LOG.md`)
found several pieces that were either dead code or subtly wrong. Worth knowing about because
Phase 1's Bug 2 (next section) is really the tail end of this same repair effort:

- **`dend_IO` (the dendritic input-output curve) had a sign defect.** The raw fitted formula
  implied that *more* inhibition could *depolarize* an unexcited branch by up to 29.89 mV — physically
  impossible, since dendritic GABA_A in this model is purely shunting (`vI_pyr = vRest_pyr`, no
  current at rest). Fixed by re-referencing the formula to rest; resting error went from up to
  29.89 mV to exactly 0.00 mV, without touching the fitted constants or the excitation-response
  slope.
- **The postsynaptic (bAP) calcium pathway was completely unwired.** `Dend` has no spike
  threshold — it never fires — so the `on_post_plasticity` handler meant to inject bAP calcium
  could never execute. This is the same underlying gap that shows up as "Bug 2" in Phase 1 below.
- **The PV interneuron's baseline current couldn't work as designed.** PV's f-I curve is nearly a
  step function (threshold-to-reset gap of only 5 mV at τ=10ms), so a bias-current approach that
  worked for SOM would need sub-fA precision for PV — not usable. Fixed by switching to a
  background Poisson **conductance** input instead (500 Hz, 0.25 nS, derived to sit just below
  the ~0.4 nS needed to reach threshold), so PV's firing is fluctuation-driven and graded rather
  than a knife-edge.
- **Two NumPy calcium-kernel bugs** were found and fixed by exact re-derivation (a kernel injected
  into the wrong ODE variable, 24x too small; a normalization constant off by ~18%).
- **The Mg²⁺ NMDA gate** was implemented using the project's own existing parameterization rather
  than importing a different form from the NumPy models, and checked to agree with the alternative
  form to within 0.064 mV of half-activation.

None of this touched the deeper calcium *model* problem yet — that's Bug 2, next.

---

## 2. Phase 1 — can we get ONE neuron to gate at all?

**The goal:** one pyramidal cell, two dendritic branches, SOM inhibiting only branch 0. The free
branch should potentiate; the SOM-inhibited branch should not.

**What we ran, and what happened:** the plasticity check (Test 3) was passing, but only barely —
ratio ~1.02. A false-positive check on that exact test showed it would pass by chance **50.7% of
the time** at that threshold. A coin flip. Something underneath was broken.

**Two independent things were broken, not one:**

**Bug 2 — the calcium computation wasn't Yang's math.** The dendrite never spikes (see §1), so
bAP calcium injection was dead code. Separately, the NMDA conductance variables were declared but
never assigned — no NMDA current existed anywhere. And the older NumPy prototypes that *did*
compute a calcium value used fixed per-spike jumps rather than Yang's leaky-integral form (his
Eq. 13) — which has a hard ceiling (0.371+0.957=**1.328**) below the potentiation threshold
(θ_p=2.78), making LTP mathematically impossible regardless of parameters.
*Fix:* implemented the actual leaky-integral NMDA calcium ODE, wired the bAP transient into the
dendrite for real, and implemented the missing saturating NMDA conductance.

**Bug 1 — even with the calcium math fixed, the branches still didn't separate.** The soma was
measured firing at ~201 Hz — Yang's protocol pins it at ~10 Hz externally. Traced to a coupling
constant: `parameters.py` already had the *correct* Yang in-vivo value (0.8 nS) sitting unused;
the experiment code used 4.0 nS instead. A calcium-component diagnostic (splitting total calcium
into its branch-specific NMDA part and its branch-uniform bAP part, across several somatic rates)
showed selectivity dying above **~74.3 Hz** somatic rate, because the uniform bAP term becomes an
ever-larger *shared* component under both branches, diluting the branch-specific signal. This had
actually been characterized once already, earlier, and *deliberately left unfixed* — the first
pass through this diagnostic ended with a decision to just document the ~74 Hz limit rather than
re-engineer anything. It came back as Phase 1's actual blocker, and that's when it got fixed for
real: 0.8 nS coupling, somatic rate **externally pinned at ~10 Hz** (Yang's own protocol), and the
branch's own excitatory drive tuned to 80 Hz (120 Hz was tried first).

**Verification, independent of the tests that were passing before:** `validate_vs_papers.py`
measured the model's dendritic half-activation at five inhibition levels and compared against
Yang's own closed-form `g₁/₂ = 5.56·(4+g_inh)`. Measured values (22.24, 33.36, 77.83, 133.42,
216.81 nS) matched **to the digit** at every level.

---

## 3. The paper-replication battery, and an honest flag

Four checks against the two source papers (`validate_vs_papers.py`):

- **V1** (Yang Fig. 2c, dendritic I/O): matches Yang's formula exactly, as above.
- **V2** (Yang Fig. 7b, rate-dependent LTP threshold): free-branch ρ climbs from 0.580 at 20 Hz
  presynaptic rate to 0.811 at 100-120 Hz; inhibited branch stays flat and low (~0.012-0.020)
  across the whole range — the LTP threshold shifts with rate the way Yang's model predicts.
- **V3** (Yang Fig. 7d-e, gating at Yang's own operating point): ρ_free=0.792, ρ_inhibited=0.012,
  ratio **64.83**.
- **V4** (Zhang wiring, qualitative): as MD drive rises 0→40 Hz, VIP rises 0→93 Hz, which
  suppresses SOM (36→0 Hz) — the disinhibition pathway working as Zhang's wiring predicts, while
  PV rises in parallel (7→127 Hz) as the separate gain-control arm.

**The flag worth carrying forward:** three different measurements of what's nominally the *same*
headline ratio disagree by close to 50% — the README's own top-line number (~43), V3's measurement
(64.83), and a later re-measurement during the γ/τ audit (42.76) — all at seed 42, same nominal
parameters. At the time this was thought to be "a reproducibility problem" (Test 5 showed the same
seed giving slightly different PV rates across runs). That has since been diagnosed (see §10): it was
a Brian2 in-process quirk in the test harness, not a model defect — results *are* reproducible per
seed. So the three-way ratio spread is a genuine, still-open measurement discrepancy in its own
right, not a symptom of non-determinism; no single "true" number was picked.

---

## 4. Phase 2 — how much can this circuit take, and what breaks it on purpose?

Two questions, asked of the *full* circuit (PV/VIP/SOM/MD added to Phase 1's bare pair of
branches), not the reduced one.

**4.1 — Noise robustness.** Three biologically distinct noise sources (MD noise input, vesicle-
release variability, SOM/VIP background conductance fluctuation) scaled together under one
`noise_level` knob. Selectivity starts around **62** at zero noise, drifts down through an
"unstable transition zone" (noise 0.30-0.40, where individual seeds start disagreeing with each
other), and collapses sharply — by noise 0.45 the ratio is below 1.5 and stays near 1 (no gating)
out to noise 2.0.

**4.2 — The ketamine / NMDA-hypofunction simulation.** A targeted disruption, not generic noise:
ketamine-class drugs preferentially block NMDA receptors on fast-spiking and VIP-type
interneurons at sub-anesthetic doses (a standard schizophrenia-dysfunction model in the
literature). Implemented at the model's one synapse for that pathway — MD→VIP excitatory weight —
linearly attenuated from intact (1.0) to fully blocked (0.0), MD held at 25 Hz throughout.

**The prediction, stated before running anything:** block MD→VIP, VIP can't be recruited by MD
anymore, SOM stops being suppressed regardless of what MD is doing, SOM sits at its own baseline
and tonically shuts its target branch even under an MD signal that should have opened the gate.

**What we saw:** exactly that. At 0% and 34% block, both branches potentiate together (ρ≈0.80-
0.81) — MD successfully drives VIP (~29 Hz), which suppresses SOM near 0 Hz, so neither branch is
shunted. At 67% and 100% block, the SOM-targeted branch collapses to ρ≈0.015-0.02 while the free
branch stays at ~0.80 — SOM has risen back to its ~36.5 Hz baseline because VIP can no longer be
driven, and that baseline firing alone is enough to permanently shunt its branch regardless of the
ongoing MD signal. **The interesting part isn't that output gets weaker — it's that MD's control
over *which* branch learns is what breaks**, below ~50% block MD can still pick the branch, above
it the branch is stuck closed no matter what MD says. That's the schizophrenia-relevant reading: a
loss of context-dependent flexibility, not global silencing.

---

## 5. The audit — does the circuit actually match Yang's paper, line by line?

Separately from building forward, the implementation was checked against Yang's Methods section
directly, looking for quiet departures. Three were found:

**Divergence 1 — SOM→PV synapse declared but never wired.** Yang's Fig. 6 includes it at P=0.8;
the weight parameter and the receiving equation channel existed, unused — PV's inhibitory current
was always exactly zero. Fixed: added the connection probability, wired the actual `Synapses`
object. Closed.

**Divergence 2 — SOM's baseline rate was ~4x too high.** Yang: ~10 Hz. Project: ~36-40 Hz.
Recalibrated analytically to 20.04 pA → 10.00 Hz in isolation. **But testing that inside the real
gating protocol broke gating almost completely** — both branches potentiated to nearly the same
degree (ratio 1.02 vs. 2.81 at the old setting). Matching Yang's literal number and preserving the
model's own headline result were directly in tension — this became the seed for the whole SOM-
baseline saga in §7.

**Divergence 3 — the γ/τ units bug.** See §6, it's big enough to be its own section.

---

## 6. The plasticity refactor — why 3 simulated seconds was ever enough

**What we were checking:** Graupner-Brunel's own time constant, τ=346.36 s (Yang's published
value), implies weight-change dynamics on a multi-minute timescale. The project's protocol runs
3 simulated seconds per trial. Why did that ever show a result?

**What we found:** the `drho/dt` equation divided only the double-well restoring term by τ; the
potentiation/depression (γ) terms were multiplied by a bare `1/second` instead. Ratio of what was
written to the correct form: exactly τ = **346.36**. The γ terms were running 346x too strong.
(A comment in the code already flagged this as "346x stronger" before it was independently
re-derived from the paper — a known, unresolved flag, not a hidden bug.)

**What we tested, to see if patching in place would work:**

```
Form                        ρ inhib   ρ free   ratio    duration
As-committed (346x term)      0.018    0.779   42.76    T = 3 s
Canonical (correct γ/τ)       0.424    0.638    1.51    T = 3 s
```

Run for 300 simulated seconds (1.7 hrs wall-clock), the corrected form oscillated between ratio
1.49 and 2.83, never converging — an order of magnitude short of 42.76.

**What we did:** stopped patching a continuous ODE we'd derived ourselves and implemented Yang's
actual published closed-form update instead (his Eqs. 32-35) — a formula, not an ODE, that
analytically returns the post-trial synaptic state given how long a trial's calcium spent above
each threshold, correctly folding in τ=346s through its own exponential term without needing to
literally simulate 346+ seconds per trial.

**A second bug turned up while wiring this in:** the old NumPy model's `w1=1.0` (a display
normalization, correct for its own plots) would flip potentiation into depression if plugged into
Yang's real formula, which needs `w1=3.0`. Caught during a provenance check before it was ever
used live; the new code hard-defaults to `w1=3`.

**Verified over multiple epochs**, not one trial:

```
epoch:        0      1      2      3      5      8     11     13     15
free ρ:     0.500  0.863  0.916  0.924  0.924  0.925  0.924  0.926  0.924
inhib ρ:    0.500  0.476  0.471  0.460  0.419  0.392  0.367  0.341  0.329
```

Final ratio **2.81** — a real mechanism (sustained vs. shunted calcium), not the 346x artifact.
Much smaller than the old 42.76 headline, and that's the point: 42.76 was never real.

---

## 7. The SOM baseline saga — 25 Hz, seed 44, and relocking to 30 Hz

**What we tried:** a duty-cycle argument (SOM needs to fire fast enough that inter-spike gaps
stay under τ_GABA,dend=20ms, roughly ≥20 Hz) → picked **25 Hz**. Re-ran Phase 1 (ratio 5.58,
agreeing to ~1.5% across three code paths) and both Phase 2 sweeps. Looked solid.

**What happened under stress-testing:** an initial 5-rate x 10-seed reliability sweep showed 25 Hz
passing 10/10 — but the sweep used a *different circuit* and a *disjoint seed range* from where a
failure had actually been seen, so the "pass" never tested the failure case. Caught before
trusting it; not acted on.

**Reproducing the real failure:** the exact failing condition (full circuit, seeds 42-46)
reproduced **seed 44 failing at ratio 1.015** — the inhibited branch's rate climbs to ~0.91,
nearly matching the free branch — confirmed identically across repeated runs. Surprising detail:
SOM's mean firing rate was statistically identical across all five seeds (25.27 Hz, including 44)
— not "seed 44 got a slower SOM," more like a stochastic escape specific to that seed's exact
spike timing.

**Getting a real failure rate, not n=5:** 20 seeds (40-59) at 25 Hz in the full circuit — **18/20
passed, seeds 44 and 53 both failed** at essentially the same ratio (~1.02). A real ~10% failure
rate, not a one-off. The same 20 seeds at **30 Hz: 20/20 passed** (ratios 3.25-5.07).

**What we did:** relocked the baseline to 30 Hz (`iBaseline_som`: 20.9 → 21.32 pA), re-ran Phase 2
under the new baseline (old 25 Hz results preserved as backups, not overwritten), regenerated the
report.

**Trying to explain *why* seed 44 fails, and how far that actually got:** compared seed 42 (pass)
against seed 44 (fail) — SOM inter-spike-gap histograms, and the inhibited branch's calcium trace
against θ_p. Honestly: the ISI-gap histograms look statistically indistinguishable between the two
seeds — the clean "SOM got an unlucky gap" story doesn't show up in the data the way expected.
What does differ is that seed 44's calcium trace sits higher and crosses θ_p more persistently.
So the escape is real and visible, but not yet pinned to one isolated cause — more likely a joint
coincidence between SOM's pattern and the branch's own reseeded 80 Hz drive than a SOM-only story.
Reported as real-but-partially-characterized, not oversold.

---

## 8. Where this leaves things right now

- **Working, verified, current baseline:** Model A, SOM at 30 Hz, analytical Yang plasticity
  (Eqs. 32-35), 20/20 seed reliability at that baseline in the full circuit.
- **Still open:**
  - The seed-44 escape mechanism is real but not fully explained (§7, last paragraph).
  - Phase-1's three-way headline-ratio discrepancy (§3) was flagged, never fully resolved.
  - ~~Reproducibility (Test 5)~~ **RESOLVED (2026-10-11, see §10):** results are exactly
    reproducible per seed (verified: same seed in two processes → bit-identical). The Test-5
    failure was a Brian2 in-process PoissonGroup RNG quirk in the harness, not a model defect;
    the test was rewritten to a fresh-process check and now passes.
  - Models B and C remain plasticity-inert; whether to repair or retire them was never decided.
  - Network-scale stage (Yang's ~3,000-neuron regime vs. this project's 1-soma/2-dendrite/
    20-interneuron circuit) hasn't been started at all.
  - Before/after diagrams for Bug 1 and Bug 2 specifically (visual, not just the numbers above)
    are still outstanding as of this writing.

---

## 9. Appendix — replicating Yang's Supplementary Figures 1 & 2 (2026-09-17)

We reproduced Yang's actual Supplementary Figures 1 and 2 with a faithful single-dendrite
spiking simulation (`experiments/yang_supp_replication.py`) using his own equations and our
Yang-calibrated constants, and compared panel-by-panel against the real supplementary PDF. A
plain side-by-side deck is in `docs/meetings/Yang_Supp_Comparison.pptx` (paper left, our model right).

Not every panel is equally relevant to *our* project — some are the mechanism our model is
built on, others are Yang justifying his own modelling choices. We split them accordingly:

**Relevant to our gating model (the dendritic NMDA-plateau mechanism we depend on):**
- **Supp Fig 1f — NMDA plateau potential.** The dendrite jumps sharply to a plateau once enough
  NMDA synapses activate (≥15). Our dendritic branches rely on exactly this nonlinearity.
- **Supp Fig 1g — NMDA input gated by inhibition.** A sharp ~25-30 Hz threshold that 30 Hz
  inhibition fully suppresses. This *is* our gating mechanism (SOM shutting a branch).
- **Supp Fig 2a — saturating NMDA enables strong inhibitory control.** The inhibited branch never
  reaches the disinhibited level at any rate — why gating is robust in our model.

**Generated only to validate Yang's modelling choices (our model does not use these):**
- **Supp Fig 1h — AMPA input.** Roughly linear, barely gated — validates the NMDA-only choice.
- **Supp Fig 2b — non-saturating NMDA.** A control: without saturation, inhibition loses control.
- **Supp Fig 2c — steady-state bistability** and **Supp Fig 2d — NMDA conductance saturation.**
  Theory panels underpinning the plateau switch.

Faithful replication verdict: panels 1f/1g/1h and 2a/2b/2c/2d match Yang qualitatively and
near-quantitatively. **Not reproduced:** Supp Fig 1a-d (the fully reconstructed Branco NEURON
morphology — not in this project) and Supp Fig 2e-h (stochastic-switching panels — deferred).
Figures: `figures/pre_audit/yang_supp1_replication.png`, `figures/pre_audit/yang_supp2_replication.png`; cropped
panels in `figures/pre_audit/supp_panels/`.

---

## 10. Reproducibility — investigated and resolved (2026-10-11)

**Concern:** `validate_model.py` Test 5 reported that the same random seed gave different PV
firing rates across runs, which had sat on the open-items list as "model not reproducible,
undiagnosed." We took it down to basics, evidence-first, assuming nothing.

**What we established, with fresh live evidence:**
1. **Our results are exactly reproducible per seed.** `build_gating_circuit` (the function behind
   every reported number) run twice at the same seed in *separate processes* → **bit-identical**
   output, full precision, including the per-epoch trace (`docs/determinism_check.py`). Independently
   corroborated: seed 44 gave identical ratio/r0/r1 in two unrelated historical runs.
2. **The non-reproducibility was isolated to Test 5's harness**, specifically the PV rate at MD = 5 Hz
   — a configuration we never use for results.
3. **Root cause, bisected** (`experiments/test5_pv_diag.py`): same seed, *same process*, two builds →
   PV differs (589 vs 543 spikes). The bisection showed **PoissonGroup spike trains differ** (BG_pv
   19977 vs 19781; MD 502 vs 509) while **connectivity is identical** (517 = 517). So Brian2's
   `connect(p=...)` reseeds correctly, but **PoissonGroup spike generation is not reset by `seed()`
   across repeated builds within one process.** Confirmed the complement: the same seed-0 build in two
   *separate processes* gives identical PV (589 = 589).

**Conclusion:** it is a known Brian2 **in-process** quirk, not a model defect. Our results are
unaffected because every result is generated one-build-per-process (sweeps use `ProcessPoolExecutor`;
diagnostics are separate invocations).

**Fix applied:** Test 5 was rewritten (`experiments/validate_model.py`) to check reproducibility the
way results are actually produced — each seed in a **fresh subprocess**. It now **passes**: seed 0 in
two fresh processes gives bit-identical PV/SOM/Pyr (14.725 / 36.500 / 6.000 Hz), and the cross-seed
CV check (seeds 0/42/84) passes (PV CV 0.07, SOM 0.01, Pyr 0.04). Supporting scripts:
`docs/determinism_check.py`, `experiments/test5_pv_diag.py`.
