"""
seed44_escape_analysis.py -- mechanistic dig on the seed-44 stochastic escape
================================================================================
2026-09-02 (Raghav): now that diag_seed44_results.json / full_circuit_reliability_*hz
have established that seed 44 fails reproducibly at the 25 Hz SOM baseline (ratio ~1.015)
while SOM's *mean* rate is statistically indistinguishable across seeds (~25.27 Hz
including seed 44), the open question is mechanistic: what's different about seed 44's
specific spike draw that lets the inhibited branch (dend 0) escape SOM control?

This is a standalone diagnostic, NOT a reuse of model.full_circuit.build_gating_circuit,
because that function returns only epoch-averaged summary stats -- it doesn't expose the
SOM spike train or the per-timestep synaptic calcium (c_total) needed to see *where* an
escape happens. It duplicates build_gating_circuit's network-construction code (same
imports, same equations, same connectivity) for ONE run at T=3s with two extra monitors
added before net.run():
  - the existing SOM SpikeMonitor (already in build_gating_circuit) -> pooled ISIs
  - a new StateMonitor(sb0, 'c_total', ...) on the inhibited branch's plastic synapses
    -> calcium trace vs. theta_p (LTP threshold, 2.78 -- model/parameters.py)
No epoch/rho-update loop is run (unnecessary here: c_total = c + bAPCa_post, both purely
determined by spike timing/dendritic voltage, not by rho -- see model/equations.py's
eqs_synapse_plasticity_template comment above `c_total`).

Uses the 25 Hz condition specifically (som_bias_pA=20.9, the value under which seed 44's
escape was found), md_signal_rate=0, noise_level=0 -- Phase 2B's baseline condition,
matching diag_seed44.py exactly except for the added monitors and single-epoch run.

Compares seed 44 (fails, ratio ~1.02) against seed 42 (passes, ratio ~4.07) as the
reference in results/pre_audit/diag_seed44_results.json.

Output: figures/pre_audit/seed44_escape_mechanism.png -- 2x2 grid:
  row 1: SOM population ISI histogram (seed 42 left, seed 44 right)
  row 2: branch-0 (inhibited) mean synaptic calcium trace vs theta_p, with SOM spike
         raster ticks along the top, same seeds/columns
"""
import os
import sys

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
sys.path.insert(0, PROOT)

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from brian2 import *

from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
from equations import (attach_rho_clipper, make_eqs_synapse_plasticity, eqs_soma, eqs_dend,
                        eqs_pv, eqs_som, eqs_vip, eqs_synapse_plasticity,
                        on_pre_plasticity_noisy as on_pre_plasticity)

T = 3.0            # seconds, one epoch -- matches Phase 2B / diag_seed44's per-epoch window
SOM_BIAS_PA = 20.9  # the 25 Hz condition under which seed 44 fails (pre-30Hz-lockin value)
STATE_DT = 0.2 * ms  # coarser than sim_dt (0.02ms) -- plenty for a calcium trace plot


