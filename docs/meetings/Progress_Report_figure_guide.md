# What to say for each figure in the progress report

*Companion to `docs/meetings/Progress_Report.docx` (12 November 2026), in the order the figures
appear. For each figure: what is on it, what to say (a script you can read nearly as is), and the
question you are most likely to get.*

## Three words you will use for every figure

- **ρ (rho)** is the state of a plastic synapse, between 0 and 1. The weight is w = 3ρ.
  - Every synapse starts at ρ = 1/3 (w = 1, Yang’s pre-learning weight).
  - **ρ ≈ 0.93 means fully strengthened (LTP).** ρ below 1/3 means weakened (LTD).
- **S (selectivity)** = (r_on − r_off) / (r_on + r_off), where r is the cell’s firing rate when
  a pattern is shown with its own gate open (on) or the other gate open (off). It is Yang’s Eq. 1.
  - **S = 1:** the cell responds only when the right gate is open.
  - **S = 0:** no preference.
  - **S < 0:** it prefers the wrong gate.
- **Free / inhibited branch:** the branch whose SOM is silenced by the active MD channel is
  free (it can learn). The other branch is inhibited.
- **f, L.**
  - f is the fraction of synapses that patterns A and B share (0 = disjoint, 1 = identical).
  - L is how many 3-s epochs each context lasts before switching (L = 4 means 12-s blocks).

---

## §2 — The circuit (`figures/circuit_canonical.png`)

**On it.**
- Two MD channels, MD₀ for context A and MD₁ for context B.
- Each drives its own VIP population; VIP inhibits its own SOM population; each SOM inhibits one
  dendritic branch.
- MD also drives PV, which inhibits the soma.
- Plastic inputs (patterns A and B) reach both branches.

**Say.** “This is the model as it is now. Each context has its own MD channel. Turning on MD₀
activates VIP₀, which silences SOM₀, which removes the inhibition from branch 0. Only that
branch can then reach the calcium level for strengthening, so only branch 0 learns. Context B
does the same for branch 1. MD also drives PV onto the soma; we found that changes how strongly
the cell fires, not what is stored.”

**Likely question:** “Is the one-channel-per-branch wiring from data?”
**Answer:** “No. Zhang gives MD→VIP and MD→PV, but not which branch each VIP controls. That is
our assumption. Section 8, step 1 tests how much mixing it tolerates.”

---

## §4 — Yang Supp. Fig. 1f–h (`figures/yang_replication/supp1_fgh.png`)

**On it.**
- **f:** dendritic voltage when 5–40 synapses fire once together. Below ~20 synapses the
  responses are small bumps. From ~25 the dendrite jumps to a plateau near −10 to −20 mV that
  lasts ~100 ms.
- **g:** NMDA input at rising rates. Without inhibition the dendrite jumps to the plateau between
  30 and 40 Hz (−21 mV at 40 Hz). With 30 Hz of inhibition it stays below −50 mV at every rate.
- **h:** the same with AMPA-only input. The response is graded, and inhibition shifts it by only
  ~5 mV.

**Say.** “This is the property the whole gating mechanism rests on. NMDA input makes an
all-or-none plateau, and inhibition can veto that plateau completely, panel g. AMPA input, panel
h, is graded and barely affected by inhibition. So a branch driven through NMDA can be switched
on and off by SOM; one driven through AMPA could not be. Our model reproduces this directly from
its equations.”

**Likely question:** “Why does it matter?”
**Answer:** “Calcium for plasticity comes mainly from the NMDA plateau. If inhibition removes the
plateau, it removes the calcium, and the branch cannot strengthen.”

---

## §4 — Yang Fig. 2b,c,e–g (`figures/yang_replication/fig2.png`)

**On it.**
- **b:** the plateau, as in Supp. 1f.
- **c:** a disinhibited dendrite (5 Hz inhibition) against an inhibited one (35 Hz). They separate
  from 40 Hz input: −43 vs −61 mV at 40 Hz, −27 vs −55 mV at 60 Hz.
