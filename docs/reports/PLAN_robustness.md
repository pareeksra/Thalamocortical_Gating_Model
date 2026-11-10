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

### SOM knife-edge — fixed (`experiments/som_baseline_fix.py`, `figures/som_baseline_fix.png`)
- **Fix (calibration only):** a sub-rheobase bias (6 pA) plus independent Poisson
  excitation on every SOM cell (60 Hz × 2 nS). SOM stays at ≈ 30 Hz, now fluctuation-driven
  and irregular. `SOM_NOISY_KW`, canonical since 2026-11-10.
- **Test:** 5 seeds per point, 10 at baseline. Metrics: gating, S, retention with silent
  inputs, S after learning (10 Hz readout), SOM rate.

| SOM drive parameter | ×0.5 | ×0.75 | ×1.25 | ×1.5 |
|---|---|---|---|---|
| bias, old bias-only (21.32 pA) | SOM 0 Hz, fail | **SOM 0 Hz, fail** | 76 Hz, pass | 112 Hz, pass |
| bias, noisy | 23.5 Hz, pass | 27.0, pass | 34.9, pass | 40.0, pass |
| Poisson rate, noisy | 9.6 Hz, fail | 19.4, pass | 42.8, pass | 55.2, pass |
| Poisson weight, noisy | 4.5 Hz, fail | 17.1, pass | 42.3, pass | 53.1, pass |

  Baseline noisy: 10/10 gated, S 0.92, S after learning 0.90. **No knife-edge at ±25%.**
- **Side finding:** retention with active inputs is bimodal in SOM rate. It is ≈ 1.0 for
  SOM ≤ 27 Hz and ≈ 0.4 for SOM ≥ 35 Hz, which explains R3's 0.40–1.00 spread.

### bAP calcium and epoch length — found and fixed
Found while freezing Yang Fig. 7b as a test (`tests/test_replication.py` S3).

- **Problem 1, bAP calcium was 5× Yang's in-vivo value.**
  - The bAP calcium transient peaked exactly at θ_d. Yang's Methods scale it by 0.2 in
    vivo so that "the weights of non-activated synapses do not change substantially".
  - At ×1.0, bAPs alone (10 Hz) depress an idle synapse: Δw −0.70 over Yang's 300-s
    protocol at 0–2 Hz input. Yang shows no change.
- **Problem 2, the epoch update hid this.** Yang's Eqs. 32–35 give switching probabilities
  for one continuous protocol. We apply them every T = 3 s, which lets each synapse
  re-consolidate between epochs. Strong drive is unaffected: 300 s of LTP in one update vs
  3-s epochs gives 0.914 vs 0.925. Slow drift is erased (`experiments/epoch_length_check.py bap1`):
  - silent-input retention over 24 s: 1.00 at T = 1.5 s → 0.80 at T = 24 s;
  - after a 300-s idle phase: 0.998 / 0.18 / 0.12 in 3 / 30 / 300-s epochs.
  - So "silent inputs retain" was an artefact of T.
