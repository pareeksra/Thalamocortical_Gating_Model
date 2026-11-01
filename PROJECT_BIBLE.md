# PROJECT BIBLE — Thalamocortical Gating & Cognitive Flexibility Model

> **Purpose of this file.** This is the single hand-off document for someone (human or
> agent) who knows *nothing* about this project. It explains the scientific question,
> why it exists, the two papers it is built from, every phase of work we went through
> (what we tried, what broke, what we concluded, what we changed, how we checked),
> where the project stands today, and what *every file and folder* is for. Read this
> top-to-bottom once and you can navigate and continue the project without asking.
>
> **It is a map, not the territory.** When a specific number, claim, or line of code
> matters, verify it against the source file named here before you act on it — code
> moves, this file can lag. Where this file and the code disagree, the code wins, and
> you should fix this file.
>
> **Last written:** 2026-11-01. **Repo:** `github.com/pareeksra/Thalamocortical_Gating_Model`.
> **Local path (Linux):** `/run/media/raghav/New Volume/minsu/Thalamocortical_Gating_Project`
> (an NTFS "New Volume" mount — the old Windows `D:/minsu/...` drive).

> **⚠ AUDIT 2026-11-01/02. Read `docs/AUDIT_2026-11-01.md` first.** Eight logic problems
> were found and fixed. The changes that alter the science:
> - **SOM fired in perfect lockstep in every prior run.** With desynchronised SOM (now the
>   default), gating follows mean inhibitory conductance, not "coverage". The 25 Hz
>   seed-44/53 failures disappear (N = 20 is 20/20 at 25 Hz).
> - **MD now selects the branch** (`model/context_circuit.py`).
> - **Retention comes from input sparsity alone.** Inhibition does not protect memories,
>   and erases them when the input stays active.
> - **V1 was circular.** The measured dendrite is far less shunted than Yang's fit.
> - **Several scripts silently returned ρ = 0.5.** They are repaired.
>
> Where this file's §6–§9 numbers conflict with the audit, the audit wins. Inline
> "[AUDIT]" notes below mark the main corrections.

---

## Table of contents

