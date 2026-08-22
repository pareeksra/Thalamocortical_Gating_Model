# Thalamocortical Gating & Cognitive Flexibility Model

Computational models extending the pathway-specific dendritic gating mechanism of
[Yang et al. (2016)](https://www.nature.com/articles/nn.4303) to the Mediodorsal
Thalamic (MD) drive and E/I balance hypothesis of Zhang (2025).

The scientific goal is to model the MD thalamus as a **meta-controller** for cognitive
flexibility: by projecting to both Somatostatin (SOM) gating circuits (via VIP
interneurons) and somatic excitability circuits (via PV interneurons), MD drive should
determine *which* dendritic branches of PFC pyramidal neurons undergo calcium-based
plasticity — allowing context-specific learning without catastrophic forgetting.

> **Implementation status.** The circuit, the interneuron populations and the
> Graupner-Brunel plasticity machinery are all implemented and run. The
> **disinhibitory arm (MD → VIP → SOM) works as specified.** However, the
> project's central claim — that dendritic inhibition gates plasticity — is
> **not currently reproduced by any of the three models**, and the automated
> suite reports **5/6**, with the branch-gating test failing. See
> [Known gaps](#known-gaps-specified-but-not-yet-working) before citing any figure
> as a result. This section is a factual status report, not a to-do list; the
> requirements it refers to remain the intended behaviour.

## Three models, not one

This repository contains **three independent implementations**. They share parameter
values by convention but not by code, and they are not interchangeable. Knowing which
one produced a figure is essential to reading it.

| Model | Files | What it is |
|---|---|---|
| **A. Brian 2 spiking network** | `src/v2/`, `experiments/` | The full spiking circuit: multi-compartment pyramidal cell, PV/SOM/VIP LIF interneurons, MD as a `PoissonGroup`, native Brian 2 Graupner-Brunel synapses. The only model with connection *probabilities*. |
| **B. Phenomenological (NumPy)** | `main_gating_figures.py` | Proof-of-concept replication of Yang et al. (2016). Uses **hardcoded** dendritic inhibition instead of simulating interneurons. Produces documentation Figures 1–4. |
| **C. Emergent mechanistic (NumPy)** | `emergent_gating_mechanistic_model.py` | Stochastic trial-based model where inhibition *emerges* from noisy interneuron rates driven by Poisson MD spike counts. Produces the four `figures/mechanistic/` figures. |

Models B and C are pure NumPy — they do **not** import `src/v2/` and do not use Brian 2.

## Repository layout

```
src/v2/                              Model A — core Brian 2 codebase
  parameters.py                      All biological parameters (see table below)
  equations.py                       Membrane ODEs + Graupner-Brunel synapse equations
  MultiCompartmentalModel.py         Model class wrapping soma + dendrite construction
  test_circuit.py                    Brian 2 migration smoke test (~46 s)
  InterneuronalCircuit.py            LEGACY / UNUSED — imported by nothing (see Known gaps)

experiments/                         Model A — runnable experiments
  validate_model.py                  6-test verification suite (~904 s, currently 5/6)
  demo_v2_zhang2025.py               MD drive context simulation (5 Hz -> 40 Hz)
  sweep_phase_diagram.py             2D sweep over MD->PV vs MD->VIP weights
  print_network_summary.py           Prints architecture + plasticity equations
  generate_network_synapse_figure.py Draws the network architecture diagram

main_gating_figures.py               Model B — phenomenological figures (~3 s)
emergent_gating_mechanistic_model.py Model C — stochastic mechanistic figures (~4 s)
generate_presentation.py             Builds the .pptx summary deck (needs python-pptx)

figures/
  phenomenological/                  Model B output (fig1..fig4)
  mechanistic/                       Model C output (4 figures)
  validation/                        validate_model.py diagnostics (test1..test4)
  phase_diagram.png                  sweep_phase_diagram.py output
  demo_zhang2025_context_switch.png  demo_v2_zhang2025.py output
  network_synaptic_architecture.png  generate_network_synapse_figure.py output
```

## Environment

**This project does not run under a plain `python` / `venv` setup on this machine.**
There is no `python` on `PATH` — only `python3`, which has no Brian 2 installed.
All simulations require the conda environment:

```bash
/home/raghav/miniconda3/envs/myenv/bin/python
```

Verified versions in that environment:

| Package | Version |
|---|---|
| Python | 3.14.2 |
| brian2 | 2.10.1 |
| numpy | 2.4.2 |
| matplotlib | 3.10.8 |
| scipy | 1.16.3 |
| python-pptx | **not installed** |

For convenience:

```bash
export PY=/home/raghav/miniconda3/envs/myenv/bin/python
```

All commands below assume `$PY` and that you are in the repository root.

**Known `requirements.txt` discrepancies** (the file is not currently accurate):

- `scipy` is listed but **never imported** by any module in this repository.
- `python-pptx` is listed and *is* required by `generate_presentation.py`, but it is
  **not installed** in `myenv`, so that script currently fails with `ModuleNotFoundError`.
- The pinned floors (`brian2>=2.5.1`, `numpy>=1.22.0`) are satisfied but do not
  describe the versions actually in use.

To recreate the environment from scratch, prefer conda for Brian 2, then:

```bash
$PY -m pip install python-pptx     # only needed for generate_presentation.py
```

## Usage

Every command below was executed against the current tree; the stated runtimes and
outputs are measured, not estimated.

### Model A — Brian 2 spiking network

**1. Inspect architecture and plasticity equations** — instant, prints to stdout.

```bash
$PY experiments/print_network_summary.py
```

> The population sizes and three of the connection probabilities in this script's
> output are **hardcoded literals and are currently wrong** — see
> [Known gaps](#known-gaps-specified-but-not-yet-working). The Graupner-Brunel
> equation block at the end is genuine (imported from `equations.py`). For accurate
> values, read `src/v2/parameters.py` or the parameter table below.

**2. Verification suite** — ~904 s (15 min). Writes `figures/validation/test{1..4}.png`.

```bash
$PY experiments/validate_model.py
```

Current result: **5/6 PASSED**. `Test 3: Branch-Specific Gating` **FAILS**
(free/inhibited weight ratio ≈ 0.99 instead of > 1). This is a genuine unresolved
model issue, not a flaky test — see [Known gaps](#known-gaps-specified-but-not-yet-working).

**3. MD drive simulation** — ~185 s. Writes
`figures/demo_zhang2025_context_switch.png`.

```bash
$PY experiments/demo_v2_zhang2025.py
```

Runs 2 s at 5 Hz MD drive followed by 2 s at 40 Hz. Measured output:

```
PV  mean rate:  Context A = 0.0 Hz,   Context B =  2.1 Hz
SOM mean rate:  Context A = 36.5 Hz,  Context B =  0.3 Hz
Pyr mean rate:  Context A = 0.0 Hz,   Context B = 54.0 Hz
```

Read this as two separate results. The **SOM row is the disinhibition mechanism
working**: raising MD drive silences SOM (36.5 → 0.3 Hz), which is exactly what the
VIP → SOM pathway is meant to do. The **PV row is the known gap**: PV reaches only
2.1 Hz, so the pyramidal cell goes from silent to 54.0 Hz essentially unopposed.

Note also that this script labels the two drive levels "Context A" and "Context B";
they are **global drive levels**, not the two branch-selective contexts of the 3-epoch
protocol described in `project_documentation.tex` (see
[Known gaps](#known-gaps-specified-but-not-yet-working)).

**4. Phase diagram sweep** — ~171 s at the default grid. Writes
`figures/phase_diagram.png`.

```bash
$PY experiments/sweep_phase_diagram.py                      # default: --grid 3 --cores 4
$PY experiments/sweep_phase_diagram.py --grid 8 --cores 8   # finer, proportionally slower
```

Sweeps `gAMPA_pv` over `[0, 0.30] nS` and `gAMPA_vip` over `[0, 1.25] nS`
(both `0` to `2.5x` their default), at a fixed 40 Hz MD drive. Emits four heatmaps:
PV rate, SOM rate, Pyr rate, and mean weight change `ΔW`.

**5. Architecture diagram** — ~3 s. Writes `figures/network_synaptic_architecture.png`.

```bash
$PY experiments/generate_network_synapse_figure.py
```

**6. Brian 2 smoke test** — ~46 s. Writes `src/v2/figures/v2_migration_test.png`.

```bash
$PY src/v2/test_circuit.py
```

### Models B and C — NumPy figure models

**7. Phenomenological figures** — ~3 s. Writes `figures/phenomenological/fig{1..4}.png`.

```bash
$PY main_gating_figures.py
```

**8. Mechanistic figures** — ~4 s. Writes the four `figures/mechanistic/*.png`.

```bash
$PY emergent_gating_mechanistic_model.py
```

Prints the Gating Selectivity indices. Seeded with `default_rng(42)`, so output is
reproducible: `VIP=0.86  SOM=-0.66  PV=0.01`.

### Presentation deck

**9. Build the .pptx** — **currently fails**, `python-pptx` is not installed.

```bash
$PY generate_presentation.py       # must be run from the repository root
```

This script resolves figure paths relative to the **current working directory**, and
skips any missing image silently. Run from anywhere else and it produces a deck with
blank slides rather than an error.

## Model architecture (as implemented)

### Pyramidal neuron

Two-layer multi-compartment reduction: 1 somatic compartment plus `num_DendEach`
independent dendritic branches, joined by Ohmic axial coupling
(`gEachCouple_pyr = 4.0 nS` per branch).

**Every runnable script sets `num_dend_each = 2`.** The `parameters.py` default is
`num_DendEach = 10`, but each experiment overrides it. Back-propagating action
potentials are delivered to the branches by a `Synapses` object
(`V_post += bAP_amp`, `bAP_amp = 10 mV`, `bAP_delay = 3 ms`).

### Populations and wiring (Model A)

Values from `src/v2/parameters.py`, as used by `experiments/demo_v2_zhang2025.py`.

| Population | Size | Parameter |
|---|---|---|
| Pyramidal soma | 1 | `num_Soma` |
| Dendritic branches | 2 | `num_dend_each` (per-script override) |
| MD thalamus (`PoissonGroup`) | 50 | `n_md` |
| PV interneurons | 20 | `n_pv` |
| SOM interneurons | 20 | `n_som_spike` |
| VIP interneurons | 20 | `n_vip_spike` |
| Cortical pathway input (`PoissonGroup`) | 30 @ 80 Hz | literal in each script |

| Projection | Probability | Weight |
|---|---|---|
| MD → PV (AMPA) | `p_md2pv = 0.5` | `gAMPA_pv = 0.12 nS` |
| MD → VIP (AMPA) | `p_md2vip = 0.3` | `gAMPA_vip = 0.5 nS` |
| VIP → SOM (GABA) | `p_vip2som_spike = 0.6` | `gGABA_som = 3.0 nS` |
| SOM → Dendrite (GABA) | `p_som2dend_spike = 0.5` | `gGABA = 4.0 nS` |
| PV → Soma (GABA) | `p_pv2soma = 0.6` | `gGABA_pv2soma = 5.0 nS` |
| Pathway → Dendrite | all-to-all | plastic, `w = w0 + (w1-w0)·ρ` |

SOM cells have **no synaptic excitation**; their baseline rate comes from a constant
bias current `iBaseline_som`, set per script (22 pA in the demo and Test 4, 25 pA in
Test 3). Measured: **22 pA produces 39.5 Hz**, which is the ~40 Hz baseline the
documentation refers to. Note that some in-code comments state "~10 Hz" or "~30 Hz";
those comments are wrong.

There is **no SOM → PV synapse** anywhere in the codebase, despite `gGABA_pv`
("SOM→PV synapse weight") being defined in `parameters.py`. The `iGABA` term in
`eqs_pv` is therefore permanently zero.

### Plasticity (Model A)

Native Brian 2 Graupner-Brunel bistable synapses (`eqs_synapse_plasticity`):

| Parameter | Value |
|---|---|
| `theta_d` / `theta_p` | 1.0 / 2.78 |
| `gamma_d` / `gamma_p` | 39.949 / 177.552 |
| `tau` | 346.36 s |
| `sigma` | 3.35 |
| `w0` / `w1` | 0.0 / 3.0 |
| `C_pre` | 1.0 |
| `tau_Ca_NMDA` | 30 ms |

Synaptic calcium is `dc/dt = -c/tau_Ca_NMDA`, incremented by `C_pre` on each
presynaptic spike. **It has no postsynaptic or voltage-dependent term** — see
[Known gaps](#known-gaps-specified-but-not-yet-working).

### Plasticity and noise (Model C)

`emergent_gating_mechanistic_model.py` runs 300 trials of 500 ms
(`DT_SIM = 0.5 ms`), in three 100-trial epochs. MD spike counts per trial are drawn
as `Poisson(rate x T)`: the active channel at 25 Hz, the opposing channel at a
**2 Hz background floor** (not silent). Interneuron rates are then
`SOM = max(0, 40 - 1.5·r_VIP)` Hz and the branch conductance is
`0.875 nS/Hz x r_SOM`, giving 35 nS at the 40 Hz SOM baseline.

| Parameter | Value | Meaning |
|---|---|---|
| `CV_CA` | 0.30 | NMDA vesicle-release amplitude noise per spike |
| `CV_RATE` | 0.20 | Interneuron rate variability |
| `SIGMA_RHO` | 0.04 | Per-trial noise on the ρ update |
| `ETA_RHO` | 0.08 | Per-trial step toward the Graupner-Brunel attractor `ρ̄` |
| `G_PER_HZ` | 0.10 nS/Hz | Excitatory conductance per Hz of pathway drive |

`CV_RATE` is applied as `std = 0.20 x rate` — **linear** in the rate. This means the
Fano factor grows in proportion to rate rather than staying ≈ 1; the module docstring's
claim of square-root scaling does not match the code.

### Weight scale differs between models

`w1` is **3.0** in `src/v2/parameters.py` and `main_gating_figures.py`, but **1.0** in
`emergent_gating_mechanistic_model.py`. Both NumPy models print the same
`w = W0 + (W1-W0)·ρ` figure caption, so their weight axes are **not** directly
comparable.

## Known gaps: specified but not yet working

These are requirements from the project specification that the current implementation
does not meet. They are listed rather than removed, because they remain the intended
behaviour. Each was verified by execution.

### Blocking the central claim

- **Dendritic inhibition does not gate plasticity in Model A.** The synaptic calcium
  equation depends only on the presynaptic spike train — there is no `V_post`, no
  NMDA Mg²⁺ block and no coincidence term. `on_post_plasticity` (`c += C_post_eff`) is
  defined in `equations.py` and imported by `MultiCompartmentalModel.py` but is
  **never attached to any `Synapses` object**, and `C_post_eff` is not defined in
  `parameters.py`. Two branches receiving the same afferents therefore evolve
  identically regardless of inhibition. This is the direct cause of the
  `Test 3` failure (ratio 0.99).
- **Models B and C currently produce no plasticity at all.** In both, every
  Graupner-Brunel update falls through to the calcium-inactive branch (400/400 and
  800/800 updates measured); peak calcium reaches ≈ 0.80 against `THETA_D = 1.0`.
  `figures/phenomenological/fig4_branch_specific_learning.png` and
  `figures/mechanistic/fig_self_organized_branching.png` therefore show an unbiased
  random walk, not learning. `ETA_RHO`, `ρ̄`, `GAMMA_D/P`, the Mg²⁺ block and the
  `CV_CA` vesicle noise have no effect on the output.
- **The `dend_IO` transfer function is inverted at low excitation.** Because
  `spread = q1·exp(inh/q2)` reaches ~2000 nS at 35 nS of inhibition while the models
  only ever generate 0.7–3.8 nS of excitation, a strongly inhibited branch reports a
  *more* depolarised voltage (−42.4 mV) than a disinhibited one (−68.8 mV). Four
  separate copies of this function exist.

### Features described but not implemented

- **The 3-epoch VIP-1 / VIP-2 protocol exists only in Model C.** Model A's
  `demo_v2_zhang2025.py` switches *global* MD drive (5 → 40 Hz) and has no
  branch-selective VIP channels and no baseline epoch;
  `sweep_phase_diagram.py` runs a single fixed context at 40 Hz.
- **The phase diagram has no regime classification.** `sweep_phase_diagram.py` emits
  four raw heatmaps and marks a single point labelled `'Healthy Baseline'` at the
  default weights — but there is no *pathological* regime, no boundary between regimes,
  and no classification logic of any kind. The documented "healthy cognitive
  flexibility vs. Schizophrenic pathology" mapping is therefore one marker, not a
  phase diagram. Additionally, because `ρ` cannot depend on the swept MD→PV / MD→VIP
  weights (see above), the `ΔW` panel carries no information.
- **`print_network_summary.py` does not inspect a live network.** It constructs no
  `NeuronGroup`, `Synapses`, `Network` or `PoissonGroup`; the report body is a list of
  string literals. Seven of its ten stated facts are wrong: it prints 30 dendritic
  branches (actual 2), 10 PV / 10 SOM / 10 VIP cells (actual 20 each), 20 MD cells
  (actual 50), and `p = 0.50` for VIP→SOM and PV→Soma (actual 0.6 each). Only the
  imported equation block is genuine.
- **MD → PV somatic gain control is non-functional.** `gAMPA_pv = 0.12 nS` is too weak
  to bring PV to threshold across the operating range. Measured PV rates: 0.0 Hz at
  5 Hz and 25 Hz MD drive, 2.9 Hz at 40 Hz, then 184.7 Hz at 100 Hz. Both Test 4 and
  Test 5 report PV = 0.0 Hz; Test 4 shows pyramidal firing at 50.6 Hz and
  `demo_v2_zhang2025.py` shows 54.0 Hz, both with no inhibitory opposition.
- **`InterneuronalCircuit.py` is unused.** Nothing imports it, and it references
  `p['n_som']`, which does not exist in `parameters.py`. It is the only place the value
  `30` appears as a dendrite count — the likely origin of the previous "30 branches"
  claim in this README.

### Figure-level limitations

- **Figure 1 (STDP curve) has no LTP arm.** `NMDA_SCALING + BAP_SCALING = 1.328` is
  below `THETA_P = 2.78`, so a single pre-post pair cannot reach the potentiation
  threshold at any Δt. The plotted curve is LTD-only. The plasticity constants appear
  to mix two different Graupner-Brunel parameter fits (`TAU_RHO`/`SIGMA` from one,
  `C`/`theta`/`gamma` from another); this should be resolved against the source paper.
- **Figure 3's NMDA calcium is identically zero.** `driving = max(v_dend + 10, 0)` is
  always 0 because `v_dend` never exceeds −10 mV in that figure's range, so all
  calcium there comes from the bAP term and the Mg²⁺-block computation is inert. No
  curve crosses `THETA_P`, so the drawn "LTP zone" band is never entered.

### Test suite caveats

- `Test 5` is named "Random Seed Reproducibility" but runs three **different** seeds
  (0, 42, 84) and checks cross-seed CV < 0.50. Because `cv` is defined as 0 when the
  mean is 0, silent populations pass vacuously — it currently reports
  `PV: 0.0, 0.0, 0.0 -> PASS`.
- `Test 4`'s firing-rate check has no numerical criterion; a fully silent inhibitory
  circuit passes.
- `Test 6` asserts two dictionary keys in `params`. It is a regression guard against a
  past Brian 2 `dt` namespace warning, not a model validation.
- `Test 1` uses a 25% tolerance against the analytic LIF rate; PV (22.8%) and VIP
  (23.8%) pass only just.

## Reference

- **Yang et al. 2016** — "A dendritic disinhibitory circuit mechanism for
  pathway-specific gating", *Nature Neuroscience*.
- **Zhang 2025** — MD thalamocortical drive, E/I imbalance, and context learning.
