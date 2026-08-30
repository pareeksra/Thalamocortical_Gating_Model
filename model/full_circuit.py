"""
full_circuit.py
================
Phase 2 network builder: combines the Phase-1 branch-specific gating protocol
(experiments/phase1_single_neuron_gating.py -- one pyramidal soma, two
dendritic branches, SOM inhibiting branch 0 only, a plastic pathway on each
branch, postsynaptic rate pinned by an external Poisson source) with the full
MD -> PV / MD -> VIP -> SOM disinhibition circuit used for the V4 validation
(experiments/validate_vs_papers.py), so that MD drive -- not a hand-set SOM
bias -- is what ultimately controls branch-specific plasticity.

This is the circuit Phase 2 (noise robustness, NMDA-hypofunction) needs: Phase
1's reduced circuit inhibits branch 0 with a directly-biased SOM population,
which has no MD input to degrade or add noise to.

Three noise channels, all OFF (reproducing the deterministic/validated
behaviour) unless explicitly requested:

  1. MD signal/noise split: MD is two independent PoissonGroups (signal and
     noise), each wired identically to PV and VIP. SNR = md_signal_rate /
     md_noise_rate. md_noise_rate=0 (default) reproduces a clean MD drive.
  2. Vesicle release variability: parameters.py's vesicle_cv (default 0.0),
     see equations.py on_pre_plasticity.
  3. Background membrane fluctuations on PV/SOM/VIP: independent Poisson
     conductance noise (PV's rate_bg_pv/weight_bg_pv already exists and is
     always on, per the validated model; SOM/VIP backgrounds default to 0 Hz
     / 0 nS and are scaled here by bg_noise_scale).

A single `noise_level` (0 = deterministic Phase-1/V4 behaviour) scales all
three channels together, for the Phase 2B noise sweep. Phase 2C instead holds
noise_level fixed and varies `md2vip_scale` (fraction of the intact MD->VIP
synaptic weight) independently.
"""
import os
import sys

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))

import numpy as np
from brian2 import *

from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
from equations import (attach_rho_clipper, make_eqs_synapse_plasticity, eqs_soma, eqs_dend,
                        eqs_pv, eqs_som, eqs_vip, eqs_synapse_plasticity,
                        on_pre_plasticity_noisy as on_pre_plasticity)

# Background-noise "fully on" reference levels for SOM and VIP (bg_noise_scale=1.0).
# PV's own background (rate_bg_pv/weight_bg_pv) is part of the validated model and is
# always active; these two are Phase-2-only additions, calibrated to add mild,
# sub-threshold-dominant fluctuation without swamping SOM's 22 pA baseline current or
# creating spurious VIP firing at MD=0.
BASE_RATE_BG_SOM = 500.0 * Hz
BASE_WEIGHT_BG_SOM = 0.15 * nS
BASE_RATE_BG_VIP = 500.0 * Hz
BASE_WEIGHT_BG_VIP = 0.15 * nS
MAX_MD_NOISE_RATE = 25.0 * Hz          # md_noise_rate at noise_level = 1.0
MAX_VESICLE_CV = 0.30                  # vesicle_cv at noise_level = 1.0


