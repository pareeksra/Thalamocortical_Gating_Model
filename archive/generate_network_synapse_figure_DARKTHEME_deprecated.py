"""
generate_network_synapse_figure.py
====================================
Generates a comprehensive 4-panel high-quality figure illustrating
the CURRENT state of the model (post-stochastic update, Aug 2026):

  Panel A: Complete Stochastic Circuit Architecture
           (MD Poisson Group → VIP/SOM/PV → Pyramidal)
  Panel B: Synaptic Receptor Kinetics (AMPA, GABA-A, NMDA)
           + NMDA Mg²⁺ voltage-dependent unblocking
  Panel C: Multi-Compartmental Soma-Dendrite ODE Equations
  Panel D: Graupner-Brunel Bistable Double-Well Plasticity
           (rho variable, noise term sigma, UP/DOWN states)

Run from the project root:
    python experiments/generate_network_synapse_figure.py
"""

import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec

# ── Dark theme ──────────────────────────────────────────────────────────────
plt.style.use("dark_background")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans"],
    "axes.facecolor":  "#0D0D14",
    "figure.facecolor": "#0D0D14",
    "text.color": "#F0F0F5",
    "axes.labelcolor": "#F0F0F5",
    "xtick.color": "#F0F0F5",
    "ytick.color": "#F0F0F5",
    "axes.edgecolor": "#444455",
    "grid.color": "#2a2a3a",
})

# ── Palette ──────────────────────────────────────────────────────────────────
CYAN    = "#00BCD4"
MAGENTA = "#E91E63"
AMBER   = "#FFC107"
GREEN   = "#4CAF50"
WHITE   = "#F0F0F5"
MUTED   = "#9E9E9E"
BOX_BG  = "#1A1A24"

# ── Output path (always relative to project root, not experiments/) ──────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
OUT_DIR     = os.path.join(PROJECT_DIR, "figures")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH    = os.path.join(OUT_DIR, "network_synaptic_architecture.png")


# ────────────────────────────────────────────────────────────────────────────
# Panel A helpers
# ────────────────────────────────────────────────────────────────────────────
def draw_node(ax, x, y, w, h, label, sublabel, color, shape="box"):
    if shape == "box":
        box = patches.FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle="round,pad=1.5",
            edgecolor=color, facecolor=BOX_BG, lw=2.5, zorder=3,
        )
        ax.add_patch(box)
    else:
        ax.add_patch(patches.Circle(
            (x, y), w / 2,
            edgecolor=color, facecolor=BOX_BG, lw=2.5, zorder=3,
        ))
    ax.text(x, y + 2, label, fontsize=11, fontweight="bold",
            color=color, ha="center", va="center", zorder=4)
    ax.text(x, y - 4, sublabel, fontsize=8.5, color=WHITE,
            ha="center", va="center", zorder=4)


def draw_arrow(ax, x1, y1, x2, y2, label, color, rad=0.0):
    ax.add_patch(patches.FancyArrowPatch(
        (x1, y1), (x2, y2),
        connectionstyle=f"arc3,rad={rad}",
        arrowstyle="->,head_width=5,head_length=7",
        color=color, lw=2.0, zorder=2,
    ))
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    if rad != 0:
        my += rad * 14
    ax.text(mx, my, label, fontsize=8, fontweight="bold", color=color,
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.2",
                      facecolor="#121214", edgecolor=color, lw=0.7),
            zorder=5)


