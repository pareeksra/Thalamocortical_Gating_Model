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
| R2 gating, 20 seeds | **20/20**, ρ_free 0.928 (0.927–0.928), ρ_inh 0.333 (0.331–0.333), ratio 2.8. Re-run at VIP→SOM ×0.25 (2026-11-11): **20/20**, identical ρ; dt and balanced-soma checks pass (soma 8.8–11.5 Hz, CV 0.96–1.38) |
| Yang Fig. 7b at ×0.25 (2026-11-11) | the same three regimes and threshold shift. The free branch's own SOM is 0.9 Hz instead of 0.0, so LTP near threshold is smaller (+0.17 at 15 Hz, +1.05 at 20 Hz; ×1: +0.66, +1.52); the inhibited curves are unchanged |
| R2 dt 0.1 vs 0.05 ms | max Δρ 0.00014 |
| R2 balanced soma | 9.3–11.8 Hz, CV 0.96–1.38 |
| Yang Fig. 7b, 300 s | free: no change ≤ 5 Hz, LTD 10 Hz, LTP ≥ 15 Hz; SOM 13 Hz: LTP only from 150 Hz; SOM 31/60 Hz: no LTP to 150 Hz. All three of Yang's regimes and the threshold shift (`docs/reports/PAPER_COMPARISON.md`) |
| V1 dendrite g½ vs Yang | within 12% for g_inh 0–10 nS (slope 4.5 vs 5.56) |
| R3 sensitivity (canonical, +SOM drive params, +learning) | **No knife-edge at ±25%** across 14 parameters (gating 5/5, S 0.81–0.97, silent retention 1.000, S_learn 0.51–0.94 at 10 Hz readout; baseline S 0.93, S_learn 0.88). The weakest points at ±25%: gLDend ×0.75 (S_learn 0.51) and gNMDA ×1.5 (S_learn 0.52). Failures only at ×0.5 of gNMDA, gLDend, md_rate, gAMPA_vip, som_bg_E_hz and som_bg_nS. ret_always 0.42–1.00, not robust (VIP→SOM ×1: `robustness_r3_canonical_vip1*`) |
| R3 re-run at VIP→SOM ×0.25 (2026-11-11) | **No knife-edge at ±25%** (gating 5/5 everywhere, S 0.84–0.99, silent retention 1.000, S_learn 0.64–0.95; baseline S 0.93, S_learn 0.89). The weakest points improve: gLDend ×0.75 and gNMDA ×1.5 both go from 0.51/0.52 to 0.64. md_rate ×0.75 (≈19 Hz) passes: S_learn 0.88. Failures still only at ×0.5 of the same six parameters: gNMDA, gLDend (2/5), md_rate, gAMPA_vip, som_bg_E_hz (1/5), som_bg_nS. ret_always 0.42–1.00 (`robustness_r3_canonical*.json`, `figures/robustness_r3_canonical.png`) |

### R5 — regression tests (`tests/test_replication.py`)
One command, one PASS/FAIL line per check, exit code 0 only if all pass.

| tier | checks | time | canonical result |
|---|---|---|---|
| fast | F1–F6: SOM rate and ±25% drive window, V1 g½, gating, silent retention, Fig. 5 S, audit and plasticity unit tests | ~1 min, 8 cores | **11/11 PASS** (canonical, 2026-11-10) |
| `--slow` | adds S1–S5: learning creates gating, dt, Fig. 7b regimes, MD control, 300-s idle phase as one epoch | ~8 min, 10 cores | **19/19 PASS** at VIP→SOM ×0.25 with S4 at MD 0/25/40 Hz, 456 s on 11 cores, 2026-11-11 (S1 S_learn 0.91, 0.95, 0.82; S3 60 Hz free +1.74, inhibited −0.68; S4 VIP 35.8 Hz, SOM own/other 0.4/31.3 Hz, PV 2/51/97 Hz; S5 1.000); log `results/current/test_replication_canonical.log`. Earlier runs: ×1, 19/19 in 466 s (S1 0.92, 0.93, 0.81); ×0.25 with S4 still pinned to ×1 at MD 20 Hz, 19/19 in 483 s (`test_replication_canonical_s4md20.log`) |

`experiments/validate_model.py` (stale, last 4/6) has been retired to `archive/`. The
stale assertion in `tests/test_postsynaptic_calcium.py` had already been fixed (16/16).
All seven test files pass.

