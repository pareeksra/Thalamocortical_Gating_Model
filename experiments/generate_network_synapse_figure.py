"""
generate_network_synapse_figure.py
Generates a comprehensive 4-panel high-quality figure illustrating:
Panel A: Complete Network Architecture & Synaptic Wiring (with receptor types)
Panel B: Receptor Kinetics (AMPA, GABA_A, NMDA waveforms & Mg2+ voltage block)
Panel C: Multi-Compartmental Soma-Dendrite Electrical Coupling
Panel D: Graupner-Brunel Bistable Double-Well Synaptic Plasticity Potential
"""
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec

# Dark theme matching our presentation style
plt.style.use('dark_background')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Segoe UI', 'Arial', 'DejaVu Sans']

def generate_pi_figure():
    fig = plt.figure(figsize=(16, 11), dpi=200)
    gs = GridSpec(2, 2, width_ratios=[1.1, 1], height_ratios=[1.1, 1], hspace=0.32, wspace=0.25)

    # Colors
    CYAN = '#00BCD4'
    MAGENTA = '#E91E63'
    AMBER = '#FFC107'
    GREEN = '#4CAF50'
    PURPLE = '#9C27B0'
    WHITE = '#F0F0F5'
    MUTED = '#9E9E9E'
    BOX_BG = '#1A1A24'

    # ==========================================
    # PANEL A: Complete Network & Synaptic Wiring Diagram
    # ==========================================
    ax_a = fig.add_subplot(gs[0, 0])
    ax_a.set_title("A. Network Architecture & Synaptic Wiring", fontsize=16, fontweight='bold', color=CYAN, pad=15)
    ax_a.axis('off')
    ax_a.set_xlim(0, 100)
    ax_a.set_ylim(0, 100)

    def draw_node(ax, x, y, width, height, label, sublabel, color, shape='box'):
        if shape == 'box':
            box = patches.FancyBboxPatch((x - width/2, y - height/2), width, height,
                                         boxstyle="round,pad=1.5", edgecolor=color,
                                         facecolor=BOX_BG, lw=2.5, zorder=3)
            ax.add_patch(box)
        else:
            circle = patches.Circle((x, y), width/2, edgecolor=color, facecolor=BOX_BG, lw=2.5, zorder=3)
            ax.add_patch(circle)
        
        ax.text(x, y + 2, label, fontsize=12, fontweight='bold', color=color, ha='center', va='center', zorder=4)
        ax.text(x, y - 4, sublabel, fontsize=9, color=WHITE, ha='center', va='center', zorder=4)

    def draw_arrow(ax, x1, y1, x2, y2, label, color, style='-', rad=0.0):
        arrow = patches.FancyArrowPatch((x1, y1), (x2, y2),
                                        connectionstyle=f"arc3,rad={rad}",
                                        arrowstyle="->,head_width=6,head_length=8",
                                        color=color, lw=2.2, linestyle=style, zorder=2)
        ax.add_patch(arrow)
        # Label position
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        if rad != 0:
            my += rad * 15
        ax.text(mx, my, label, fontsize=9, fontweight='bold', color=color,
                ha='center', va='center', bbox=dict(boxstyle='round,pad=0.2', facecolor='#121214', edgecolor=color, lw=0.8), zorder=5)

    # Draw Nodes
    draw_node(ax_a, 20, 85, 24, 14, "MD Thalamus", "Context Drive", AMBER)
    draw_node(ax_a, 80, 85, 26, 14, "Sensory / PFC", "Pathway A & B", CYAN)
    
    draw_node(ax_a, 20, 50, 18, 14, "VIP", "Interneuron", MAGENTA, shape='circle')
    draw_node(ax_a, 50, 50, 18, 14, "SOM", "Interneuron", MAGENTA, shape='circle')
    draw_node(ax_a, 20, 15, 18, 14, "PV", "Fast-Spiking", MAGENTA, shape='circle')
    
    # Multi-compartment Pyramidal
    dend_box = patches.FancyBboxPatch((70 - 14, 50 - 9), 28, 18, boxstyle="round,pad=1.0", edgecolor=GREEN, facecolor='#162216', lw=2.5, zorder=3)
    ax_a.add_patch(dend_box)
    ax_a.text(70, 53, "Pyramidal Dendrites", fontsize=11, fontweight='bold', color=GREEN, ha='center')
    ax_a.text(70, 45, "(N=30 Branches)", fontsize=9, color=WHITE, ha='center')

    soma_box = patches.FancyBboxPatch((70 - 14, 15 - 9), 28, 18, boxstyle="round,pad=1.0", edgecolor=GREEN, facecolor='#162216', lw=2.5, zorder=3)
    ax_a.add_patch(soma_box)
    ax_a.text(70, 18, "Pyramidal Soma", fontsize=11, fontweight='bold', color=GREEN, ha='center')
    ax_a.text(70, 10, "Spiking Output (Hz)", fontsize=9, color=WHITE, ha='center')

    # Draw Synaptic Connections with Receptors
    draw_arrow(ax_a, 80, 77, 70, 60, "AMPA / NMDA\n(+ Ca2+ Plasticity)", CYAN, rad=-0.1)
    draw_arrow(ax_a, 20, 77, 20, 58, "AMPA (MD→VIP)", AMBER)
    draw_arrow(ax_a, 20, 77, 20, 23, "AMPA (MD→PV)", AMBER, rad=-0.35)
    
    draw_arrow(ax_a, 29, 50, 41, 50, "GABA_A (Inhib)", MAGENTA)
    draw_arrow(ax_a, 59, 50, 68, 50, "GABA_A / B\n(Dend Gate)", MAGENTA)
    draw_arrow(ax_a, 29, 15, 55, 15, "GABA_A\n(Soma Clamp)", MAGENTA)

    # Ohmic Coupling arrow
    coupling = patches.FancyArrowPatch((70, 40), (70, 25), arrowstyle="<->,head_width=6,head_length=8", color=GREEN, lw=2.5, zorder=4)
    ax_a.add_patch(coupling)
    ax_a.text(78, 32.5, "g_couple\nOhmic Axial", fontsize=9, fontweight='bold', color=GREEN, ha='center')

    # ==========================================
    # PANEL B: Synaptic Receptor Kinetics & Mg2+ Block
    # ==========================================
    ax_b = fig.add_subplot(gs[0, 1])
    ax_b.set_title("B. Receptor Conductance Kinetics & NMDA Mg2+ Block", fontsize=16, fontweight='bold', color=CYAN, pad=15)
    
    t = np.linspace(0, 150, 500)
    # AMPA: tau = 2 ms
    g_ampa = np.exp(-t / 2.0)
    # GABA: tau = 10 ms
    g_gaba = np.exp(-t / 10.0)
    # NMDA: rise tau = 2 ms, decay = 80 ms
    g_nmda = (np.exp(-t / 80.0) - np.exp(-t / 2.0))
    g_nmda /= np.max(g_nmda)

    ax_b.plot(t, g_ampa, color=CYAN, lw=2.5, label="AMPA (τ = 2 ms)")
    ax_b.plot(t, g_gaba, color=MAGENTA, lw=2.5, label="GABA_A (τ = 10 ms)")
    ax_b.plot(t, g_nmda, color=AMBER, lw=2.5, label="NMDA (τ_decay = 80 ms)")
    
    ax_b.set_xlabel("Time after spike (ms)", fontsize=12, color=WHITE)
    ax_b.set_ylabel("Normalized Conductance g(t)", fontsize=12, color=WHITE)
    ax_b.set_xlim(0, 120)
    ax_b.set_ylim(0, 1.1)
    ax_b.grid(True, linestyle='--', alpha=0.2)
    ax_b.legend(loc="upper right", frameon=True, facecolor='#121214', edgecolor=MUTED, fontsize=10)

    # Inset for Mg2+ Voltage Sigmoid
    ax_b_ins = ax_b.inset_axes([0.45, 0.35, 0.5, 0.4])
    v_mv = np.linspace(-90, 20, 200)
    v_half = -20.0
    v_spread = 10.0
    mg_block = 1.0 / (1.0 + np.exp(-(v_mv - v_half) / v_spread))
    ax_b_ins.plot(v_mv, mg_block, color=GREEN, lw=2.2)
    ax_b_ins.set_title("NMDA Voltage Mg2+ Unblocking", fontsize=9, color=GREEN)
    ax_b_ins.set_xlabel("Membrane Potential V (mV)", fontsize=8)
    ax_b_ins.set_ylabel("Fraction Open", fontsize=8)
    ax_b_ins.grid(True, linestyle='--', alpha=0.2)
    ax_b_ins.tick_params(labelsize=8)

    # ==========================================
    # PANEL C: Multi-Compartment Soma-Dendrite Equations
    # ==========================================
    ax_c = fig.add_subplot(gs[1, 0])
    ax_c.set_title("C. Multi-Compartment Soma-Dendrite Circuit & Equations", fontsize=16, fontweight='bold', color=CYAN, pad=15)
    ax_c.axis('off')
    ax_c.set_xlim(0, 100)
    ax_c.set_ylim(0, 100)

    eq_box = patches.FancyBboxPatch((5, 5), 90, 90, boxstyle="round,pad=2.0", edgecolor=GREEN, facecolor='#121518', lw=2.0)
    ax_c.add_patch(eq_box)

    eq_text = (
        "PYRAMIDAL TWO-LAYER MULTI-COMPARTMENT MODEL\n"
        "──────────────────────────────────────────────────────────\n"
        "• 1 Somatic Spiking Compartment  +  N=30 Independent Dendritic Branches\n"
        "• Ohmic Axial Coupling Current between Soma and Dendrite k:\n"
        "       I_couple,k = g_couple * (V_soma - V_dend,k)\n\n"
        "1. DENDRITE MEMBRANE ODE (Branch k ∈ 1...30):\n"
        "    C_dend * dV_k/dt = -g_L*(V_k - E_L) - I_Syn,k - g_couple*(V_k - V_soma)\n"
        "    where I_Syn,k = I_AMPA + I_NMDA(V_k, Mg2+) + I_GABA_A + I_GABA_B\n\n"
        "2. SOMATIC MEMBRANE ODE (Spiking Output):\n"
        "    C_soma * dV_soma/dt = -g_L*(V_soma - E_L) - I_soma_Syn - Σ I_couple,k\n"
        "    where SOMATIC INHIBITION (PV→Soma): I_soma_Syn = g_GABA_PV * (V_soma - E_I)\n\n"
        "• BIOPHYSICAL GATING LOGIC:\n"
        "    SOM interneurons locally clamp V_dend,k -> prevents NMDA Mg2+ unblocking\n"
        "    VIP interneurons silence SOM -> allows Dendritic Ca2+ Spikes & LTP"
    )
    ax_c.text(10, 50, eq_text, fontsize=11, color=WHITE, fontfamily='monospace', va='center')

    # ==========================================
    # PANEL D: Graupner-Brunel Bistable Double-Well Potential
    # ==========================================
    ax_d = fig.add_subplot(gs[1, 1])
    ax_d.set_title("D. Graupner-Brunel Bistable Double-Well Plasticity", fontsize=16, fontweight='bold', color=CYAN, pad=15)

    rho = np.linspace(-0.1, 1.1, 300)
    U_rho = 0.25 * (rho**4) - 0.5 * (rho**3) + 0.25 * (rho**2)
    U_rho *= 10  # scale for visual clarity

    ax_d.plot(rho, U_rho, color=CYAN, lw=3.0, label="Bistable Potential U(ρ)")
    ax_d.fill_between(rho, U_rho, max(U_rho), where=(rho <= 0.5), color=MAGENTA, alpha=0.15, label="LTD Basin (ρ → 0)")
    ax_d.fill_between(rho, U_rho, max(U_rho), where=(rho > 0.5), color=GREEN, alpha=0.15, label="LTP Basin (ρ → 1)")

    ax_d.scatter([0.0, 1.0], [0.0, 0.0], color=GREEN, s=120, zorder=5, label="Stable Attractors (0, 1)")
    ax_d.scatter([0.5], [(0.25*0.5**4 - 0.5*0.5**3 + 0.25*0.5**2)*10], color=AMBER, s=120, zorder=5, label="Unstable Threshold ρ* = 0.5")

    ax_d.axvline(0.5, color=AMBER, linestyle='--', lw=1.5, alpha=0.8)
    ax_d.text(0.52, 0.12, "ρ* = 0.5\nThreshold", color=AMBER, fontweight='bold', fontsize=10)
    ax_d.text(0.05, 0.03, "DOWN State\n(w = w_0)", color=MAGENTA, fontweight='bold', fontsize=11)
    ax_d.text(0.75, 0.03, "UP State\n(w = w_1)", color=GREEN, fontweight='bold', fontsize=11)

    ax_d.set_xlabel("Synaptic Efficacy State Variable ρ", fontsize=12, color=WHITE)
    ax_d.set_ylabel("Potential Energy U(ρ)", fontsize=12, color=WHITE)
    ax_d.set_xlim(-0.1, 1.1)
    ax_d.set_ylim(-0.02, 0.18)
    ax_d.grid(True, linestyle='--', alpha=0.2)
    ax_d.legend(loc="upper center", frameon=True, facecolor='#121214', edgecolor=MUTED, fontsize=10, ncol=2)

    os.makedirs("figures", exist_ok=True)
    out_path = os.path.join("figures", "network_synaptic_architecture.png")
    plt.savefig(out_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    print(f"PI Network & Synaptic Architecture figure saved to: {os.path.abspath(out_path)}")

if __name__ == "__main__":
    generate_pi_figure()