- **e:** the whole neuron’s firing as the stimulus moves along pathway 1’s tuning curve. With gate
  1 open it peaks at 27 Hz; with gate 2 open, at 8 Hz. S = 0.60.
- **f, g:** 2-D tuning (pathway 1 on the x axis, pathway 2 on the y axis).
  - With all gates closed (f) the response is weak and unstructured.
  - With gate 1 open (g) there is a vertical stripe: the cell responds to the pathway-1 stimulus
    whatever pathway 2 does.

**Say.** “This is Yang’s Figure 2, rerun on our model. Opening a dendritic gate decides which
input pathway drives the cell’s output. In panel e the same stimulus gives 27 Hz when its gate
is open and 8 Hz when the other gate is open, a selectivity of 0.60, which is what Yang reports.
Panel g shows the same thing in two dimensions: with gate 1 open, the cell follows pathway 1 and
ignores pathway 2.”

**Likely question:** “Any differences from Yang’s setup?”
**Answer:** “Two, both stated in the notebook.
- 0.8 nS dendrite–soma coupling for the clamped-soma panels, because Yang’s 4 nS prevents any
  plateau when the soma is clamped.
- A 300 Hz soma background instead of 500 Hz, to get Yang’s 3–4 Hz baseline.”

---

## §4 — Yang Fig. 2c fit, V1 (`figures/v1_dendrite_io_yang.png`)

**On it.**
- **Left:** mean dendritic voltage against excitatory conductance, at six inhibition levels
  (0–10 nS). The curves shift right as inhibition grows.
- **Right:** the half-activation point g½ (where the dendrite is halfway to the plateau) against
  inhibition. Our measured points are dots; Yang’s fitted formula g½ = 5.56 (4 + g_inh) is the line.

**Say.** “Yang summarises the dendrite with a formula: how much excitation you need to reach
half-activation, as a function of inhibition. We measured that on our simulated dendrite. The
points lie within 12% of Yang’s line at every inhibition level. Our slope is a little shallower,
4.5 instead of 5.6, so our dendrite is slightly less shunted by strong inhibition. That is one
reason our SOM has to fire faster than Yang’s.”

**Likely question:** “The September report said this matched to the digit.”
**Answer:** “That check was circular: it plotted Yang’s formula against itself. The audit
replaced it with this measurement, which is the honest number.”

---

## §4 — Yang Fig. 7b (`figures/paper_comparison_v2.png`)

**On it.**
- The weight change after a 300-s protocol (post-synaptic firing 10 Hz) against presynaptic rate
  (log axis), at four levels of SOM inhibition. 3 seeds.
- **Light blue, disinhibited branch (MD on, SOM ~1 Hz):** no change up to 5 Hz; a dip (LTD,
  −0.26) at 10 Hz; LTP from 15 Hz, saturating near +1.7.
- **SOM 13 Hz:** LTD from 20 to 100 Hz; LTP only at 150 Hz.
- **SOM 31 and 60 Hz:** no LTP at any rate; LTD from 30–40 Hz.

**Say.** “This is the plasticity rule doing what Yang’s Figure 7b shows. With weak inhibition
there are three regimes as the input rate rises: no change, depression, potentiation. Inhibition
moves the potentiation threshold up: to 150 Hz with SOM at 13 Hz, and out of reach with SOM at 31
Hz. That is exactly the ‘gate’ for learning. At our SOM baseline of ~30 Hz an inhibited branch
cannot potentiate, and when MD silences SOM the branch potentiates from 15 Hz.”

**Likely question:** “Why does the inhibited branch show LTD at high rates?”
**Answer:** “Inhibition keeps calcium between the two thresholds, in the depression band. That
is Yang’s mechanism too.”

---

## §4 — Yang Supp. Fig. 4: the rate model refit to our neuron (`figures/yang_replication/supp4.png`)