### A/B re-runs on the canonical model (2026-11-10; re-run at VIP→SOM ×0.25 on 2026-11-11)
The tables show the ×0.25 numbers. The ×1 outputs are kept as `*_canonical_vip1*`; where a
value changed by more than 0.05 the ×1 value is given in brackets.
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
| 0 | 0.95 | **0.93** | 0.92 | 1.000 (—) | ≈ 0 (−0.11 to 0.04) |
| 0.25 | 0.93 | 0.49 (0.38) | 0.92 | 0.86 (0.42) | ≈ 0 |
| 0.5 | 0.90 | 0.03 | 0.90 | 0.71 (0.42) | ≈ 0 |
| 0.75 | 0.91 | −0.18 | 0.60 | 0.70 (0.60) | ≈ 0 |
| 1.0 | 0.94 | −0.28 | 0.36 (0.30) | 0.75 (0.75) | ≈ 0 |

- MD gating is necessary for any recall. Without it, S ≈ 0 at every f.
- It protects the old memory only for disjoint patterns. From f = 0.5 the shared synapses
  move to B's branch, and recall of A is lost or reversed. Unique synapses keep ρ = 1.000,
  but that is not enough to read A out.

**Alternation** (`alternation_experiment.py canonical`): 32 × 3-s epochs, alternating A/B in
blocks of L epochs; recall at the end of the run.

| f | L = 1: current / previous | L = 4: current / previous |
|---|---|---|
| 0 | 0.94 / 0.95 | 0.94 / 0.95 |
| 0.25 | 0.63 / 0.50 (×1: 0.51 / 0.38) | **0.91 / 0.90** |
| 0.5 | 0.28 / 0.12 | 0.82 / 0.11 ± 0.25 (×1: 0.52 ± 0.46) |
| 0.75 | 0.06 / −0.01 | 0.46 / −0.14 |
| 1.0 | 0.02 / −0.05 | 0.10 / −0.16 |
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

**Effect of VIP→SOM ×0.25 on the A/B results.**
- **Retention 2×2 and the MD→PV arm:** identical within 0.002 at every seed. Retention
  depends on the inhibited branch, where the VIP channel is silent, so the VIP→SOM weight
  does not enter.
- **Overlap:** recall is slightly better, by 0.01–0.11.
- **Alternation:**
  - L = 1 at f = 0.25 improves (0.63 / 0.50 vs 0.51 / 0.38).
  - L = 4 at f = 0.5, previous context: 0.11 ± 0.25, against 0.52 ± 0.46 at ×1. It is
    high-variance in both runs and was not a claim.
- **Conclusions unchanged:**
  - silent inputs retain;
  - erasure under inhibition with active inputs is partial and seed-dependent;
  - MD gating protects only disjoint patterns, or ≤ 25% overlap with 12-s blocks;
  - the PV arm sets output gain, not storage.

### Step 1 — branch specificity of the MD→VIP→SOM→dendrite channels (G2, 2026-11-10)
`experiments/specificity_test.py`, `results/current/specificity_test{,_summary}.json`,
`figures/specificity_test.png`.
- Method: each stage is mixed from specific to uniform with total drive held constant.
  5 seeds per level. Pass = gating 5/5, S > 0.5 and S_learn > 0.5 (as in R3).
- New model option `som2dend_cross`.
- Prediction, written beforehand: about 25% cross-talk tolerated at each stage.

| stage mixed | tolerated | fails at | how it fails |
|---|---|---|---|
| SOM → dendrite | ≤ 20% of SOM synapses on the wrong branch (S_learn 0.87) | 30% (4/5 gated, S_learn 0.57) | the open branch gets the other SOM's inhibition, ρ_free falls |
| VIP → SOM | < 11% of a SOM cell's VIP input from the wrong channel | 11% (3/5, S_learn 0.66); uniform S ≈ 0 | the *other* context's SOM falls 31 → 10 Hz, both branches open |
| MD → VIP | none | MD_k reaching 25% of the other channel's VIP (1/5, S_learn 0.23) | same as VIP → SOM |

**Follow-up: VIP→SOM is calibrated far stronger than needed.**
- Own-channel SOM sits at 0 Hz with a large margin, so a little cross-talk also silences
  the other channel.
- Prediction (written after the first run): a weaker VIP→SOM keeps gating and widens the
  tolerance.

