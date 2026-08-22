#!/usr/bin/env python3
"""
demo_meeting_figures.py
=======================
Generates 4 high-quality figures demonstrating:
  1. Graupner-Brunel calcium-based plasticity rule (STDP curve)
  2. Dendritic disinhibitory gating mechanism (Yang et al. 2016)
  3. Inhibition-dependent plasticity regimes
  4. Branch-specific gating self-organisation

Requirements: numpy, scipy, matplotlib (Python 3.10+)
"""

import os
import math
import numpy as np
from math import erf, exp, sqrt, pi, tanh
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle
from matplotlib.lines import Line2D
import matplotlib.colors as mcolors

from dendritic_io import dend_IO

# ──────────────────────────────────────────────────────────────
# Global style
# ──────────────────────────────────────────────────────────────
plt.style.use("default")
plt.rcParams.update({
    "font.family":      "serif",
    "font.size":        11,
    "axes.titlesize":   13,
    "axes.labelsize":   12,
    "legend.fontsize":  9,
    "xtick.labelsize":  10,
    "ytick.labelsize":  10,
    "figure.dpi":       200,
    "savefig.dpi":      200,
    "savefig.bbox":     "tight",
    "lines.linewidth":  1.8,
    "axes.grid": True, "grid.alpha": 0.3,
    "axes.facecolor": "white",
    "figure.facecolor": "white"
})

# Colour palette
CYAN    = "#00BCD4"
MAGENTA = "#E91E63"
AMBER   = "#FFC107"
GREEN   = "#4CAF50"
WHITE   = "#FFFFFF"
GRAY    = "#888888"

# Output directory
FIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures", "phenomenological")
os.makedirs(FIG_DIR, exist_ok=True)


# ──────────────────────────────────────────────────────────────
# Graupner-Brunel plasticity helpers
# ──────────────────────────────────────────────────────────────

# --- Model parameters (Yang 2016 / Graupner-Brunel) ---

# [EXPERIMENTATION] Change these to alter the calcium influx amplitude.
# Higher NMDA_SCALING increases pre-synaptic calcium, promoting more LTP.
NMDA_SCALING  = 0.371
BAP_SCALING   = 0.957

# [EXPERIMENTATION] Change these to alter the learning rate magnitude.
# GAMMA_D controls how fast weights depress in LTD; GAMMA_P controls how fast they potentiate in LTP.
GAMMA_D       = 39.949
GAMMA_P       = 177.552

# [EXPERIMENTATION] Change these to alter the calcium thresholds needed for plasticity.
# Lowering THETA_P makes it easier to achieve Long-Term Potentiation (LTP).
THETA_P       = 2.78
THETA_D       = 1.0

SIGMA         = 3.35
TAU_RHO       = 346.36        # seconds — slow weight variable time-constant
W0            = 0.0
W1            = 3.0
RHO_STAR      = 0.5
REPEAT_TIMES  = 60            # number of pre-post pairings
DT_SIM        = 0.0005        # 0.5 ms simulation step (seconds)
SIM_DURATION  = 0.500         # 500 ms window per pairing

TAU_CA_NMDA   = 0.030         # 30 ms NMDA calcium decay
TAU_CA_RISE   = 0.002         # 2 ms bAP calcium rise
TAU_CA_DECAY  = 0.030         # 30 ms bAP calcium decay


