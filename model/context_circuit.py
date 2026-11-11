"""
context_circuit.py -- MD-driven, branch-SELECTIVE context circuit (audit Problem 2,
2026-11-01).

Why this exists. Every headline Model A result before 2026-11-01 ran with MD switched
OFF (md_signal_rate=0): which branch was gated was hard-wired (SOM -> branch 0 only), and
in model/full_circuit.py MD can only remove branch 0's gate globally. MD never *chose*
a branch, so the project's core hypothesis ("MD selects which branch learns") had not
been tested in the canonical simulator. This builder makes MD the context selector.

Architecture (one pyramidal cell, 2 branches, one disinhibitory channel per branch):

    MD_k (Poisson, n_md)  --AMPA p_md2vip-->  VIP_k (n_vip)  --GABA p_vip2som-->  SOM_k (n_som)
    SOM_k --GABA p_som2dend--> branch k           (the gate; SOM_k only reaches branch k)
    MD_0 + MD_1  --AMPA p_md2pv-->  PV (n_pv)  --GABA p_pv2soma-->  soma
    SOM_0 + SOM_1 --GABA p_som2pv--> PV ;  background Poisson -> PV (validated model)
    exc_k (20 Poisson @ exc_rate)  --plastic (Yang analytical rule)-->  branch k

Context k = MD_k firing at md_on_rate, MD_other at md_off_rate. MD_k -> VIP_k silences
SOM_k, opening branch k; SOM_other keeps its baseline (bias current, ~30 Hz) and shunts
the other branch. Branch-specific VIP->SOM channels are a modelling ASSUMPTION (the same
one Model C's 3-epoch protocol made); Zhang 2025 gives the cell-type wiring, not the
branch-level map.

Input gating (the other half of a "context", FINDING_catastrophic_forgetting):
    input_mode='context'  exc_k on only while context k is active (idle input silent)
    input_mode='always'   both inputs always on (inhibition-only context switch)
Inhibition can be removed entirely with inhibition=False (SOM -> dendrite weight 0),
which is the control the original forgetting test lacked.

All parameters come from model/parameters.py (Yang/Zhang values); SOM cells are
desynchronised (som_phase='random', see circuit_helpers.py); coupling is compiled.
"""
import os, sys
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model')); sys.path.insert(0, PROOT)

import numpy as np
from brian2 import (Network, NeuronGroup, PoissonGroup, Synapses, SpikeMonitor, StateMonitor, seed,
                    second, ms, mV, pA, nS, Hz)

from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
from equations import (attach_rho_clipper, make_eqs_synapse_plasticity, eqs_soma, eqs_dend,
                       eqs_pv, eqs_som, eqs_vip, eqs_vip_inh, eqs_synapse_plasticity, on_pre_plasticity)
from circuit_helpers import add_compiled_coupling, som_initial_voltages
from src.v2.plasticity import yang_synapse_update


# Calibrated balanced, fluctuation-driven somatic drive + PV->soma weight for
# bap_source='soma' (2026-11-02, experiments/soma_balanced_calibration.py, seeds 42-44).
# Inhibitory background g_I = 5 nS (2x leak), excitation at 0.6x the threshold level.
# Soma ~9-15 Hz in a context at MD->PV x1 (Yang's ~10 Hz), ISI CV ~1.1, graded decline
# over MD->PV x0 -> x3 (~21 -> 18 -> 12 -> 5 -> 2 Hz). gGABA_pv2soma = 0.1 nS here vs the
# global 5 nS, which silences a driven soma once PV is active. Use as:
#   run_context_protocol(..., bap_source='soma', **BALANCED_SOMA_KW,
#                        param_overrides={'gGABA_pv2soma': BALANCED_SOMA_G_PV2SOMA, ...})
BALANCED_SOMA_KW = dict(soma_drive_hz=18.0, soma_drive_nS=0.5, n_soma_drive=100,
                        soma_inh_hz=5.0, soma_inh_nS=1.0, n_soma_inh=100)
BALANCED_SOMA_G_PV2SOMA = 0.1 * nS
# Fluctuation-driven SOM baseline (2026-11-10, experiments/som_baseline_fix.py): sub-rheobase
# bias (rheobase 20 pA) + 60 Hz x 2 nS Poisson excitation per SOM cell -> ~30 Hz, the same
# rate as the bias-only 21.32 pA, but the rate depends smoothly on each drive parameter.
VIP2SOM_SCALE_CANON = 0.25   # canonical VIP->SOM factor (2026-11-10, see vip2som_scale)
SOM_NOISY_KW = dict(som_bias_pA=6.0, som_bg_E_hz=60.0, som_bg_nS=2.0)


