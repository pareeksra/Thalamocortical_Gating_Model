# Paper Replications — Model A vs source-paper figures

Fresh Model-A (Brian 2) outputs mapped to the specific figures they replicate. Generated
by `experiments/validate_vs_papers.py` on **2026-08-26** (Python 3.14.5 / brian2 2.10.1).
Full write-up with narrative: `../../Validation_Report.docx`. Raw numbers:
`measured_results.json`.

Yang 2016 is the same model class → **quantitative** replication. Zhang 2025 is a trained
rate RNN (we borrow only its wiring labels) → **qualitative/mechanistic** check only.

| Replicated figure | Replicates | What it shows | Verdict |
|---|---|---|---|
| `replicated_YANG2016_fig2c_dendritic_IO.png` | Yang 2016 **Fig. 2c** | Dendritic I/O `V_D(g_E)`; half-activation shifts with inhibition | **MATCH (exact)** |
| `replicated_YANG2016_fig7b_LTP_vs_rate.png` | Yang 2016 **Fig. 7b** | Steady-state ρ vs presynaptic rate; inhibition blocks LTP | **MATCH (directional)** |
| `replicated_YANG2016_fig7de_branch_gating.png` | Yang 2016 **Fig. 7d–e** | Branch-specific gating: free potentiates, inhibited does not | **MATCH** |
| `replicated_ZHANG2025_MD_interneuron_control.png` | Zhang 2025 (wiring) | MD↑ → SOM↓ (disinhibition), PV↑ (gain) | **MATCH (qualitative)** |

## Measured highlights

- **Fig. 2c** — half-activation `g_1/2` reproduces Yang's `5.56·(4+g_inh)` to the digit:
  g_inh = 0/2/10/20/35 nS → 22.2/33.4/77.8/133.4/216.8 nS.
- **Fig. 7b** — free branch ρ crosses 0.5 (LTP) by ~20 Hz and saturates ~0.79–0.81; the
  SOM-inhibited branch stays at ρ ≈ 0.012–0.020 across **every** rate (20–120 Hz). Inhibition
  shifts the LTP threshold out of range — Yang's effect.
- **Fig. 7d–e** — at exc 80 Hz / post 10 Hz / coupling 0.8 nS: free ρ = 0.79, inhibited
  ρ = 0.012, **free/inhibited ratio ≈ 65**.
- **Zhang wiring** — SOM 36 → 0 Hz and PV 7 → 127 Hz as MD goes 0 → 40 Hz; VIP rises in
  parallel (0 → 93 Hz) driving the SOM suppression.

## Caveats

- Single seed (42). Given the earlier reproducibility flag (Test 5), confirm across seeds
  before treating exact ρ values as fixed.
- Divergences from Yang left unchanged: SOM baseline ~36–40 Hz vs Yang ~10 Hz; SOM→PV synapse
  (Yang P=0.8) defined but unwired.
- Zhang's PFC→MD loop and MD→Exc projection are omitted; MD here is a bare Poisson input.

## Note on the older `figures/phenomenological/` and `figures/mechanistic/` PNGs

Those come from the NumPy figure models (B, C), whose plasticity is inert (random-walk /
surrogate). They are **not** valid replications — use the files in this folder instead.
