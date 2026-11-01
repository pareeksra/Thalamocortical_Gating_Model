"""
generate_network_diagram.py
============================
Generates the network wiring diagram for Model A: boxes for each population,
arrows for each synaptic projection, labelled with the connection probability
and synaptic weight actually defined in model/parameters.py. No panels of
equations or free-energy landscapes -- this figure documents connectivity
only, in the style of a standard circuit schematic for a methods figure.

Excitatory synapses are drawn as arrows; inhibitory synapses are drawn with
an open-circle terminal (standard convention). The plastic pathway synapse
(subject to the Graupner-Brunel rule) is dashed.

Run from the project root:
    python experiments/generate_network_diagram.py
"""
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
from matplotlib.lines import Line2D

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
from brian2 import nS
from parameters import params, pv_params, som_params, vip_params, md_params

G_MD2VIP = float(vip_params['gAMPA_vip'] / nS)
G_MD2PV = float(pv_params['gAMPA_pv'] / nS)
G_VIP2SOM = float(som_params['gGABA_som'] / nS)
G_SOM2DEND = float(params['gGABA'] / nS)
G_PV2SOMA = float(pv_params['gGABA_pv2soma'] / nS)
G_COUPLE_VIVO = float(params['gEachCouple_pyr_vivo'] / nS)

OUT_PATH = os.path.join(PROOT, 'figures', 'network_architecture.png')

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 10,
})

FACE = "white"
EDGE = "black"
LW = 1.1


def box(ax, xy, w, h, label, sublabel=None):
    x, y = xy
    p = FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                        boxstyle="round,pad=0.02,rounding_size=0.06",
                        facecolor=FACE, edgecolor=EDGE, linewidth=LW, zorder=3)
    ax.add_patch(p)
    if sublabel:
        ax.text(x, y + 0.09, label, ha='center', va='center',
                 fontsize=10.5, fontweight='bold', zorder=4)
        ax.text(x, y - 0.14, sublabel, ha='center', va='center',
                 fontsize=8.3, zorder=4)
    else:
        ax.text(x, y, label, ha='center', va='center',
                 fontsize=10.5, fontweight='bold', zorder=4)
    return (x, y, w, h)


def _edge_point(box_xy, box_w, box_h, toward_xy):
    """Point on the rectangle boundary of a box, facing toward another point."""
    bx, by = box_xy
    tx, ty = toward_xy
    dx, dy = tx - bx, ty - by
    if dx == 0 and dy == 0:
        return bx, by
    sx = (box_w / 2) / abs(dx) if dx != 0 else float('inf')
    sy = (box_h / 2) / abs(dy) if dy != 0 else float('inf')
    s = min(sx, sy)
    return bx + dx * s, by + dy * s


def _place_label(ax, p0, p1, label, curve):
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    if abs(dy) > abs(dx):
        ax.text(mx + 0.18, my - 0.35, label, ha='left', va='center',
                 fontsize=7.6, zorder=5,
                 bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                            edgecolor='none', alpha=0.85))
    else:
        ax.text(mx, my + 0.12 + abs(curve) * 0.6, label, ha='center', va='bottom',
                 fontsize=7.6, zorder=5,
                 bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                            edgecolor='none', alpha=0.85))


def excitatory(ax, src, dst, label, curve=0.0):
    (sx, sy, sw, sh) = src
    (dx, dy, dw, dh) = dst
    p0 = _edge_point((sx, sy), sw, sh, (dx, dy))
    p1 = _edge_point((dx, dy), dw, dh, (sx, sy))
    arr = FancyArrowPatch(p0, p1, arrowstyle='-|>', mutation_scale=14,
                           color=EDGE, linewidth=LW,
                           connectionstyle=f"arc3,rad={curve}", zorder=2)
    ax.add_patch(arr)
    _place_label(ax, p0, p1, label, curve)


def inhibitory(ax, src, dst, label, curve=0.0):
    (sx, sy, sw, sh) = src
    (dx, dy, dw, dh) = dst
    p0 = _edge_point((sx, sy), sw, sh, (dx, dy))
    p1 = _edge_point((dx, dy), dw, dh, (sx, sy))
    r = 0.045
    ux, uy = (p1[0] - p0[0]), (p1[1] - p0[1])
    n = (ux ** 2 + uy ** 2) ** 0.5
    ux, uy = ux / n, uy / n
    p1_short = (p1[0] - ux * r * 2, p1[1] - uy * r * 2)
    arr = FancyArrowPatch(p0, p1_short, arrowstyle='-', mutation_scale=14,
                           color=EDGE, linewidth=LW,
                           connectionstyle=f"arc3,rad={curve}", zorder=2)
    ax.add_patch(arr)
    circ = Circle(p1_short, r, facecolor='white', edgecolor=EDGE,
                   linewidth=LW, zorder=3)
    ax.add_patch(circ)
    _place_label(ax, p0, p1, label, curve)