def _calcium_trace(delta_t: float, dt: float = DT_SIM,
                   T: float = SIM_DURATION):
    """Return calcium trace for a single pre-post pairing at offset *delta_t*.

    delta_t > 0 ⇒ pre fires first (pre-before-post)
    delta_t < 0 ⇒ post fires first (post-before-pre)
    """
    n_steps = int(round(T / dt))
    t = np.arange(n_steps) * dt

    # Pre spike at t=0.1 s, post spike at t=0.1+delta_t
    t_pre  = 0.100
    t_post = 0.100 + delta_t

    # NMDA calcium: instantaneous rise, exponential decay
    ca_nmda = np.where(t >= t_pre,
                       NMDA_SCALING * np.exp(-(t - t_pre) / TAU_CA_NMDA),
                       0.0)

    # bAP calcium: double-exponential (rise + decay)
    ca_bap = np.zeros_like(t)
    mask = t >= t_post
    dt_post = t[mask] - t_post
    # Normalise so the peak equals BAP_SCALING.
    #
    # The previous constant, TAU_CA_DECAY/(TAU_CA_DECAY - TAU_CA_RISE) = 1.0714, is not
    # the peak factor for this kernel -- it left the actual peak at 0.824*BAP_SCALING,
    # i.e. 18% low. The peak of exp(-t/td) - exp(-t/tr) is
    #     (tr/td)**(tr/(td-tr)) - (tr/td)**(td/(td-tr)),
    # so the normalisation is its reciprocal. Same class of error as the missing
    # NORM_BAP in the mechanistic model, but far milder.
    _x = TAU_CA_RISE / TAU_CA_DECAY
    _peak = _x ** (TAU_CA_RISE / (TAU_CA_DECAY - TAU_CA_RISE)) - \
            _x ** (TAU_CA_DECAY / (TAU_CA_DECAY - TAU_CA_RISE))
    norm = 1.0 / _peak
    ca_bap[mask] = BAP_SCALING * norm * (
        np.exp(-dt_post / TAU_CA_DECAY) - np.exp(-dt_post / TAU_CA_RISE)
    )

    ca_total = ca_nmda + ca_bap
    return t, ca_nmda, ca_bap, ca_total


def _compute_alpha(ca: np.ndarray, theta: float, dt: float):
    """Fraction of time calcium spends above *theta*."""
    return np.sum(ca > theta) * dt


def _synapse_change(alpha_d: float, alpha_p: float,
                    rho_init: float = RHO_STAR):
    """Graupner-Brunel analytical weight-change formula (GB 2012, Eq. 6).

    rho(T) = rho_bar + (rho_0 - rho_bar) * exp(-T*(gamma_p*a_p + gamma_d*a_d)/tau)

    `alpha_d` / `alpha_p` are *absolute* times (s) spent above each threshold,
    accumulated over the whole protocol, so GAMMA_X * alpha_X already carries
    the protocol duration T and the exponent needs only a division by TAU_RHO.

    Returns w_post / w_pre ratio, where both weights derive from the same
    rho -> w map, w = W0 + (W1 - W0) * rho.
    """
    gamma_d = GAMMA_D * alpha_d
    gamma_p = GAMMA_P * alpha_p
    total   = gamma_d + gamma_p

    if total < 1e-12:
        return 1.0          # no plasticity

    # Attractor the synapse is driven toward (0 = pure LTD, 1 = pure LTP)
    rho_bar = gamma_p / total

    exp_temp = exp(-total / TAU_RHO)

    # Relax from the *initial* rho toward rho_bar.
    # (Previously this used beta = (W1 - w_pre)/(W1 - W0), i.e. the COMPLEMENT
    #  of rho_0, which inverted the LTD arm and made every Dt report LTP.)
    rho_mean = rho_bar + (rho_init - rho_bar) * exp_temp

    w_post = W0 + (W1 - W0) * rho_mean
    w_pre  = W0 + (W1 - W0) * rho_init
    if w_pre < 1e-12:
        return 1.0
    return w_post / w_pre


def stdp_curve(delta_ts):
    """Compute weight-change ratio for an array of Δt values."""
    ratios = np.zeros_like(delta_ts, dtype=float)
    for i, dt_val in enumerate(delta_ts):
        # Accumulate alpha over repeated pairings
        total_alpha_d = 0.0
        total_alpha_p = 0.0
        for _ in range(REPEAT_TIMES):
            _, _, _, ca = _calcium_trace(dt_val)
            total_alpha_d += _compute_alpha(ca, THETA_D, DT_SIM)
            total_alpha_p += _compute_alpha(ca, THETA_P, DT_SIM)
        ratios[i] = _synapse_change(total_alpha_d, total_alpha_p)
    return ratios


