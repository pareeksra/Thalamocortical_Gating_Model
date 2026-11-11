# Canonical model vs the papers (R4 of PLAN_robustness.md, 2026-11-10)

**Canonical model** = `model/context_circuit.py` defaults since 2026-11-10:
- Yang's NMDA-plastic synapse (w scales NMDA, AMPA off, ρ₀ = 1/3).
- Fluctuation-driven SOM baseline (6 pA bias + 60 Hz × 2 nS Poisson input, ≈ 30 Hz).
- bAP calcium ×0.2, Yang's in-vivo recalibration.

Each row names the script and result file. Tolerances are stated before the comparison.
Yang's figures give mostly qualitative or plot-read values. Zhang 2025 is a trained rate
RNN, so it supplies wiring, not rates.

## Yang, Murray & Wang 2016

| # | Yang claim (figure) | Our number (canonical) | Verdict | Source |
|---|---|---|---|---|
| V1 | Dendritic half-activation g½ = 5.56 (4 + g_inh) (Fig. 2c fit, Eqs. 20–22) | 24.9, 26.6, 33.6, 39.7, 52.9, 68.4 nS at g_inh = 0, 1, 2, 4, 6, 10 nS (Yang 22.2, 27.8, 33.4, 44.5, 55.6, 77.8). Fit 4.51 (g_inh + 5.27), vs 5.56 (g_inh + 4) | **match** within 12% at g_inh ≥ 1 nS (+12% at 0) | `experiments/v1_dendrite_io_measured.py yang`, `results/current/v1_dendrite_io_yang.json` |
| | (old synapse, for contrast) | g½ saturates at ≈ 48 nS for g_inh ≥ 10 nS | was "shunted less than Yang" | `v1_dendrite_io.json` |
| V2 | Fig. 7b, weak inhibition: no change at low rate, LTD at medium rate, LTP at high rate (300 s, post 10 Hz) | disinhibited branch (own SOM 0.9 Hz): Δw = 0 at ≤ 5 Hz, −0.26 at 10 Hz, LTP from 15 Hz (+0.17 at 15, +1.05 at 20, +1.45 at 30 Hz). VIP→SOM ×1: −0.39 at 10 Hz, +1.52 at 20 Hz (`paper_comparison_vip1*`) | **match** | `experiments/paper_comparison.py`, `results/current/paper_comparison_summary.json`, `figures/paper_comparison_v2.png` |
| V2 | Medium inhibition shifts the LTP threshold up | SOM 13 Hz: no change ≤ 15 Hz, LTD 20–100 Hz, LTP from 150 Hz | **match** | same |
| V2 | Strong inhibition: no LTP over a reasonable rate range | SOM 31 and 60 Hz: no LTP up to 150 Hz, LTD from 30–40 Hz | **match** | same |
| V2 | Non-activated synapses do not change (Methods: k_VGCC ×0.2 "ensures the weights of non-activated synapses do not change substantially") | Δw = 0.000 at 0–2 Hz; a learned memory with silent inputs keeps 1.000 over a 300-s idle phase | **match** (after the bAP recalibration; with bAP ×1.0: Δw −0.70 at 0–2 Hz, retention 0.12) | `experiments/epoch_length_check.py`, `epoch_length_check.json` / `_bap1.json` |
| V3 | Learning: activated synapses onto disinhibited branches strengthen, those onto inhibited branches weaken (Fig. 7c) | free 0.928, inhibited 0.333 (unchanged from ρ₀, ratio 2.8) after 8 × 3 s at 80 Hz, 20/20 seeds; inhibited weakening needs longer exposure (ρ_inh 0.27–0.32 with 24-s epochs) | **partial**: strengthening matches; weakening is slow at our protocol length | `experiments/robustness_r2.py canonical`, `epoch_length_check.json` |
| Fig. 7d,e | Before learning no gate preference; after learning strong pathway-specific gating | S before ≈ 0 at equal drive (0.06, −0.01, −0.12); after learning S = 0.88 (5 seeds, 10 Hz readout; R5 S1: 0.92, 0.93, 0.81) | **match**, at readout drive ≤ 15 Hz/synapse | `robustness_r3_canonical.json`, `tests/test_replication.py --slow` S1 |
| Fig. 2e–g | Open gate transmits tuning; S of the 2-D tuning ≈ 0.6 at Yang's settings | 27 vs 8 Hz at the preferred stimulus, S ≈ 0.6 | **match** (with 0.8 nS clamped-soma coupling, 300 Hz soma background) | `notebooks/yang_fig2_supp1.ipynb` |
| Supp. Fig. 1f–h | Inhibition gates NMDA input strongly, AMPA input weakly | qualitative match | **match** | same notebook, `figures/yang_supp1_fgh_model.png` |
| Figs. 3–5 | Gating selectivity typically 0.5–0.9, high when control is branch-specific; collapses with non-specific control | Fig. 5 protocol at default wiring: S = 0.93 (5 seeds) | **match**, *given* branch-specific VIP→SOM (assumption G2) | `robustness_r3_canonical.json`; `gating_selectivity_fig5.py` (old synapse) |