def panel_A(ax):
    ax.set_title("A. Stochastic Circuit Architecture", fontsize=14,
                 fontweight="bold", color=CYAN, pad=12)
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)

    # ── Nodes ────────────────────────────────────────────────
    # MD Thalamus — Poisson Group (n=50)
    draw_node(ax, 20, 88, 26, 14,
              "MD Thalamus", "Poisson Group  n=50\n25 Hz / 0 Hz context switch",
              AMBER)

    # Sensory / PFC pathway input
    draw_node(ax, 80, 88, 26, 14,
              "Sensory/PFC", "Pathway A & B\n(0.5 × r_MD Hz)",
              CYAN)

    # VIP, SOM, PV interneurons
    draw_node(ax, 18, 54, 16, 13, "VIP",
              "Disinhibitor\n(p=0.3 from MD)", MAGENTA, shape="circle")
    draw_node(ax, 50, 54, 16, 13, "SOM",
              "Dendritic Gate\n40 Hz baseline",  MAGENTA, shape="circle")
    draw_node(ax, 18, 18, 16, 13, "PV",
              "Somatic Clamp\n(p=0.5 from MD)", MAGENTA, shape="circle")

    # Pyramidal dendrites
    ax.add_patch(patches.FancyBboxPatch(
        (56, 45), 28, 18, boxstyle="round,pad=1.0",
        edgecolor=GREEN, facecolor="#162216", lw=2.5, zorder=3))
    ax.text(70, 56.5, "Pyramidal Dendrites", fontsize=10,
            fontweight="bold", color=GREEN, ha="center")
    ax.text(70, 51,   "N = 30 branches", fontsize=8.5,
            color=WHITE, ha="center")
    ax.text(70, 47,   "Stochastic Ca²⁺ trace\n(Poisson spikes, CV_CA=0.30)",
            fontsize=7.5, color=MUTED, ha="center")

    # Pyramidal soma
    ax.add_patch(patches.FancyBboxPatch(
        (56, 9), 28, 18, boxstyle="round,pad=1.0",
        edgecolor=GREEN, facecolor="#162216", lw=2.5, zorder=3))
    ax.text(70, 21, "Pyramidal Soma",  fontsize=10,
            fontweight="bold", color=GREEN, ha="center")
    ax.text(70, 15, "Spiking output (Hz)", fontsize=8.5,
            color=WHITE, ha="center")

    # ── Arrows ───────────────────────────────────────────────
    # MD → VIP  (AMPA, context-selective, p=0.3 g=0.5 nS)
    draw_arrow(ax, 20, 81, 18, 61,
               "AMPA\np=0.3, g=0.5 nS", AMBER)

    # MD → PV  (AMPA, broad, p=0.5 g=0.12 nS)
    draw_arrow(ax, 20, 81, 18, 25,
               "AMPA\np=0.5, g=0.12 nS", AMBER, rad=-0.35)

    # Sensory → Dendrites  (AMPA+NMDA, plasticity)
    draw_arrow(ax, 80, 81, 70, 63,
               "AMPA / NMDA\n+ Graupner-Brunel ρ", CYAN, rad=-0.15)

    # VIP → SOM  (GABA-A, p=0.6, g=3.0 nS)
    draw_arrow(ax, 26, 54, 42, 54,
               "GABA-A\np=0.6, g=3 nS", MAGENTA)

    # SOM → Dendrites  (GABA-A/B, dendritic gate)
    draw_arrow(ax, 58, 54, 56, 54,
               "GABA-A/B\n(Dend gate)", MAGENTA)

    # PV → Soma  (GABA-A, somatic clamp, p=0.6 g=5 nS)
    draw_arrow(ax, 26, 18, 56, 18,
               "GABA-A\np=0.6, g=5 nS", MAGENTA)

    # Soma ↔ Dendrite coupling
    ax.add_patch(patches.FancyArrowPatch(
        (70, 45), (70, 27),
        arrowstyle="<->,head_width=5,head_length=7",
        color=GREEN, lw=2.3, zorder=4))
    ax.text(78.5, 36, "g_couple\nOhmic Axial", fontsize=8.5,
            fontweight="bold", color=GREEN, ha="center")

    ax.text(50, 3,
            "[NOTE] All rates stochastic: Poisson MD counts · CV_RATE=0.20 · "
            "NMDA vesicle CV=0.30 · sigma_rho=0.04",
            fontsize=7, color=AMBER, ha="center", style="italic")