# ──────────────────────────────────────────────────────────────
# Dendritic I/O from Yang 2016
# ──────────────────────────────────────────────────────────────

# dend_IO now lives in dendritic_io.py (single canonical definition, imported above).


# ══════════════════════════════════════════════════════════════
# FIGURE 1 — Calcium-Based Plasticity Rule
# ══════════════════════════════════════════════════════════════

def make_figure1():
    print("  → Figure 1: calcium plasticity …")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5),
                             gridspec_kw={"wspace": 0.35})

    # ---- Panel A: single calcium trace (pre→post, Δt = +10 ms) ----
    ax = axes[0]
    t, ca_nmda, ca_bap, ca_total = _calcium_trace(0.010)
    t_ms = t * 1000.0

    ax.fill_between(t_ms, 0, ca_total, alpha=0.15, color=CYAN)
    ax.plot(t_ms, ca_nmda,  label="NMDA Ca²⁺",     color=CYAN,    ls="--")
    ax.plot(t_ms, ca_bap,   label="bAP Ca²⁺",      color=MAGENTA, ls="--")
    ax.plot(t_ms, ca_total, label="Total Ca²⁺",     color=AMBER,   lw=2.2)

    ax.axhline(THETA_D, color=GREEN,   ls=":", lw=1.2, label=f"θ_d = {THETA_D}")
    ax.axhline(THETA_P, color=MAGENTA, ls=":", lw=1.2, label=f"θ_p = {THETA_P}")

    ax.set_xlim(80, 250)
    ax.set_ylim(0, 1.6)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Calcium concentration (a.u.)")
    ax.set_title("A  Pre→Post Calcium Trace (Δt = +10 ms)", loc="left",
                 fontweight="bold")
    ax.legend(loc="upper right", framealpha=0.4, fontsize=8)

    # ---- Panel B: STDP curve ----
    ax = axes[1]
    dts = np.linspace(-0.060, 0.060, 61)   # seconds
    ratios = stdp_curve(dts)

    dts_ms = dts * 1000.0
    ax.axhline(1.0, color=GRAY, ls=":", lw=0.8)
    ax.axvline(0.0, color=GRAY, ls=":", lw=0.8)

    # colour LTP / LTD regions
    ax.fill_between(dts_ms, 1.0, ratios,
                    where=(ratios > 1.0), interpolate=True,
                    color=CYAN, alpha=0.25, label="LTP")
    ax.fill_between(dts_ms, 1.0, ratios,
                    where=(ratios < 1.0), interpolate=True,
                    color=MAGENTA, alpha=0.25, label="LTD")
    ax.plot(dts_ms, ratios, color=AMBER, lw=2.2)

    ax.set_xlabel("Δt = t_post − t_pre  (ms)")
    ax.set_ylabel("w_post / w_pre")
    ax.set_title("B  STDP Curve (60 pairings)", loc="left",
                 fontweight="bold")
    ax.legend(loc="upper left", framealpha=0.4, fontsize=8)

    fig.savefig(os.path.join(FIG_DIR, "fig1_calcium_plasticity.png"))
    plt.close(fig)
    print("    ✓ saved fig1_calcium_plasticity.png")


# ══════════════════════════════════════════════════════════════
# FIGURE 2 — Dendritic Disinhibitory Gating
# ══════════════════════════════════════════════════════════════