1. [The one-paragraph version](#1-the-one-paragraph-version)
2. [The scientific question, and why it's interesting](#2-the-scientific-question-and-why-its-interesting)
3. [The two source papers and exactly what we borrow](#3-the-two-source-papers-and-exactly-what-we-borrow)
4. [The plan (the phase roadmap)](#4-the-plan-the-phase-roadmap)
5. [Three implementations — and which one is canonical](#5-three-implementations--and-which-one-is-canonical)
6. [The biology/math the model actually implements](#6-the-biologymath-the-model-actually-implements)
7. [The full history: what we tried, what broke, what we did](#7-the-full-history-what-we-tried-what-broke-what-we-did)
8. [Where the project stands right now](#8-where-the-project-stands-right-now)
9. [Open questions and the honest caveats](#9-open-questions-and-the-honest-caveats)
10. [File-by-file: every folder and file in the repo](#10-file-by-file-every-folder-and-file-in-the-repo)
11. [How to run things (environment + commands)](#11-how-to-run-things-environment--commands)
12. [Glossary](#12-glossary)

---

## 1. The one-paragraph version

> [AUDIT] The forgetting sentence below is superseded. Input sparsity alone prevents
> forgetting; inhibition is not needed for it. The SOM-rate explanation is also
> superseded (lockstep artefact plus weaker dendritic shunting). See
> `docs/AUDIT_2026-11-01.md`.

Can the **mediodorsal thalamus (MD)** control *which dendritic branch* of a prefrontal
pyramidal neuron is allowed to learn, so that different contexts write onto different
physical branches instead of overwriting the same synapses — i.e. **context-specific
learning without catastrophic forgetting**? We build a spiking circuit that grafts the
**cell-type-specific MD→interneuron wiring of Zhang et al. (2025)** onto the **dendritic
disinhibitory gating circuit + calcium plasticity of Yang et al. (2016)**. The central
mechanism — dendritic inhibition gating which branch undergoes plasticity — **works at
the single-neuron level** (free branch potentiates, inhibited branch does not). We have
since shown that **branch separation alone does NOT prevent forgetting** — you also need
the idle context's *input* to be silent — and we have quantitatively resolved why our
spiking model needs a higher SOM rate than Yang's rate-based one. The **network-scale
build (~3000 neurons) has not been started.** This is a **novel synthesis, not a
replication** of either paper.

---

## 2. The scientific question, and why it's interesting

**The core question.** When you learn task B, why doesn't it erase task A? Brains switch
contexts constantly without wiping memory. One candidate mechanism: the brain routes
different contexts' learning to *physically different* synapses on *different dendritic
branches* of the same neuron, and some upstream signal decides which branch is "open" for
plasticity at any moment. The hypothesis this project tests is that **MD thalamus is that
upstream signal**, acting through cortical inhibitory interneurons.

**Why dendritic branches?** A pyramidal neuron's dendrites are not a passive funnel. A
single branch can generate a local **NMDA plateau potential** — a regenerative, nonlinear
depolarization — when enough excitatory input lands on it *and* it is not being inhibited.
That plateau is what drives enough calcium into the branch to trigger synaptic
potentiation (LTP). So if you can control, per-branch, whether that plateau is allowed to
form, you control which branch learns. The control knob is **dendrite-targeting
inhibition** (from SOM interneurons): shunt the branch, no plateau, no learning.

**Why MD thalamus?** MD doesn't talk to dendrites directly. It talks to interneurons.
Zhang et al. (2025) showed MD has **cell-type-specific** projections: one MD population
drives PV interneurons (which inhibit the soma — gain control / noise suppression),
another drives VIP interneurons (which *inhibit SOM*, i.e. **disinhibit** the dendrite —
opening it for learning). So MD can, in principle, pick which branches are open by
choosing which VIP→SOM→dendrite chains it disinhibits. That is the link between a
thalamic context signal and branch-specific plasticity.

**Why it matters (the payoff claim).** If this works, it is a concrete, biophysical,
testable account of cognitive flexibility: a mechanism by which a subcortical structure
gates *where* cortical learning happens, enabling context switching without catastrophic
forgetting. It also gives a disease handle — disrupt the MD→VIP arm (as NMDA-receptor
hypofunction does, the standard schizophrenia model) and you predict a *specific* failure:
not global silencing, but a **loss of context-dependent flexibility** (the branch gets
stuck closed regardless of what MD says). Phase 2 tested exactly this.

---

## 3. The two source papers and exactly what we borrow

Neither paper alone answers the question; that's why we graft them.

| | **Yang, Murray & Wang (2016)** — *Nat. Commun.* 7:12815 | **Zhang, Mukherjee, Halassa & Chen (2025)** — *Nat. Commun.* 16:2640 |
|---|---|---|
| Model class | Spiking / reduced-compartment | **Rate-based RNN, machine-learning-trained** |
| Dendrites | **Yes — the mechanism we need** | None |
| Plasticity | **Graupner–Brunel calcium** | None (trained weights) |
| MD thalamus | Absent (abstract "control input") | **Feedforward corticothalamic loop (PFC↔MD)** |
| Headline result | Branch-specific dendritic gating; inhibition shifts the LTP threshold | MD improves working memory & context-switching under low SNR |

**What we genuinely inherit from Yang 2016:** the reduced multi-compartment pyramidal
cell, the VIP→SOM→dendrite disinhibition and PV→soma motifs, GABA_A shunting inhibition,
the NMDA plateau nonlinearity, the Graupner–Brunel plasticity rule, and — exactly — the
dendritic I/O transfer function (Eq. 20–22) with all its fitted constants. **Every
plasticity constant in the model is Yang's published value** (verified against the paper;
see §6 and the README "Provenance" table).

**What we inherit from Zhang 2025 — wiring labels only:** the two cell-type-specific MD
projections. The marker→target pairing is verified against Zhang and is **not swapped**:
- **MD^GRIK4 → PV** (kainate-receptor MD cells → PV; Zhang frames this as feedforward
  inhibition / prefrontal-noise suppression).
- **MD^DRD2 → VIP** (dopamine-D2 MD cells → VIP; the disinhibition arm).

**What we do NOT do (do not claim otherwise):**
- We do **not** reproduce Yang's full quantitative results at network scale, nor his
  ~3000-neuron network. Our canonical model is **1 pyramidal soma, 2 dendritic branches,
  20 of each interneuron**.
- We do **not** reproduce or extend Zhang's model: none of its trained task, psychometric
  curves, working-memory delay, attractor analysis, PFC→MD feedback loop, or MD→excitatory
  projection is implemented. MD here is a bare external `PoissonGroup`.
- This is therefore a **novel synthesis**. Calling it "a replication of Yang" or "an
  extension of Zhang" overstates what exists.

---

## 4. The plan (the phase roadmap)

Organizing principle: **don't build on a broken foundation.** Fix and verify each level
against the source papers before moving up. (Full version: `docs/ROADMAP.md`.)

- **Phase 0 — Foundation & hygiene.** One parameter source; freeze the two NumPy models;
  make results reproducible. *(Done.)*
- **Phase 1 — Make ONE neuron gate correctly.** 1 pyramidal cell, 2 branches;
  disinhibited branch potentiates, inhibited does not. *(Done — passes.)*
- **Phase 2 — Verify Yang replication quantitatively** + stress-test the circuit (noise
  robustness, NMDA-hypofunction / "ketamine" simulation). *(Done — V1–V4 battery + both
  sweeps run.)*
- **Phase 3 — Add MD (Zhang extension), honestly framed.** MD→PV + MD→VIP; port the
  context protocol; test no-catastrophic-forgetting (learn A → switch to B → is A
  retained?). *(Forgetting test done in miniature; full MD-driven context protocol in the
  canonical model still outstanding.)*
- **Phase 4 — Scale to a network** (~3000 pyr, hundreds of interneurons, ~30 dendrites);
  reproduce Yang's gating-selectivity-vs-sparsity. *(NOT started.)*
- **Phase 5 — Novel contribution & write-up.** MD-gated plasticity in a network; testable
  predictions; healthy/pathology phase diagram. *(NOT started.)*

---

## 5. Three implementations — and which one is canonical

The repo contains **three independent implementations**. They share parameter *values* by
convention but not by code, and are **not interchangeable**. Knowing which one produced a
figure is essential to reading it.

| Model | Files | What it is | Status |
|---|---|---|---|
| **A — Brian 2 spiking network** | `model/`, `experiments/`, `src/v2/` | The full spiking circuit: multi-compartment pyramidal cell, PV/SOM/VIP LIF interneurons, MD as a `PoissonGroup`, Graupner–Brunel plasticity. The only model with connection *probabilities*, and the only one whose plasticity actually works. | **CANONICAL. Use this.** |
| **B — Phenomenological (NumPy)** | `numpy_models/main_gating_figures.py` | Proof-of-concept of Yang. Uses *hardcoded* dendritic inhibition instead of simulating interneurons. Produces documentation Figures 1–4. | **Frozen. Plasticity inert** (random walk). |
| **C — Emergent mechanistic (NumPy)** | `numpy_models/emergent_gating_mechanistic_model.py` | Stochastic trial-based model where inhibition *emerges* from noisy interneuron rates driven by Poisson MD. Produces `figures/mechanistic/`. | **Frozen. Plasticity inert.** |

**Why B and C are inert (do not "fix" them without reading this).** Both replace
Graupner–Brunel's bistable ρ dynamics with a monostable relaxation (because the true
τ = 346 s moves nothing in 300 trials), and both treat calcium as a fixed per-spike jump
rather than Yang's leaky integral — which caps single-pairing calcium at
0.371 + 0.957 = **1.328 < θ_p = 2.78**, making LTP structurally impossible. Their "bistable"
figure captions are therefore unsupported by their own code. They were **deliberately
frozen as illustrative sketches.** Everything going forward is Model A only.

> **One caveat on Model A's layout:** the modern canonical code lives in `model/` and
> `src/v2/plasticity.py`. The old `src/v2/equations.py` / `parameters.py` /
> `MultiCompartmentalModel.py` paths referenced in `docs/REPAIR_LOG.md` were an earlier
> layout; the live files are now under `model/`. When REPAIR_LOG says `src/v2/equations.py`,
> read `model/equations.py`.

---

## 6. The biology/math the model actually implements (Model A)

### Populations and wiring (from `model/parameters.py`, `model/full_circuit.py`)

| Population | Size | | Population | Size |
|---|---|---|---|---|
| Pyramidal soma | 1 | | PV interneurons | 20 |
| Dendritic branches | 2 (Phase-1 override; `num_DendEach` default is 10) | | SOM interneurons | 20 |
| MD thalamus (`PoissonGroup`) | 50 | | VIP interneurons | 20 |
| Cortical pathway (`PoissonGroup`) | 30 @ 80 Hz | | PV background (`PoissonGroup`) | 20 @ 500 Hz |

> Note the `num_DendEach = 10` default in `parameters.py`; the Phase-1 and full-circuit
> builders **override it to 2** (`experiments/phase1_single_neuron_gating.py`,
> `model/full_circuit.py`). The "2 branches" figure is the operating config, not the raw default.

| Projection | p (requested) | Weight | Role |
|---|---|---|---|
| MD → PV (AMPA) | 0.5 | 0.12 nS | gain control / noise suppression |
| MD → VIP (AMPA) | 0.3 | 0.5 nS | disinhibition arm |
| VIP → SOM (GABA) | 0.6 | 3.0 nS | VIP shuts SOM |
| SOM → Dendrite (GABA) | 0.5 | 4.0 nS | **the gate** (shunts the branch) |
| PV → Soma (GABA) | 0.6 | 5.0 nS | somatic gain control |
| SOM → PV (GABA) | 0.8 | — | added during the audit (was declared-but-unwired) |
| Background → PV (AMPA) | all-to-all | 0.25 nS | makes PV fluctuation-driven |
| Pathway → Dendrite | all-to-all | **plastic**, `w = w0 + (w1−w0)·ρ` | the learning synapse |

**The MD→PV / MD→VIP asymmetry** is deliberate: total drive `p·n·g` is 3.0 nS (PV) vs
7.5 nS (VIP), so MD onto VIP is 2.5× stronger in aggregate despite the *lower* connection
probability. The pathway distinction rests on VIP's sparser, stronger contacts.

**SOM cells receive no synaptic excitation** — their baseline comes from a bias current
`iBaseline_som` (see §7.4 for the 25 Hz → 30 Hz saga).

### The gating mechanism in one line

MD → VIP → (shuts) SOM → (un-shunts) a dendritic branch → that branch can reach the NMDA
plateau → calcium crosses θ_p → that branch's synapse potentiates. The other branch, still
SOM-shunted, stays below plateau, so its calcium stays sub-threshold and it does not learn.

### Calcium and plasticity (the heart of it)

Dendritic calcium has **two components** (Yang Methods p.11):
- **NMDA calcium — a leaky integral of the NMDA current** (Eq. 13):
  `τ_Ca · d[Ca]/dt = −[Ca] + κ_NMDA · I_NMDA`. This is branch-specific and *saturating*;
  under a plateau it accumulates past θ_p → LTP. **This is the gating signal.**
- **VGCC / bAP calcium — per-spike bumps from back-propagating action potentials**
  (Eq. 14). This is **branch-uniform** (same on every branch), has no voltage/location
  dependence, and does **not** saturate. (This uniformity is the source of the ~74 Hz
  selectivity ceiling — see §7.1.)

Plasticity is Graupner–Brunel: a bistable synaptic efficacy `ρ ∈ [0,1]` with a
potentiation threshold θ_p and a depression threshold θ_d. Calcium above θ_d drives
depression; calcium above θ_p drives potentiation. **Published Yang/GB constants (all
verified against the paper):**

| Constant | Value | Meaning |
|---|---|---|
| `theta_d` / `theta_p` | 1.0 / 2.78 | LTD / LTP calcium thresholds |
| `gamma_d` / `gamma_p` | 39.949 / 177.552 | depression / potentiation strengths (1/s) |
| `tau` | 346.36 s | the **ρ (weight)** time constant — *not* a calcium τ |
| `sigma` | 3.35 | plasticity noise amplitude |
| `w0` / `w1` | 0.0 / 3.0 | DOWN / UP synaptic weights |
| `tau_Ca_NMDA` | 30 ms | calcium decay |
| `kappa_Ca_NMDA` | 0.26 /pA | Phase-1 calibrated; ≈ Yang's in-vivo 0.278 /pA |

**Two ways the plasticity is computed** (this matters a lot for reading the history):
1. **Continuous ODE** (`drho/dt`, in `model/equations.py`) — the original. Had a units
   bug (§7.3) and needs ~346 s of simulated time to mean anything.
2. **Analytical closed-form** (`src/v2/plasticity.py`, Yang Eqs. 32–35) — the current
   default for all reported results. Given how long a trial's calcium spent above each
   threshold (`alpha_p`, `alpha_d`), it returns the exact post-epoch ρ, folding in the
   346 s timescale analytically without simulating it. **This is what "analytical Yang
   plasticity" means everywhere in the docs.**

> [AUDIT] Simulation step: every group integrates at Brian 2's default **0.1 ms**
> (`defaultclock.dt` is never set; `sim_dt` = 0.02 ms clocked only the retired Python
> coupling). It was checked to be dt-converged (`docs/audit/dt_convergence.json`).
> Coupling is now compiled (`model/circuit_helpers.py`) and bit-identical to the legacy
> path. SOM cells start at random phases of their cycle (`som_phase='random'`);
> `'sync'` reproduces the legacy lockstep. bAPs come from an external Poisson source, so
> the soma/PV arm cannot affect plasticity unless `context_circuit(bap_source='soma')`
> is used.

### Two documented departures from Yang (not bugs — logged divergences)

- **SOM baseline rate.** Yang: ~10 Hz (experimentally observed). This model: locked to
  **30 Hz** (see §7.4 for why, and §7.5 for why that's really masking a deeper effect).
- **Spiking vs rate sensitivity.** Yang gates at ~10 Hz SOM; our spiking model needs
  ~18–21 Hz at the same τ_GABA,dend = 20 ms — because our calcium is event-driven. This is
  **resolved and quantified** (§7.6): gating tracks inhibition *coverage* (rate × τ), not
  rate alone.

---

## 7. The full history: what we tried, what broke, what we did

Every episode has the same shape: **what we were checking → what happened → what we
concluded → what we changed → how we verified.** Sources: `docs/PROJECT_STORY.md`,
`docs/NARRATIVE_WALKTHROUGH.md`, `docs/REPAIR_LOG.md`, and the three `docs/FINDING_*.md`.

### 7.0 The repair pass (before any real experiment)

An audit of the inherited code (`docs/REPAIR_LOG.md`) found dead/wrong pieces:
- **`dend_IO` sign defect:** the raw fit implied *more* inhibition could *depolarize* an
  unexcited branch by up to 29.89 mV — impossible for shunting GABA_A. Fixed by
  re-referencing the sigmoid to rest; resting error → exactly 0.00 mV, fitted constants
  untouched. (Now the single canonical `model/dendritic_io.py`, consolidated from 4 copies,
  proven bit-identical over a 61×61 grid.)
- **bAP calcium pathway was unwired:** `Dend` has no spike threshold, so the
  `on_post` handler could never fire. Rewired to inject the bAP transient properly.
- **PV baseline current couldn't work:** PV's f-I is a near-step (5 mV threshold-to-reset),
  so a bias current needs sub-fA precision. Switched to a background **Poisson conductance**
  (500 Hz, 0.25 nS) so PV fires fluctuation-driven and graded.
- Two NumPy calcium-kernel bugs (wrong ODE variable, off-by-18% normalization) fixed by
  exact re-derivation. Mg²⁺ gate verified against the alternative Jahr–Stevens form.

### 7.1 Phase 1 — getting ONE neuron to gate (the two blocking bugs)

Test 3 ("free branch beats inhibited branch") was *passing at ratio ~1.02* — but a
false-positive check showed that threshold passes **50.7% of the time by chance**. A coin
flip. Two independent things were broken:

- **Bug 2 — calcium wasn't Yang's math.** NMDA conductance variables were declared but
  never assigned (no NMDA current existed); the NumPy prototypes used per-spike jumps capped
  at 1.328 < θ_p, making LTP impossible. *Fix:* implemented the real leaky-integral NMDA
  calcium (Eq. 13) + the saturating NMDA conductance + wired the bAP transient.
- **Bug 1 — drive/coupling wrong.** The soma was firing ~201 Hz; Yang pins it at ~10 Hz.
  Cause: the experiment used dendrite–soma coupling 4.0 nS instead of Yang's in-vivo
  **0.8 nS** (which was already sitting unused in `parameters.py`). A calcium-component
  diagnostic showed **selectivity dies above ~74.3 Hz somatic rate**, because the
  branch-uniform bAP calcium becomes a large *shared* term diluting the branch-specific NMDA
  signal. *Fix:* 0.8 nS coupling, somatic rate externally pinned at ~10 Hz (Yang's protocol),
  branch drive tuned to 80 Hz.

**Result:** free branch potentiates (ρ ≈ 0.78–0.92), inhibited branch does not (ρ ≈ 0.01–0.02).
**Verification independent of the tests:** `validate_vs_papers.py` measured dendritic
half-activation at five inhibition levels and matched Yang's closed-form
`g₁/₂ = 5.56·(4+g_inh)` **to the digit** (22.24, 33.36, 77.83, 133.42, 216.81 nS).

### 7.2 The paper-replication battery (V1–V4) and a flagged discrepancy

`experiments/validate_vs_papers.py`:
- **V1** (Yang Fig 2c, dendritic I/O): matches Yang's formula exactly.
- **V2** (Yang Fig 7b, rate-dependent LTP threshold): free ρ climbs 0.58→0.81 over
  20→120 Hz; inhibited stays ~0.01–0.02. Threshold shifts with rate as Yang predicts.
- **V3** (Yang Fig 7d-e, gating): ρ_free 0.792 / ρ_inhib 0.012, ratio **64.83**.
- **V4** (Zhang wiring, qualitative): MD 0→40 Hz ⇒ VIP 0→93 Hz ⇒ SOM 36→0 Hz
  (disinhibition), PV 7→127 Hz (gain arm).

**Open flag:** the "same" headline ratio is measured three different ways that disagree by
~50% — README's ~43, V3's 64.83, and a γ/τ-audit re-measure of 42.76, all at seed 42. This
is **not** a reproducibility problem (that's resolved, §7.7) — it's a genuine still-open
measurement discrepancy; no single "true" number was ever picked.

### 7.3 The γ/τ units bug and the plasticity refactor

**Why did 3 simulated seconds ever give a result when τ = 346 s?** Because the `drho/dt`
equation divided only the double-well term by τ while the γ (potentiation/depression) terms
were multiplied by a bare `1/second` — running **346× too strong** (a code comment had even
flagged "346x stronger"). Patching it to the correct form barely separated the branches at
3 s (ratio 1.51), and at 300 simulated seconds (1.7 h wall-clock) it oscillated 1.49–2.83,
never converging. **Decision:** stop patching a self-derived ODE and implement Yang's actual
published closed-form update (Eqs. 32–35) in `src/v2/plasticity.py`. A second bug caught
during this: the NumPy model's `w1 = 1.0` (a display normalization) would flip potentiation
into depression in Yang's formula, which needs `w1 = 3.0`. Verified over multiple epochs,
final honest ratio **2.81** (vs the old artifactual 42.76 — which was never real).

### 7.4 The SOM-baseline saga: 25 Hz → seed 44 → 30 Hz

The audit found SOM firing ~36–40 Hz vs Yang's ~10 Hz. Recalibrating to a literal 10 Hz
(20.04 pA) **broke gating** (ratio 1.02). A duty-cycle argument (SOM gaps must stay under
τ_GABA,dend = 20 ms ⇒ ≥ ~20 Hz) led to **25 Hz**. Under stress-testing, **seed 44
reproducibly failed** at 25 Hz (ratio 1.015, inhibited branch escapes to ρ ≈ 0.91) —
surprisingly, SOM's *mean rate* was identical (25.27 Hz) across all seeds including 44, so
this is a **stochastic escape**, not a mean-rate miss. A 20-seed sweep (40–59): **25 Hz =
18/20 pass (seeds 44 AND 53 fail, ~10%); 30 Hz = 20/20 pass.** → baseline **relocked to
30 Hz** (`iBaseline_som`: 20.9 → 21.32 pA, commit `9b359be`), Phase 2 re-run under it, old
25 Hz results preserved as backups.

### 7.5 FINDING: the 25 Hz failure is a small-N disinhibition-variance artifact

> [AUDIT] Superseded. The failure needs SOM lockstep. With desynchronised SOM, N = 20 is
> 20/20 at 25 Hz (`docs/audit/som_async_full.json`).

(`docs/FINDING_disinhibition_variance.md`.) We then root-caused *why* seeds 44/53 fail.
It is **not** rate and **not** a timing gap. With only 20 SOM cells at p = 0.5, the
inhibited branch gets GABA from a small *integer* number of synapses, quantized in ~1.98 nS
steps. Low-draw seeds (~6 synapses, ≈12 nS) can't shunt the branch → voltage rises ~12 mV →
NMDA Mg²⁺ block opens → NMDA current ~doubles → calcium escapes → ρ ratchets to ~0.9.
**Controlled proof:** raise the SOM pool to N = 100 while holding *mean* inhibition constant
(so only its variance falls) → **20/20 pass, both failures rescued** (seed 44: 1.015→4.866).
**Key implication:** locking to 30 Hz *works but masks* this population-size fragility by
overdriving the few synapses a weak seed has. The *principled* robustness knob is **SOM
population size / connection probability** — at realistic N the inhibition self-averages and
the 25 Hz failure disappears. (Honest wrinkle: the fix is a *tail* property — N = 40 doesn't
help; it takes a substantial N to pull the whole gGABA distribution off the ~12 nS floor.)

### 7.6 FINDING: resolving the SOM-rate divergence from Yang

> [AUDIT] Superseded. "Rate × τ coverage" is the gap between lockstep volleys. With
> desynchronised SOM, the threshold is ~13–15 Hz, and at 10 Hz extra gGABA or τ rescues
> gating, i.e. mean conductance governs. The rest of the gap to Yang is the dendrite's
> weaker shunting (measured V1). The working-tree τ table (345/395/347/479 Hz·ms) also
> never showed a constant product at 40 ms.

(`docs/FINDING_som_rate_divergence.md`.) The reviewer question: Yang gates at ~10 Hz SOM,
we need ~18–21 Hz at the *same* τ_GABA,dend = 20 ms — why? **Answer: gating is set by
inhibition *coverage* (rate × τ), not rate.** In a spiking model dendritic calcium is
event-driven, so any within-ISI window the GABA tail doesn't cover lets calcium cross θ_p —
a sensitivity a rate-averaged rule smooths away. Evidence: same spike train, doubling τ
rescues gating (16.8 Hz fails at τ=20 ms, passes at τ=40 ms); critical rate × τ ≈ constant
(354 at 10 ms, 364 at 20 ms); **the model recovers Yang's ~10 Hz regime at τ = 40 ms.** So
the divergence is a quantified consequence of event-driven calcium, **not a bug.**

### 7.7 Reproducibility (Test 5) — investigated and resolved

(`docs/PROJECT_STORY.md` §10.) Test 5 reported the same seed giving different PV rates.
Root-caused (`experiments/test5_pv_diag.py`): **results are exactly reproducible per seed**
when each run is a fresh process (bit-identical across processes). The non-determinism was a
Brian2 **in-process** quirk — `PoissonGroup` spike generation isn't reset by `seed()` across
repeated builds *within one process*, while connectivity *is*. Our results are unaffected
(every result is one-build-per-process; sweeps use `ProcessPoolExecutor`). Test 5 rewritten
to the fresh-subprocess check and now **passes**.

### 7.8 Phase 2 — stress tests

- **Noise robustness** (`phase2_snr_breakdown.py`): selectivity ~62 at zero noise, drifts
  through an unstable transition (noise 0.30–0.40), collapses below ratio 1.5 by noise 0.45.
- **Ketamine / NMDA-hypofunction** (`phase2_schizophrenia_sim.py`): attenuate MD→VIP weight
  1.0→0.0. **Prediction, stated before running:** block MD→VIP ⇒ VIP can't be recruited ⇒
  SOM stays at baseline ⇒ the targeted branch is stuck shut regardless of MD. **Saw exactly
  that:** at 0–34% block both branches learn; at 67–100% block the SOM-targeted branch
  collapses (ρ ≈ 0.015) while the free branch stays ~0.80. **The interesting part: MD's
  control over *which* branch learns is what breaks** — the schizophrenia-relevant reading is
  lost flexibility, not global silencing.

### 7.9 FINDING: catastrophic forgetting — found, then fixed (the central claim)

> [AUDIT] The missing control (idle input off, NO inhibition) retains equally well:
> 99.9–100% over 5 seeds, MD-driven (`docs/audit/retention_md_context.json`), and 99.8%
> in the original script. "Needs BOTH" is not supported. Input sparsity alone protects,
> and inhibition on an active-input branch erases.

(`docs/FINDING_catastrophic_forgetting.md`.) First-ever run of the project's headline claim.
Protocol: learn A (branch 0 free) → switch → learn B (branch 1 free) → is A retained?
- **Inhibition-only context switch** (branch-0 input stays ON during B): **30% retention —
  CATASTROPHIC FORGETTING.** Diagnosis: gating ≠ protection. A gated branch has calcium
  below θ_p (no LTP) but *above* θ_d (active LTD), because its excitatory input + bAP calcium
  keep it in the depression band → it is actively erased, smoothly, ~0.17 ρ/epoch. This
  calcium rule has **no frozen/protected state.** (8× stronger gating only drops alpha_d
  3.0→1.1 s — inhibition alone can't reach the hold regime.)
- **Input + inhibition gated** (branch-0 input OFF during B): **99.9% retention — RETAINED**,
  branch 1 learns B, both coexist. With input off, calcium falls below θ_d, so the Yang
  update holds ρ unchanged.

**The sharpened claim (the real result):** *No catastrophic forgetting requires
context-specific gating of BOTH the disinhibition AND the input.* Branch separation is
**necessary but not sufficient.** This is more faithful to Zhang (a context = an active input
pattern + its MD-set disinhibition). **Consequence for scaling: the network build must keep
inputs context-SPARSE, not just branch-gated** — or it will forget at scale.

### 7.10 Appendix work — Yang Supplementary Figs 1 & 2

(`experiments/yang_supp_replication.py`, `docs/Yang_Supp_Comparison.pptx`.) Faithful
single-dendrite replication of Yang's Supp Figs 1f/1g/1h and 2a/2b/2c/2d — the NMDA-plateau
mechanism our model depends on — matched panel-by-panel against the real PDF. (Not
reproduced: Supp 1a–d full Branco morphology; Supp 2e–h stochastic switching.)

---

## 8. Where the project stands right now

> [AUDIT 2026-11-02] Current baseline: Model A with desynchronised SOM, compiled
> coupling, analytical plasticity. Full circuit at md = 0: 20/20 seeds gated at both
> 25 Hz and 30 Hz (11/20 at 15 Hz). V3 ratio 4.1 (free 0.925 / inhibited 0.227). V2 LTP
> threshold 12 Hz (free) → 98 Hz (SOM 15 Hz) → >240 Hz (SOM 30 Hz). MD-selected context
> switching works (`experiments/demo_v2_zhang2025.py`). The old "ρ_inh ≈ 0.01, ratio
> 64.83" numbers came from the retired ODE.

**Working, verified, current baseline:** Model A, SOM at 30 Hz, analytical Yang plasticity
(Eqs. 32–35), **20/20 seed reliability** in the full circuit. Single-neuron branch gating
passes. V1–V4 paper battery passes/sane. Phase 2 noise + ketamine sweeps done. Reproducibility
resolved. Forgetting mechanism resolved in miniature (needs both input- and inhibition-gating).
SOM-rate divergence from Yang quantitatively explained.

**Committed and pushed** through `7118644` (2026-10-15): all findings, the before/after proof
figure (`figures/before_after_proof.png`), and the 9-slide PI deck
(`docs/PI_Meeting_2026-10-15.pptx`) with speaker notes.

**Uncommitted working-tree state (as of 2026-11-01):** a large set of untracked analysis
scripts and result JSONs exists beyond the last commit (e.g. `experiments/seed44_escape_analysis.py`,
`experiments/across_seed_diag.py`, `experiments/model_explorer.py`,
`experiments/gating_selectivity_readout.py`, `experiments/yang_supp_replication.py`,
`docs/PROJECT_STORY.md`, `docs/NARRATIVE_WALKTHROUGH.md`, many `docs/phase1_analytical_state_*.json`,
retention figures, supp-panel figures, and several `.docx`/`.pptx`/`.odp` deliverables).
**Before building forward, run `git status` and decide what to commit** — this file does not
assume any of it is saved.

**NOT started:** the network-scale build (Phase 4) — Yang's ~3000-pyramidal regime vs our
1-soma / 2-dendrite / 20-interneuron circuit. It is **unblocked in principle** (forgetting
works with the correct context definition; calibration settled) but the build **must preserve
input context-sparsity** (§7.9).

---

## 9. Open questions and the honest caveats

> [AUDIT] Items 3 (ratio discrepancy: all three numbers predate the plasticity refactor),
> 5 (MD context protocol: now in Model A, `model/context_circuit.py`) and 8 (forgetting
> test: now MD-driven, 5 seeds, with control) are resolved. New open items:
> - PV arm: the input side was RECALIBRATED 2026-11-02 (`weight_bg_pv` 0.29 nS,
>   `gGABA_pv` 0.05 nS). PV is now ~7 Hz at rest and graded with MD (see the audit doc).
>   Output side: a balanced, fluctuation-driven somatic drive plus PV→soma 0.1 nS gives
>   graded somatic inhibition (`BALANCED_SOMA_KW` in `model/context_circuit.py`).
>   Tested result: MD→PV does NOT protect memories via fewer bAPs (retention 0.37–0.39
>   over the physiological range). The erasing LTD is NMDA-driven, so input sparsity
>   remains the only protector.
> - Overlapping inputs (`docs/PLAN_overlapping_inputs.md`): MD gating is the ONLY source of
>   context separation (discriminability ≈ 0.65·(1−f); 0 without gating), paid for by
>   erosion of shared afferents (retention ≈ 1 − 0.6·f). It is a separation/retention
>   trade-off set by overlap. Untested next: repeated A/B alternation, a functional recall
>   readout. Heavy runs can go to `toothless` (`~/tcg/`,
>   `~/miniconda3/envs/myenv/bin/python`, verified bit-identical).
> - Yang's 10 Hz needs ~1.5× gGABA (because of the dendrite's weaker shunting).
> - No experiment yet shows inhibition gating mattering for retention; that needs
>   overlapping inputs.

1. **Network scale is the next big step and the real deliverable.** Everything so far is
   single-neuron / tiny-circuit. The novel contribution (Phase 5) needs the network.
2. **The 30 Hz baseline masks a population-size fragility (§7.5).** The scientifically
   principled choice is a larger SOM pool at 25 Hz, where inhibition self-averages. Worth
   revisiting when scaling (a big network naturally has a bigger SOM pool — the problem may
   dissolve on its own, which would be a nice result to show).
3. **The three-way headline-ratio discrepancy (~43 / 64.83 / 42.76) is unresolved (§7.2).**
   Not a determinism problem — a genuine measurement-definition spread.
4. **The seed-44/53 escape is real but only partially mechanistically characterized** — the
   N-variance story (§7.5) is the best account; the sub-epoch spike-timing "why these exact
   seeds" is not fully pinned.
5. **The full MD-driven 3-epoch context protocol lives only in Model C.** Model A's
   `demo_v2_zhang2025.py` switches *global* MD drive (5→40 Hz), not branch-selective VIP
   channels. Porting the real context protocol into Model A is outstanding (it's implicitly
   what the forgetting test abstracted with a per-phase SOM-gain + input on/off switch).
6. **The legacy `validate_model.py` Test 3** still uses the old unpinned-post-rate config and
   needs rewriting to Yang's 10 Hz protocol (the dedicated `phase1_single_neuron_gating.py`
   supersedes it, but the suite is stale).
7. **Models B and C are permanently inert** — repair or retire was never decided.
8. **The forgetting test is single-seed (42), 8 epochs/phase, reduced circuit.** A fuller
   version drives the switch through MD, repeats across seeds, and runs in the full circuit.
9. **`requirements.txt` is inaccurate** — `scipy` is used by `src/v2/plasticity.py` (erf),
   contrary to older README notes; `python-pptx`/`python-docx` are needed for the deliverable
   builders. Treat it as approximate.

---

## 10. File-by-file: every folder and file in the repo

### `model/` — Model A core library (the canonical simulator)

| File | Lines | What it is |
|---|---|---|
| `parameters.py` | 250 | **All biological parameters** (Yang 2016 values, cited inline). The one parameter source. Note `num_DendEach = 10` default (overridden to 2 by builders). |
| `equations.py` | 326 | Brian 2 string equations: membrane ODEs (soma + dendrite), NMDA conductance + Mg²⁺ gate, GABA_A/GABA_B, the Eq. 13 NMDA-current calcium, the bAP calcium trace, and the (now-retired, commented) continuous `drho/dt` plasticity ODE. |
| `dendritic_io.py` | 117 | **Canonical Yang Eq. 20–22 dendritic transfer function**, rest-referenced to fix the sign defect. Single source (was 4 copies). Read its docstring for the sign-defect derivation. |
| `MultiCompartmentalModel.py` | 116 | `Model(Network)` class — builds soma + dendrites, wires bAP calcium, in-vitro/in-vivo coupling switch. |
| `full_circuit.py` | 358 | **The Phase-2 network builder** (`build_gating_circuit`). Combines Phase-1 branch gating with the full MD→PV / MD→VIP→SOM circuit; three switchable noise channels (all off by default); the `monitor_epoch0` diagnostic hook. This function is behind every reported number. |

### `src/v2/` — the analytical plasticity module

| File | Lines | What it is |
|---|---|---|
| `plasticity.py` | 148 | **Yang Eqs. 32–35 closed-form epoch update** — the current default for all reported plasticity results. Given `alpha_p`/`alpha_d` (time above each threshold), returns post-epoch ρ. Uses `scipy.special.erf`. |
| `__init__.py` | 0 | package marker |

### `experiments/` — runnable Model A experiments (Brian 2)

**Core result-producers:**
| File | Lines | Purpose |
|---|---|---|
| `phase1_single_neuron_gating.py` | 109 | **Headline result:** branch-specific gating, free vs inhibited branch (PASS). |
| `phase1_analytical.py` | 247 | Phase-1 under the analytical plasticity rule; has the `param_overrides` hook used by the τ sweep. |
| `validate_vs_papers.py` | 233 | **V1–V4 replication battery** vs Yang/Zhang figures (~10 min). |
| `validate_model.py` | 1028 | Legacy 6-test verification suite (~17 min; Test 3 stale, Test 5 now fixed). |
| `full_circuit_reliability_sweep.py` | 123 | Multi-seed reliability in the full circuit (the 18/20 vs 20/20 evidence). |
| `demo_v2_zhang2025.py` | 255 | MD context sim (global 5→40 Hz drive); shows disinhibition (SOM 36→0 Hz) + PV gain arm. |
| `sweep_phase_diagram.py` | 242 | 2D sweep over MD→PV vs MD→VIP weights (raw heatmaps; one annotated point). |
| `print_network_summary.py` | 224 | Live introspection of the built network (sizes, realised connection probabilities). |

**The three findings' scripts:**
| File | Lines | Purpose |
|---|---|---|
| `retention_catastrophic_forgetting.py` | 203 | **The forgetting test** (modes: `inputgated` retains / `inhibonly` forgets). |
| `tau_gaba_duty_cycle_sweep.py` | 113 | **SOM-rate divergence** (rate × τ coverage law). |
| `n_som_reliability_sweep.py` | 121 | **Disinhibition-variance** citable N=100 test. |
| `n_som_variance_test.py` | 54 | Fast 1-epoch `ap0 > 0.67` proxy for the N-size sweep. |
| `epoch0_timing_diag.py` | 116 | Sub-epoch E/I-balance diagnostic (why branch-0 calcium elevates). |

**Diagnostics / investigations (mostly uncommitted):**
| File | Lines | Purpose |
|---|---|---|
| `seed44_escape_analysis.py` | 217 | Mechanistic dig on the seed-44 stochastic escape. |
| `diag_seed44.py` | 48 | Confirms seed-44 collapse reproduces in the full circuit. |
| `across_seed_diag.py` | 70 | Hunts the culprit for across-seed gating failure. |
| `determinism_check.py` | 85 | Live same-seed reproducibility test of `build_gating_circuit`. |
| `test5_pv_diag.py` | 176 | Root-causes the Test-5 PV in-process non-determinism. |
| `cross_session_check.py` | 18 | Cross-session bit-identity re-run of seed 42. |
| `brian2_rng_mechanism.py` / `brian2_rng_mechanism2.py` | 80 / 60 | Pin the exact Brian2 in-process RNG mechanism. |
| `model_explorer.py` | 221 | Vary *any* parameter and see the effect (exploration harness). |
| `gating_selectivity_readout.py` | 176 | Gating-selectivity readout experiment. |
| `extract_phase1_alpha.py` | 152 | Formula-comparison helper (extract alpha operating points). |
| `phase1_ggaba_sweep.py` | 126 | gGABA (inhibition charge) sweep. |
| `phase1_som_rate_sweep.py` | 125 | SOM-rate sweep. |
| `phase1_reliability_sweep.py` / `phase1_reliability_finalize.py` | 93 / 101 | Reduced-circuit multi-seed reliability (retired as evidence — used a disjoint circuit/seeds). |
| `phase2_snr_breakdown.py` | 156 | Phase-2 noise-robustness (SNR) sweep. |
| `phase2_schizophrenia_sim.py` | 132 | Phase-2 ketamine / NMDA-hypofunction sweep. |
| `yang_supp_replication.py` | 277 | Faithful replication of Yang Supp Figs 1 & 2. |

### Added by the 2026-11-01 audit

| File | Purpose |
|---|---|
| `model/circuit_helpers.py` | Compiled soma↔dendrite coupling; SOM phase initialisation (`sync`/`random`/`even`). |
| `model/context_circuit.py` | **MD-driven, branch-selective context circuit** (MD_k→VIP_k→SOM_k→branch k), input gating, inhibition on/off, optional somatic bAPs. |
| `experiments/som_async_sweep.py` | Lockstep vs desynchronised SOM: reduced-rate sweep, mechanism test, 20-seed full circuit. |
| `experiments/retention_md_context.py` | MD-driven forgetting 2×2 (input × inhibition), 5 seeds. |
| `experiments/v1_dendrite_io_measured.py` | Non-circular V1: measured Brian 2 dendrite I/O vs Yang. |
| `experiments/bap_soma_coupling_test.py` | Somatic bAPs; does the PV arm reach plasticity. |
| `experiments/dt_convergence_check.py` | 0.1 vs 0.02 ms convergence. |
| `tests/test_audit_fixes.py` | Regression tests for the audit fixes (`--slow` adds the full-circuit legacy-equivalence check). |
| `docs/AUDIT_2026-11-01.md`, `docs/audit/` | The audit record and all its raw data/logs. |

Rewritten: `phase1_single_neuron_gating.py` (analytical wrapper), `demo_v2_zhang2025.py`
(context circuit), `sweep_phase_diagram.py` (canonical full circuit), V1/V2/V4 in
`validate_vs_papers.py`, link 5 of `tests/test_postsynaptic_calcium.py`.

### `numpy_models/` — Models B & C (frozen, inert)

| File | Lines | What it is |
|---|---|---|
| `main_gating_figures.py` | 636 | **Model B** — phenomenological figures (Figs 1–4). Plasticity inert. |
| `emergent_gating_mechanistic_model.py` | 545 | **Model C** — stochastic mechanistic figures. Plasticity inert. Only place the 3-epoch VIP context protocol exists. |

### `tests/` — unit tests (run individually)

| File | Lines | What it covers |
|---|---|---|
| `test_dendritic_io.py` | 307 | 9 assertions on the transfer function + 2 characterised limits. |
| `test_dendritic_nmda.py` | 318 | NMDA-calcium plasticity. |
| `test_postsynaptic_calcium.py` | 322 | Calcium kinetics (one assertion stale-by-design). |
| `test_pv_arm.py` | 175 | PV interneuron arm. |
| `test_numpy_plasticity.py` | 222 | Models B & C plasticity characterisation. |
| `test_circuit.py` | 71 | Brian 2 migration smoke test (~46 s). |

### `plotting/` — figure and deliverable builders (not part of the model)

Scripts that generate figures / `.pptx` / `.docx`. Key ones:
`before_after_proof.py` (the consolidated before→after proof figure),
`retention_figure.py`, `som_rate_divergence_figure.py`, `n_som_variance_figure.py`,
`generate_network_diagram.py` (network architecture), `yang_supp_reconstruction.py`,
`formula_comparison.py`, and the deck/report builders `build_pi_meeting_ppt.py`,
`build_pi_report.py`, `build_pi_story.py`, `build_results_ppt.py`,
`build_supp_comparison_ppt.py`, `build_progress_report.py`, `build_validation_docx.py`,
`generate_presentation.py`. (Deck/report builders need `python-pptx` / `python-docx`.)

### `docs/` — documentation, findings, data, deliverables

**Narrative / status (read these first):**
- `PROJECT_STORY.md` — the whole project as one continuous story (supersedes NARRATIVE_WALKTHROUGH).
- `NARRATIVE_WALKTHROUGH.md` — episodic "we tried X, it broke, we did Y" version.
- `REPAIR_LOG.md` — the audit-and-repair record (detailed; note the old `src/v2/*` paths = now `model/*`).
- `ROADMAP.md` — the phase plan (git-ignored).
- `gamma_tau_analysis.md` — the γ/τ units-bug analysis.

**The three findings (the real scientific results):**
- `FINDING_catastrophic_forgetting.md` — needs both input + inhibition gating.
- `FINDING_som_rate_divergence.md` — gating ∝ coverage (rate × τ).
- `FINDING_disinhibition_variance.md` — 25 Hz failure is small-N variance.

**Data (`*.json`, `*.csv`, `*_run.log`):** raw results and run logs for every sweep —
reliability sweeps per rate/seed, τ-duty-cycle, gGABA, SOM-rate, ketamine, SNR,
seed-44 diagnostics, phase1 analytical state dumps (`phase1_analytical_state_*.json`),
retention results, determinism checks. These are the evidence behind the findings.

**Deliverables:** `PI_Meeting_2026-10-15.pptx` (+ `.odp`), `Progress_Report.docx` /
`Progress_Report_Detailed.docx`, `Validation_Report.docx`, `PI_Story.docx`,
`Results_Summary.pptx` / `Results_Summary_PI.pptx`, `Yang_Supp_Comparison.pptx`,
`presentations/*.pptx` (v1–v3 summaries), `project_documentation.tex` (LaTeX write-up).

### `figures/` — all generated figures

Organized by producer: `phenomenological/` (Model B), `mechanistic/` (Model C),
`validation/` (validate_model), `validation_vs_papers/` (V1–V4), `paper_replications/`
(curated bundle + README), `supp_panels/` (Yang supp panels, ours vs paper). Standalone key
figures: `before_after_proof.png` (the headline before→after), `network_architecture.png`,
`retention_forgetting*.png`, `som_rate_divergence.png`, `n_som_disinhibition_variance.png`,
`seed44_escape_mechanism.png`, `phase2_*` (ketamine/SNR), `phase_diagram.png`,
`yang_supp{1,2}_*.png`. (`figures/test.txt` is a stray; ignorable.)

### `archive/` — dead code kept for reference (do not import)

`InterneuronalCircuit.py` (419 lines, LEGACY/UNUSED, references a nonexistent `p['n_som']`),
`generate_network_synapse_figure_DARKTHEME_deprecated.py`.

### `scripts/` — effectively empty now

Only `__pycache__` remains; the real builders moved to `plotting/`. (Older README/REPAIR_LOG
references to `scripts/generate_presentation.py` etc. now live in `plotting/`.)

### Root files

`README.md` (the authoritative factual status report — read it), `requirements.txt`
(inaccurate, see §9), `.gitignore` (ignores `__pycache__`, Office temp files, and
`ROADMAP.md`), and **this file** `PROJECT_BIBLE.md`.

---

## 11. How to run things (environment + commands)

**Environment (verified 2026-11-01, this Linux box):** use `/home/raghav/myenv/bin/python`
— Python 3.14.4, **brian2 2.10.1, numpy 2.5.3, scipy 1.18.1**. The project *can run here now*
(an earlier note that brian2 wasn't installed on Linux is **stale**). The bare system
`python3` has no brian2; there is no `conda` and no `~/miniconda3` on this machine — use the
`myenv` venv directly.

```bash
export PY=/home/raghav/myenv/bin/python
cd "/run/media/raghav/New Volume/minsu/Thalamocortical_Gating_Project"

# instant — inspect the live network
$PY experiments/print_network_summary.py

# the headline gating result
$PY experiments/phase1_single_neuron_gating.py

# the three findings
$PY -I experiments/retention_catastrophic_forgetting.py inputgated   # retains (100%)
$PY -I experiments/retention_catastrophic_forgetting.py inhibonly    # forgets (30%)
$PY -I experiments/tau_gaba_duty_cycle_sweep.py                      # SOM-rate / coverage
$PY -I experiments/n_som_reliability_sweep.py n100 4                 # disinhibition variance

# paper battery (~10 min) and full suite (~17 min) — background them
nohup $PY experiments/validate_vs_papers.py > /tmp/v.txt 2>&1 &
nohup $PY experiments/validate_model.py     > /tmp/s.txt 2>&1 &

# the inert NumPy figure models (fast)
$PY numpy_models/main_gating_figures.py
$PY numpy_models/emergent_gating_mechanistic_model.py
# audit (2026-11-01) checks
$PY tests/test_audit_fixes.py --slow                          # ~3 min
$PY -I experiments/retention_md_context.py 10                 # MD-driven forgetting 2x2
$PY -I experiments/som_async_sweep.py reduced|mech|full 10    # lockstep vs desync
$PY experiments/demo_v2_zhang2025.py                          # MD selects the branch
```

**Gotchas:**
- Long runs exceed a 2-minute foreground limit — **background them** (`nohup … &`).
- Reduced Phase-1 runs are ~8–9 min per 8-epoch point regardless of codegen. For τ/rate
  sweeps: use cython, one τ per process, run τ's in **parallel** (the box has 12 cores);
  `nohup`+`disown` mostly survives a session but verify the job is alive (one died silently once).
- Results are **reproducible per seed only across separate processes** (Brian2 in-process RNG
  quirk, §7.7). Sweeps already use `ProcessPoolExecutor`; keep diagnostics one-build-per-process.
- Run untrusted-data scripts with `-I` (isolated) as several already do.
- `git` here uses `gh`/HTTPS auth (account `pareeksra`); the SSH key is **not** registered on
  GitHub, so push via HTTPS, not SSH.
- On a Windows console (if ever back there), prefix `PYTHONIOENCODING=utf-8` so `→`/`✓` prints
  don't trip cp1252.

---

## 12. Glossary

- **MD** — mediodorsal thalamus. The upstream "context" signal.
- **PFC** — prefrontal cortex. Where the pyramidal neuron and interneurons live.
- **PV / SOM / VIP** — three interneuron types. PV→soma (gain control); SOM→dendrite (the
  gate); VIP→SOM (disinhibition — opens the gate).
- **Disinhibition** — inhibiting an inhibitor. VIP inhibits SOM, which *removes* SOM's
  inhibition of the dendrite → the branch is free to learn.
- **Dendritic branch** — a compartment of the pyramidal cell that can independently reach an
  NMDA plateau and thus independently learn.
- **NMDA plateau** — a regenerative dendritic depolarization; the nonlinear "on-switch" for
  branch-specific calcium and LTP.
- **bAP** — back-propagating action potential. Drives branch-*uniform* calcium (Eq. 14) — the
  reason selectivity dies above ~74 Hz somatic rate.
- **ρ (rho)** — Graupner–Brunel bistable synaptic efficacy, ∈ [0,1]. 0 = DOWN/weak, 1 = UP/strong.
- **θ_p / θ_d** — calcium thresholds for potentiation (2.78) / depression (1.0).
- **τ_GABA,dend** — dendritic GABA decay time constant (20 ms). With SOM rate it sets
  inhibition *coverage* (§7.6).
- **Coverage / duty cycle** — fraction of time a branch is shunted = rate × τ_GABA,dend. The
  real control variable for gating in a spiking model.
- **Gating ratio** — ρ_free / ρ_inhibited. > ~1.5 (with separation) = gating works; ~1 = failed.
- **Catastrophic forgetting** — learning B erases A. Prevented by silencing the idle context's input (inhibition not needed; [AUDIT] §7.9).
- **Analytical plasticity** — Yang's closed-form Eqs. 32–35 (not the continuous ODE); current default.
- **Model A / B / C** — the three implementations (§5). **A (Brian 2) is canonical.**
```