**On it.** Left: mean dendritic voltage against excitatory conductance, one curve per inhibition
level; dots are our spiking dendrite, black is Yang's formula fitted to it, dotted is Yang's own fit.
Right: soma rate against the current the dendrites deliver; black our fit, orange Yang's.

**Say.** "Yang made his network figures with a rate model fitted to his spiking neuron. We fitted
the same formula to ours. The numbers come out almost the same: half-activation slope 5.62 against
his 5.56, soma exponent 2.63 against 2.89. So for the network figures our neuron is essentially his."

**Likely question:** "Why does the soma fit stop at 100 Hz?" **Answer:** "Our soma bends below a
power law above ~100 Hz because of refractoriness; the network figures never drive it that high."

---

## §4 — Yang Fig. 3: sparseness and disinhibition (`figures/yang_replication/fig3.png`)

**On it.** Gating selectivity against the fraction of dendrites a pathway targets. Points are our
spiking neuron with 10, 20 or 30 dendrites; lines the rate model; diamonds non-overlapping patterns.
Right panel: 10, 20, 30 Hz disinhibition.

**Say.** "Yang did this with his rate model; we did it on the spiking neuron itself, with up to 30
dendrites. Sparse patterns gate best, about 0.6, and selectivity falls to zero when every dendrite
is targeted, because the two pathways then overlap completely. Stronger disinhibition gates better.
The rate model lies on the spiking points, which validates using it for the next three figures."

---

## §4 — Yang Figs. 4–6: the interneuron network (`fig4.png`, `fig5.png`, `fig6.png` in `figures/yang_replication/`)

**On them.** Yang's column: 1,000 pyramidal cells × 30 dendrites, 160 SOM, 140 VIP, 200 PV, random
connections, our fitted neuron. Curves are means, bands 10–90% of cells; dotted = Yang's fit in the
same code.

**Say.**
- Fig. 4: "With about five SOM cells per dendrite, as measured, selectivity is 0.38; Yang reports
  about 0.5, and his own fit in our code gives 0.41. As in Yang, only the number of SOM cells per
  dendrite matters."
- Fig. 5: "If control reaches only VIP, it works only when a few VIP cells are targeted (peak 0.42).
  If control reaches SOM too, what matters is which SOM cells it targets, not VIP."
- Fig. 6: "Adding somatic PV inhibition raises selectivity from 0.39 to 0.68, until it is so strong
  that it silences cells."

**Likely question:** "Is this your circuit?" **Answer:** "The pyramidal neuron is ours; the
interneuron populations are Yang's rate units, as in his paper. Our own circuit has one SOM group per
branch, which is the specific case where selectivity is highest (0.93)."

---

## §4 — Yang Fig. 7c–e: learning creates gating (`fig7c.png`, `fig7de.png`)

**On them.** 7c: weights per synapse after learning A, then B; and mean weights over the run. 7d,e:
tuning to pathway 1 with gate 1 or gate 2 open, before and after learning; bottom, 2-D tuning.

**Say.** "Each pattern ends up strong on the branch its context opened, w 2.78, and stays at 1 on the
other; in Yang it would also weaken there, which in our runs needs longer exposure. Before learning
both gates give the same tuning, S = 0.06; after learning only the open gate transmits it, S = 0.92.
Yang reports about 0.7."

---

## §4 — Learned gating against readout drive (`figures/robustness_r4_readout_canonical.png`)

**On it.** Left: selectivity against readout input rate, before (grey) and after (blue) learning;
open symbols = the cell does not respond, S undefined. Right: plateau fraction of each branch.

**Say.** "Re-made on the final model. After learning, S is 0.9 at 5–10 Hz per synapse, 0.62 at 15,
about zero from 30. Between 5 and 15 Hz only the learned branch reaches a plateau; above 20 Hz an
open gate makes any branch plateau. We state this readout condition with every functional claim."