## Zhang et al. 2025 (wiring, qualitative)

| # | Zhang | Ours | Verdict |
|---|---|---|---|
| V4 | MD1 → PV (MD^GRIK4), MD2 → VIP (MD^DRD2) | MD → PV, MD_k → VIP_k | match |
| V4 | VIP → SOM (disinhibition); no VIP → PV, no VIP → E | VIP_k → SOM_k only, weight ×0.25 (canonical since 2026-11-10) | match. Branch-specific channels are **our assumption** (G2); `specificity_test.py`: MD → VIP must be channel-specific; VIP → SOM tolerates ≈ 7.5% cross-talk at ×0.25 and 20% at ×0.1 |
| V4 | SOM → E (dendrite), SOM → PV, SOM → VIP | SOM → dendrite, SOM → PV; SOM → VIP as an option (`som2vip_nS`) | SOM → VIP off in the canonical model. Gating survives it up to 0.1 nS uniform, or ≥ 0.5 nS within-channel (`zhang_wiring_test.py`) |
| V4 | PV → E (soma), PV → PV | PV → soma; PV → PV as an option (`pv2pv_nS`) | PV → PV off in the canonical model. It has no effect on gating or learning up to 1 nS (PV 51 → 10 Hz) |
| V4 | Recurrent E → all types; PFC ↔ MD loop | E → all types in a 20-cell network (`network_circuit.py`); MD is still an input | E → all: gating and learning survive up to gain 0.6 of our reference weights, then fail abruptly as the inactive channel's VIP ignites (`network_test.py`). PFC ↔ MD loop as rate units (`md_loop.py`, `network_loop_test.py`): it works. A self-sustaining loop needs competition, ≤ 5% loop cross-talk and weak non-context E→MD feedback |
| V4 | MD activation disinhibits via VIP and adds PV gain | MD 0 → 40 Hz: VIP 0 → 85 Hz, own SOM 31 → 0.1 Hz (4.1 Hz at 20, 0.2 Hz at 30), other SOM unchanged (31 Hz), PV 2 → 95 Hz. VIP→SOM ×1: own SOM 0.8 Hz at 20 | match (sign and monotonicity) |

## Remaining mismatches, one line each
- **Inhibited-branch weakening** is slow at our learning length (8 × 3 s); ρ_inh stays near ρ₀. Yang's synapses on inhibited branches weaken. Gating does not depend on it (ratio 2.8).
- **V1 at g_inh = 0** is 12% above Yang's fit. No AMPA, 40 synapses; within tolerance.
- **Fig. 2 needs a 0.8 nS coupling** for the clamped-soma panels and a 300 Hz soma background (Yang: 500 Hz).
- **Readout regime**: learned gating shows only for readout drive ≤ 15 Hz per synapse. Yang equalised drive by activating 5 of 15 synapses.
- **Zhang wiring**: SOM → VIP and PV → PV are tested as options (compatible within limits). All recurrence is absent. The MD → VIP channel specificity is required.
