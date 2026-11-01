# Plan — overlapping-inputs experiment (2026-11-02)

## Question

The audit found that, with context-*specific* inputs, retention comes entirely from input
sparsity, and MD→VIP→SOM gating plays no part in it. Real contexts share inputs, though.
**When contexts A and B share a fraction f of their afferents, what does MD-driven branch
gating buy: retention, separation, or a trade-off between them?**

## Design

Model A, `model/context_circuit.py`, new `input_mode='patterns'`.

- **Afferent pool.** Pattern A = afferents [0, 20); pattern B = 20 afferents of which
  round(20·f) are shared with A. Every afferent makes a plastic synapse on **both**
  branches, so inputs are not pre-sorted by branch. Only MD gating can decide which
  branch stores a pattern.
- **Drive.** Each epoch the active pattern's afferents fire at 80 Hz and all others are
  silent. Each branch therefore sees the same 20 × 80 Hz drive as every calibrated run.
- **Schedule.** Context A (MD₀ on, pattern A) for 8 epochs, then context B (MD₁ on,
  pattern B) for 8 epochs, T = 3 s. Analytical Yang plasticity, pinned 10 Hz bAPs
  (canonical protocol), desynchronised SOM, calibrated PV.
- **Conditions.** Gating {MD (SOM inhibition on), none (inhibition off)} ×
  f {0, 0.25, 0.5, 0.75, 1} × seeds 42–46 = 50 runs. Run on toothless, one fresh process
  per run.

## Metrics

All are computed from per-synapse ρ at the end of A and the end of B.

| metric | definition | meaning |
|---|---|---|
| `ret_A` | mean ρ(A→b0) after B ÷ after A | A's memory on its storage branch |
| `ret_A_shared` / `ret_A_unique` | same, split into shared vs A-only afferents | where any loss happens |
| `sep_b0` | mean ρ(A→b0) − mean ρ(B-only→b0), after B | does branch 0 hold A *and not* B? |
| `sep_b1` | mean ρ(B→b1) − mean ρ(A-only→b1), after B | does branch 1 hold B *and not* A? |
| `D(X,b)` | Σ w over pattern-X afferents onto branch b | pattern drive; discriminability = D(A,b0)−D(B,b0) |

## Predictions (written before running)

1. **No gating.** Both branches learn A, then both learn B. Shared afferents are active
   and free in B, so they stay potentiated. A-only afferents are silent in B, so they are
   held. → `ret_A` ≈ 1 at every f, but `sep_b0` ≈ `sep_b1` ≈ 0 (no context separation).
2. **MD gating.** A is stored on b0 only, B on b1 only. In context B the shared afferents
   onto b0 are active on a gated branch, so they are depressed (the audit's mechanism).
   → `ret_A` ≈ (1−f) + f·(depressed fraction), falling with f. `sep_b0` and `sep_b1` stay
   large.
3. Hence a **retention ↔ separation trade-off** controlled by overlap. MD gating buys
   separation, and pays for it in proportion to the shared fraction.

## Built-in anchors (correctness checks)

- f = 0, MD gating ≡ the audit's "both" condition: expect `ret_A` ≈ 1.0.
- f = 1, MD gating ≡ "inhibition-only": expect `ret_A` ≈ 0.35.
- f = 1, no gating ≡ "neither": expect `ret_A` ≈ 1.0 with no separation.

If the anchors fail, stop and debug before interpreting anything.

## Steps

1. Implement `input_mode='patterns'` and per-synapse ρ recording; keep the old modes
   bit-identical.
2. Fast local smoke test (1 epoch per context). Regression: existing modes unchanged.
3. Run the 50-run grid on toothless.
4. Check the anchors, then analyse the metrics and figure.
5. Document (results section in this file + audit doc + bible), commit.

---

## Results (2026-11-02; 50 runs, run locally)

Data: `docs/audit/overlap_experiment.json`. Figure: `figures/overlap_experiment.png`.
Code: `experiments/overlap_experiment.py`, `context_circuit(input_mode='patterns')`.

**Implementation checks.**
- The existing `context` mode is bit-identical to the committed code.
- Smoke test as predicted: in context B, silent A-only afferents are held exactly, and
  shared afferents on the gated branch are depressed.
- The metric code is unit-checked on hand-built cases.

**Anchors: all pass.**

| anchor | expected | got |
|---|---|---|
| f = 0, MD gating ("both") | ret_A ≈ 1.0 | 1.000 |
| f = 1, MD gating ("inhibition-only") | ≈ 0.35 | 0.365 ± 0.028 |
| f = 1, no gating ("neither") | 1.0, no separation | 1.000, 0 |

**Results** (mean over seeds 42–46; SDs ≤ 0.03):

| gating | f | ret_A | shared kept | unique kept | sep_b0 | sep_b1 | discriminability |
|---|---|---|---|---|---|---|---|
| MD | 0 | 1.000 | — | 1.000 | 0.63 | 0.67 | **0.65** |
| MD | 0.25 | 0.867 | 0.47 | 1.000 | 0.52 | 0.67 | 0.49 |
| MD | 0.5 | 0.705 | 0.41 | 1.000 | 0.40 | 0.67 | 0.34 |
| MD | 0.75 | 0.543 | 0.39 | 1.000 | 0.26 | 0.67 | 0.17 |
| MD | 1 | 0.365 | 0.37 | — | — | — | 0 |
| none | any | 1.000 | 1.00 | 1.00 | 0.00 | 0.00 | **0.00** |

**All three predictions confirmed.**

1. **No gating:** perfect retention at every overlap, and zero context separation even at
   f = 0. Both branches learn both patterns, so the cell responds identically to A and B.
2. **MD gating:**
   - A-only afferents are retained exactly (1.000 at every f).
   - Shared afferents keep only ~37–47%: they are active on a gated branch in context B.
   - So ret_A ≈ 1 − 0.6·f.
   - Discriminability is ≈ 0.65·(1 − f), and B's storage on branch 1 is unaffected
     (sep_b1 0.67 at every f).
3. **Trade-off:** MD gating is the **only** source of context separation in this model,
   at any overlap. Its price is the erosion of shared synapses, proportional to f.
   Overlap therefore sets an exchange rate between separation and retention; nowhere does
   gating deliver both at once.

**Caveats.**
- Discriminability here is branch-level: it assumes something downstream can read which
  branch is driven, e.g. branch-specific plateaus or output. A purely somatic, summed
  readout sees Σ_b D(A,b) = Σ_b D(B,b) in both conditions.
- 8 + 8 epochs, one A→B order. Repeated alternation (A, B, A, B, …) is untested; shared
  synapses could re-potentiate on each A epoch.
- Pinned bAPs, 2 branches, 20-afferent patterns.

**Next steps.**
1. Repeated alternation A/B/A/B, to test whether shared synapses reach a stable
   compromise.
2. A functional recall readout: present A or B with plasticity frozen and measure branch
   plateaus.
3. Scale up (more branches/contexts) in the network build.