def plastic(ax, src, dst, label):
    (sx, sy, sw, sh) = src
    (dx, dy, dw, dh) = dst
    p0 = _edge_point((sx, sy), sw, sh, (dx, dy))
    p1 = _edge_point((dx, dy), dw, dh, (sx, sy))
    arr = FancyArrowPatch(p0, p1, arrowstyle='-|>', mutation_scale=14,
                           color=EDGE, linewidth=LW, linestyle=(0, (5, 3)), zorder=2)
    ax.add_patch(arr)
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    ax.text(mx + 0.35, my, label, ha='left', va='center', fontsize=7.6, zorder=5,
             bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                        edgecolor='none', alpha=0.85))


def coupling(ax, src, dst, label):
    (sx, sy, sw, sh) = src
    (dx, dy, dw, dh) = dst
    p0 = _edge_point((sx, sy), sw, sh, (dx, dy))
    p1 = _edge_point((dx, dy), dw, dh, (sx, sy))
    arr = FancyArrowPatch(p0, p1, arrowstyle='<|-|>', mutation_scale=12,
                           color=EDGE, linewidth=LW, zorder=2)
    ax.add_patch(arr)
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    ax.text(mx + 0.42, my, label, ha='left', va='center', fontsize=7.6, zorder=5)


def main():
    fig, ax = plt.subplots(figsize=(9.0, 7.2))
    ax.set_xlim(-0.3, 8.6)
    ax.set_ylim(-0.4, 7.4)
    ax.set_aspect('equal')
    ax.axis('off')

    md = box(ax, (1.1, 6.6), 2.0, 0.85, 'MD thalamus',
              f"PoissonGroup, n={md_params['n_md']}")
    pathway = box(ax, (6.3, 6.6), 2.4, 0.85, 'Cortical pathway',
                   'PoissonGroup, n=30, 80 Hz')

    vip = box(ax, (0.9, 4.6), 1.7, 0.85, 'VIP',
               f"n={md_params['n_vip_spike']}")
    pv = box(ax, (3.0, 4.6), 1.7, 0.85, 'PV',
              f"n={md_params['n_pv']}")

    som = box(ax, (0.9, 2.6), 1.7, 0.85, 'SOM',
               f"n={md_params['n_som_spike']}")

    dend = box(ax, (5.6, 2.6), 2.6, 0.9, 'Pyramidal dendrites',
                '2 branches (Phase-1 protocol)')
    soma = box(ax, (3.0, 0.4), 2.0, 0.85, 'Pyramidal soma',
                'spiking output')

    excitatory(ax, md, vip, f"AMPA\np={md_params['p_md2vip']}, g={G_MD2VIP:.2f} nS")
    excitatory(ax, md, pv, f"AMPA\np={md_params['p_md2pv']}, g={G_MD2PV:.2f} nS", curve=-0.15)

    inhibitory(ax, vip, som, f"GABA-A\np={md_params['p_vip2som_spike']}, g={G_VIP2SOM:.2f} nS")
    inhibitory(ax, som, dend, f"GABA-A\np={md_params['p_som2dend_spike']}, g={G_SOM2DEND:.2f} nS")
    inhibitory(ax, pv, soma, f"GABA-A\np={md_params['p_pv2soma']}, g={G_PV2SOMA:.2f} nS")

    plastic(ax, pathway, dend, "AMPA/NMDA, plastic\n(Graupner-Brunel ρ)")
    coupling(ax, dend, soma, f"ohmic coupling, g_c\n(in-vivo: {G_COUPLE_VIVO:.1f} nS)")

    legend_elems = [
        Line2D([0], [0], color=EDGE, lw=LW, marker='>', markersize=6,
                markerfacecolor=EDGE, linestyle='-', label='Excitatory (AMPA/NMDA)'),
        Line2D([0], [0], color=EDGE, lw=LW, marker='o', markersize=7,
                markerfacecolor='white', markeredgecolor=EDGE, linestyle='-',
                label='Inhibitory (GABA-A)'),
        Line2D([0], [0], color=EDGE, lw=LW, linestyle=(0, (5, 3)),
                label='Plastic (Graupner-Brunel)'),
    ]
    ax.legend(handles=legend_elems, loc='lower left', frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.0, -0.06))

    ax.set_title('Model A network connectivity', fontsize=12, fontweight='bold', pad=14)

    fig.tight_layout()
    fig.savefig(OUT_PATH, dpi=200, bbox_inches='tight', facecolor='white')
    print('Saved', OUT_PATH)


if __name__ == '__main__':
    main()