# ────────────────────────────────────────────────────────────────────────────
# Panel B — Receptor kinetics + Mg²⁺ block
# ────────────────────────────────────────────────────────────────────────────
def panel_B(ax):
    ax.set_title("B. Receptor Conductance Kinetics & NMDA Mg²⁺ Block",
                 fontsize=14, fontweight="bold", color=CYAN, pad=12)

    t = np.linspace(0, 150, 600)

    # Receptor waveforms
    g_ampa = np.exp(-t / 2.0)
    g_gaba = np.exp(-t / 10.0)
    g_nmda = np.exp(-t / 80.0) - np.exp(-t / 2.0)
    g_nmda /= g_nmda.max()

    # Calcium-like kernel (bAP double-exponential used in model)
    TAU_RISE, TAU_DECAY = 2.0, 30.0
    norm = TAU_DECAY / (TAU_DECAY - TAU_RISE)
    g_ca = norm * (np.exp(-t / TAU_DECAY) - np.exp(-t / TAU_RISE))
    g_ca = np.clip(g_ca, 0, None)
    g_ca /= g_ca.max()

    ax.plot(t, g_ampa, color=CYAN,    lw=2.3, label="AMPA  (τ = 2 ms)")
    ax.plot(t, g_gaba, color=MAGENTA, lw=2.3, label="GABA-A (τ = 10 ms)")
    ax.plot(t, g_nmda, color=AMBER,   lw=2.3, label="NMDA  (τ_d = 80 ms)")
    ax.plot(t, g_ca,   color=GREEN,   lw=2.0, ls="--",
            label="bAP Ca²⁺ kernel\n(τ_r=2 ms, τ_d=30 ms)")

    ax.set_xlabel("Time after spike (ms)", fontsize=11)
    ax.set_ylabel("Normalised Conductance / Ca²⁺", fontsize=11)
    ax.set_xlim(0, 120)
    ax.set_ylim(-0.05, 1.15)
    ax.grid(True, ls="--", alpha=0.25)
    ax.legend(loc="upper right", frameon=True,
              facecolor="#121214", edgecolor=MUTED, fontsize=9)

    # Inset — Mg²⁺ block
    ins = ax.inset_axes([0.40, 0.30, 0.55, 0.42])
    v   = np.linspace(-90, 20, 300)
    mg  = 1.0 / (1.0 + np.exp(-0.062 * v) * (1.0 / 3.57))   # exact GB formula
    ins.plot(v, mg, color=GREEN, lw=2.2)
    ins.fill_between(v, mg, alpha=0.12, color=GREEN)
    ins.axvline(-55, color=AMBER, ls="--", lw=1.2,
                label="Resting V_dend")
    ins.set_title("NMDA Mg²⁺ Unblocking\n(voltage-dependent)", fontsize=8.5,
                  color=GREEN)
    ins.set_xlabel("V_dend (mV)", fontsize=8)
    ins.set_ylabel("Fraction Open", fontsize=8)
    ins.legend(fontsize=7.5, facecolor="#121214", edgecolor=MUTED)
    ins.grid(True, ls="--", alpha=0.2)
    ins.tick_params(labelsize=8)


# ────────────────────────────────────────────────────────────────────────────
# Panel C — Multi-compartment equations
# ────────────────────────────────────────────────────────────────────────────
def panel_C(ax):
    ax.set_title("C. Multi-Compartment Soma–Dendrite Model",
                 fontsize=14, fontweight="bold", color=CYAN, pad=12)
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)

    ax.add_patch(patches.FancyBboxPatch(
        (2, 2), 96, 96, boxstyle="round,pad=2.0",
        edgecolor=GREEN, facecolor="#0D1210", lw=1.8))

    lines = [
        ("PYRAMIDAL TWO-LAYER MULTI-COMPARTMENT MODEL", WHITE, 12, "bold"),
        ("─" * 62, MUTED, 9, "normal"),
        ("",  WHITE, 9, "normal"),
        ("• 1 Somatic compartment  +  N = 30 independent dendritic branches", WHITE, 10, "normal"),
        ("• Ohmic axial coupling:  I_couple,k = g_couple × (V_soma − V_dend,k)", GREEN, 10, "normal"),
        ("",  WHITE, 9, "normal"),
        ("DENDRITE ODE (branch k):", CYAN, 10, "bold"),
        ("   C_d dV_k/dt = −g_L(V_k − E_L) − I_syn,k − g_couple(V_k − V_soma)", WHITE, 10, "normal"),
        ("   I_syn,k = I_AMPA + I_NMDA(V_k, Mg²⁺) + I_GABA-A + I_GABA-B", MUTED, 9.5, "normal"),
        ("   NMDA Ca²⁺: stochastic Poisson spike train, CV_CA = 0.30", AMBER, 9.5, "normal"),
        ("",  WHITE, 9, "normal"),
        ("SOMA ODE (spiking output):", CYAN, 10, "bold"),
        ("   C_s dV_s/dt = −g_L(V_s − E_L) − I_soma − Σ_k I_couple,k", WHITE, 10, "normal"),
        ("   I_soma = I_GABA-A,PV  (somatic clamp from PV interneurons)", MUTED, 9.5, "normal"),
        ("",  WHITE, 9, "normal"),
        ("GATING LOGIC:", GREEN, 10, "bold"),
        ("   SOM ↑  →  V_dend depolarised  →  Mg²⁺ block stays ON  →  Ca²⁺ blocked", MAGENTA, 9.5, "normal"),
        ("   VIP ↑  →  SOM ↓  →  Mg²⁺ block relieved  →  NMDA open  →  Ca²⁺ spike  →  LTP", GREEN, 9.5, "normal"),
    ]
    y = 92
    for (txt, col, sz, wt) in lines:
        ax.text(5, y, txt, fontsize=sz, color=col,
                fontfamily="monospace", fontweight=wt, va="top")
        y -= (5.2 if sz >= 10 else 4.2)