---

## §6 — Parameter sensitivity, R3 (`figures/robustness_r3_canonical.png`)

**On it.**
- Six panels; each line is one of 16 parameters, scaled ×0.5, ×0.75, ×1.25, ×1.5 (5 seeds). The
  grey band is ±25%.
- Panels:
  - gating ratio (pass ≥ 2);
  - selectivity S (pass > 0.5);
  - S after learning (pass > 0.5);
  - retention with silent inputs (pass ≥ 0.9);
  - retention with inputs always on (reported only);
  - ρ of the inhibited branch.

**Say.** “To check that nothing depends on a lucky parameter value, we scaled 16 parameters up
and down by 25% and 50%. Inside the grey ±25% band every measure passes: gating, selectivity,
learned selectivity (lowest 0.64), and retention with silent inputs, which is 1.000 everywhere.
Failures happen only at half the value of six parameters, such as the NMDA conductance or the MD
rate, where the mechanism genuinely cannot work. The one thing that is not robust is the fifth
panel: whether inhibition erases a memory whose inputs stay active. It varies from 0.42 to 1.0,
so we do not claim it.”

**Likely question:** “Which parameter is most sensitive?”
**Answer:** “Dendritic leak at ×0.75 gives the lowest learned selectivity (0.64), still a pass.”

---

## §6 — Is the alternation claim robust? (`figures/robustness_claims.png`)

**On it.** For each of 16 parameters scaled ×0.75 (blue) and ×1.25 (orange): recall of the previous
context (filled) and the current one (open), at 25% overlap (left) and 50% (right). Vertical lines =
baseline; dashed = 0.5.

**Say.** "We tested the main context result itself under ±25% changes: 330 runs. It holds in 30 of
32. It breaks with 25% stronger NMDA or 25% weaker SOM drive. There, learning itself suffers: even the
current context is barely recalled at 50% overlap. So the result needs SOM inhibition strong relative
to NMDA drive, which is a stated condition rather than a hidden tuning."

---

## §7 — Alternation in the single cell (`figures/alternation_experiment_canonical.png`)

**On it.**
- **Top row:** ρ over 32 epochs for overlap f = 0.5. Grey bands are context B. Solid lines are
  synapses unique to one pattern; dashed lines are shared synapses.
  - Left: MD gating, blocks of 4.
  - Middle: alternating every epoch.
  - Right: no gating.
- **Bottom row:** end-of-run summaries against overlap.
  - Left: how much of A is kept across one B block.
  - Middle: each pattern’s preference for its own branch at the end of an A block (recent pattern
    blue, older pattern pink).
  - Right: shared synapses on branch 0 at the end of A and at the end of B.

**Say.**
- **Top left:** “Synapses unique to a pattern (solid) go to 0.93 on their own branch and stay
  there for the whole run. They are never forgotten. The shared synapses (dashed) swing: they
  strengthen on whichever branch is currently open and weaken on the other, every block.”
- **Top middle:** “If contexts alternate every 3 s, the shared synapses never settle.”
- **Top right:** “Without gating, both branches are identical, so the cell cannot tell the
  contexts apart.”
- **Bottom middle:** “This is the cost. At high overlap with long blocks, the older pattern ends up
  preferring the wrong branch (below zero from about f = 0.6).”
- **Summary:** “MD gating separates the contexts. For disjoint inputs, or up to 25% overlap with
  12-s blocks, both contexts are recalled. Beyond that, shared synapses follow the most recent
  context.”

**Likely question:** “In the no-gating panel, why are B’s own synapses low?”
**Answer:** “Without SOM inhibition the soma fires at ~68 Hz. We have not analysed why
B-unique synapses end at 0.13. The point of that panel is that both branches end up identical,
so there is no context separation.”

---

## §8 step 1 — Channel specificity (`figures/specificity_test_canonical.png`)

