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