def _draw_circuit(ax):
    """Draw a schematic circuit diagram on *ax*."""
    ax.set_xlim(-0.1, 1.1)
    ax.set_ylim(-0.1, 1.1)
    ax.set_aspect("equal")
    ax.axis("off")

    box_kw = dict(boxstyle="round,pad=0.12", linewidth=1.5)

    # --- Nodes ---
    nodes = {
        "MD":   (0.20, 0.85, "#42A5F5", "MD\nThalamus"),
        "SENS": (0.20, 0.55, "#42A5F5", "Cortical\nInput"),
        "PYR":  (0.55, 0.45, "#42A5F5", "PFC\nSoma"),
        "DEND": (0.55, 0.85, AMBER,     "Dendrite"),
        "VIP":  (0.85, 0.85, GREEN,     "VIP"),
        "SOM":  (0.85, 0.60, MAGENTA,   "SOM"),
        "PV":   (0.55, 0.15, MAGENTA,   "PV"),
    }

    for key, (x, y, col, txt) in nodes.items():
        bbox = FancyBboxPatch((x - 0.09, y - 0.07), 0.18, 0.14,
                              facecolor=col, edgecolor="white",
                              alpha=0.85, **box_kw)
        ax.add_patch(bbox)
        ax.text(x, y, txt, ha="center", va="center", fontsize=7,
                fontweight="bold", color="white")

    # --- Arrows ---
    arrow_kw = dict(arrowstyle="-|>", lw=1.8,
                    connectionstyle="arc3,rad=0.0",
                    mutation_scale=14)

    def _arrow(src, dst, color, rad=0.0, ls="-"):
        x0, y0 = nodes[src][:2]
        x1, y1 = nodes[dst][:2]
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=color,
                                    lw=2.0, connectionstyle=f"arc3,rad={rad}",
                                    linestyle=ls))

    _arrow("SENS", "DEND", "#42A5F5")              # cortical -> dendrite
    _arrow("MD",   "VIP",  "#42A5F5", rad=-0.2)    # MD -> VIP
    _arrow("MD",   "PV",   "#42A5F5", rad=-0.3)    # MD -> PV
    _arrow("VIP",  "SOM",  GREEN)                   # VIP -> SOM
    _arrow("SOM",  "DEND", MAGENTA)                 # SOM -> DEND
    _arrow("PV",   "PYR",  MAGENTA)                 # PV -> SOMA
    _arrow("DEND", "PYR",  AMBER, rad=0.0)          # DEND -> SOMA

    # Legend
    legend_elements = [
        Line2D([0], [0], color="#42A5F5", lw=2, label="Excitatory"),
        Line2D([0], [0], color=MAGENTA,   lw=2, label="Inhibitory"),
        Line2D([0], [0], color=GREEN,     lw=2, label="Disinhibitory"),
    ]
    ax.legend(handles=legend_elements, loc="lower left",
              fontsize=7, framealpha=0.3)


def make_figure2():
    print("  → Figure 2: dendritic gating …")
    fig = plt.figure(figsize=(12, 4.8))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1, 1.2], wspace=0.30)

    # ---- Panel A: circuit diagram ----
    ax_circ = fig.add_subplot(gs[0])
    ax_circ.set_title("A  Disinhibitory Circuit", loc="left",
                       fontweight="bold")
    _draw_circuit(ax_circ)

    # ---- Panel B: dendritic I/O ----
    ax = fig.add_subplot(gs[1])
    exc = np.linspace(0, 60, 300)
    inh_levels = [0, 15, 30]
    colors = [CYAN, AMBER, MAGENTA]
    labels = ["SOM inh = 0 nS", "SOM inh = 15 nS", "SOM inh = 30 nS"]

    for inh, col, lab in zip(inh_levels, colors, labels):
        v = dend_IO(exc, inh)
        ax.plot(exc, v, color=col, lw=2.2, label=lab)

    ax.set_xlabel("Excitatory conductance (nS)")
    ax.set_ylabel("Dendritic voltage (mV)")
    ax.set_title("B  Dendritic I/O — SOM Gating", loc="left",
                 fontweight="bold")
    ax.legend(loc="upper left", framealpha=0.4, fontsize=9)

    # annotate gating shift
    ax.annotate("SOM inhibition\nshifts sigmoid →",
                xy=(38, -50), fontsize=9, color=GREEN,
                fontstyle="italic",
                arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.5),
                xytext=(15, -45))

    fig.savefig(os.path.join(FIG_DIR, "fig2_dendritic_gating.png"))
    plt.close(fig)
    print("    ✓ saved fig2_dendritic_gating.png")


# ══════════════════════════════════════════════════════════════
# FIGURE 3 — How Inhibition Controls Plasticity
# ══════════════════════════════════════════════════════════════