**On it.** Three panels. Each mixes one stage of the MD→VIP→SOM→dendrite chain from fully
specific (left end) to uniform (right end). Lines:
- black dashed = ρ_free − ρ_inh (weight separation);
- blue = S before learning (Yang Fig. 5 gating);
- orange = S after learning.

The panels:
- **Left, MD→VIP:** the fraction of all VIP cells an MD channel reaches (0.5 = only its own
  channel).
- **Middle, VIP→SOM:** the probability of wrong-channel connections (0 = specific, 0.6 = uniform).
- **Right, SOM→dendrite:** the fraction of SOM synapses on the wrong branch (0.5 = uniform).

**Say.** “Since the one-channel-per-branch wiring is our assumption, we asked how specific it
has to be. This is the final model, VIP→SOM at a quarter of the original weight. SOM→dendrite
tolerates 20% of synapses on the wrong branch (right panel), VIP→SOM 7.5% (middle). MD→VIP is the
weak point (left): 25% spill-over to the other channel already loses one seed in five, and more
collapses learning. So the one hard requirement on anatomy is a channel-specific MD→VIP projection.”

**Likely question:** “Why does MD→VIP spill-over break it?”
**Answer:** “It drives the other context’s VIP, which silences the other SOM, so both branches
open and both learn.”

---

## §8 step 3a — Recurrent network (`figures/network_test.png`)

**On it.** 20 canonical cells sharing the interneurons, with Zhang’s recurrence E→E, E→SOM, E→VIP,
E→PV scaled by a common gain (gain 1 = our reference weights). 5 seeds.
- **Left:** against gain.
  - S after learning (blue) is flat at 0.93 up to 0.5–0.6, then falls.
  - The fraction of cells gated (black) is 100% up to 0.6, 80% at 0.7 and 20% at 0.9–1.
  - S before learning (orange) stays ≈ 0.
- **Middle:** rates in context A (log scale).
  - E stays at 10–12 Hz up to 0.6, then jumps.
  - The other channel’s VIP (red) is 0 up to 0.35, then ignites at 0.6–0.7.
  - The other SOM (green) falls; PV rises.
- **Right:** one pathway at a time.
  - E→SOM and E→PV are flat.
  - E→E and E→VIP fail from 0.7–0.8, and E→VIP is the worst.

**Say.** “Next we put 20 cells together with the excitatory recurrence Zhang’s network has. Up to
a gain of 0.6, nothing changes: gating and learning are as in one cell. Above that it fails
abruptly, like a cliff. The middle panel shows why: the recurrent excitation reaches the other
context’s VIP, which ignites and silences the other SOM, opening the wrong branch. The right
panel confirms it is E→VIP (and runaway E→E) that does this. Recurrence onto SOM or PV is
harmless. So the limit is network stability, not the dendritic mechanism.”

**Likely question:** “Is a gain of 0.6 realistic?”
**Answer:** “We don’t know yet. The reference weights are our own guesses, so the gain has no
biological calibration. That is an open point.”

---

## §8 step 3b — MD from a PFC↔MD loop (`figures/network_loop_test.png`)

**On it.** Network at gain 0.35; MD now produced by a rate loop (context populations ↔ MD).
- **Left:** S after learning (blue bars) and fraction gated (orange bars) for four MD sources.
  - Fixed Poisson, `amp` (the loop amplifies a held cue) and `persist` (self-sustained after a
    0.5-s cue) all pass.
  - `persist_weakcomp` (competition too weak) gates after A but S ≈ 0, because B is learned on
    both branches.
- **Middle:** non-specific feedback from the network’s E cells to both MD channels.
  - `amp` keeps S ≈ 0.9 up to the largest weight.
  - `persist` drops at 0.5 and fails at 1, as its OFF channel re-ignites (dashed, up to ~23 Hz).
- **Right:** loop cross-talk.
  - `amp` degrades gently (S 0.74 at 25%).
  - `persist` collapses at 10%, as its ON channel falls to ~7 Hz.

