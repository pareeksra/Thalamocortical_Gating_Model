"""
demo_v2_zhang2025.py — Context-switching simulation with MD Thalamocortical Drive.

This script tests the hypothesis from Zhang et al. 2025:
Can thalamocortical drive (MD) act as a "meta-controller" that determines
WHICH dendritic branches undergo plasticity, by simultaneously controlling
somatic excitability (via PV) and branch-specific disinhibition (via VIP→SOM)?

Architecture:
  MD Thalamus (PoissonGroup, controllable rate)
    ├─→ PV (fast-spiking LIF) ──→ Pyramidal Soma (inhibition)
    └─→ VIP (LIF) ──→ SOM (LIF) ──→ Pyramidal Dendrites (inhibition)
                        ↑ baseline excitation
"""
import sys, os
import numpy as np
import matplotlib.pyplot as plt

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'model'))

from brian2 import *
prefs.codegen.target = 'numpy'

from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
from equations import (attach_rho_clipper, eqs_soma, eqs_dend, eqs_pv, eqs_som, eqs_vip,
                       eqs_synapse_plasticity, on_pre_plasticity)

def main():
    print('=' * 60)
    print(' Zhang 2025 — MD Thalamocortical Drive Demo')
    print('=' * 60)

    # Merge all parameter dictionaries
    p = params.copy()
    p.update(plasticity_params)
    p.update(pv_params)
    p.update(som_params)
    p.update(vip_params)
    p.update(md_params)

    # Demo-scale network
    num_pyr = 1
    num_dend_each = 2
    num_pv = p['n_pv']
    num_som = p['n_som_spike']
    num_vip = p['n_vip_spike']
    num_md = p['n_md']

    p['num_Soma'] = num_pyr
    p['num_DendEach'] = num_dend_each
    p['num_Dend'] = num_pyr * num_dend_each
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * num_dend_each

    temp = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']
    p['norm_factor_Ca'] = temp ** (1 / (temp - 1))
    temp = p['tauGABABRise'] / p['tauGABABDecay']
    p['norm_factor_GABAB'] = temp ** (1 / (temp - 1))

    net = Network()

    # ── 1. Pyramidal Neuron (Soma + Dendrites) ──────────────────
    print('[1/7] Building pyramidal neuron...')
    reset_eqs = 'V = vReset_pyr'
    Soma = NeuronGroup(num_pyr, eqs_soma, threshold='V > vThres_pyr',
                       reset=reset_eqs, refractory=p['refracTime_pyr'],
                       method='euler', namespace=p)
    Soma.V = p['vRest_pyr']
    Soma.vShadow = p['vRest_pyr']
    Soma.vAveDend = p['vRest_pyr']

    Dend = NeuronGroup(p['num_Dend'], eqs_dend, method='euler', namespace=p)
    Dend.V = p['vRest_pyr']
    Dend.vSoma = p['vRest_pyr']

    # Soma↔Dendrite coupling
    @network_operation(dt=p['sim_dt'])
    def SomaDendCoupling():
        temp = Dend.V[:].reshape((num_pyr, num_dend_each))
        Soma.vAveDend = np.mean(temp, axis=1)
        Dend.vSoma = np.repeat(Soma.vShadow[:], num_dend_each)

    # bAP delivery
    bAP = Synapses(Soma, Dend, on_pre='V_post += bAP_amp\nbAPCa_rise_post += norm_factor_Ca', delay=p['bAP_delay'], namespace=p)
    bAP.connect(j='i*num_DendEach + k for k in range(num_DendEach)')

    net.add([Soma, Dend, SomaDendCoupling, bAP])

    # ── 2. PV Interneurons ──────────────────────────────────────
    print('[2/7] Building PV interneurons...')
    PV = NeuronGroup(num_pv, eqs_pv, threshold='V > vThres_pv',
                     reset='V = vReset_pv', refractory=p['refrac_pv'],
                     method='euler', namespace=p)
    PV.V = p['vRest_pv']

    # Tonic background drive giving PV a baseline it can be modulated around.
    BG_pv = PoissonGroup(num_pv, rates=p['rate_bg_pv'])
    syn_bg_pv = Synapses(BG_pv, PV, on_pre='gTotAMPA_post += weight_bg_pv',
                         namespace=p)
    syn_bg_pv.connect(j='i')
    net.add([PV, BG_pv, syn_bg_pv])

    # ── 3. SOM Interneurons ─────────────────────────────────────
    print('[3/7] Building SOM interneurons...')
    SOM = NeuronGroup(num_som, eqs_som, threshold='V > vThres_som',
                      reset='V = vReset_som', refractory=p['refrac_som'],
                      method='euler', namespace=p)
    SOM.V = p['vRest_som']
    # Baseline excitatory drive to keep SOM firing (~10 Hz at rest)
    SOM.iBaseline_som = 22.0 * pA  # ~30 Hz baseline (rheobase ≈ 20 pA)
    net.add(SOM)

    # ── 4. VIP Interneurons ─────────────────────────────────────
    print('[4/7] Building VIP interneurons...')
    VIP = NeuronGroup(num_vip, eqs_vip, threshold='V > vThres_vip',
                      reset='V = vReset_vip', refractory=p['refrac_vip'],
                      method='euler', namespace=p)
    VIP.V = p['vRest_vip']
    net.add(VIP)

    # ── 5. MD Thalamus ──────────────────────────────────────────
    print('[5/7] Building MD Thalamus...')
    # Start at low rate; we will change it mid-simulation
    MD = PoissonGroup(num_md, rates=5*Hz)
    net.add(MD)

    # ── 6. Wire the Circuit ─────────────────────────────────────
    print('[6/7] Wiring circuit...')

    # MD → PV (excitatory AMPA)
    syn_md2pv = Synapses(MD, PV, on_pre='gTotAMPA_post += gAMPA_pv', namespace=p)
    syn_md2pv.connect(p=p['p_md2pv'])

    # MD → VIP (excitatory AMPA)
    syn_md2vip = Synapses(MD, VIP, on_pre='gTotAMPA_post += gAMPA_vip', namespace=p)
    syn_md2vip.connect(p=p['p_md2vip'])

    # VIP → SOM (inhibitory GABA, disinhibition pathway)
    syn_vip2som = Synapses(VIP, SOM, on_pre='gTotGABA_post += gGABA_som', namespace=p)
    syn_vip2som.connect(p=p['p_vip2som_spike'])

    # SOM → Dendrites (inhibitory GABA)
    syn_som2dend = Synapses(SOM, Dend, on_pre='gTotGABA_post += gGABA', namespace=p)
    syn_som2dend.connect(p=p['p_som2dend_spike'])

    # PV → Pyramidal Soma (inhibitory GABA, strong fast inhibition)
    syn_pv2soma = Synapses(PV, Soma, on_pre='gTotGABA_post += gGABA_pv2soma', namespace=p)
    syn_pv2soma.connect(p=p['p_pv2soma'])

    # Excitatory input pathways → Dendrites (with plasticity)
    pathway_input = PoissonGroup(30, rates=80*Hz)
    syn_input = Synapses(pathway_input, Dend, model=eqs_synapse_plasticity,
                         on_pre=on_pre_plasticity, method='heun', namespace=p)
    syn_input.connect()
    syn_input.rho = 0.5  # Start at mid-point
    attach_rho_clipper(syn_input)

    net.add([syn_md2pv, syn_md2vip, syn_vip2som, syn_som2dend, syn_pv2soma,
             pathway_input, syn_input])

    # ── Monitors ────────────────────────────────────────────────
    mon_soma = StateMonitor(Soma, 'V', record=True, dt=1*ms)
    mon_pv_spike = SpikeMonitor(PV)
    mon_som_spike = SpikeMonitor(SOM)
    mon_vip_spike = SpikeMonitor(VIP)
    mon_soma_spike = SpikeMonitor(Soma)
    mon_w = StateMonitor(syn_input, 'w', record=[0, 1], dt=50*ms)  # Track 2 synapses

    net.add([mon_soma, mon_pv_spike, mon_som_spike, mon_vip_spike, mon_soma_spike, mon_w])

    # ── 7. Run Context-Switching Simulation ─────────────────────
    print('[7/7] Running context-switching simulation...')

    # Context A: Low MD drive (0–2s)
    print('  Context A (0-2s): Low MD drive (5 Hz)...')
    MD.rates = 5 * Hz
    net.run(2.0 * second, report='text')

    # Context B: High MD drive (2–4s)
    print('  Context B (2-4s): High MD drive (40 Hz)...')
    MD.rates = 40 * Hz
    net.run(2.0 * second, report='text')

    # ── Generate Plots ──────────────────────────────────────────
    print('\nGenerating plots...')

    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)

    # Panel 1: MD firing rate (step function)
    t_all = np.linspace(0, 4000, 1000)
    md_rate = np.where(t_all < 2000, 5, 40)
    axes[0].fill_between(t_all, md_rate, alpha=0.3, color='#FF6F00')
    axes[0].plot(t_all, md_rate, color='#FF6F00', linewidth=2.5)
    axes[0].set_ylabel('MD Rate (Hz)', fontsize=12)
    axes[0].set_title('MD Thalamus Drive (Context Switch at 2s)', fontsize=14, fontweight='bold')
    axes[0].axvline(2000, color='gray', linestyle='--', alpha=0.5)
    axes[0].text(900, 35, 'Context A\n(Low MD)', ha='center', fontsize=11, color='#555')
    axes[0].text(3000, 35, 'Context B\n(High MD)', ha='center', fontsize=11, color='#555')
    axes[0].grid(True, alpha=0.2)

    # Panel 2: PV population firing rate (binned)
    bin_size = 100  # ms
    bins = np.arange(0, 4001, bin_size)
    pv_counts, _ = np.histogram(mon_pv_spike.t / ms, bins=bins)
    pv_rate = pv_counts / (bin_size / 1000) / num_pv
    axes[1].bar(bins[:-1] + bin_size/2, pv_rate, width=bin_size*0.9, color='#D32F2F', alpha=0.8)
    axes[1].set_ylabel('PV Rate (Hz)', fontsize=12)
    axes[1].set_title('PV Interneuron Activity', fontsize=14, fontweight='bold')
    axes[1].axvline(2000, color='gray', linestyle='--', alpha=0.5)
    axes[1].grid(True, alpha=0.2)

    # Panel 3: Pyramidal Soma Voltage
    axes[2].plot(mon_soma.t / ms, mon_soma.V[0] / mV, color='#1565C0', linewidth=0.5)
    axes[2].set_ylabel('Soma V (mV)', fontsize=12)
    axes[2].set_title('Pyramidal Soma Activity', fontsize=14, fontweight='bold')
    axes[2].axvline(2000, color='gray', linestyle='--', alpha=0.5)
    axes[2].grid(True, alpha=0.2)

    # Panel 4: Synaptic Weights
    axes[3].plot(mon_w.t / ms, mon_w.w[0], linewidth=2.5, color='#D32F2F', label='Synapse → Dend 1')
    axes[3].plot(mon_w.t / ms, mon_w.w[1], linewidth=2.5, color='#2E7D32', label='Synapse → Dend 2')
    axes[3].set_ylabel('Synaptic Weight', fontsize=12)
    axes[3].set_xlabel('Time (ms)', fontsize=12)
    axes[3].set_title('Graupner-Brunel Plasticity Under Context Switch', fontsize=14, fontweight='bold')
    axes[3].axvline(2000, color='gray', linestyle='--', alpha=0.5)
    axes[3].legend(fontsize=11)
    axes[3].grid(True, alpha=0.2)

    plt.tight_layout()
    fig_dir = os.path.join(PROJECT_ROOT, 'figures')
    os.makedirs(fig_dir, exist_ok=True)
    save_path = os.path.join(fig_dir, 'demo_zhang2025_context_switch.png')
    plt.savefig(save_path, dpi=200)
    print(f'Success! Plot saved to: {save_path}')

    # Print summary statistics
    pv_rate_A = len(mon_pv_spike.t[mon_pv_spike.t < 2*second]) / 2.0 / num_pv
    pv_rate_B = len(mon_pv_spike.t[mon_pv_spike.t >= 2*second]) / 2.0 / num_pv
    som_rate_A = len(mon_som_spike.t[mon_som_spike.t < 2*second]) / 2.0 / num_som
    som_rate_B = len(mon_som_spike.t[mon_som_spike.t >= 2*second]) / 2.0 / num_som
    pyr_rate_A = len(mon_soma_spike.t[mon_soma_spike.t < 2*second]) / 2.0 / num_pyr
    pyr_rate_B = len(mon_soma_spike.t[mon_soma_spike.t >= 2*second]) / 2.0 / num_pyr

    print(f'\n--- Summary ---')
    print(f'PV  mean rate:  Context A = {pv_rate_A:.1f} Hz,  Context B = {pv_rate_B:.1f} Hz')
    print(f'SOM mean rate:  Context A = {som_rate_A:.1f} Hz,  Context B = {som_rate_B:.1f} Hz')
    print(f'Pyr mean rate:  Context A = {pyr_rate_A:.1f} Hz,  Context B = {pyr_rate_B:.1f} Hz')

    try:
        plt.show()
    except Exception:
        pass

if __name__ == '__main__':
    main()