def run_seed(seed_val):
    seed(seed_val)
    p = dict(params)
    for d in (plasticity_params, pv_params, som_params, vip_params, md_params):
        p.update(d)
    p['vesicle_cv'] = 0.0

    ndend = 2
    p['num_Soma'] = 1
    p['num_DendEach'] = ndend
    p['num_Dend'] = ndend
    p['gEachCouple_pyr'] = 0.8 * nS
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * ndend
    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']
    p['norm_factor_Ca'] = t ** (1 / (t - 1))
    t = p['tauGABABRise'] / p['tauGABABDecay']
    p['norm_factor_GABAB'] = t ** (1 / (t - 1))

    net = Network()

    Soma = NeuronGroup(1, eqs_soma, threshold='V>vThres_pyr', reset='V=vReset_pyr',
                        refractory=p['refracTime_pyr'], method='euler', namespace=p)
    Soma.V = p['vRest_pyr']; Soma.vShadow = p['vRest_pyr']; Soma.vAveDend = p['vRest_pyr']
    Dend = NeuronGroup(ndend, eqs_dend, method='euler', namespace=p)
    Dend.V = p['vRest_pyr']; Dend.vSoma = p['vRest_pyr']

    @network_operation(dt=p['sim_dt'])
    def coupling():
        Soma.vAveDend = np.mean(Dend.V[:])
        Dend.vSoma = np.repeat(Soma.vShadow[:], ndend)
    net.add([Soma, Dend, coupling])

    post_src = PoissonGroup(1, rates=10.0 * Hz)
    bAP = Synapses(post_src, Dend, on_pre='V_post+=bAP_amp\nbAPCa_rise_post+=norm_factor_Ca',
                    delay=p['bAP_delay'], namespace=p)
    bAP.connect(j='k for k in range(2)')
    net.add([post_src, bAP])

    PV = NeuronGroup(p['n_pv'], eqs_pv, threshold='V>vThres_pv', reset='V=vReset_pv',
                      refractory=p['refrac_pv'], method='euler', namespace=p)
    PV.V = p['vRest_pv']
    BG_pv = PoissonGroup(p['n_pv'], rates=p['rate_bg_pv'])
    sbg_pv = Synapses(BG_pv, PV, on_pre='gTotAMPA_post+=weight_bg_pv', namespace=p)
    sbg_pv.connect(j='i')

    SOM = NeuronGroup(p['n_som_spike'], eqs_som, threshold='V>vThres_som', reset='V=vReset_som',
                       refractory=p['refrac_som'], method='euler', namespace=p)
    SOM.V = p['vRest_som']; SOM.iBaseline_som = SOM_BIAS_PA * pA
    # Phase-2's SOM/VIP background channels stay at 0 (noise_level=0), matching
    # diag_seed44's noise=0 condition exactly.
    net.add([PV, BG_pv, sbg_pv, SOM])

    VIP = NeuronGroup(p['n_vip_spike'], eqs_vip, threshold='V>vThres_vip', reset='V=vReset_vip',
                       refractory=p['refrac_vip'], method='euler', namespace=p)
    VIP.V = p['vRest_vip']
    net.add(VIP)

    # md_signal_rate=0 -> MD contributes nothing; omitted entirely here (equivalent to
    # the noise=0/md_signal_rate=0 condition build_gating_circuit runs for Phase 2B).
    s_vip2som = Synapses(VIP, SOM, on_pre='gTotGABA_post+=gGABA_som', namespace=p)
    s_vip2som.connect(p=p['p_vip2som_spike'])
    s_som2dend = Synapses(SOM, Dend, on_pre='gTotGABA_post+=gGABA', namespace=p)
    s_som2dend.connect(condition='j==0', p=p['p_som2dend_spike'])
    s_pv2soma = Synapses(PV, Soma, on_pre='gTotGABA_post+=gGABA_pv2soma', namespace=p)
    s_pv2soma.connect(p=p['p_pv2soma'])
    s_som2pv = Synapses(SOM, PV, on_pre='gTotGABA_post+=gGABA_pv', namespace=p)
    s_som2pv.connect(p=p['p_som2pv'])
    net.add([s_vip2som, s_som2dend, s_pv2soma, s_som2pv])

    exc0 = PoissonGroup(20, rates=80.0 * Hz)
    sb0 = Synapses(exc0, Dend, model=eqs_synapse_plasticity, on_pre=on_pre_plasticity,
                    method='heun', namespace=p)
    sb0.connect(j='0'); sb0.rho = 0.5; attach_rho_clipper(sb0)
    exc1 = PoissonGroup(20, rates=80.0 * Hz)
    sb1 = Synapses(exc1, Dend, model=make_eqs_synapse_plasticity(2), on_pre=on_pre_plasticity,
                    method='heun', namespace=p)
    sb1.connect(j='1'); sb1.rho = 0.5; attach_rho_clipper(sb1)
    net.add([exc0, sb0, exc1, sb1])

    som_mon = SpikeMonitor(SOM)
    # c_total = c (presynaptic, per-synapse) + bAPCa_post (postsynaptic, per-branch) is a
    # subexpression that links to Dend via a summed/indexed reference -- Brian 2 can't put
    # a StateMonitor directly on that link (TypeError: "need to precalculate direct
    # indices but index _postsynaptic_idx can change"). Monitor the two components
    # separately instead: `c` is a native synapse variable (record=True is fine), and
    # `bAPCa` lives natively on Dend (record=[0] for branch 0, which all 20 of sb0's
    # synapses share as their postsynaptic target) -- then sum them in Python below.
    ca_mon = StateMonitor(sb0, 'c', record=True, dt=STATE_DT)
    bap_mon = StateMonitor(Dend, 'bAPCa', record=[0], dt=STATE_DT)
    net.add([som_mon, ca_mon, bap_mon])

    net.run(T * second)

    som_spike_times = np.asarray(som_mon.t / second)
    c_trace = np.asarray(ca_mon.c)              # shape (20 synapses, n_timesteps)
    bap_trace = np.asarray(bap_mon.bAPCa)[0]     # shape (n_timesteps,), branch 0 only
    ca_trace = c_trace + bap_trace[np.newaxis, :]  # c_total per synapse, broadcast bAPCa
    t_axis = np.asarray(ca_mon.t / second)
    return som_spike_times, ca_trace, t_axis


