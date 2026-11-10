# Plan — making the model robust before more A/B context work (2026-11-04)

PI guidance (2026-11-04): the A/B context experiments are fine, but **first make the
model robust**. Gaps G1–G5 are defined in `docs/reports/MODEL_STATUS_2026-11-04.md`.
No new mechanisms are added here. The work consists of decisions, re-runs, sensitivity
checks and tests.

**Robust** means: the headline conclusions do not depend on
- the random seed,
- the integration step,
- one finely tuned parameter value,
- an unchecked mismatch with the papers.

Any regression must be caught automatically.

## R1. Choose the canonical synapse (blocks everything below; closes G1)

| option | learned weight scales | consequence |
|---|---|---|
| current | AMPA only (0.4 nS × w) | learning has no effect on which branch plateaus |
| Yang 2016 | NMDA (w × 2.5 nS), AMPA off | learning changes branch output, as in Yang Fig. 7 |

**Done when:** the PI agrees on one. `context_circuit` defaults are switched to it, or
it is passed everywhere, and the old synapse is kept as an option for comparison.

## R2. Numerical robustness (G5)

Already established for the current synapse: dt-converged, bit-identical rebuilds,
reproducible per seed across processes.

**To do for the chosen synapse:**
- dt check (0.1 vs 0.05 ms);
- headline gating with 20 seeds.

**Pass:** dt changes ρ by less than 0.01; at least 19/20 seeds gate (r1 > 0.65,
r0 < 0.5, ratio ≥ 2).

## R3. Parameter sensitivity (G3)

One parameter at a time, at ×0.5, ×0.75, ×1.25 and ×1.5, 5 seeds each. Parameters:
- gNMDA, gLDend_pyr, gGABA, tauGABA, coupling;
- SOM bias (rate), MD rate, gAMPA_vip, p_vip2som;
- weight_bg_pv + gGABA_pv (moved together, because they form a ridge);
- soma background.

Metrics:
1. Branch gating after learning (r1, r0, ratio).
2. Gating selectivity S from soma firing at the default wiring (Fig. 5 protocol).
3. Retention, idle-inputs-silent vs inputs-always-on (forgetting 2×2).

**Pass:** at ±25% every metric keeps its qualitative conclusion: gated, S > 0.5, and
silent inputs retain while active inputs erase. Parameters that fail at ±25% are listed
as **knife-edge** and reported to the PI. Each one gets either a justification from the
papers or a documented caveat.

Rough cost: ~12 parameters × 4 levels × 5 seeds ≈ 240 runs per metric, about 25–40 min
each locally.

## R4. Quantitative agreement with the papers (G3)

Put our numbers next to the published ones, with a stated tolerance:
- V1 dendritic I/O half-activation vs Yang's g½ = 5.56(4 + g_inh);
- V2 LTP threshold;
- V3 branch ratio;
- V4 MD→interneuron rates vs Zhang;
- Fig. 2 plateau threshold and S;
- Supp. Fig. 1 gating of NMDA vs AMPA.

**Decision for the PI:** refit the dendrite to Yang's shunting, or keep it and document
the ~1.5× gGABA difference. Every remaining mismatch gets a one-line explanation.

## R5. Regression tests (G5)

Freeze the R2–R4 numbers as automated tests with tolerances, in
`tests/test_replication.py` with a fast default and a `--slow` mode. Retire or fix
`experiments/validate_model.py` and the stale assertion in
`tests/test_postsynaptic_calcium.py`.

**Pass:** one command reports all replications PASS or FAIL.

## Then: A/B context experiments on the robust model

Re-run, using the existing scripts:
- forgetting 2×2;
- overlap;
- alternation;
- MD→PV retention;
- recall test (learning frozen, branch response measured);

with the chosen synapse and 10+ seeds.

## Order and estimate

R1 (decision) → R2 (~30 min) → R3 (~2–3 h compute) → R4 (~1 h) → R5 (~1 h). Then the
A/B re-runs (~2 h). Everything runs locally.

---

## Results (2026-11-05 to 2026-11-10)

### R1 — done
`context_circuit(synapse='yang')` is the default: the weight scales NMDA, AMPA input is
off, and ρ starts at 1/3. `synapse='ampa'` is the old synapse; the 11 scripts behind
earlier results pin it, and it is verified bit-identical to the previous commit.

### R2 — pass (`experiments/robustness_r2.py`)