def _simplified_calcium(rate_hz: float, inh_rate_hz: float):
    """Simplified mean calcium level for a given presynaptic rate and
    inhibition rate.

    Uses mean-field NMDA gating × voltage-dependent Mg²⁺ block
    computed from the dend_IO function.
    """
    # Mean NMDA gating variable (1st-order kinetics)
    alpha_nmda = 0.06    # ~ alpha * tau_rise * tau_decay  (lumped)
    s_nmda = alpha_nmda * rate_hz / (1.0 + alpha_nmda * rate_hz)

    # Excitatory conductance → dendritic voltage
    g_nmda = 0.5          # nS per synapse
    n_inputs = 80         # number of afferents
    w_nom = 1.0           # nominal weight
    g_exc = g_nmda * n_inputs * s_nmda * w_nom

    # Inhibitory conductance (from SOM driven by inh_rate)
    g_inh = 0.8 * inh_rate_hz    # linear map Hz → nS

    v_dend = dend_IO(np.atleast_1d(g_exc), g_inh)[0]   # mV

    # Mg²⁺ block factor: B(V) = 1 / (1 + [Mg²⁺]/3.57 * exp(-0.062 V))
    mg_block = 1.0 / (1.0 + (1.0 / 3.57) * np.exp(-0.062 * v_dend))

    # NMDA calcium ∝ s_NMDA × mg_block × driving force
    driving = max(v_dend - (-10.0), 0.0)   # reversal ~ 0 mV, floor at 0
    ca_nmda = NMDA_SCALING * s_nmda * mg_block * driving / 30.0

    # bAP contribution proportional to post firing (assume post rate ~ f(v))
    post_rate = max(0.0, (v_dend + 50.0) / 20.0)  # rough F–I
    ca_bap = BAP_SCALING * post_rate / 30.0

    # Scale up steady-state mean calcium to match peak-calibrated thresholds (THETA_D=1.0)
    return (ca_nmda + ca_bap) * 50.0


def _weight_change_from_ca(ca_level: float):
    """Map a mean calcium level to a weight-change ratio using a
    simplified steady-state version of the Graupner-Brunel rule."""
    if ca_level < THETA_D:
        # No threshold crossing -> synapse stays at its baseline weight.
        # (Must return an absolute weight, not the ratio 1.0: the caller
        #  divides this by the baseline, so returning 1.0 rendered the
        #  sub-threshold regime as a spurious 0.67x depression.)
        return W0 + (W1 - W0) * RHO_STAR
    elif ca_level < THETA_P:
        # LTD regime — depression proportional to time above θ_d
        depression = GAMMA_D * (ca_level - THETA_D) / (THETA_P - THETA_D)
        rho_bar = 0.0
        rho_mean = rho_bar + (0.5 - rho_bar) * exp(-depression / TAU_RHO)
        return W0 + (W1 - W0) * rho_mean
    else:
        # LTP regime — potentiation proportional to time above θ_p
        alpha_d = (ca_level - THETA_D) / THETA_D
        alpha_p = (ca_level - THETA_P) / THETA_P
        gd = GAMMA_D * alpha_d
        gp = GAMMA_P * alpha_p
        rho_bar = gp / (gp + gd)
        rho_mean = rho_bar + (0.5 - rho_bar) * exp(-(gp + gd) / TAU_RHO)
        return W0 + (W1 - W0) * rho_mean