| VIP→SOM weight (× 3 nS) | cross 0 | cross 0.075 (11%) | cross 0.15 (20%) | MD→VIP spill 25% |
|---|---|---|---|---|
| ×1 (canonical) | pass, S_learn 0.92 | 3/5, 0.66 | 0/5, 0.05 | 1/5, 0.23 |
| ×0.5 | pass, 0.93 | 3/5, 0.81 | 1/5, 0.16 | 3/5, 0.48 |
| ×0.25 | pass, 0.93 | **pass, 0.90** | 2/5, 0.66 | 4/5, 0.81 |
| ×0.1 | pass, 0.93 (own SOM 3.5 Hz) | **pass, 0.92** | **pass, 0.87** | 3/5, 0.58 |

- **Conclusion:** the fragility to VIP→SOM cross-talk is mostly calibration.
  - At ×0.1, 20% wrong-channel input is tolerated.
  - The fully specific model still gates there, S_learn 0.93.
  - MD→VIP spill-over stays the weak point: it is never fully tolerated, best 4/5 at ×0.25.
- **Claim we can make:** gating needs the MD→VIP projection to respect the channel. The
  VIP→SOM and SOM→dendrite stages may be partly mixed.
- **Decision (2026-11-10):** the canonical VIP→SOM weight is now **×0.25**
  (`VIP2SOM_SCALE_CANON` in `model/context_circuit.py`, applied with the noisy SOM baseline;
  `vip2som_scale=1.0` reproduces the ×1 results, which are kept as `*_canonical_vip1*`).
  - At ×0.25 and MD 25 Hz the own SOM channel is silenced to 0.3 Hz, but at MD 20 Hz only to
    3.2 Hz.
  - So R5's S4 MD check now uses MD 0/25/40 Hz instead of 0/20/40.
  - R3 and the A/B experiments were re-run at ×0.25.

### Step 2 — Zhang 2025's SOM→VIP and PV→PV added (2026-11-10)
`experiments/zhang_wiring_test.py`, `results/current/zhang_wiring_test{,_summary}.json`,
`figures/zhang_wiring_test.png`.
- New model options `som2vip_nS`, `som2vip_wiring` and `pv2pv_nS`, all off by default.
  The canonical model is unchanged: R5 fast tier 11/11 with identical numbers.
- Zhang gives signs only, so weight and wiring are swept. p = 0.5; 5 seeds.
- Scale: mean SOM→VIP conductance ≈ 12 nS × w, against MD→VIP ≈ 0.4 nS at 25 Hz.

| SOM→VIP wiring | MD 25 Hz: works up to | fails at | MD 50 Hz |
|---|---|---|---|
| uniform (all SOM → all VIP) | 0.1 nS (VIP 5 Hz, own SOM 8 Hz, S_learn 0.91) | 0.2 nS: VIP 0 Hz, SOM 29 Hz, 0/5 gated | works to 0.2 nS (S_learn 0.94), fails at 0.5 (2/5) |
| cross (SOM_k → VIP_j) | 0.1 nS | 0.2 nS (2/5, S_learn 0.77) | — |
| own (SOM_k → VIP_k) | **≥ 0.5 nS** (all pass) | — | — |

- **Mechanism.** SOM→VIP makes a "SOM on / VIP off" state that MD must overcome.
  - With uniform or cross wiring, the active VIP channel is braked by the *other* context's SOM (30 Hz).
  - With own-channel wiring the switch is self-reinforcing: once VIP_k wins, SOM_k is silent.
- **PV→PV** at 0.05–1 nS lowers PV from 51 to 10 Hz. Gating, S (0.96), S_learn (0.91) and
  retention do not change.
- **Prediction vs result.**
  - Failure point predicted at 0.03–0.1 nS; measured at 0.1–0.2 nS.
  - 'own' less sensitive: yes, far less.
  - MD 50 Hz shifts the failure point about ×2: yes.
  - PV→PV inert for gating: yes.
- **Claim we can make:** Zhang's SOM→VIP is compatible with MD-gated learning when it is
  weak (≲ 0.1 nS, about a quarter of the MD drive), within-channel, or opposed by stronger MD.
  Strong cross-channel SOM→VIP abolishes MD disinhibition.

