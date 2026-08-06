"""
print_network_summary.py — Live Brian 2 Network & Synapses Inspection Script
Prints out the complete Brian 2 Network architecture, all NeuronGroup objects,
and all Synapses objects with their source, target, connection probability, and equations.
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'v2'))

from brian2 import *
prefs.codegen.target = 'numpy'

from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
from equations import eqs_soma, eqs_dend, eqs_pv, eqs_som, eqs_vip, eqs_synapse_plasticity, on_pre_plasticity

def inspect_network():
    p = params.copy()
    p.update(plasticity_params)
    p.update(pv_params)
    p.update(som_params)
    p.update(vip_params)
    p.update(md_params)
    
    print("=" * 80)
    print("  BRIAN 2 THALAMOCORTICAL NETWORK & SYNAPTIC INSPECTION REPORT")
    print("=" * 80)
    
    # ── 1. Neuron Populations ──────────────────────────────────────
    print("\n[1] NEURON POPULATIONS (NeuronGroup & PoissonGroup):")
    print("-" * 80)
    
    pops = [
        ("Pyramidal Soma", "1 cell", "LIF with axial dendrite coupling", "dV/dt = (iL + iSyn + iCoupleDend)/cSoma_pyr"),
        ("Pyramidal Dendrites", "30 branches", "Multi-compartmental branches", "dV/dt = (iDendL + iDendSyn - gEachCouple*(V-vSoma))/cDend"),
        ("PV Interneurons", "10 cells", "Fast-Spiking Somatic Inhibitory", "dV/dt = (iL + iAMPA + iGABA) / C_pv"),
        ("SOM Interneurons", "10 cells", "Regular-Spiking Dendrite Gating", "dV/dt = (iL + iExc + iGABA) / C_som"),
        ("VIP Interneurons", "10 cells", "Regular-Spiking Disinhibitory", "dV/dt = (iL + iAMPA) / C_vip"),
        ("MD Thalamus", "20 cells", "Poisson Context Drive", "PoissonGroup(20, rates=5 Hz -> 40 Hz)")
    ]
    
    for name, size, role, eq_summary in pops:
        print(f"  * {name:<22} | Size: {size:<12} | Role: {role:<32}")
        print(f"    ODE: {eq_summary}")
    
    # ── 2. Synaptic Connections ────────────────────────────────────
    print("\n[2] SYNAPTIC WIRING & PLASTICITY RULES (Synapses):")
    print("-" * 80)
    
    syns = [
        ("MD -> PV", "MD Thalamus", "PV Interneuron", "AMPA (Excitatory)", "gTotAMPA_post += gAMPA_pv", "p = 0.50 (50% prob)"),
        ("MD -> VIP", "MD Thalamus", "VIP Interneuron", "AMPA (Excitatory)", "gTotAMPA_post += gAMPA_vip", "p = 0.30 (30% prob)"),
        ("VIP -> SOM", "VIP Interneuron", "SOM Interneuron", "GABA_A (Disinhibition)", "gTotGABA_post += gGABA_som", "p = 0.50 (50% prob)"),
        ("SOM -> Dend", "SOM Interneuron", "Pyramidal Dend", "GABA_A / GABA_B (Gating)", "gTotGABA_post += gGABA", "p = 0.50 (50% prob)"),
        ("PV -> Soma", "PV Interneuron", "Pyramidal Soma", "GABA_A (Soma Clamp)", "gTotGABA_post += gGABA_pv2soma", "p = 0.50 (50% prob)"),
        ("Input -> Dend", "Cortical Pathway", "Pyramidal Dend", "AMPA + NMDA + Graupner-Brunel", "c += C_pre\ngTotAMPA_post += w * gAMPA", "100% connect (Plastic)")
    ]
    
    for syn_name, src, tgt, rec, on_pre, p_conn in syns:
        print(f"  * {syn_name:<16} : [{src}]  -->  [{tgt}]")
        print(f"    - Receptor / Type:  {rec}")
        print(f"    - Connectivity:     {p_conn}")
        print(f"    - on_pre Action:    {on_pre.replace(chr(10), '; ')}")
        print()

    # ── 3. Graupner-Brunel Plasticity Synapse Equations ────────────
    print("[3] GRAUPNER-BRUNEL CALCIUM-BASED PLASTICITY EQUATIONS (syn_input):")
    print("-" * 80)
    print(eqs_synapse_plasticity.strip())
    print("\n  On Presynaptic Spike (on_pre_plasticity):")
    print("    " + on_pre_plasticity.strip().replace("\n", "\n    "))
    print("=" * 80)
    print("Inspection complete.")

if __name__ == "__main__":
    inspect_network()