def make_figure3():
    print("  → Figure 3: inhibition × rate plasticity …")
    fig, ax = plt.subplots(figsize=(7, 5))

    rates = np.linspace(0, 50, 200)
    inh_configs = [
        (0,  "No inhibition (0 Hz)",  CYAN),
        (20, "Moderate (20 Hz)",      AMBER),
        (40, "Strong (40 Hz)",        MAGENTA),
    ]

    # Background bands
    ax.axhspan(0.0,  0.95, color=MAGENTA, alpha=0.07, label="LTD zone")
    ax.axhspan(0.95, 1.05, color=GRAY,    alpha=0.10, label="No change")
    ax.axhspan(1.05, 3.20, color=CYAN,    alpha=0.07, label="LTP zone")

    for inh_hz, lab, col in inh_configs:
        wc = np.array([_weight_change_from_ca(_simplified_calcium(r, inh_hz))
                        for r in rates])
        # normalise to ratio
        wc_ratio = wc / (W0 + (W1 - W0) * 0.5)   # baseline at rho=0.5
        ax.plot(rates, wc_ratio, color=col, lw=2.3, label=lab)

    ax.axhline(1.0, color=GRAY, ls=":", lw=0.8)

    ax.set_xlabel("Presynaptic firing rate (Hz)")
    ax.set_ylabel("w_post / w_pre")
    ax.set_title("Inhibition Controls Plasticity Regime", fontweight="bold")
    ax.legend(loc="upper left", framealpha=0.35, fontsize=8)
    ax.set_xlim(0, 50)
    ax.set_ylim(0, 2.5)

    fig.savefig(os.path.join(FIG_DIR, "fig3_weight_change_vs_rate.png"))
    plt.close(fig)
    print("    ✓ saved fig3_weight_change_vs_rate.png")


# ══════════════════════════════════════════════════════════════
# FIGURE 4 — Branch-Specific Gating Self-Organisation
# ══════════════════════════════════════════════════════════════