def _syn_model(eqs, nmda_plastic):
    """Synapse model string; with nmda_plastic the weight w scales gNMDA (Yang 2016)."""
    if not nmda_plastic:
        return eqs
    assert eqs.count('gNMDA*s_nmda') >= 2
    return eqs.replace('gNMDA*s_nmda', 'w*gNMDA*s_nmda')


def run_context_protocol(schedule, T=3.0, exc_rate=80.0, post_rate=10.0, gcouple_nS=0.8,
                         md_on_rate=25.0, md_off_rate=0.0, som_bias_pA=None,
                         input_mode='context', inhibition=True, seed_val=42,
                         som_phase='random', md2vip_scale=1.0, bap_source='poisson',
                         param_overrides=None, rho_init=None,
                         soma_drive_hz=0.0, soma_drive_nS=0.0, n_soma_drive=100,
                         soma_inh_hz=0.0, soma_inh_nS=0.0, n_soma_inh=100,
                         overlap=0.0, n_pattern=20,
                         plastic=True, rho_init_syn=None, cue=None, record_dend=False,
                         nmda_plastic=None, synapse='yang', stim=None, md_vip_frac=None, p_vip2som_cross=None,
                         md2som_frac=0.0, md2som_nS=0.5,
                         som_bg_E_hz=None, som_bg_I_hz=0.0, som_bg_nS=None, som_baseline=None,
                         bap_ca_scale=None, som2dend_cross=0.0,
                         som2vip_nS=0.0, p_som2vip=0.5, som2vip_wiring='uniform', pv2pv_nS=0.0, p_pv2pv=0.5,
                         vip2som_scale=None):
    """Run the analytical-plasticity epoch loop under a context schedule.

    schedule : list of ints (0 or 1) -- the active context for each T-second epoch.
    bap_source : 'poisson' (Yang protocol: bAPs from an independent post_rate Poisson
        source -- the soma's own spikes do not reach the dendrites) or 'soma' (bAPs are
        the soma's own spikes, so PV/soma activity can influence plasticity; audit P8).
        With 'soma', give the soma a drive (soma_drive_hz x n_soma_drive Poisson AMPA
        inputs of soma_drive_nS each) so it fires near Yang's ~10 Hz; the dendrites alone
        (0.8 nS coupling) do not make it fire.
    input_mode='patterns' (2026-11-02, docs/reports/PLAN_overlapping_inputs.md): ONE afferent pool
        whose every neuron makes a plastic synapse on BOTH branches (inputs not pre-sorted
        by branch). Context 0 activates pattern A = afferents [0, n_pattern); context 1
        activates pattern B = n_pattern afferents, round(overlap*n_pattern) of them shared
        with A. Each traj record then also holds per-synapse rho ('rho0_syn', 'rho1_syn',
        index = afferent index); the result holds 'idx_A' / 'idx_B'.
    synapse         CANONICAL SYNAPSE (2026-11-04, docs/reports/PLAN_robustness.md R1):
                    'yang' (default): Yang 2016 -- the plastic weight scales NMDA
                    (g = w x gNMDA, w = 3 rho), AMPA input off (gAMPA = 0 unless given in
                    param_overrides), rho starts at 1/3 (w = 1, Yang's pre-learning 2.5 nS).
                    'ampa': the pre-2026-11-04 synapse (w scales AMPA 0.4 nS, NMDA fixed,
                    rho starts at 0.5). Every result committed before 2026-11-04 used 'ampa';
                    the scripts that produced them pin synapse='ampa' and stay reproducible.
                    nmda_plastic / rho_init, if given, override the synapse's choice.
    Recall options (2026-11-02; see docs/reports/PLAN_alternation.md and experiments/nmda_plastic_check.py):
    plastic=False   freeze plasticity (rho is not updated after epochs).
    rho_init_syn    (rho_branch0, rho_branch1) per-synapse initial rho arrays
                    ('patterns' mode only), e.g. a state saved from a learning run.
    cue             per-epoch list of bools; False = MD silent in that epoch (both channels
                    at md_off_rate) while the epoch's pattern is still presented.
    record_dend     record each branch's voltage and NMDA-calcium per epoch:
                    dV{b} (mean V, mV), plat{b} (fraction of time V > -40 mV),
                    dV{b}_pct (5/25/50/75/95th percentiles of V).
    Control-specificity options (Yang 2016 Fig. 5 analogue, experiments/gating_selectivity_fig5.py):
    stim            per-epoch list: which input pathway is on (0, 1 or None), independent
                    of the context ('context' and 'patterns' modes; default: pathway = context;
                    in 'patterns' mode 0/1 = pattern A/B).
    md_vip_frac     q in (0, 1]: MD_k targets a fraction q of ALL VIP cells, own channel
                    first (q <= 0.5 stays inside channel k; q > 0.5 spills into the other
                    channel). Weight scaled by 0.5/q so total control drive is constant.
    p_vip2som_cross VIP_k -> SOM_j (j != k) connection probability; VIP->SOM weight scaled
                    by p_own/(p_own + p_cross) so each SOM's total VIP inhibition is constant.
    som2dend_cross  x in [0, 0.5] (2026-11-10, experiments/specificity_test.py): SOM_k contacts
                    its own branch with probability p_som2dend_spike*(1-x) and the other branch
                    with p_som2dend_spike*x, so each SOM cell's and each branch's expected
                    synapse count is unchanged; 0 = branch-specific (default), 0.5 = uniform.
    Zhang 2025 wiring absent from the canonical model (2026-11-10, experiments/zhang_wiring_test.py;
    all off by default):
    som2vip_nS      SOM -> VIP GABA weight (nS); VIP then uses eqs_vip_inh (tauGABA_vip 20 ms).
    p_som2vip       its connection probability.
    som2vip_wiring  'uniform' (every SOM -> every VIP channel), 'own' (SOM_k -> VIP_k: mutual
                    inhibition inside a channel) or 'cross' (SOM_k -> VIP_j, j != k).
    pv2pv_nS        PV -> PV GABA weight (nS), probability p_pv2pv, no self-connections.
    md2som_frac     fraction of the OTHER channel's SOM cells that MD_k excites directly
                    (Yang's scheme 2), weight md2som_nS, probability p_md2vip.
    Custom wiring draws from a dedicated RNG (default_rng(20000 + seed)).
    SOM baseline (2026-11-10, PLAN_robustness.md 'SOM knife-edge'):
    som_baseline    'noisy' (CANONICAL with synapse='yang'): SOM_NOISY_KW, 6 pA bias +
                    60 Hz x 2 nS Poisson excitation, ~30 Hz, irregular, robust to +/-25% of
                    each drive parameter (experiments/som_baseline_fix.py).
                    'bias' (default with synapse='ampa', and every result committed before
                    2026-11-10): noiseless 21.32 pA bias just above the 20 pA rheobase, ~30 Hz.
                    som_bias_pA / som_bg_E_hz / som_bg_nS, if given, override the preset.
    bap_ca_scale    amplitude of the bAP calcium transient (2026-11-10). 0.2 (CANONICAL with
                    synapse='yang'): Yang 2016 Methods' in-vivo recalibration (k_VGCC x0.2),
                    so bAPs alone stay below theta_d and idle synapses do not drift; this
                    also makes slow LTD independent of the epoch length T
                    (experiments/epoch_length_check.py). 1.0 (default with synapse='ampa',
                    and every result committed before 2026-11-10): peak = theta_d, so bAPs
                    alone depress idle synapses over minutes (hidden by 3-s epochs).
                    param_overrides['bAP_Ca_scale'] is equivalent.
    vip2som_scale   VIP -> SOM weight factor on gGABA_som (3 nS) (2026-11-10, step 1 of
                    PLAN_robustness.md). 0.25 (CANONICAL with the noisy SOM baseline): own
                    SOM still silenced (0.5 Hz), S_learn unchanged (0.93), and VIP->SOM
                    cross-talk of 11% tolerated (x1: fails at 11%;
                    experiments/specificity_test.py). 1.0 otherwise, and for every result
                    produced before this change (scripts pin vip2som_scale=1.0).
                    An explicit param_overrides['gGABA_som'] is used as given (not scaled).
    som_bg_E_hz / som_bg_I_hz / som_bg_nS  independent Poisson AMPA (E) and GABA (I)
                    background onto every SOM cell (one aggregate source each, weight
                    som_bg_nS). With a sub-rheobase som_bias_pA this makes SOM's baseline
                    fluctuation-driven, so its rate depends smoothly on the drive instead of
                    switching on at rheobase (20 pA). Default 0 = off (bit-identical).
    nmda_plastic    Yang 2016 form: the plastic weight scales the NMDA conductance
                    (g = w x gNMDA, w = w0 + (w1-w0) rho, so rho = 1/3 gives Yang's 2.5 nS)
                    in both the NMDA current and its calcium. Combine with
                    param_overrides={'gAMPA': 0*nS} for Yang's NMDA-only inputs.
    The defaults leave all earlier behaviour bit-identical.
    soma_inh_hz / soma_inh_nS / n_soma_inh : optional inhibitory Poisson input onto the
        soma (GABA, tauGABA_soma). Together with the excitatory drive this gives a
        BALANCED, fluctuation-driven soma (2026-11-02): mean input just below threshold,
        firing driven by fluctuations, so extra PV inhibition scales the rate gradually
        instead of switching it off (a purely excitatory mean-driven drive is switch-like;
        results/current/pv_soma_calibration.json). traj records pyr_cv (ISI CV) per epoch.
    Returns dict(traj=[per-epoch records], summary...)."""
    seed(seed_val)
    p = dict(params)
    for d in (plasticity_params, pv_params, som_params, vip_params, md_params):
        p.update(d)
    if param_overrides:
        for k, v in param_overrides.items():
            if k not in p:
                raise KeyError(f"param_overrides key '{k}' is not a known model parameter")
            p[k] = v
    if synapse not in ('yang', 'ampa'):
        raise ValueError(f"synapse must be 'yang' or 'ampa', got {synapse!r}")
    if nmda_plastic is None:
        nmda_plastic = synapse == 'yang'
    if rho_init is None:
        rho_init = 1 / 3 if synapse == 'yang' else 0.5
    if synapse == 'yang' and not (param_overrides and 'gAMPA' in param_overrides):
        p['gAMPA'] = 0 * nS
    if bap_ca_scale is not None:
        p['bAP_Ca_scale'] = float(bap_ca_scale)
    elif not (param_overrides and 'bAP_Ca_scale' in param_overrides):
        p['bAP_Ca_scale'] = 0.2 if synapse == 'yang' else 1.0
    if som_baseline is None:
        som_baseline = 'noisy' if synapse == 'yang' else 'bias'
    if som_baseline not in ('noisy', 'bias'):
        raise ValueError(f"som_baseline must be 'noisy' or 'bias', got {som_baseline!r}")
    if vip2som_scale is None:
        vip2som_scale = VIP2SOM_SCALE_CANON if som_baseline == 'noisy' else 1.0
    if not (param_overrides and 'gGABA_som' in param_overrides):
        p['gGABA_som'] = p['gGABA_som'] * float(vip2som_scale)
    som_pre = SOM_NOISY_KW if som_baseline == 'noisy' else dict(som_bias_pA=21.32, som_bg_E_hz=0.0, som_bg_nS=0.0)
    som_bias_pA = som_pre['som_bias_pA'] if som_bias_pA is None else som_bias_pA
    som_bg_E_hz = som_pre['som_bg_E_hz'] if som_bg_E_hz is None else som_bg_E_hz
    som_bg_nS = som_pre['som_bg_nS'] if som_bg_nS is None else som_bg_nS
    ndend = 2
    p['num_Soma'] = 1; p['num_DendEach'] = ndend; p['num_Dend'] = ndend
    p['gEachCouple_pyr'] = gcouple_nS * nS; p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * ndend
    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']; p['norm_factor_Ca'] = t ** (1 / (t - 1)) * float(p.get('bAP_Ca_scale', 1.0))  # bap_ca_scale (see docstring)
    t = p['tauGABABRise'] / p['tauGABABDecay']; p['norm_factor_GABAB'] = t ** (1 / (t - 1))
    n_md, n_pv, n_som, n_vip = p['n_md'], p['n_pv'], p['n_som_spike'], p['n_vip_spike']
    p['gGABA_dend_eff'] = p['gGABA'] if inhibition else 0 * nS
    p['gAMPA_vip_eff'] = p['gAMPA_vip'] * md2vip_scale
    p['n_som_ch'] = n_som; p['n_vip_ch'] = n_vip; p['n_md_ch'] = n_md

    net = Network()
    Soma = NeuronGroup(1, eqs_soma, threshold='V>vThres_pyr', reset='V=vReset_pyr',
                       refractory=p['refracTime_pyr'], method='euler', namespace=p)
    Soma.V = p['vRest_pyr']; Soma.vShadow = p['vRest_pyr']; Soma.vAveDend = p['vRest_pyr']
    Dend = NeuronGroup(ndend, eqs_dend, method='euler', namespace=p)
    Dend.V = p['vRest_pyr']; Dend.vSoma = p['vRest_pyr']
    net.add([Soma, Dend])
    add_compiled_coupling(net, Soma, Dend, ndend, p)

    if bap_source == 'poisson':
        post_src = PoissonGroup(1, rates=post_rate * Hz)
        net.add(post_src)
        bap_pre = post_src
    elif bap_source == 'soma':
        bap_pre = Soma
    if soma_drive_hz > 0:
        p['soma_drive_w'] = soma_drive_nS * nS
        SD = PoissonGroup(n_soma_drive, rates=soma_drive_hz * Hz)
        s_sd = Synapses(SD, Soma, on_pre='gTotAMPA_post += soma_drive_w', namespace=p)
        s_sd.connect()
        net.add([SD, s_sd])
    if soma_inh_hz > 0:
        p['soma_inh_w'] = soma_inh_nS * nS
        SI = PoissonGroup(n_soma_inh, rates=soma_inh_hz * Hz)
        s_si = Synapses(SI, Soma, on_pre='gTotGABA_post += soma_inh_w', namespace=p)
        s_si.connect()
        net.add([SI, s_si])
    if bap_source not in ('poisson', 'soma'):
        raise ValueError(f"bap_source must be 'poisson' or 'soma', got {bap_source!r}")
    bAP = Synapses(bap_pre, Dend, on_pre='V_post+=bAP_amp\nbAPCa_rise_post+=norm_factor_Ca',
                   delay=p['bAP_delay'], namespace=p)
    bAP.connect(j='k for k in range(2)')
    net.add(bAP)

    # interneurons: one SOM and one VIP channel per branch (index // n gives the channel)
    PV = NeuronGroup(n_pv, eqs_pv, threshold='V>vThres_pv', reset='V=vReset_pv',
                     refractory=p['refrac_pv'], method='euler', namespace=p)
    PV.V = p['vRest_pv']
    BG_pv = PoissonGroup(n_pv, rates=p['rate_bg_pv'])
    sbg_pv = Synapses(BG_pv, PV, on_pre='gTotAMPA_post+=weight_bg_pv', namespace=p)
    sbg_pv.connect(j='i')
    SOM = NeuronGroup(2 * n_som, eqs_som, threshold='V>vThres_som', reset='V=vReset_som',
                      refractory=p['refrac_som'], method='euler', namespace=p)
    SOM.V = som_initial_voltages(2 * n_som, p, som_bias_pA, som_phase, seed_val)
    SOM.iBaseline_som = som_bias_pA * pA
    if som_bg_E_hz > 0 or som_bg_I_hz > 0:
        p['som_bg_w'] = som_bg_nS * nS
        for rate_, tgt in ((som_bg_E_hz, 'gTotAMPA'), (som_bg_I_hz, 'gTotGABA')):
            if rate_ > 0:
                BG_som = PoissonGroup(2 * n_som, rates=rate_ * Hz)
                s_bg_som = Synapses(BG_som, SOM, on_pre=f'{tgt}_post += som_bg_w', namespace=p)
                s_bg_som.connect(j='i')
                net.add([BG_som, s_bg_som])
    VIP = NeuronGroup(2 * n_vip, eqs_vip_inh if som2vip_nS > 0 else eqs_vip, threshold='V>vThres_vip', reset='V=vReset_vip',
                      refractory=p['refrac_vip'], method='euler', namespace=p)
    VIP.V = p['vRest_vip']
    MD = PoissonGroup(2 * n_md, rates=0 * Hz)
    net.add([PV, BG_pv, sbg_pv, SOM, VIP, MD])

    s_md2pv = Synapses(MD, PV, on_pre='gTotAMPA_post+=gAMPA_pv', namespace=p)
    s_md2pv.connect(p=p['p_md2pv'])
    wrng = np.random.default_rng(20000 + seed_val)
    s_md2vip = Synapses(MD, VIP, on_pre='gTotAMPA_post+=gAMPA_vip_eff', namespace=p)
    if md_vip_frac is None:
        s_md2vip.connect(condition='i // n_md_ch == j // n_vip_ch', p=p['p_md2vip'])
    else:
        q = float(md_vip_frac); p['gAMPA_vip_eff'] = p['gAMPA_vip_eff'] * 0.5 / q
        ii, jj = [], []
        for k in (0, 1):
            own = np.arange(k * n_vip, (k + 1) * n_vip); oth = np.arange((1 - k) * n_vip, (2 - k) * n_vip)
            n_t = int(round(q * 2 * n_vip))
            tgt = (wrng.choice(own, n_t, replace=False) if n_t <= n_vip else
                   np.concatenate([own, wrng.choice(oth, n_t - n_vip, replace=False)]))
            for m in range(k * n_md, (k + 1) * n_md):
                sel = tgt[wrng.random(len(tgt)) < p['p_md2vip']]
                ii += [m] * len(sel); jj += sel.tolist()
        s_md2vip.connect(i=np.array(ii, int), j=np.array(jj, int))
    if p_vip2som_cross is None:
        s_vip2som = Synapses(VIP, SOM, on_pre='gTotGABA_post+=gGABA_som', namespace=p)
        s_vip2som.connect(condition='i // n_vip_ch == j // n_som_ch', p=p['p_vip2som_spike'])
    else:
        po, pc = p['p_vip2som_spike'], float(p_vip2som_cross)
        p['gGABA_vip2som_eff'] = p['gGABA_som'] * po / (po + pc)
        s_vip2som = Synapses(VIP, SOM, on_pre='gTotGABA_post+=gGABA_vip2som_eff', namespace=p)
        ch_v = np.arange(2 * n_vip) // n_vip; ch_s = np.arange(2 * n_som) // n_som
        P = np.where(ch_v[:, None] == ch_s[None, :], po, pc)
        ii, jj = np.nonzero(wrng.random(P.shape) < P)
        s_vip2som.connect(i=ii, j=jj)
    if md2som_frac > 0:
        p['md2som_w'] = md2som_nS * nS
        s_md2som = Synapses(MD, SOM, on_pre='gTotAMPA_post+=md2som_w', namespace=p)
        ii, jj = [], []
        for k in (0, 1):
            oth = np.arange((1 - k) * n_som, (2 - k) * n_som)
            tgt = wrng.choice(oth, int(round(md2som_frac * n_som)), replace=False)
            for m in range(k * n_md, (k + 1) * n_md):
                sel = tgt[wrng.random(len(tgt)) < p['p_md2vip']]
                ii += [m] * len(sel); jj += sel.tolist()
        s_md2som.connect(i=np.array(ii, int), j=np.array(jj, int))
        net.add(s_md2som)
    s_som2dend = Synapses(SOM, Dend, on_pre='gTotGABA_post+=gGABA_dend_eff', namespace=p)
    if not som2dend_cross:
        s_som2dend.connect(condition='i // n_som_ch == j', p=p['p_som2dend_spike'])
    else:
        x = float(som2dend_cross); ps = p['p_som2dend_spike']
        P = np.where((np.arange(2 * n_som) // n_som)[:, None] == np.arange(2)[None, :], ps * (1 - x), ps * x)
        ii, jj = np.nonzero(wrng.random(P.shape) < P)
        s_som2dend.connect(i=ii, j=jj)
    s_pv2soma = Synapses(PV, Soma, on_pre='gTotGABA_post+=gGABA_pv2soma', namespace=p)
    s_pv2soma.connect(p=p['p_pv2soma'])
    s_som2pv = Synapses(SOM, PV, on_pre='gTotGABA_post+=gGABA_pv', namespace=p)
    s_som2pv.connect(p=p['p_som2pv'])
    net.add([s_md2pv, s_md2vip, s_vip2som, s_som2dend, s_pv2soma, s_som2pv])
    if som2vip_nS > 0:   # Zhang 2025: VIP <- SOM
        p['som2vip_w'] = som2vip_nS * nS
        s_som2vip = Synapses(SOM, VIP, on_pre='gTotGABA_post+=som2vip_w', namespace=p)
        ch_s = np.arange(2 * n_som) // n_som; ch_v = np.arange(2 * n_vip) // n_vip
        same = ch_s[:, None] == ch_v[None, :]
        allow = {'uniform': np.ones_like(same), 'own': same, 'cross': ~same}[som2vip_wiring]
        ii, jj = np.nonzero(allow & (wrng.random(same.shape) < p_som2vip))
        s_som2vip.connect(i=ii, j=jj)
        net.add(s_som2vip)
    if pv2pv_nS > 0:     # Zhang 2025: PV <- PV
        p['pv2pv_w'] = pv2pv_nS * nS
        s_pv2pv = Synapses(PV, PV, on_pre='gTotGABA_post+=pv2pv_w', namespace=p)
        M = wrng.random((n_pv, n_pv)) < p_pv2pv; np.fill_diagonal(M, False)
        ii, jj = np.nonzero(M)
        s_pv2pv.connect(i=ii, j=jj)
        net.add(s_pv2pv)

    acc_eqs = '\nad_acc : second\nap_acc : second\n'
    accumulate = ('ad_acc = ad_acc + int(c_total > theta_d)*dt\n'
                  'ap_acc = ap_acc + int(c_total > theta_p)*dt')
    if input_mode not in ('context', 'always', 'patterns'):
        raise ValueError(f"input_mode must be 'context', 'always' or 'patterns', got {input_mode!r}")
    if input_mode == 'patterns':
        n_sh = int(round(overlap * n_pattern))
        n_aff = 2 * n_pattern - n_sh
        idx_A = np.arange(0, n_pattern)
        idx_B = np.arange(n_pattern - n_sh, 2 * n_pattern - n_sh)
        AFF = PoissonGroup(n_aff, rates=0 * Hz)
        sb0 = Synapses(AFF, Dend, model=_syn_model(eqs_synapse_plasticity, nmda_plastic) + acc_eqs, on_pre=on_pre_plasticity,
                       method='heun', namespace=p)
        sb0.connect(i=np.arange(n_aff), j=0)
        sb0.rho = rho_init if rho_init_syn is None else np.asarray(rho_init_syn[0], float)
        attach_rho_clipper(sb0)
        sb0.run_regularly(accumulate, when='end')
        sb1 = Synapses(AFF, Dend, model=_syn_model(make_eqs_synapse_plasticity(2), nmda_plastic) + acc_eqs,
                       on_pre=on_pre_plasticity, method='heun', namespace=p)
        sb1.connect(i=np.arange(n_aff), j=1)
        sb1.rho = rho_init if rho_init_syn is None else np.asarray(rho_init_syn[1], float)
        attach_rho_clipper(sb1)
        sb1.run_regularly(accumulate, when='end')
        for sb in (sb0, sb1):   # synapse k must be afferent k (per-synapse rho indexing)
            assert np.array_equal(np.asarray(sb.i[:]), np.arange(n_aff))
        net.add([AFF, sb0, sb1])
    else:
        exc0 = PoissonGroup(20, rates=exc_rate * Hz)
        exc1 = PoissonGroup(20, rates=exc_rate * Hz)
        sb0 = Synapses(exc0, Dend, model=_syn_model(eqs_synapse_plasticity, nmda_plastic) + acc_eqs, on_pre=on_pre_plasticity,
                       method='heun', namespace=p)
        sb0.connect(j='0'); sb0.rho = rho_init; attach_rho_clipper(sb0)
        sb0.run_regularly(accumulate, when='end')
        sb1 = Synapses(exc1, Dend, model=_syn_model(make_eqs_synapse_plasticity(2), nmda_plastic) + acc_eqs,
                       on_pre=on_pre_plasticity, method='heun', namespace=p)
        sb1.connect(j='1'); sb1.rho = rho_init; attach_rho_clipper(sb1)
        sb1.run_regularly(accumulate, when='end')
        net.add([exc0, exc1, sb0, sb1])

    m_som, m_vip, m_pv, m_pyr = SpikeMonitor(SOM), SpikeMonitor(VIP), SpikeMonitor(PV), SpikeMonitor(Soma)
    net.add([m_som, m_vip, m_pv, m_pyr])
    if rho_init_syn is not None and input_mode != 'patterns':
        raise ValueError("rho_init_syn needs input_mode='patterns'")
    if record_dend:
        m_dend = StateMonitor(Dend, 'V', record=True)
        net.add(m_dend)

    ykw = dict(sigma=float(p['sigma']), tau=float(p['tau'] / second),
               gamma_d=float(p['gamma_d']), gamma_p=float(p['gamma_p']),
               w0=float(p['w0']), w1=float(p['w1']), rho_star=float(p['rhoStar']))
    som_ch = np.arange(2 * n_som) // n_som
    vip_ch = np.arange(2 * n_vip) // n_vip
    md_ch = np.arange(2 * n_md) // n_md
    n_som_syn = [int(np.sum(np.asarray(s_som2dend.j[:]) == b)) for b in range(2)]

    traj = []
    for e, ctx in enumerate(schedule):
        if cue is None or cue[e]:
            MD.rates = np.where(md_ch == ctx, md_on_rate, md_off_rate) * Hz
        else:
            MD.rates = md_off_rate * Hz
        if input_mode == 'context':
            on = ctx if stim is None else stim[e]
            exc0.rates = (exc_rate if on == 0 else 0.0) * Hz
            exc1.rates = (exc_rate if on == 1 else 0.0) * Hz
        elif input_mode == 'patterns':
            on = ctx if stim is None else stim[e]
            active = idx_A if on == 0 else (idx_B if on == 1 else np.array([], int))
            AFF.rates = np.where(np.isin(np.arange(n_aff), active), exc_rate, 0.0) * Hz
        for sb in (sb0, sb1):
            sb.ad_acc = 0 * second; sb.ap_acc = 0 * second
        n_s0, n_v0, n_p0, n_y0 = m_som.num_spikes, m_vip.num_spikes, m_pv.num_spikes, m_pyr.num_spikes
        t_start = float(net.t / second)
        net.run(T * second)
        rec = dict(epoch=e + 1, context=int(ctx))
        for b, sb in ((0, sb0), (1, sb1)):
            ad = np.asarray(sb.ad_acc[:] / second); ap = np.asarray(sb.ap_acc[:] / second)
            r = np.asarray(sb.rho[:])
            if plastic:
                r_new = np.array([yang_synapse_update(ad[k], ap[k], r[k], **ykw)['rho_new']
                                  for k in range(len(r))])
                sb.rho[:] = r_new
            else:
                r_new = r
            rec[f'rho{b}'] = float(r_new.mean()); rec[f'ad{b}'] = float(ad.mean()); rec[f'ap{b}'] = float(ap.mean())
            if input_mode == 'patterns':
                rec[f'rho{b}_syn'] = r_new.tolist()
        # per-channel rates over this epoch
        st = np.asarray(m_som.t / second); si = np.asarray(m_som.i)
        vt = np.asarray(m_vip.t / second); vi = np.asarray(m_vip.i)
        for ch in (0, 1):
            rec[f'som{ch}_hz'] = float(np.sum((st >= t_start) & (som_ch[si] == ch)) / T / n_som)
            rec[f'vip{ch}_hz'] = float(np.sum((vt >= t_start) & (vip_ch[vi] == ch)) / T / n_vip)
        if record_dend:
            tm = np.asarray(m_dend.t / second) >= t_start
            for b in (0, 1):
                v = np.asarray(m_dend.V[b] / mV)[tm]
                rec[f'dV{b}'] = float(v.mean()); rec[f'plat{b}'] = float(np.mean(v > -40.0))
                rec[f'dV{b}_pct'] = np.percentile(v, [5, 25, 50, 75, 95]).round(2).tolist()
        rec['pv_hz'] = (m_pv.num_spikes - n_p0) / T / n_pv
        rec['pyr_hz'] = (m_pyr.num_spikes - n_y0) / T
        yt = np.asarray(m_pyr.t / second); yt = yt[yt >= t_start]
        isi = np.diff(yt)
        rec['pyr_cv'] = float(isi.std() / isi.mean()) if len(isi) >= 5 else float('nan')
        traj.append(rec)
    out = dict(traj=traj, n_som_syn_per_branch=n_som_syn, seed=seed_val,
               rho0=traj[-1]['rho0'], rho1=traj[-1]['rho1'])
    if input_mode == 'patterns':
        out.update(idx_A=idx_A.tolist(), idx_B=idx_B.tolist(), overlap=overlap)
    return out