### Step 3a — recurrent network with Zhang's E→all recurrence (2026-11-11)
`model/network_circuit.py`, `experiments/network_test.py`,
`results/current/network_test{,_summary}.json`, `figures/network_test.png`.
- **Network:**
  - 20 canonical cells (soma plus 2 branches, VIP→SOM ×0.25) sharing the canonical
    interneurons;
  - MD is still a Poisson context signal.
- **Recurrence added:** E→E, E→SOM, E→VIP and E→PV.
  - AMPA, p = 0.2, delay 1 ms.
  - Not specific to a channel, because Zhang gives no branch structure.
  - Reference weights (gain 1): E→E 2.0, E→SOM 0.75, E→VIP 1.2, E→PV 0.9 nS. These are
    our own guesses, so a gain of 1 has no biological meaning.
- **Protocol:**
  - learn A for 8 × 3 s at 50 Hz, then B for 8 × 3 s;
  - read out with plasticity frozen at 10 Hz;
  - 5 seeds.
  - Pass: ≥ 90% of cells gated and S_learn > 0.5.
- **At gain 0 it matches the single cell:** ρ_free 0.926, ρ_inh 0.333, E 10 Hz,
  S_learn 0.93, S before learning 0.01.

| recurrence | passes up to | breaks at | how it breaks |
|---|---|---|---|
| all four pathways | gain 0.6 (E 13 Hz, S_learn 0.84) | 0.7: 80% gated, E 36 Hz; 1.0: 20%, E 111 Hz | the other VIP channel ignites (0.6 → 31 Hz), the other SOM channel falls, both branches open |
| E→E only | 0.6 (E 50 Hz, 93% gated) | 0.7: 77% gated, E 105 Hz; 1.0: E 284 Hz | runaway firing; bAP calcium potentiates the inhibited branch although its SOM stays at 31 Hz |
| E→VIP only | 0.7 (S_learn 0.84 ± 0.18) | 0.8: 40% gated; 0.9: none gated | the other VIP channel ignites (0.2 → 8 → 52 Hz), the other SOM channel falls to 4–8 Hz |
| E→SOM only | ≥ 1.0 | — | raises only the other channel's SOM (31 → 44 Hz); learning unchanged |
| E→PV only | ≥ 1.0 | — | lowers E to 7 Hz; harmless |

- **The failure is a cliff, not a slope.** As long as the network stays in its low-rate
  state, gating and learning are as in the single cell. They are lost when activity runs
  away, through one of two routes:
  - E→VIP: recurrence ignites the other context's VIP and disinhibits the wrong branch;
  - E→E: high firing makes the bAPs strong enough to potentiate the inhibited branch.
- **Prediction vs result.**
  - The failing pathways (E→VIP and E→E) and E→PV being harmless: correct.
  - The threshold: predicted at gain ≈ 0.1–0.2, measured at ≈ 0.6–0.7.
  - E→SOM slowing LTP: wrong, it does not.
- **Claim we can make:** MD-gated, branch-specific learning survives recurrent excitation
  that is not specific to a channel, provided the network stays stable at low rates. The
  limit is network stability, mainly whether E→VIP can ignite the inactive channel's VIP;
  the single-cell mechanism is not the limit.
- Step 3b (below) adds the PFC↔MD loop.

### Step 3b — MD from a PFC↔MD loop (2026-11-11)
`model/md_loop.py`, `network_circuit.py` option `md_loop=`, `experiments/network_loop_test.py`,
`results/current/network_loop_test{,_summary}.json`, `figures/network_loop_test.png`.
- **The loop:**
  - Context-coding PFC populations C_A and C_B; each excites its own MD channel and receives
    excitation back from it.
  - Shared inhibition, w_inh, makes the two contexts compete.
  - A context cue drives C_k.
  - Optional nonspecific feedback from the 20 plastic E cells' rate to **both** MD channels
    (w_em).
  - Optional loop cross-talk: a fraction x of the loop drive reaches the other channel.
- **Rate units, as in Zhang's RNN.**
  - A spiking LIF version had no regime between silence and 100–400 Hz latching, so it
    was dropped.
  - MD spikes are Poisson at the loop's rate and feed VIP/PV through the canonical synapses.
  - The parameters are ours, set so that ON MD ≈ 25 Hz and OFF ≈ 0 Hz.
- **Regimes:**
  - `amp`: loop gain 0.4, cue held for the whole epoch.
  - `persist`: gain 2 with saturation; a 0.5-s cue per epoch, after which the loop sustains MD.
  - `persist_weakcomp`: gain 3, too strong for the competition.