- **Fix: bAP calcium ×0.2** (Yang's value; `bap_ca_scale`, canonical with the Yang synapse).
  Canonical model (`epoch_length_check.py`):
  - silent-input retention 1.000 for every T from 1.5 to 24 s;
  - 300-s idle phase 1.000 in 3 / 30 / 300-s epochs;
  - gating holds for every T (ρ_free 0.92–0.94; ρ_inh 0.33, or 0.27–0.32 at T = 24 s).
- **Unchanged:** retention with *active* inputs stays parameter- and T-dependent
  (0.33–0.96). It is not a robust claim.

### Canonical model (2026-11-10)
The default of `run_context_protocol`:
- Yang NMDA-plastic synapse;
- noisy SOM baseline;
- bAP calcium ×0.2.

Earlier results are reproduced bit-identically through pins:
- `synapse='ampa'` for the 11 pre-2026-11-04 scripts;
- `som_baseline='bias', bap_ca_scale=1.0` for R2–R4 and `som_baseline_fix.py`.

R2/R3 take the argument `canonical`.

| check | canonical result |
|---|---|
| R2 gating, 20 seeds | **20/20**, ρ_free 0.928 (0.927–0.928), ρ_inh 0.333 (0.331–0.333), ratio 2.8 |
| R2 dt 0.1 vs 0.05 ms | max Δρ 0.00014 |
| R2 balanced soma | 9.3–11.8 Hz, CV 0.96–1.38 |
| Yang Fig. 7b, 300 s | free: no change ≤ 5 Hz, LTD 10 Hz, LTP ≥ 15 Hz; SOM 13 Hz: LTP only from 150 Hz; SOM 31/60 Hz: no LTP to 150 Hz. All three of Yang's regimes and the threshold shift (`docs/reports/PAPER_COMPARISON.md`) |
| V1 dendrite g½ vs Yang | within 12% for g_inh 0–10 nS (slope 4.5 vs 5.56) |
| R3 sensitivity (canonical, +SOM drive params, +learning) | **No knife-edge at ±25%** across 14 parameters (gating 5/5, S 0.81–0.97, silent retention 1.000, S_learn 0.51–0.94 at 10 Hz readout; baseline S 0.93, S_learn 0.88). The weakest points at ±25%: gLDend ×0.75 (S_learn 0.51) and gNMDA ×1.5 (S_learn 0.52). Failures only at ×0.5 of gNMDA, gLDend, md_rate, gAMPA_vip, som_bg_E_hz and som_bg_nS. ret_always 0.42–1.00, not robust (`robustness_r3_canonical*.json`, `figures/robustness_r3_canonical.png`) |

### R5 — regression tests (`tests/test_replication.py`)
One command, one PASS/FAIL line per check, exit code 0 only if all pass.

| tier | checks | time | canonical result |
|---|---|---|---|
| fast | F1–F6: SOM rate and ±25% drive window, V1 g½, gating, silent retention, Fig. 5 S, audit and plasticity unit tests | ~1 min, 8 cores | **11/11 PASS** (canonical, 2026-11-10) |
| `--slow` | adds S1–S5: learning creates gating, dt, Fig. 7b regimes, MD control, 300-s idle phase as one epoch | ~8 min, 10 cores | **19/19 PASS** in 466 s on 10 cores (S1 S_learn 0.92, 0.93, 0.81; S3 60 Hz free +1.74, inhibited −0.68; S5 1.000); log `results/current/test_replication_canonical.log` |

`experiments/validate_model.py` (stale, last 4/6) has been retired to `archive/`. The
stale assertion in `tests/test_postsynaptic_calcium.py` had already been fixed (16/16).
All seven test files pass.

### A/B re-runs on the canonical model (2026-11-10)
10 seeds (42–51) each; recall = S at a 10 Hz readout with plasticity frozen
(`experiments/readout.py`). The scripts take the argument `canonical`; outputs are
`results/current/*_canonical*` and `figures/*_canonical.png`.

**Retention 2×2** (`retention_md_context.py canonical`): context A learned, then 24 s of context B.

| A's branch during B | A's inputs silent | A's inputs active |
|---|---|---|
| disinhibited | 1.000 (`neither`) | 1.000 (`inputonly`) |
| inhibited | 1.000 (`both`) | **0.69 ± 0.26** (`inhibonly`): bimodal, 6/10 seeds erased to ≈ 0.42, 4/10 keep ≥ 0.97 |

- Silent inputs retain perfectly. That is now a genuine result, not an epoch artefact (see above).
- Erasure by inhibition with active inputs is partial and seed-dependent. With the old AMPA
  synapse it was 0.35 in 5/5 seeds. It is not a robust claim.

**Overlap** (`overlap_experiment.py canonical`): learn A, then learn B, which shares a fraction f of A's synapses.

| f | MD gating: S_A after A | S_A after B (old memory) | S_B (new memory) | ρ retention of A (shared) | no gating: all S |
|---|---|---|---|---|---|
| 0 | 0.94 | **0.92** | 0.91 | 1.000 (—) | ≈ 0 (−0.10 to 0.06) |
| 0.25 | 0.91 | 0.38 | 0.89 | 0.86 (0.42) | ≈ 0 |
| 0.5 | 0.89 | −0.01 | 0.88 | 0.71 (0.42) | ≈ 0 |
| 0.75 | 0.89 | −0.15 | 0.57 | 0.70 (0.60) | ≈ 0 |
| 1.0 | 0.92 | −0.27 | 0.30 | 0.75 (0.75) | ≈ 0 |

- MD gating is necessary for any recall. Without it, S ≈ 0 at every f.
- It protects the old memory only for disjoint patterns. From f = 0.5 the shared synapses
  move to B's branch, and recall of A is lost or reversed. Unique synapses keep ρ = 1.000,
  but that is not enough to read A out.

**Alternation** (`alternation_experiment.py canonical`): 32 × 3-s epochs, alternating A/B in
blocks of L epochs; recall at the end of the run.

| f | L = 1: current / previous | L = 4: current / previous |
|---|---|---|
| 0 | 0.93 / 0.94 | 0.93 / 0.94 |
| 0.25 | 0.51 / 0.38 | **0.90 / 0.93** |
| 0.5 | 0.21 / 0.06 | 0.80 / 0.52 ± 0.46 |
| 0.75 | 0.05 / −0.04 | 0.40 / −0.14 |
| 1.0 | 0.03 / −0.07 | 0.08 / −0.17 |
| no gating (L = 4) | — | ≈ 0 at f = 0, 0.5, 1 |

- Both contexts are recalled for f ≤ 0.25 with blocks of 4 epochs (12 s).
- One-epoch blocks are worse: the shared synapses never settle on either branch.
- At high overlap the older pattern prefers the wrong branch. This confirms the per-pattern
  analysis in `PLAN_alternation.md` with a functional readout.

**MD→PV arm** (`retention_pv_arm.py canonical`): MD→PV gain ×0–×3 in 'always' mode.
- PV rises 7 → 220 Hz and suppresses the soma (pinned bAP: 12.7 → 0 Hz on B's context).
- Retention of A barely moves: 0.81 → 0.76 with pinned bAPs, 0.87 → 0.77 with somatic bAPs.
  The same seeds erase at every gain.
- In context mode it is 1.000.
- So the PV arm controls output gain, not what is stored. With the old synapse PV slightly
  *reduced* erasure (0.39 → 0.46); both effects are small.

### Still to do
- Branch-specific VIP→SOM (G2), and Zhang's SOM→VIP and PV→PV, are untested assumptions.
- Inhibited-branch weakening is slow at the 8 × 3-s learning length.
