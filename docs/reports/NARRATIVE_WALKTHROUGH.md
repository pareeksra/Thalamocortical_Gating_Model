# Narrative walkthrough — the project's story, in "we tried X, it broke, we did Y" form

This is a plain-language companion to `Progress_Report.docx`. That document is organized by
*topic* (Section 2.1 "calibration bugs," Section 4 "audit," Section 5 "plasticity refactor," ...)
and reads well if you already know the shape of the story. This document is organized by
*time* instead — what we were doing, what happened when we ran it, what we concluded, what we
changed — so a third-party reader (or the same reader a week later) can follow the causal chain
without already holding the ending in their head. Every number below is cited back to the source
doc/script; nothing here is a new claim, it's the same facts told as a sequence of events.

---

## Episode 1 — Phase 1: can we even get ONE neuron to gate?

**The goal we were testing for:** one pyramidal cell, two dendritic branches, SOM inhibiting
only branch 0. Drive both branches the same way; the free branch should potentiate (LTP), the
SOM-inhibited branch should not. This is the entire foundation the rest of the project sits on.

**What we ran, and what happened:** we ran the model's plasticity check (Test 3: does the free
branch beat the inhibited branch?) and it was passing — but only barely, at ratio ~1.02. That's
not a real result. A quick false-positive-rate check on that exact test showed it would pass by
pure chance **50.7% of the time** at that threshold — i.e., a coin flip. So "Test 3 passes" told
us nothing. Something underneath it was broken, and we had to find out what.

**What we found — two independent things, not one:**

1. **The calcium computation itself wasn't Yang's.** Digging into the equations, we found the
   dendrite (`Dend`) has no spike threshold — it literally never fires — so the code path meant
   to inject postsynaptic (bAP) calcium into the plasticity variable could never execute. It was
   dead code. Separately, the NMDA conductance variables (`iTotNMDA1`/`iTotNMDA2`) were declared
   in the equations but nothing ever assigned them — no NMDA current existed anywhere in the
   model. And the *older* NumPy prototype versions of the calcium model, which did compute
   something, used fixed per-spike calcium jumps rather than Yang's leaky-integral form (his
   Eq. 13). That distinction matters structurally: a per-spike jump has a hard ceiling
   (0.371 + 0.957 = **1.328**) no matter how long you drive it, and that ceiling sits *below*
   the potentiation threshold θ_p = 2.78. So even a perfectly-driven branch could never LTP —
   the math made it impossible before any parameter was even touched. **This is "Bug 2."**

2. **Once the calcium math was fixed, the branches still didn't separate — for a completely
   different reason.** We measured the soma firing at ~201 Hz in the actual experiment. Yang's
   protocol pins the soma at ~10 Hz externally; running it 20x faster was never intended. We
   traced this to a coupling constant: `parameters.py` already had the *correct* Yang in-vivo
   dendrite-soma coupling value (0.8 nS) sitting there, unused — the experiment code was instead
   using 4.0 nS. At that coupling and firing rate, we ran a diagnostic that split total dendritic
   calcium into its two physical components (NMDA — branch-specific, saturating; bAP —
   branch-uniform, does not saturate) at several somatic rates:

   ```
    soma Hz   bAP-Ca   total(free)  total(inhib)   ratio    outcome
          0    0.000      1.613        0.076       21.22    selective
         37    1.347      2.960        1.423        2.08    selective (weaker)
         74    2.704      4.317        2.780        1.55    boundary
        201    7.316      8.929        7.392        1.21    selectivity LOST
   ```

   The pattern: bAP calcium is identical on both branches and doesn't saturate, so as somatic
   rate climbs it becomes a bigger *shared* term sitting under both branches' totals, diluting
   the actual branch-specific signal. We derived analytically that selectivity dies above
   **~74.3 Hz** somatic rate. At 201 Hz we were nearly 3x past that line. **This is "Bug 1."**

**What we did about it, in order (this took two passes, not one):**

- *First pass (early audit, before Phase 1 experiments):* we ran the diagnostic above, understood
  exactly why selectivity was breaking, and — at that point — decided **not** to re-engineer
  anything. We documented it as a known limitation ("valid below ~74 Hz somatic rate") and moved
  on to other things. This was a deliberate, logged decision, not an oversight.
