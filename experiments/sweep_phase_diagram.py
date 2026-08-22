"""
sweep_phase_diagram.py — 2D Parameter Sweep for Phase Diagram

Sweeps over MD→PV and MD→VIP synaptic weights to map out the regimes
of cognitive flexibility in the thalamocortical model.
Uses multiprocessing to run simulations in parallel.
"""
import sys, os, argparse, time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from multiprocessing import Pool
import itertools

def run_sim(args):
    """
    Runs a single simulation for a given parameter combination.
    This function is completely self-contained for multiprocessing safety.
    """
    idx_pv, val_pv, idx_vip, val_vip = args
    
    import sys, os
    import numpy as np
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(_root, 'src', 'v2'))
    
    from brian2 import (prefs, start_scope, Network, NeuronGroup, Synapses, 
                        SpikeMonitor, StateMonitor, PoissonGroup, network_operation,
                        ms, mV, pA, Hz, second, nS)
    
    prefs.codegen.target = 'numpy'
    start_scope()
    
    from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
    from equations import (attach_rho_clipper, eqs_soma, eqs_dend, eqs_pv, eqs_som, eqs_vip, 
                           eqs_synapse_plasticity, on_pre_plasticity)
    
    p = params.copy()
    p.update(plasticity_params)
    p.update(pv_params)
    p.update(som_params)
    p.update(vip_params)
    p.update(md_params)
    
    # ── APPLY SWEEP PARAMETERS ──
    p['gAMPA_pv'] = val_pv * nS
    p['gAMPA_vip'] = val_vip * nS
    
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
    
    @network_operation(dt=p['sim_dt'])
    def Coupling():
        temp_v = Dend.V[:].reshape((num_pyr, num_dend_each))
        Soma.vAveDend = np.mean(temp_v, axis=1)
        Dend.vSoma = np.repeat(Soma.vShadow[:], num_dend_each)
        
    bAP = Synapses(Soma, Dend, on_pre='V_post += bAP_amp\nbAPCa_rise_post += norm_factor_Ca', delay=p['bAP_delay'], namespace=p)
    bAP.connect(j='i*num_DendEach + k for k in range(num_DendEach)')
    
    PV = NeuronGroup(num_pv, eqs_pv, threshold='V > vThres_pv', reset='V = vReset_pv', refractory=p['refrac_pv'], method='euler', namespace=p)
    PV.V = p['vRest_pv']
    # Tonic background drive giving PV a baseline it can be modulated around.
    BG_pv = PoissonGroup(num_pv, rates=p['rate_bg_pv'])
    syn_bg_pv = Synapses(BG_pv, PV, on_pre='gTotAMPA_post += weight_bg_pv',
                         namespace=p)
    syn_bg_pv.connect(j='i')

    
    SOM = NeuronGroup(num_som, eqs_som, threshold='V > vThres_som', reset='V = vReset_som', refractory=p['refrac_som'], method='euler', namespace=p)
    SOM.V = p['vRest_som']
    SOM.iBaseline_som = 22.0 * pA
    
    VIP = NeuronGroup(num_vip, eqs_vip, threshold='V > vThres_vip', reset='V = vReset_vip', refractory=p['refrac_vip'], method='euler', namespace=p)
    VIP.V = p['vRest_vip']
    
    MD = PoissonGroup(num_md, rates=40 * Hz)  # High MD drive (Context B)
    
    syn_md2pv = Synapses(MD, PV, on_pre='gTotAMPA_post += gAMPA_pv', namespace=p)
    syn_md2pv.connect(p=p['p_md2pv'])
    syn_md2vip = Synapses(MD, VIP, on_pre='gTotAMPA_post += gAMPA_vip', namespace=p)
    syn_md2vip.connect(p=p['p_md2vip'])
    syn_vip2som = Synapses(VIP, SOM, on_pre='gTotGABA_post += gGABA_som', namespace=p)
    syn_vip2som.connect(p=p['p_vip2som_spike'])
    syn_som2dend = Synapses(SOM, Dend, on_pre='gTotGABA_post += gGABA', namespace=p)
    syn_som2dend.connect(p=p['p_som2dend_spike'])
    syn_pv2soma = Synapses(PV, Soma, on_pre='gTotGABA_post += gGABA_pv2soma', namespace=p)
    syn_pv2soma.connect(p=p['p_pv2soma'])
    
    pathway_input = PoissonGroup(30, rates=80 * Hz)
    syn_input = Synapses(pathway_input, Dend, model=eqs_synapse_plasticity,
                         on_pre=on_pre_plasticity, method='heun', namespace=p)
    syn_input.connect()
    syn_input.rho = 0.5
    attach_rho_clipper(syn_input)
    
    mon_pv = SpikeMonitor(PV)
    mon_som = SpikeMonitor(SOM)
    mon_pyr = SpikeMonitor(Soma)
    mon_w = StateMonitor(syn_input, 'w', record=True, dt=50 * ms)
    
    net.add([Soma, Dend, Coupling, bAP, PV, SOM, VIP, MD,
             BG_pv, syn_bg_pv, syn_md2pv, syn_md2vip, syn_vip2som, syn_som2dend, syn_pv2soma,
             pathway_input, syn_input, mon_pv, mon_som, mon_pyr, mon_w])
    
    # Run 1.5 seconds (0.5s settle, 1.0s measurement)
    net.run(1.5 * second)
    
    dur = 1.0  # Measure over the last 1 second
    
    pv_spikes = sum(mon_pv.t >= 0.5 * second)
    som_spikes = sum(mon_som.t >= 0.5 * second)
    pyr_spikes = sum(mon_pyr.t >= 0.5 * second)
    
    rate_pv = pv_spikes / dur / num_pv
    rate_som = som_spikes / dur / num_som
    rate_pyr = pyr_spikes / dur / num_pyr
    
    # Calculate average plasticity (delta W)
    w_initial = 1.5 # Since w0=0, w1=3, rho=0.5 -> w=1.5
    w_final = np.mean([mon_w.w[i][-1] for i in range(len(syn_input))])
    delta_w = float(w_final - w_initial)
    
    return (idx_pv, idx_vip, rate_pv, rate_som, rate_pyr, delta_w)

