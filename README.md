# Thalamocortical Gating & Cognitive Flexibility Model

A computational study that grafts the **cell-type-specific mediodorsal-thalamic (MD)
projections of Zhang et al. (2025)** onto the **dendritic disinhibitory gating circuit
and Graupner–Brunel calcium plasticity of Yang et al. (2016)**, to ask whether MD drive
can control *which* dendritic branches of a PFC pyramidal neuron undergo calcium-based
plasticity — context-specific learning without catastrophic forgetting.

> **Read this before citing any figure.** This is a factual status report, verified by
> executing the code and by checking both source papers, not a to-do list.
> Last verified **2026-08-26** (Windows, `python` = Python 3.14.5 / brian2 2.10.1).
>
> - **This is a novel synthesis, not a replication.** The plasticity constants and the
>   dendritic transfer function are faithful to Yang 2016 (see
>   [Provenance](#provenance-what-is-and-isnt-from-the-papers)), but the project does
>   **not reproduce the full headline result of either paper.** Calling it a "replication
>   of Yang" or an "extension of Zhang" overstates what exists.
> - **The central claim — that dendritic inhibition gates which branch undergoes
>   plasticity — is now demonstrated at the single-neuron level.**
>   `experiments/phase1_single_neuron_gating.py` produces a disinhibited (free) branch that
>   potentiates (ρ ≈ 0.78, w ≈ 2.34) while the SOM-inhibited branch does not (ρ ≈ 0.02,
>   w ≈ 0.06) — a free/inhibited ratio of **~43** at Yang's 10 Hz post-synaptic rate. This
>   **supersedes** the earlier "branch-gating fails at ratio 0.991" status.
> - **Caveats, stated plainly:** (i) this is the dedicated single-neuron Phase-1
>   experiment, *not* the legacy `validate_model.py` Test 3, whose old configuration
>   (unpinned post rate, soma ~200 Hz) has not yet been re-run or rewritten; (ii) the two
>   NumPy figure models (B, C) remain plasticity-inert; (iii) the network-scale stage is
>   still essentially unstarted.
> - The two calibration bugs that used to block gating are now fixed in Model A; see
>   [Status of the two former blocking bugs](#status-of-the-two-former-blocking-bugs).

## Relationship to the two source papers

The project's stated arc is *replicate Yang 2016 → extend to Zhang 2025 → build a
scalable network*. It is important to be precise about how far each stage has actually
gone, because the two papers are **different classes of model** and the project only
borrows selectively from each.

| | **Yang et al. 2016** (Nat. Commun. 7:12815) | **Zhang et al. 2025** (Nat. Commun. 16:2640) |
|---|---|---|
| Model class | Spiking / reduced-compartment | **Rate-based RNN, ML-trained** |
| Dendrites | Yes — the mechanism | None |
| Plasticity | Graupner–Brunel calcium | None (trained weights) |
| MD thalamus | Absent (abstract "control input") | Feedforward **corticothalamic loop** (PFC↔MD) |
| Headline result | Branch-specific dendritic gating; inhibition shifts the LTP threshold | MD improves working memory & context-switching under low SNR |

**What this project genuinely inherits:**

- *From Yang 2016:* the reduced multi-compartment pyramidal cell, the VIP→SOM→dendrite
  disinhibition and PV→soma motifs, GABA_A shunting inhibition, NMDA plateau nonlinearity,
  the Graupner–Brunel plasticity rule, and — exactly — the dendritic I/O transfer
  function (Eq. 20–22) and all of its fitted plasticity constants.
- *From Zhang 2025:* the two cell-type-specific MD projections — **MD→PV** (their
  MD^GRIK4→PV pathway) and **MD→VIP** (their MD^DRD2→VIP pathway, disinhibition). The
  marker→target pairing is verified against Zhang: **GRIK4 (kainate-receptor) → PV** and
  **DRD2 (dopamine-D2) → VIP**, not swapped. Wording caveat: Zhang frames MD^GRIK4→PV as
  *feedforward inhibition / prefrontal-noise suppression*; the term "gain control" in that
  paper refers to the VIP–SOM motif and to corticothalamic modulation, not to MD→PV
  directly. Calling MD→PV "gain control" is a defensible paraphrase (feedforward PV
  inhibition is a form of gain control) but is not the paper's literal attribution.

**What it does NOT do (do not claim otherwise):**

- **It reproduces Yang's gating at the single-neuron level, but not yet at network
  scale.** Branch-specific gating requires the disinhibited branch to reach the NMDA
  plateau while the inhibited branch stays at rest. This now works in
  `experiments/phase1_single_neuron_gating.py` (free/inhibited ratio ~43 at Yang's 10 Hz
  post rate). What is *not* done is Yang's full quantitative replication (Fig. 2c I/O,
  Fig. 7b LTP-threshold shift, Fig. 7d–e) or the ~3,000-neuron network.
- **It does not reproduce or extend Zhang's model.** Zhang is a rate RNN performing a
  trained cognitive task; none of that (the task, psychometric curves, working-memory
  delay, attractor/subspace analysis, or the SOM→Exc-sparsity E/I-imbalance result) is
  implemented here. The project takes Zhang's **wiring labels only**, and even then omits
  Zhang's PFC→MD feedback loop and MD→excitatory projection — its MD is a bare external
  `PoissonGroup`.
- **The scalable-network stage is essentially unstarted.** Yang's network is ~3,000
  pyramidal + 160 SOM + 140 VIP + 200 PV neurons with ~30 dendrites each. Model A here is
  **1 pyramidal soma, 2 dendrites, 20 of each interneuron**.

## Status of the two former blocking bugs

Both were calibration/formulation errors against Yang 2016's own Methods. **Both are now
fixed in Model A** (the Brian 2 model), which is why Phase-1 gating passes. They remain in
the two NumPy figure models (B, C), which were frozen as illustrative sketches.

### Bug 1 (drive too weak) — FIXED in Model A

Yang sets the maximum excitatory conductance per dendrite to **g_E,max = 25 nS**, with
half-activation **g₁/₂ = β_g·(g_L,D + g_inh) = 5.56·(4 + g_inh) nS** (Eqs 21–22; the "4"
is the dendritic leak g_L,D = 4.0 nS). That gives the gating:

- disinhibited branch (g_inh ≈ 2 nS): g₁/₂ ≈ 33 nS, driven near plateau → **activates**;
- inhibited branch (g_inh ≈ 35 nS): g₁/₂ ≈ 217 nS, same drive → **stays at rest**.

The Phase-1 experiment drives the pathway at **80 Hz** with Yang's **in-vivo dendrite–soma
coupling g_c = 0.8 nS** (`gEachCouple_pyr_vivo`, previously the experiments used 4.0 nS),
which brings the free branch onto the plateau while the shunted branch stays near rest.
Measured: free branch potentiates (ρ ≈ 0.78), inhibited branch does not (ρ ≈ 0.02). The
NumPy figure models still use the old sub-threshold drive and remain inert.

### Bug 2 (calcium model not Yang's) — FIXED in Model A

Yang's dendritic calcium has **two components** (Methods p. 11):

- **NMDA calcium — a leaky integral of the NMDA current** (Eq. 13):
  `τ_Ca · d[Ca]_NMDA/dt = −[Ca]_NMDA + κ_NMDA · I_NMDA`, where κ_NMDA (0.371, unit **per
  pA**) scales a *current*. Under a plateau this accumulates well past `θ_p = 2.78` → LTP.
- **VGCC calcium — per-spike bumps from back-propagating APs** (Eq. 14): a sum of
  bi-exponential transients whose per-spike peak is κ_VGCC = 0.957.

Model A now implements exactly this: `equations.py` integrates the NMDA-current calcium
(`kappa_Ca_NMDA * gNMDA * s_nmda * mg_gate * (vE − V)`, Eq. 13) and reads the branch's bAP
transient `bAPCa` (Eq. 14) as the postsynaptic component. The two NumPy models (B, C)
instead treat κ_NMDA as a fixed **per-spike jump**, capping single-pairing calcium at
`0.371 + 0.957 = 1.328 < θ_p`, so **LTP stays structurally impossible in B and C** — which
is why their figures remain inert. (Note: Yang's rule was *fit* to spike pairings but
*deployed* with Poisson rate trains at a fixed 10 Hz post rate, so a single pair failing to
reach θ_p is expected, not a defect.)

## Provenance: what is and isn't from the papers

An earlier note in this repository claimed these constants were unsourced (it pointed to
`data/parameters.txt` / `data/equations.txt` files that **never existed in any commit**).
That was a documentation gap, not a values problem: **every constant is Yang 2016's
published value**, verified against the paper (Methods pp. 11–12):

| Constant | Yang 2016 value | Location |
|---|---|---|
| `theta_p = 2.78` | θ_p = 2.78 | Methods p. 12 |
| `theta_d = 1.0` | θ_d = 1 (fixed, from Graupner–Brunel ref. 36) | Methods p. 12 |
| `gamma_d = 39.949` / `gamma_p = 177.552` | γ_d = 39.9 / γ_p = 177.6 | Methods p. 12 |
| `tau = 346.36 s` | τ_ρ = 346.36 s (the **ρ/weight** time constant, from ref. 36) | Methods p. 12 |
| `sigma = 3.35` | σ = 3.35 (from ref. 36) | Methods p. 12 |
| κ_NMDA = 0.371 (NumPy `C_NMDA`) | κ_NMDA = 0.371 | Methods p. 12, Eq. 13 |
| κ_VGCC = 0.957 (NumPy `C_BAP`) | κ_VGCC = 0.957 | Methods p. 12, Eq. 14 |

The dendritic I/O function `dend_IO` is Yang's Eq. 20–22 with its exact fit values
(β_g = 5.56 → `Q[0]`, k = 9.64 nS → `Q[1]`, γ = 6.54 nS → `Q[2]`, V₀ = 0.78 mV → `Q[3]`;
Methods p. 11), and `g_E,max = 25 nS`, `g_L,D = 4.0 nS` match Yang exactly.

Three points worth keeping straight, because the papers distinguish them and the earlier
docs blurred them:

- **`tau = 346.36 s` is the ρ (synaptic-weight) time constant, not a calcium time
  constant.** Yang's calcium decays with τ_Ca,decay = 30 ms (`tau_Ca_NMDA` = 30 ms here).
- **κ_NMDA and κ_VGCC are different kinds of constant.** κ_NMDA (unit **per pA**) scales
  the NMDA *current* inside a leaky integral (Eq. 13); κ_VGCC is the **per-postspike bump
  peak** (Eq. 14). Treating either as a symmetric per-spike jump — as the NumPy models B/C
  do — is [Bug 2](#status-of-the-two-former-blocking-bugs).
- **In vivo, Yang scales both down:** κ̂_NMDA = 0.75·κ_NMDA = 0.278, κ̂_VGCC = 0.2·κ_VGCC =
  0.191. Model A's calibrated `kappa_Ca_NMDA = 0.26 /pA` sits close to Yang's in-vivo
  0.278 /pA (it was reached by Phase-1 calibration, not cited — worth noting as a
  near-coincidence, not a claimed provenance).

## Three models, not one

This repository contains **three independent implementations**. They share parameter
values by convention but not by code, and they are not interchangeable. Knowing which one
produced a figure is essential to reading it.

| Model | Files | What it is |
|---|---|---|
| **A. Brian 2 spiking network** | `model/`, `experiments/` | The full spiking circuit: multi-compartment pyramidal cell, PV/SOM/VIP LIF interneurons, MD as a `PoissonGroup`, native Brian 2 Graupner–Brunel synapses. The only model with connection *probabilities*, and the only one whose single-synapse LTP/LTD works. |
| **B. Phenomenological (NumPy)** | `numpy_models/main_gating_figures.py` | Proof-of-concept of Yang et al. (2016). Uses **hardcoded** dendritic inhibition instead of simulating interneurons. Produces documentation Figures 1–4. Plasticity currently inert (bugs 1 & 2). |
| **C. Emergent mechanistic (NumPy)** | `numpy_models/emergent_gating_mechanistic_model.py` | Stochastic trial-based model where inhibition *emerges* from noisy interneuron rates driven by Poisson MD spike counts. Produces the four `figures/mechanistic/` figures. Plasticity currently inert (bugs 1 & 2). |

Models B and C are pure NumPy — they do **not** import `model/` and do not use Brian 2.
Both replace Graupner–Brunel's bistable ρ dynamics with a **monostable relaxation** toward
`rho_bar` at rate `ETA_RHO = 0.08` (because the true τ = 346 s moves nothing in 300
trials). Their figures are therefore captioned "bistable" but the code is not — there is
no double well.

## Repository layout

```
model/                               Model A — core Brian 2 library (importable modules)
  parameters.py                      All biological parameters (see table below)
  equations.py                       Membrane ODEs + Graupner-Brunel synapse equations
  dendritic_io.py                    Canonical Yang 2016 Eq. 20-22 transfer function
                                     (was copy-pasted into 4 files; now the single source)
  MultiCompartmentalModel.py         Model class wrapping soma + dendrite construction

experiments/                         Model A — runnable experiments (Brian 2)
  phase1_single_neuron_gating.py     Headline result: branch-specific gating (PASS, ratio ~43)
  validate_vs_papers.py              V1-V4 replication vs Yang/Zhang figures (~10 min)
  validate_model.py                  6-test verification suite (~17 min; last recorded 4/6, stale)
  demo_v2_zhang2025.py               MD drive context simulation (5 Hz -> 40 Hz)
  sweep_phase_diagram.py             2D sweep over MD->PV vs MD->VIP weights
  print_network_summary.py           Live introspection of the built network
  generate_network_synapse_figure.py Draws the network architecture diagram (hand-drawn)

numpy_models/                        Models B & C — pure-NumPy figure models (no Brian 2)
  main_gating_figures.py             Model B — phenomenological figures (~3 s)
  emergent_gating_mechanistic_model.py Model C — stochastic mechanistic figures (~4 s)

tests/                               Unit tests (run any with `python tests/<name>.py`)
  test_dendritic_io.py               9 assertions on the transfer function
  test_dendritic_nmda.py             NMDA-calcium plasticity tests
  test_postsynaptic_calcium.py       (1 assertion is stale-by-design; see Known gaps)
  test_pv_arm.py                     PV interneuron arm
  test_numpy_plasticity.py           Models B & C plasticity characterisation
  test_circuit.py                    Brian 2 migration smoke test (~46 s)

scripts/                             Utilities (not part of the model)
  generate_presentation.py           Builds the .pptx deck (needs python-pptx; not installed)
  build_validation_docx.py           Assembles docs/Validation_Report.docx (needs python-docx)

docs/                                Documentation and deliverables
  REPAIR_LOG.md                      Detailed record of the audit-and-repair pass
  ROADMAP.md                         Planning notes (git-ignored)
  project_documentation.tex          LaTeX write-up
  Validation_Report.docx             Generated validation report
  presentations/                     .pptx summary decks (v1..v3)

archive/                             Dead code kept for reference
  InterneuronalCircuit.py            LEGACY / UNUSED — imported by nothing

figures/                             All generated output figures
  phenomenological/                  Model B output (fig1..fig4)
  mechanistic/                       Model C output (4 figures)
  validation/                        validate_model.py diagnostics (test1..test4)
  validation_vs_papers/              validate_vs_papers.py output (v1..v4 + results.json)
  paper_replications/                Curated presentation bundle of the replication figures
  phase_diagram.png                  sweep_phase_diagram.py output
  demo_zhang2025_context_switch.png  demo_v2_zhang2025.py output
  network_synaptic_architecture.png  generate_network_synapse_figure.py output
  v2_migration_test.png              test_circuit.py output
```

All scripts resolve their own paths, so they can be run from anywhere (e.g.
`python experiments/phase1_single_neuron_gating.py` or `python tests/test_pv_arm.py`).
On a Windows console, prefix with `PYTHONIOENCODING=utf-8` (or `set PYTHONIOENCODING=utf-8`)
so the `→`/`✓` characters in progress prints don't trip the cp1252 codec.

## Environment

On this Windows machine the project runs under the plain Python on `PATH`:

```bash
python experiments/print_network_summary.py   # etc. — no conda needed here
```

Verified working (2026-08-26, Windows): `C:\Python314\python` — Python 3.14.5,
brian2 2.10.1, numpy 2.4.6. `python-pptx` is **not installed**, so
`scripts/generate_presentation.py` fails with `ModuleNotFoundError`.

> The project was originally developed on a Linux host (referenced in older docs as
> `/home/raghav/miniconda3/envs/myenv/bin/python`) and has also been run from a Windows
> machine over an SSHFS mount of that host. It now lives on a local disk and runs with the
> local `python` above. On any machine where plain `python` lacks Brian 2, create an env
> (`conda`/`venv`) and point at its interpreter instead.

**`requirements.txt` discrepancies** (the file is not currently accurate):

- `scipy` is listed but **never imported** by any module in this repository.
- `python-pptx` is listed and required by `scripts/generate_presentation.py`, but is not
  installed, so that script fails with `ModuleNotFoundError`.
- The pinned floors do not describe the versions actually in use.

## Usage

Every command below was executed against the current tree; the stated runtimes and
outputs are measured, not estimated.

### Model A — Brian 2 spiking network

**1. Inspect the live network** — instant. Genuinely builds the network and reads
`len(group)` / `len(synapses)` / realised connection probabilities.

```bash
python experiments/print_network_summary.py
```

**2. Verification suite** — ~17 min. Writes `figures/validation/test{1..4}.png`.

```bash
python experiments/validate_model.py       # long; background it
```

Last recorded result (before the Phase-1 fixes): **4/6 PASSED**, with `Test 3:
Branch-Specific Gating` and `Test 5: Reproducibility` failing. **This has not been re-run
since the calcium/coupling fixes landed**, so treat 4/6 as stale. Note that Test 3 builds
an *old* configuration (SOM-only, unpinned post rate, soma ~200 Hz) that the dedicated
`experiments/phase1_single_neuron_gating.py` was written to supersede — Test 3 needs to be
rewritten to pin the post rate at Yang's 10 Hz (see `docs/REPAIR_LOG.md` §6). Re-running the
suite and porting the Phase-1 protocol into Test 3 is the next verification task.

**3. MD drive simulation** — ~3 min. Writes `figures/demo_zhang2025_context_switch.png`.

```bash
python experiments/demo_v2_zhang2025.py
```

Runs 2 s at 5 Hz MD drive then 2 s at 40 Hz. Measured output:

```
PV  mean rate:  Context A = 15.9 Hz,  Context B = 130.8 Hz
SOM mean rate:  Context A = 36.5 Hz,  Context B =   0.0 Hz
Pyr mean rate:  Context A =  6.0 Hz,  Context B =   0.0 Hz
```

The **SOM row is the disinhibition working**: MD silences SOM (36.5 → 0 Hz). The **PV row
is the working gain-control arm**: PV rises 15.9 → 130.8 Hz. The pyramidal cell is
**suppressed** at high drive (6.0 → 0 Hz) — PV inhibition now dominates. Note these two
levels are *global* MD drive, not the branch-selective contexts of the 3-epoch protocol,
which exists only in Model C.

**4. Phase diagram sweep** — ~3 min. Writes `figures/phase_diagram.png`. Emits four raw
heatmaps and marks one "Healthy Baseline" point; there is **no** pathological regime or
classification logic, and because ρ cannot depend on the swept weights, the ΔW panel
carries no information.

```bash
python experiments/sweep_phase_diagram.py
```

### Models B and C — NumPy figure models

```bash
python numpy_models/main_gating_figures.py                # ~3 s -> figures/phenomenological/
python numpy_models/emergent_gating_mechanistic_model.py  # ~4 s -> figures/mechanistic/
```

Model C prints Gating Selectivity indices (seed 42): **VIP = 0.84, SOM = −0.66,
PV = −0.02**. These describe the *interneuron rates* doing their jobs (VIP selective, SOM
anti-selective via disinhibition, PV non-selective) — not synaptic learning, which is
inert (see the two bugs).

## Model architecture (as implemented, Model A)

### Populations and wiring

Values from `model/parameters.py`, read live via `print_network_summary.py`.

| Population | Size | Population | Size |
|---|---|---|---|
| Pyramidal soma | 1 | PV interneurons | 20 |
| Dendritic branches | 2 (`num_dend_each`) | SOM interneurons | 20 |
| MD thalamus (`PoissonGroup`) | 50 | VIP interneurons | 20 |
| Cortical pathway (`PoissonGroup`) | 30 @ 80 Hz | PV background (`PoissonGroup`) | 20 @ 500 Hz |

| Projection | p (requested) | Weight |
|---|---|---|
| MD → PV (AMPA) | 0.5 | 0.12 nS |
| MD → VIP (AMPA) | 0.3 | 0.5 nS |
| VIP → SOM (GABA) | 0.6 | 3.0 nS |
| SOM → Dendrite (GABA) | 0.5 | 4.0 nS |
| PV → Soma (GABA) | 0.6 | 5.0 nS |
| Background → PV (AMPA) | all-to-all | 0.25 nS |
| Pathway → Dendrite | all-to-all | plastic, `w = w0 + (w1−w0)·ρ`, `c += C_pre·mg_gate` |

The MD→PV/MD→VIP asymmetry: total drive `p·n·g` is 3.0 nS (PV) vs 7.5 nS (VIP), so MD
drive onto VIP is 2.5× stronger in aggregate despite the *lower* connection probability.
The pathway distinction rests on VIP's sparser, stronger contacts, not on total drive.

SOM cells receive **no synaptic excitation**; their baseline comes from a bias current
`iBaseline_som` (22 pA → ~36–40 Hz measured).

**Two documented divergences from Yang 2016** (verified against the paper — these are not
quirks, they are places the model departs from its source):

- **SOM baseline rate.** Yang 2016 sets SOM baseline at **~10 Hz** ("SOM neurons receive
  150 pA input current … baseline firing ~10 Hz", Methods p. 11); this project runs
  ~36–40 Hz, roughly 4× higher. This matters because a high somatic/interneuron rate is
  what drove the old bAP-swamping problem.
- **Missing SOM → PV synapse.** Yang 2016 *does* include SOM → PV inhibition
  (connection probability **P_SOM–PV = 0.8**, used in his Fig. 6). This project defines
  `gGABA_pv` for exactly such a synapse but **never wires it**, so the `iGABA` term in
  `eqs_pv` is always zero. It is an unfinished Yang connection, not an intentional
  simplification.

### Plasticity (Model A)

Native Brian 2 Graupner–Brunel synapses. Calcium now follows Yang's Eq. 13: the NMDA
component is the **leaky integral of the local NMDA current**,
`tau_Ca_NMDA · dc/dt = −c + kappa_Ca_NMDA · gNMDA · s_nmda · mg_gate · (vE − V)`, driven by
a dendritic NMDA conductance with a voltage-dependent Mg²⁺ gate (the summed variable
`iTotNMDA1`). The postsynaptic component is the branch's bAP transient (`bAPCa`, Eq. 14),
read as `c_total = c + bAPCa_post`. (The old per-spike `c += C_pre · mg_gate` form is
retired; `C_pre` is kept in `parameters.py` only for backward reference.) Noise on ρ is
gated on calcium activity (integrated with `method='heun'`), and a clipper holds ρ in
[0, 1]. See `docs/REPAIR_LOG.md` for the wiring history.

| Parameter | Value | Parameter | Value |
|---|---|---|---|
| `theta_d` / `theta_p` | 1.0 / 2.78 | `gamma_d` / `gamma_p` | 39.949 / 177.552 |
| `tau` | 346.36 s | `sigma` | 3.35 |
| `w0` / `w1` | 0.0 / 3.0 | `C_pre` | 1.0 (legacy, no longer scales Ca) |
| `tau_Ca_NMDA` | 30 ms | `tau_Ca_bAP_decay` | 30 ms |
| `kappa_Ca_NMDA` | 0.26 /pA (Phase-1 calibrated; ≈ Yang in-vivo 0.278) | | |

**Weight scale differs between models:** `w1 = 3.0` in `parameters.py` and Model B, but
`1.0` in Model C, so their weight axes are **not** directly comparable despite carrying
the same caption.

## Known gaps: specified but not yet working

Each was verified by execution.

- **Single-neuron gating now works (`phase1_single_neuron_gating.py`), but the legacy
  Test 3 has not been updated.** Phase-1 gives free/inhibited ratio ~43 at Yang's 10 Hz
  post rate. The old `validate_model.py` Test 3 still uses the unpinned-post-rate
  configuration in which the branch-uniform bAP calcium swamps the selective NMDA signal
  above ~74 Hz somatic rate (`docs/REPAIR_LOG.md` §6); it needs rewriting to Yang's 10 Hz
  protocol and re-running.
- **Models B and C produce no plasticity** — every Graupner–Brunel update falls to the
  calcium-inactive branch (peak calcium ≈ 0.02 vs θ_d = 1.0). Their "learning" figures are
  random walks driven by `sigma`. See [both bugs](#status-of-the-two-former-blocking-bugs).
- **Not reproducible under a fixed seed (Model A, Test 5)** — same seed gives PV
  14.425 vs 14.275 Hz. Undiagnosed; a shared RNG stream couples plasticity to circuit
  noise in the mechanistic model.
- **The 3-epoch VIP-1/VIP-2 protocol exists only in Model C.** Model A's
  `demo_v2_zhang2025.py` switches *global* MD drive (5 → 40 Hz); no branch-selective VIP
  channels, no baseline epoch. Porting it to Model A is outstanding.
- **No pathology classification in the phase diagram** (one annotated point, not a phase
  diagram); the ΔW panel carries no information.
- **Figure 1 (STDP curve) has no LTP arm** — single-pairing calcium (≤ 1.328) cannot cross
  θ_p = 2.78. This is [bug 2](#status-of-the-two-former-blocking-bugs); note also that
  Yang's plasticity is *rate*-based (Fig. 7b), not single-pair STDP, so this figure tests
  the wrong protocol.
- **Figure 3 is a hand-calibrated surrogate** with invented lumped constants and a `×50`
  scale factor; its NMDA driving-force term is identically zero across the plotted range,
  so the "NMDA-controlled" curve contains no NMDA contribution.
- **`archive/InterneuronalCircuit.py` is unused** and references `p['n_som']`, which does not exist.

## References

- **Yang, G. R., Murray, J. D. & Wang, X.-J. (2016).** A dendritic disinhibitory circuit
  mechanism for pathway-specific gating. *Nature Communications* **7**, 12815.
- **Graupner, M. & Brunel, N. (2012).** Calcium-based plasticity model explains
  sensitivity of synaptic changes to spike pattern, rate and dendritic location.
  *PNAS* **109**, 3991–3996.
- **Zhang, X., Mukherjee, A., Halassa, M. M. & Chen, Z. S. (2025).** Mediodorsal thalamus
  regulates task uncertainty to enable cognitive flexibility. *Nature Communications*
  **16**, 2640.
```