- *Second pass (Phase 1 itself):* when this exact problem came back as the thing actually
  blocking Phase 1's real experiment, we used the diagnostic we'd already done to fix it properly
  this time: switch to the correct 0.8 nS coupling, **externally pin the somatic rate at ~10 Hz**
  (matching Yang's own protocol instead of letting it run free), and tune the branch's own
  excitatory drive rate (we tried 120 Hz first, landed on 80 Hz as what's actually committed).
  We then explicitly characterized the safe window this produces — free branch crosses θ_p once
  `post_rate > 7.6 Hz`; inhibited branch stays below θ_d as long as `post_rate < 25 Hz` — and
  confirmed Yang's own 10 Hz sits comfortably inside it.

**How we verified this actually worked**, not just "the test passed": `validate_vs_papers.py`
independently measured the model's dendritic half-activation at five inhibition levels and
compared against Yang's own closed-form formula, `g₁/₂ = 5.56·(4+g_inh)`. The measured values
(22.24, 33.36, 77.83, 133.42, 216.81 nS) matched the formula **to the digit** at every level —
strong evidence the fix landed the model in Yang's actual regime, not just a regime that happens
to pass one internal check.

---

## Episode 2 — the audit: does the *circuit* actually match Yang's paper?

**The goal we were testing for:** separate from building the model forward, we went back and
checked the implementation against Yang's Methods section line by line, looking for places it
quietly departs from the paper it's supposed to implement.

**What we found — three "divergences," of very different character:**

1. **SOM→PV synapse was declared but never wired.** Yang's Fig. 6 includes a SOM→PV inhibitory
   connection at P=0.8. The project already had the weight parameter (`gGABA_pv`) and the
   receiving side of the equations sitting there, unused — the connection itself was never built,
   so PV's inhibitory current was always exactly zero. An honest omission, not a deliberate
   simplification.
   **What we did:** added `p_som2pv = 0.8` and wired the actual `Synapses` object in
   `full_circuit.py`. Divergence closed.

2. **SOM's baseline firing rate was ~4x too high.** Yang sets SOM at ~10 Hz via a 150 pA bias
   current; the project's SOM cells were running at ~36-40 Hz under a 22 pA bias.
   **What we did:** recalibrated analytically (SOM's f-I curve is nearly a step function, so a
   0.01 pA sweep was needed) and landed on 20.04 pA → measured 10.00 Hz in isolation.
   **What happened when we actually tested that fix inside the real gating protocol:** it broke
   gating almost completely — both branches potentiated to nearly the same degree (ratio 1.02
   vs. 2.81 at the old 25 pA / ~63 Hz setting the project had been using). So "matching Yang's
   rate" and "the model's own headline result" were directly in tension — recalibrating to be
   more faithful to the paper's stated number made the model's actual signature result collapse.
   This divergence is *closed* in the narrow sense that SOM now fires at Yang's stated rate, but
   it opened a bigger question the project had to keep working through (see Episode 4).

3. **The γ/τ units bug** — this one reshaped the whole next phase of work. See Episode 3.

---

## Episode 3 — the plasticity refactor: chasing down why 3 seconds of simulated time was enough

**What we were testing for:** understanding *why* the model's `drho/dt` equation gave any
result at all in a 3-second simulated run, when the underlying theory (Graupner-Brunel 2012) has
a weight-change time constant τ = 346.36 seconds — nearly six minutes.

**What we found:** the equation as written divided only the double-well restoring term by τ; the
potentiation/depression (γ) terms were instead multiplied by a bare `1/second`. The ratio between
what was written and the mathematically correct form is exactly τ = **346.36** — the γ terms were
running 346x stronger than they should. (The code already carried a comment flagging this as
"346x stronger" before we re-derived it independently from the paper — it wasn't hidden, it was a
known-but-unresolved flag.)

**What we tried, to see if just patching the units bug in place would work:** swapped in the
mathematically correct form (both terms divided by τ), left everything else untouched, and ran
it at two timescales:

```
Form                       ρ inhib   ρ free   ratio   duration
As-committed (346x term)     0.018    0.779   42.76   T = 3 s
Canonical (correct γ/τ)      0.424    0.638    1.51   T = 3 s
```

At 3 seconds, the corrected form barely separates the branches. We then ran the corrected form
for 300 simulated seconds (1.7 hours of wall-clock) to see if it just needed more time — it
oscillated between ratio 1.49 and 2.83 without converging, an order of magnitude short of the
old 42.76 headline number.

**What we concluded and did:** patching the ODE in place and hoping it would settle out over
more (expensive) simulated time wasn't obviously going anywhere. Yang's own paper doesn't
actually integrate a continuous ODE during a trial in the first place — it uses a closed-form,
per-epoch analytical update (his Eqs. 32-35). So we stopped debugging our own derived ODE and
implemented Yang's actual published formula instead. The old ODE was commented out (not deleted,
kept for provenance), and `src/v2/plasticity.py` now implements Eqs. 32-35 directly: given how
long a trial's calcium trace spends above each threshold, the formula returns the exact
analytical post-trial synaptic state — correctly incorporating the full τ=346s timescale via its
own exponential term, without needing to literally simulate 346+ seconds per trial.

**A second bug turned up while wiring this in:** the old NumPy prototype (Model C) used
`w1 = 1.0` (a [0,1] display normalization, correct for its own plots) where Yang's actual formula
needs `w1 = 3.0`. Caught during a provenance check *before* it was ever plugged into the new
pipeline — plugging w1=1.0 into Eq. 34-35's potentiation term would flip its sign and turn
potentiation into depression. `src/v2/plasticity.py` hard-defaults to `w1 = 3`.

**What we verified after implementing the real formula, over multiple epochs (not just one
3-second trial):**

```
epoch:        0      1      2      3      5      8     11     13     15
free ρ:     0.500  0.863  0.916  0.924  0.924  0.925  0.924  0.926  0.924
inhib ρ:    0.500  0.476  0.471  0.460  0.419  0.392  0.367  0.341  0.329
```

Final ratio **2.81** — real, honest, and driven by an actual mechanism (sustained calcium on the
free branch vs. shunted calcium on the inhibited branch), not by the 346x artifact. This is a
much smaller number than the old 42.76 headline, and that's the point — 42.76 was never real.

---

## Episode 4 — the SOM baseline saga: 25 Hz, seed 44, and relocking to 30 Hz

**What we were testing for:** picking a defensible SOM baseline firing rate. Episode 2 showed
Yang's literal 10 Hz breaks the model's own gating result. We needed a rate that both gates
reliably and has a real justification.

**What we tried first:** a duty-cycle argument — gating needs SOM firing fast enough that gaps
between its spikes stay shorter than `tau_GABA,dend = 20 ms`, i.e. roughly ≥ 20 Hz. We picked
**25 Hz** and re-ran Phase 1 (ratio 5.58, agreeing to ~1.5% across three code paths) and both
Phase 2 sweeps. Looked solid.

**What happened when we stress-tested it with more seeds:** a 5-rate x 10-seed reliability sweep
initially showed 25 Hz passing 10/10 seeds — but we caught, before trusting that result, that the
sweep script used a *different* reduced circuit and a *disjoint* set of seeds (0-9) from the one
where a failure had actually been seen (seeds 42-44, full circuit). The "pass" never actually
tested the failure case. We stopped and did not act on that misleading result.

**Reproducing the real failure directly:** ran the exact failing condition (full circuit,
noise=0, seeds 42-46) and found **seed 44 reproducibly fails** — ratio 1.015, and the inhibited
branch's rate climbs to ~0.91 (nearly matching the free branch, 0.925) — a real collapse, not
noise, confirmed identically across two separate runs.

**The surprising part:** SOM's mean firing rate was statistically *identical* across all five
seeds (25.27 Hz, including seed 44) — so this wasn't "seed 44 happened to get a slower SOM," it
looked more like a stochastic escape specific to that seed's exact spike timing.

**Scaling this up to get a real number, not n=5:** ran the full circuit across 20 seeds (40-59)
at 25 Hz — **18/20 passed, seeds 44 and 53 both failed** at essentially the same ratio (~1.02).
So it's a real ~10% failure rate at 25 Hz, not a one-off. The same 20 seeds at **30 Hz: 20/20
passed** (ratios 3.25-5.07).

**What we did:** relocked the SOM baseline to 30 Hz (`iBaseline_som`: 20.9 → 21.32 pA), re-ran
Phase 2 (SNR + ketamine sweeps) under the new baseline, and regenerated the Progress Report,
with the old 25 Hz results preserved as backups rather than overwritten silently.

**What we tried to explain, and how far we actually got:** built a mechanism figure comparing
seed 42 (pass) against seed 44 (fail) — SOM inter-spike-gap histograms, and the inhibited
branch's calcium trace against θ_p. Honest result: the ISI-gap histograms look statistically
indistinguishable between the two seeds — the "SOM got an unlucky gap" story doesn't show up
cleanly in the data the way we expected. What *does* differ is that seed 44's calcium trace sits
higher and crosses θ_p more persistently through the window. So the escape is real and visible,
but we have not yet isolated a single clean cause — more likely a joint coincidence between SOM's
pattern and the branch's own 80 Hz excitatory drive (both reseeded together) than a "SOM gap"
story on its own. We're reporting that as a real but partially-characterized mechanism, not
overselling a clean explanation the data doesn't fully support.

---

## How to use this document

Each episode above follows the same shape on purpose: **what we were checking → what we actually
saw when we ran it → what we concluded → what we changed → how we verified it**. If you're
explaining any one of these to someone without the full history, that five-step shape is the
thing to reproduce, even if you compress the numbers. The full quantitative detail for each
episode lives in `Progress_Report.docx` (see the section references above) and in the underlying
data files (`docs/*.json`, `docs/*.md`) each episode cites.