def main():
    parser = argparse.ArgumentParser(description="2D Parameter Sweep for Phase Diagram")
    parser.add_argument('--grid', type=int, default=3, help="Grid size N (for NxN sweep)")
    parser.add_argument('--cores', type=int, default=4, help="Number of cores to use")
    args = parser.parse_args()
    
    N = args.grid
    print(f"Starting {N}x{N} sweep using {args.cores} cores...")
    
    # Base parameters from parameters.py
    base_pv = 0.12  # nS
    base_vip = 0.5  # nS
    
    pv_vals = np.linspace(0.0, base_pv * 2.5, N)
    vip_vals = np.linspace(0.0, base_vip * 2.5, N)
    
    tasks = []
    for i in range(N):
        for j in range(N):
            tasks.append((i, pv_vals[i], j, vip_vals[j]))
            
    t_start = time.time()
    
    with Pool(processes=args.cores) as pool:
        results = pool.map(run_sim, tasks)
        
    t_end = time.time()
    print(f"Sweep completed in {t_end - t_start:.1f} seconds.")
    
    # Process results into matrices
    mat_pv = np.zeros((N, N))
    mat_som = np.zeros((N, N))
    mat_pyr = np.zeros((N, N))
    mat_dw = np.zeros((N, N))
    
    for (i, j, r_pv, r_som, r_pyr, dw) in results:
        mat_pv[i, j] = r_pv
        mat_som[i, j] = r_som
        mat_pyr[i, j] = r_pyr
        mat_dw[i, j] = dw
        
    # Plotting
    fig_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'figures')
    os.makedirs(fig_dir, exist_ok=True)
    plt.style.use('dark_background')
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    axes = axes.flatten()
    
    metrics = [
        (mat_pv, 'PV Firing Rate (Hz)', 'Reds'),
        (mat_som, 'SOM Firing Rate (Hz)', 'Blues'),
        (mat_pyr, 'Pyr Firing Rate (Hz)', 'Greens'),
        (mat_dw, 'Synaptic Plasticity (Delta W)', 'coolwarm')
    ]
    
    for k, (mat, title, cmap) in enumerate(metrics):
        ax = axes[k]
        if 'Plasticity' in title:
            # Center colormap around 0 for Delta W
            vmax = max(abs(np.min(mat)), abs(np.max(mat)))
            if vmax == 0:
                vmax = 1
            im = ax.imshow(mat.T, origin='lower', cmap=cmap, aspect='auto', 
                           extent=[pv_vals[0], pv_vals[-1], vip_vals[0], vip_vals[-1]],
                           vmin=-vmax, vmax=vmax)
        else:
            im = ax.imshow(mat.T, origin='lower', cmap=cmap, aspect='auto', 
                           extent=[pv_vals[0], pv_vals[-1], vip_vals[0], vip_vals[-1]])
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('MD->PV Weight (nS)', fontsize=12)
        ax.set_ylabel('MD->VIP Weight (nS)', fontsize=12)
        fig.colorbar(im, ax=ax)
        
        # Mark the "Healthy Baseline" (from our parameters)
        ax.plot(base_pv, base_vip, 'w*', markersize=12, markeredgecolor='k', label='Healthy Baseline')
        if k == 0:
            ax.legend(loc='upper right')
            
    plt.suptitle('Phase Diagram of Cognitive Flexibility', fontsize=18, y=0.98)
    plt.tight_layout()
    out_path = os.path.join(fig_dir, 'phase_diagram.png')
    plt.savefig(out_path, dpi=200)
    print(f"Phase diagram saved to {out_path}")
    
if __name__ == '__main__':
    main()