def build_gating_circuit(T=3.0, post_rate=10.0, exc_rate=80.0, gcouple_nS=0.8,
                          md_signal_rate=25.0, noise_level=0.0,
                          md2vip_scale=1.0, seed_val=42):
    """Build and run the Phase-2 branch-gating circuit; return measured outcomes.

    noise_level in [0, 1] (values above 1 are a deliberate overdrive/stress range)
    jointly scales MD noise rate, vesicle_cv, and SOM/VIP background conductance.
    md2vip_scale in [0, 1] independently scales the MD->VIP synaptic weight, for the
    NMDA-hypofunction / MD->VIP degradation protocol (Phase 2C); 1.0 = intact.
    """
    seed(seed_val)
    p = dict(params)
    for d in (plasticity_params, pv_params, som_params, vip_params, md_params):
        p.update(d)

    p['vesicle_cv'] = MAX_VESICLE_CV * noise_level
    md_noise_rate = MAX_MD_NOISE_RATE * noise_level
    bg_rate_som = BASE_RATE_BG_SOM
    bg_weight_som = BASE_WEIGHT_BG_SOM * noise_level
    bg_rate_vip = BASE_RATE_BG_VIP
    bg_weight_vip = BASE_WEIGHT_BG_VIP * noise_level
    gAMPA_vip_eff = p['gAMPA_vip'] * md2vip_scale

    ndend = 2
    p['num_Soma'] = 1
    p['num_DendEach'] = ndend
    p['num_Dend'] = ndend
    p['gEachCouple_pyr'] = gcouple_nS * nS
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * ndend
    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']
    p['norm_factor_Ca'] = t ** (1 / (t - 1))
    t = p['tauGABABRise'] / p['tauGABABDecay']
    p['norm_factor_GABAB'] = t ** (1 / (t - 1))

    net = Network()

    # -- Pyramidal soma + 2 dendritic branches --------------------------------
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

    post_src = PoissonGroup(1, rates=post_rate * Hz)
    bAP = Synapses(post_src, Dend, on_pre='V_post+=bAP_amp\nbAPCa_rise_post+=norm_factor_Ca',
                    delay=p['bAP_delay'], namespace=p)
    bAP.connect(j='k for k in range(2)')
    net.add([post_src, bAP])

    # -- Interneurons ----------------------------------------------------------
    PV = NeuronGroup(p['n_pv'], eqs_pv, threshold='V>vThres_pv', reset='V=vReset_pv',
                      refractory=p['refrac_pv'], method='euler', namespace=p)
    PV.V = p['vRest_pv']
    BG_pv = PoissonGroup(p['n_pv'], rates=p['rate_bg_pv'])
    sbg_pv = Synapses(BG_pv, PV, on_pre='gTotAMPA_post+=weight_bg_pv', namespace=p)
    sbg_pv.connect(j='i')

    SOM = NeuronGroup(p['n_som_spike'], eqs_som, threshold='V>vThres_som', reset='V=vReset_som',
                       refractory=p['refrac_som'], method='euler', namespace=p)
    # NOT switched to p['iBaseline_som'] (Yang's calibrated 10 Hz) -- confirmed by
    # direct test to collapse gating (ratio 42.76 -> 1.04, Phase-1's own PASS/FAIL
    # check flips to FAIL). See diagnosis delivered 2026-08-27; left at the original
    # value pending a decision on how to reconcile Yang's rate with this model's
    # calibration. p['iBaseline_som'] is defined and documented for that purpose.
    SOM.V = p['vRest_som']; SOM.iBaseline_som = 22.0 * pA
    BG_som = PoissonGroup(p['n_som_spike'], rates=bg_rate_som)
    sbg_som = Synapses(BG_som, SOM, on_pre='gTotAMPA_post+=bg_weight_som', namespace={**p, 'bg_weight_som': bg_weight_som})
    sbg_som.connect(j='i')

    VIP = NeuronGroup(p['n_vip_spike'], eqs_vip, threshold='V>vThres_vip', reset='V=vReset_vip',
                       refractory=p['refrac_vip'], method='euler', namespace=p)
    VIP.V = p['vRest_vip']
    BG_vip = PoissonGroup(p['n_vip_spike'], rates=bg_rate_vip)
    sbg_vip = Synapses(BG_vip, VIP, on_pre='gTotAMPA_post+=bg_weight_vip', namespace={**p, 'bg_weight_vip': bg_weight_vip})
    sbg_vip.connect(j='i')

    net.add([PV, BG_pv, sbg_pv, SOM, BG_som, sbg_som, VIP, BG_vip, sbg_vip])

    # -- MD thalamus: signal + noise Poisson populations ------------------------
    MD_signal = PoissonGroup(p['n_md'], rates=md_signal_rate * Hz)
    MD_noise = PoissonGroup(p['n_md'], rates=md_noise_rate)
    s_sig_pv = Synapses(MD_signal, PV, on_pre='gTotAMPA_post+=gAMPA_pv', namespace=p)
    s_sig_pv.connect(p=p['p_md2pv'])
    s_noise_pv = Synapses(MD_noise, PV, on_pre='gTotAMPA_post+=gAMPA_pv', namespace=p)
    s_noise_pv.connect(p=p['p_md2pv'])
    s_sig_vip = Synapses(MD_signal, VIP, on_pre='gTotAMPA_post+=gAMPA_vip_eff',
                          namespace={**p, 'gAMPA_vip_eff': gAMPA_vip_eff})
    s_sig_vip.connect(p=p['p_md2vip'])
    s_noise_vip = Synapses(MD_noise, VIP, on_pre='gTotAMPA_post+=gAMPA_vip_eff',
                            namespace={**p, 'gAMPA_vip_eff': gAMPA_vip_eff})
    s_noise_vip.connect(p=p['p_md2vip'])
    net.add([MD_signal, MD_noise, s_sig_pv, s_noise_pv, s_sig_vip, s_noise_vip])

    # -- Disinhibition and feedforward inhibition -------------------------------
    s_vip2som = Synapses(VIP, SOM, on_pre='gTotGABA_post+=gGABA_som', namespace=p)
    s_vip2som.connect(p=p['p_vip2som_spike'])
    s_som2dend = Synapses(SOM, Dend, on_pre='gTotGABA_post+=gGABA', namespace=p)
    s_som2dend.connect(condition='j==0', p=p['p_som2dend_spike'])
    s_pv2soma = Synapses(PV, Soma, on_pre='gTotGABA_post+=gGABA_pv2soma', namespace=p)
    s_pv2soma.connect(p=p['p_pv2soma'])
    # Divergence fix: Yang et al. wire SOM->PV at P=0.8 (gGABA_pv/eqs_pv's gTotGABA
    # channel were already present but unwired -- see parameters.py p_som2pv).
    s_som2pv = Synapses(SOM, PV, on_pre='gTotGABA_post+=gGABA_pv', namespace=p)
    s_som2pv.connect(p=p['p_som2pv'])
    net.add([s_vip2som, s_som2dend, s_pv2soma, s_som2pv])

    # -- Plastic pathway: independent excitatory input onto each branch --------
    exc0 = PoissonGroup(20, rates=exc_rate * Hz)
    sb0 = Synapses(exc0, Dend, model=eqs_synapse_plasticity, on_pre=on_pre_plasticity,
                    method='heun', namespace=p)
    sb0.connect(j='0'); sb0.rho = 0.5; attach_rho_clipper(sb0)
    exc1 = PoissonGroup(20, rates=exc_rate * Hz)
    sb1 = Synapses(exc1, Dend, model=make_eqs_synapse_plasticity(2), on_pre=on_pre_plasticity,
                    method='heun', namespace=p)
    sb1.connect(j='1'); sb1.rho = 0.5; attach_rho_clipper(sb1)
    net.add([exc0, sb0, exc1, sb1])

    mons = {'pv': SpikeMonitor(PV), 'som': SpikeMonitor(SOM), 'vip': SpikeMonitor(VIP),
            'pyr': SpikeMonitor(Soma)}
    net.add(list(mons.values()))

    net.run(T * second)

    w0 = float(np.mean(sb0.w[:])); w1 = float(np.mean(sb1.w[:]))
    r0 = float(np.mean(sb0.rho[:])); r1 = float(np.mean(sb1.rho[:]))
    ratio = r1 / r0 if r0 > 1e-6 else float('inf')
    n_pv, n_som, n_vip = p['n_pv'], p['n_som_spike'], p['n_vip_spike']
    return dict(
        r0=r0, r1=r1, w0=w0, w1=w1, ratio=ratio,
        pv_rate=len(mons['pv'].t) / T / n_pv,
        som_rate=len(mons['som'].t) / T / n_som,
        vip_rate=len(mons['vip'].t) / T / n_vip,
        pyr_rate=len(mons['pyr'].t) / T,
    )