| check | criterion | result |
|---|---|---|
| gating, seeds 42–61 | ≥ 19/20 | **20/20**: ρ_free 0.928 (0.927–0.928), ρ_inh 0.298 (0.288–0.309), ratio ≈ 3.1 |
| dt 0.1 vs 0.05 ms | Δρ < 0.01 | pass, max 0.0089 |
| balanced-soma preset | 5–15 Hz, CV ≥ 0.7 | pass: 9.3–12.8 Hz, CV 0.92–1.44 |

### R3 — mostly pass, two caveats (`experiments/robustness_r3.py`, `figures/robustness_r3.png`)
12 parameters × {0.5, 0.75, 1.25, 1.5} × 5 seeds (245 runs).

- **Gating ratio, gating selectivity S and retention with silent inputs hold at ±25% for
  11 of 12 parameters.** Most also hold at ±50%.
  - Failures at ×0.5 only: gNMDA (no LTP at all), MD→VIP weight (MD cannot silence SOM),
    dendritic leak (ρ_free 0.61).
  - Retention with silent inputs is 0.999–1.000 everywhere.
  - S stays 0.80–0.98, except where gating itself fails.
- **Knife-edge: the SOM bias current.**
  - The default 21.32 pA sits just above SOM rheobase. ×0.75 silences SOM (no gating);
    ×1.25 raises it from 30 to 76 Hz.
  - Expressed as a rate, gating holds from about 15 Hz (audit) to 112 Hz. The fragility
    is in how SOM's baseline rate is set (a noiseless bias near threshold), not in the
    gating mechanism.
  - To fix or document.
- **Not robust: "inhibition erases a memory whose inputs stay active".** With the Yang
  synapse, retention with active inputs ranges 0.40–1.00 across parameters (baseline 0.68).
  - It reaches ≈ 1.0 with more NMDA, more input, or less or shorter inhibition.
  - The audit's 32–38% erasure was a property of the old synapse. It must not be claimed
    for the canonical model.

### R4 — learning creates gating, given the right readout drive
- **First test failed** (`experiments/robustness_r4_learning.py`). The weights aligned as in
  Yang (A → own branch 0.925, other 0.31), but with a 50 Hz readout, S after learning was
  −0.05 ± 0.12.
- **Diagnosis 1 rejected the shunting hypothesis** (`robustness_r4_shunting.py`).
  - Scaling gGABA ×1.5 or ×2 gives S_after only 0.08 or 0.10.
  - Branch voltages show why: with the wrong gate open, the learned branch is held down
    (plateau 7%), but the open, weakly connected branch plateaus 98% of the time.
- **Diagnosis 2 confirmed a readout-drive window** (`robustness_r4_readout.py`,
  `figures/robustness_r4_readout.png`). Same learned weights, readout rate swept; Yang
  synapse, 7 seeds:

| readout rate | S before learning | S after learning | pattern A: own gate / other gate (after) |
|---|---|---|---|
| 5 Hz | (cell silent) | **0.86 ± 0.10** | 5.1 / 0.4 Hz |
| 10 Hz | (cell silent) | **0.89 ± 0.09** | 9.3 / 0.5 Hz |
| 15 Hz | −0.14 | **0.75 ± 0.14** | 10.6 / 1.3 Hz |
| 20 Hz | −0.09 | 0.27 | 11.0 / 5.6 Hz |
| 30 Hz | −0.06 | 0.10 | |
| 50 Hz | −0.05 | −0.06 | |

  At equal total drive (before learning at about 2.8× the rate, since w rises from 1 to
  about 2.8 on the learned branch), S goes from ≈ −0.1 to 0. That is **Yang Fig. 7d,e:**
  no gate preference before learning, strong pathway-specific gating after. Above about
  20 Hz, an open gate makes even a weak branch plateau, so learning cannot show.
- **Contrast: the old AMPA-only synapse** (`robustness_r4_readout.py ampa`, 10 seeds).
  S after learning is −0.27 / +0.33 / 0.00 / −0.07 at 5 / 10 / 15 / 20 Hz, with output
  rates of 0.3–1.5 Hz at the low rates, so nothing is learned functionally. This confirms
  the choice of synapse.
- **Gap G1 is closed for the canonical synapse, within a readout regime.** Readout
  drive must be ≤ 15 Hz per synapse (20 synapses). This should be stated with every
  functional claim.

### Still to do
- **R4 paper table:** V1–V4 and Fig. 2 numbers against the papers on the new synapse.
- **SOM baseline knife-edge:** fix or document.
- **R5:** regression tests freezing R2–R4.
- **Then the A/B re-runs** (on toothless), using a recall readout at 5–15 Hz.