**Say.** “Zhang’s MD is part of a loop with prefrontal cortex, so we replaced the fixed MD input
by a loop. If the loop amplifies a context cue that is present, it works as well as the fixed
input and is robust: to 10% cross-talk, and to strong feedback from the network. If the loop has
to hold the context by itself after a brief cue, it brings three requirements. It needs enough
competition (else the old context stays on and the new pattern is learned on both branches),
less than 5% cross-talk, and only weak non-specific feedback. In no condition is the stored
memory damaged; every failure is a failure to write the new context on the right branch.”

**Likely question:** “Why not spiking neurons for the loop?”
**Answer:** “A spiking loop had no regime between silence and 100–400 Hz latching, so we used rate
units, as Zhang’s own model does.”

---

## §8 step 4a — Alternation on the network (`figures/network_alternation.png`)

**On it.**
- **Left (3-s blocks) and middle (12-s blocks):** recall S at the end of the run against overlap.
  - Blue: network with the MD loop. Green: network with fixed MD (on top of each other).
  - Black: single cell.
  - Solid lines are the current context, dashed lines the previous one.
  - Orange ×: no gating.
- **Right:** ρ over the run in the network (loop, f = 0.5, 12-s blocks). It shows the same swing
  of the shared synapses as the single cell.

**Say.** “Finally we ran the single-cell alternation experiment on the network, with MD from the
loop. Up to 50% overlap it reproduces the single cell within about 0.05, and the loop gives the
same result as a fixed MD input. Without gating nothing is recalled. One new effect: with large
overlap and 12-s blocks, the network is more biased to the latest context (at full overlap 0.41
for the current context against −0.41 for the previous one, versus 0.10 / −0.16 in the single
cell). We then traced it — next figure — and it is not a network effect. The conclusion stays the
same: both contexts are recalled only up to 25% overlap with 12-s blocks.”

---

## §8 step 4b — What caused the extra recency? (`figures/recency_cause.png`)

**On it.** Recall of the current (left) and previous (right) context against overlap for: single
cell at 80 and 50 Hz learning, network at 50 Hz, network without recurrence, network at 80 Hz.

**Say.** “On the same seeds the single cell and the network agree at 75% overlap; the earlier gap
came from comparing a 10-seed single-cell mean with 5 network seeds. At full overlap the difference
is the learning rate: a single cell learning at 50 Hz, like the network, behaves like the network.
So the network adds no recency of its own. One thing we can't explain yet: the network learning at
80 Hz keeps the previous context at 50% overlap, 0.53. We are not claiming it until we understand it.”

**Likely question:** “What is next?”
**Answer:**
- Understand the 80 Hz network result.
- Overlap and retention on the network.
- A more realistic E/I balance, to see whether the stability limit moves.

---

## If you have one minute: the story the figures tell

1. **The mechanism works as in Yang.** NMDA plateaus can be vetoed by inhibition (Supp. 1). An
   open gate routes an input to the output (Fig. 2). Inhibition moves the LTP threshold (Fig. 7b).
2. **MD now picks the branch, and learning changes behaviour.** Selectivity goes from 0 to 0.9
   after learning (Fig. 7d,e analogue), robustly (R3).
   Every reproducible Yang figure is reproduced, including Fig. 3 on a spiking neuron with many
   dendrites and his network Figs. 4–6 (rate model refit to our neuron, as Yang did); one PDF:
   `docs/reports/Yang2016_replication.pdf`.
3. **What it buys.** Context separation and protection of old memories for disjoint or
   lightly overlapping inputs, but not at high overlap (alternation). This holds under ±25% of
   30 of 32 parameter changes, given SOM inhibition strong relative to NMDA.
4. **It scales to a first network** up to a stability limit, and works with MD from a PFC↔MD loop
   (steps 3a, 3b, 4a).