if __name__ == '__main__':
    theta_p = float(params.get('theta_p', 2.78))
    n_som = md_params['n_som_spike']

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex='row')
    labels = {42: 'seed 42 (PASS, ratio 4.07)', 44: 'seed 44 (FAIL, ratio 1.02)'}

    results = {}
    for col, seed_val in enumerate([42, 44]):
        print(f"Running seed {seed_val}...", flush=True)
        seed(seed_val)  # reseed before rebuilding, mirrors full_circuit.py's own seed() call
        som_t, ca_trace, t_axis = run_seed(seed_val)
        results[seed_val] = dict(som_t=som_t, ca_trace=ca_trace, t_axis=t_axis)

        # --- ISI histogram of the MERGED population spike train, i.e. gaps in the total
        # inhibitory drive that actually hits Dend0's GABA conductance (each connected
        # SOM spike, from any of the 20 neurons, adds a GABA event -- what matters for
        # escape is a gap in this combined train relative to tau_GABA,dend, not any
        # single neuron's own ISI) ---
        isis_ms = np.diff(np.sort(som_t)) * 1000.0 if len(som_t) > 1 else np.array([])
        expected_merged_isi_ms = 1000.0 / (25.0 * n_som)  # per-neuron rate x pop size
        ax = axes[0, col]
        ax.hist(isis_ms, bins=30, color='#4c72b0' if seed_val == 42 else '#c44e52', alpha=0.8)
        ax.axvline(expected_merged_isi_ms, color='k', linestyle='--', linewidth=1,
                   label=f'expected mean gap ({expected_merged_isi_ms:.2f} ms)')
        ax.set_title(labels[seed_val])
        ax.set_xlabel('merged SOM population inter-spike gap (ms)')
        if col == 0:
            ax.set_ylabel('count')
        ax.legend(fontsize=7)

        # --- calcium trace on branch 0 (inhibited), mean across the 20 plastic synapses ---
        ax2 = axes[1, col]
        mean_ca = ca_trace.mean(axis=0)
        ax2.plot(t_axis, mean_ca, color='#4c72b0' if seed_val == 42 else '#c44e52', linewidth=1.2,
                 label='mean c_total (branch 0, 20 synapses)')
        ax2.axhline(theta_p, color='k', linestyle='--', linewidth=1, label=f'theta_p = {theta_p}')
        # SOM spike raster along the top of the calcium panel
        ymax = max(mean_ca.max(), theta_p) * 1.15
        ax2.eventplot([som_t], lineoffsets=ymax * 0.97, linelengths=ymax * 0.05,
                      colors='k', linewidths=0.5)
        ax2.set_ylim(0, ymax)
        ax2.set_xlabel('time (s)')
        if col == 0:
            ax2.set_ylabel('synaptic calcium c_total')
        ax2.legend(fontsize=7, loc='upper left')

    fig.suptitle('Seed-44 stochastic escape: SOM ISI structure and branch-0 calcium '
                  '(25 Hz SOM baseline, noise=0, T=3s single epoch)')
    fig.tight_layout()
    out_path = os.path.join(PROOT, 'figures', 'pre_audit', 'seed44_escape_mechanism.png')
    fig.savefig(out_path, dpi=150)
    print(f"Saved {out_path}", flush=True)

    for seed_val in (42, 44):
        r = results[seed_val]
        print(f"seed={seed_val}: n_som_spikes={len(r['som_t'])}  "
              f"mean_ca_final={r['ca_trace'].mean(axis=0)[-1]:.3f}  "
              f"max_mean_ca={r['ca_trace'].mean(axis=0).max():.3f}  theta_p={theta_p}", flush=True)