# ────────────────────────────────────────────────────────────────────────────
# Panel D — Graupner-Brunel bistable double-well
# ────────────────────────────────────────────────────────────────────────────
def panel_D(ax):
    ax.set_title("D. Graupner-Brunel Bistable Double-Well Plasticity",
                 fontsize=14, fontweight="bold", color=CYAN, pad=12)

    rho = np.linspace(-0.05, 1.05, 400)
    U   = (0.25 * rho**4 - 0.5 * rho**3 + 0.25 * rho**2) * 10

    ax.plot(rho, U, color=CYAN, lw=3.0, label="Bistable Potential U(ρ)")
    ax.fill_between(rho, U, U.max(),
                    where=(rho <= 0.5),  color=MAGENTA, alpha=0.12,
                    label="LTD Basin (ρ → 0)")
    ax.fill_between(rho, U, U.max(),
                    where=(rho >= 0.5),  color=GREEN,   alpha=0.12,
                    label="LTP Basin (ρ → 1)")

    ax.scatter([0.0, 1.0], [0.0, 0.0], color=GREEN, s=130, zorder=5,
               label="Stable Attractors (0, 1)")
    u_star = (0.25*0.5**4 - 0.5*0.5**3 + 0.25*0.5**2) * 10
    ax.scatter([0.5], [u_star], color=AMBER, s=130, zorder=5,
               label="Unstable Threshold ρ* = 0.5")

    ax.axvline(0.5, color=AMBER, ls="--", lw=1.5, alpha=0.8)
    ax.text(0.53, 0.115, "ρ* = 0.5\nThreshold",
            color=AMBER, fontweight="bold", fontsize=10)
    ax.text(0.08, 0.025, "DOWN State\n(w = w₀)", color=MAGENTA,
            fontweight="bold", fontsize=10.5)
    ax.text(0.76, 0.025, "UP State\n(w = w₁)", color=GREEN,
            fontweight="bold", fontsize=10.5)

    # Noise annotation  — stochastic rho fluctuation around mean
    rho_ex = np.array([0.3, 0.35, 0.28, 0.32, 0.27, 0.25, 0.18, 0.12, 0.05])
    u_ex   = (0.25*rho_ex**4 - 0.5*rho_ex**3 + 0.25*rho_ex**2) * 10
    ax.plot(rho_ex, u_ex, color=AMBER, lw=1.4, ls=":", alpha=0.8,
            label="Example stochastic trajectory (σ_ρ = 0.04)")
    ax.annotate("", xy=(0.05, u_ex[-1]),
                xytext=(0.12, u_ex[-3]),
                arrowprops=dict(arrowstyle="->", color=AMBER, lw=1.2))

    ax.set_xlabel("Synaptic Efficacy State Variable ρ", fontsize=11)
    ax.set_ylabel("Potential Energy U(ρ)", fontsize=11)
    ax.set_xlim(-0.05, 1.1)
    ax.set_ylim(-0.02, 0.185)
    ax.grid(True, ls="--", alpha=0.22)
    ax.legend(loc="upper center", frameon=True,
              facecolor="#121214", edgecolor=MUTED, fontsize=9, ncol=2)


# ────────────────────────────────────────────────────────────────────────────
# Assemble figure
# ────────────────────────────────────────────────────────────────────────────
def generate_figure():
    fig = plt.figure(figsize=(18, 12), dpi=200,
                     facecolor=plt.rcParams["figure.facecolor"])
    gs  = GridSpec(2, 2, width_ratios=[1.1, 1],
                   height_ratios=[1.1, 1], hspace=0.36, wspace=0.28)

    panel_A(fig.add_subplot(gs[0, 0]))
    panel_B(fig.add_subplot(gs[0, 1]))
    panel_C(fig.add_subplot(gs[1, 0]))
    panel_D(fig.add_subplot(gs[1, 1]))

    fig.suptitle(
        "Thalamocortical Gating Project — Network & Synaptic Architecture\n"
        "Stochastic Graupner-Brunel Model  |  Aug 2026",
        fontsize=15, fontweight="bold", color=WHITE, y=1.005,
    )

    plt.savefig(OUT_PATH, dpi=200, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"✓  Figure saved to: {OUT_PATH}")


if __name__ == "__main__":
    generate_figure()