- **Protocol:** recurrence gain 0.35 (step 3a's safe range), step 3a protocol, 5 seeds.

| condition | MD own / other, context A | MD own / other, context B | gated | S_learn | result |
|---|---|---|---|---|---|
| Poisson MD (reference) | 25 / 0 | 25 / 0 | 100% | 0.94 | pass |
| `amp` | 25 / 0 | 25 / 0 | 100% | 0.93 | pass |
| `persist` | 25 / 0 | 25 / 0.1 | 100% | 0.92 | pass |
| `persist_weakcomp` | 25 / 0 | **25 / 25** | 100% after A | **−0.03** | fail: A's loop stays on during B, so B potentiates on both branches (ρ_B 0.925 / 0.925); A's memory kept (ret 1.000) |
| `amp` + E→MD, w_em 0.25 / 0.5 / 1 | 28–34 / 2.3–6.1 | same | 100% | 0.92 / 0.91 / 0.90 | pass at every weight |
| `persist` + E→MD, w_em 0.25 | 25 / 2.6 | 25 / 2.8 | 100% | 0.92 | pass |
| `persist` + E→MD, w_em 0.5 | 25 / 4.8 | 25 / **12.9** | 100% | 0.73 ± 0.22 | 2/5 seeds: A's loop re-ignites during B (25 / 25), S_learn 0.46 |
| `persist` + E→MD, w_em 1 | **25 / 23** | 25 / 25 | **0%** | −0.12 | fail: both loops on from the start; other SOM 3.8 Hz; E 27 Hz |
| `amp`, cross-talk 0.05 / 0.1 / 0.25 | 23 / 1.2, 21 / 2.3, 16 / 5.5 | same | 100 / 100 / 87% | 0.94 / 0.93 / 0.74 | pass, pass, fail (seed-dependent: 3/5 fully gated) |
| `persist`, cross-talk 0.05 | 25 / 1.6 | 25 / 1.7 | 100% | 0.93 | pass |
| `persist`, cross-talk 0.1 / 0.25 | **7.2 / 1.1**, 4.9 / 2.6 | same | 17% / 1% | 0.59 / 0.25 | fail: the sustained state collapses after the 0.5-s cue, so MD is on only during the cue |

- **Findings:**
  - A loop that **amplifies a held cue** is robust. It tolerates 10% loop cross-talk, and
    nonspecific E→MD feedback up to the largest weight tested (OFF MD 6 Hz). The feedback
    raises ON MD to 34 Hz, so PV lowers E from 11 to 6 Hz.
  - A loop that **sustains context by itself** brings three new requirements:
    - competition strong enough for its gain (otherwise the old context never switches off
      and the new pattern is learned on both branches);
    - loop specificity ≤ 5% (at 10% the sustained state collapses);
    - weak nonspecific E→MD feedback (≤ 0.25; at 0.5 the old loop re-ignites in 2/5
      seeds, at 1 both loops are on).
  - Neither regime touches the stored memory: ret_A is 1.000 everywhere. Every failure is
    a failure to *write* B on the right branch, or to gate at all.
- **Prediction vs result.**
  - `amp` and `persist` reproduce Poisson MD: correct.
  - Weak competition gives both channels on and B learned on both branches: correct.
  - `amp` with E→MD failing from w_em ≈ 0.5: **wrong**, it passes at 1.0. Step 1's
    spill-over test *moved* MD→VIP drive away from the ON channel. Here the ON channel gains
    drive as well, so own VIP stays strong. And with VIP→SOM ×0.25, an OFF MD of 6 Hz
    leaves the other SOM at 32 Hz.
  - `persist` with E→MD failing from w_em ≈ 1: correct; it is partial at 0.5.
  - Loop cross-talk degrades `amp` gradually and collapses `persist` at 10%: correct.
- **Claim we can make:** MD-gated, branch-specific learning works with an MD signal
  generated by a PFC↔MD loop. If the context must be held by the loop itself, rather than
  by a sustained cue, the loop needs its own specificity and competition. PFC feedback to
  MD that does not code the context must stay weak.

### Still to do
- Step 3b is done with rate-unit context populations. A spiking context/MD loop is not built (no regime found).
- Inhibited-branch weakening is slow at the 8 × 3-s learning length.