def make_figure4():
    print("  → Figure 4: branch-specific learning (3 Epochs, correct Graupner-Brunel) …")

    rng_gb = np.random.default_rng(42)
    n_trials = 300

    # ρ: bistable Graupner-Brunel weight variable ∈ [0, 1]
    # W: actual weight derived from ρ via W = W0 + (W1-W0)*ρ
    RHO_STAR_LOCAL = 0.5
    rho = np.full((2, 2), RHO_STAR_LOCAL)
    # W0 and W1 from module-level constants
    W   = np.zeros((2, 2))
    for i in range(2):
        for j in range(2):
            W[i, j] = W0 + (W1 - W0) * rho[i, j]

    W_history = np.zeros((n_trials, 2, 2))

    # Conductance scaling (nS per Hz of pre-synaptic drive)
    G_PER_HZ = 0.10   # nS/Hz

    for trial in range(n_trials):
        if trial < 100:
            rate_A = rng_gb.poisson(0.0)
            rate_B = rng_gb.poisson(0.0)
            rates = [rate_A, rate_B]
            inh   = [35.0, 35.0]
        elif trial < 200:
            rate_A = rng_gb.poisson(25.0 * 0.5) / 0.5
            rate_B = rng_gb.poisson(0.0)
            rates = [rate_A, rate_B]
            inh   = [2.0, 35.0]
        else:
            rate_A = rng_gb.poisson(0.0)
            rate_B = rng_gb.poisson(25.0 * 0.5) / 0.5
            rates = [rate_A, rate_B]
            inh   = [35.0, 2.0]

        for branch in range(2):
            g_inh = 0.8 * inh[branch]

            # Total conductance on this branch from ALL pathways
            g_exc_total = sum(rates[pw] * G_PER_HZ * W[pw, branch]
                              for pw in range(2))

            for pathway in range(2):
                r_pre = rates[pathway]
                if r_pre < 1e-6:
                    continue   # silent pathway — no plasticity

                g_exc_pathway = r_pre * G_PER_HZ * W[pathway, branch]

                # --- Correct Graupner-Brunel calcium ---
                v_dend = dend_IO(np.atleast_1d(g_exc_total), g_inh)[0]

                # Mg2+ block (voltage-dependent)
                mg = 1.0 / (1.0 + (1.0 / 3.57) * np.exp(-0.062 * v_dend))

                # NMDA calcium amplitude per pre-spike (Mg-gated)
                c_nmda_amp = NMDA_SCALING * mg

                # Post-synaptic rate → bAP calcium amplitude
                r_post    = max(0.0, (v_dend + 55.0) / 10.0)

                # Representative pre-post pairing interval
                r_pair  = min(r_pre, max(r_post, 1.0))
                dt_pair = min(0.010, 1.0 / r_pair)

                # Calcium trace for one representative pair.
                # The Mg2+ block gates the NMDA component ONLY — bAP calcium
                # enters through voltage-gated Ca channels and is not
                # Mg-dependent. (Previously the whole trace was scaled by mg,
                # which incorrectly suppressed bAP calcium on inhibited
                # branches on top of the genuine NMDA suppression.)
                _, ca_nmda, ca_bap, _ = _calcium_trace(dt_pair)
                ca = ca_nmda * mg + ca_bap

                # Alpha = time integral above threshold × number of pairings
                n_pairings = max(1, int(r_pair * SIM_DURATION))
                alpha_d = _compute_alpha(ca, THETA_D, DT_SIM) * n_pairings
                alpha_p = _compute_alpha(ca, THETA_P, DT_SIM) * n_pairings

                # ── Fast Visible Update (ETA_RHO) ──
                gamma_d = GAMMA_D * alpha_d
                gamma_p = GAMMA_P * alpha_p
                total = gamma_d + gamma_p

                if total < 1e-12:
                    rho_new = float(np.clip(rho[pathway, branch] + rng_gb.normal(0, 0.04 * 0.3), 0.0, 1.0))
                else:
                    rho_bar = gamma_p / total
                    ETA_RHO = 0.08
                    rho_mean = rho[pathway, branch] + ETA_RHO * (rho_bar - rho[pathway, branch])
                    noise_scale = 0.04 * math.sqrt((alpha_d + alpha_p) / total)
                    rho_new = float(np.clip(rng_gb.normal(rho_mean, max(noise_scale, 0.02)), 0.0, 1.0))
                
                rho[pathway, branch] = rho_new

            # Derive weight from ρ
            for pathway in range(2):
                W[pathway, branch] = W0 + (W1 - W0) * rho[pathway, branch]

        W_history[trial] = W.copy()

    # ---- Plot ----
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"wspace": 0.35})
    trials = np.arange(n_trials)

    ax = axes[0]
    ax.axvspan(0, 100, color='gray', alpha=0.1, label='Baseline')
    ax.axvspan(100, 200, color=CYAN, alpha=0.1, label='Context A')
    ax.axvspan(200, 300, color=MAGENTA, alpha=0.1, label='Context B')

    labels = [("w_A→br1", CYAN,    "-"),
              ("w_A→br2", CYAN,    "--"),
              ("w_B→br1", MAGENTA, "--"),
              ("w_B→br2", MAGENTA, "-")]

    for idx, (lab, col, ls) in enumerate(labels):
        p, b = divmod(idx, 2)
        ax.plot(trials, W_history[:, p, b], color=col, ls=ls, lw=2.0, label=lab)

    ax.set_xlabel("Trial")
    ax.set_ylabel("Synaptic weight")
    ax.set_title("A  Weight Evolution (3 Epochs)", loc="left", fontweight="bold")
    ax.legend(loc="upper left", framealpha=0.35, fontsize=8)
    ax.set_xlim(0, n_trials)

    ax = axes[1]
    final_W = W_history[-1]
    im = ax.imshow(final_W, cmap="viridis", vmin=0, vmax=2.0, aspect="equal")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Branch 1", "Branch 2"])
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Pathway A", "Pathway B"])
    ax.set_title("B  Final Weight Matrix", loc="left", fontweight="bold")

    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{final_W[i, j]:.2f}",
                    ha="center", va="center", fontsize=13,
                    fontweight="bold", color="white" if final_W[i, j] < 1.0 else "black")

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Weight", fontsize=10)

    fig.savefig(os.path.join(FIG_DIR, "fig4_branch_specific_learning.png"))
    plt.close(fig)
    print("    ✓ saved fig4_branch_specific_learning.png")


# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Generating demo meeting figures …\n")
    make_figure1()
    make_figure2()
    make_figure3()
    make_figure4()
    print(f"\nAll figures saved to: {FIG_DIR}")
