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
sys.path.insert(0, PROOT)

import numpy as np
from brian2 import *

from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
from equations import (attach_rho_clipper, make_eqs_synapse_plasticity, eqs_soma, eqs_dend,
                        eqs_pv, eqs_som, eqs_vip, eqs_synapse_plasticity,
                        on_pre_plasticity_noisy as on_pre_plasticity)
from src.v2.plasticity import yang_synapse_update

# 2026-08-30 migration: plasticity here now uses the same analytical epoch update as
# experiments/phase1_analytical.py (Yang 2016 Eqs. 32-35), NOT the continuous drho/dt ODE
# -- that ODE is commented out in model/equations.py (rho is a bare parameter there), so
# the single-shot net.run() this function used to do would otherwise leave rho frozen at
# its initial 0.5 for both branches (ratio identically 1.0) for every noise_level /
# md2vip_scale / seed. See docs/Progress_Report.docx Section 7.2 for how this was found.

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
                          md2vip_scale=1.0, seed_val=42, n_epochs=15, som_bias_pA=21.32,
                          return_trace=False, param_overrides=None,
                          monitor_epoch0=False, monitor_dt_ms=1.0):
    """Build the Phase-2 branch-gating circuit and run it for n_epochs analytical
    plasticity epochs (Yang 2016 Eqs. 32-35, src/v2/plasticity.py); return measured
    outcomes averaged/final over the run.

    noise_level in [0, 1] (values above 1 are a deliberate overdrive/stress range)
    jointly scales MD noise rate, vesicle_cv, and SOM/VIP background conductance.
    md2vip_scale in [0, 1] independently scales the MD->VIP synaptic weight, for the
    NMDA-hypofunction / MD->VIP degradation protocol (Phase 2C); 1.0 = intact.
    som_bias_pA defaults to the 2026-09-01 full-circuit reliability lock-in value
    (21.32 pA, measured ~30.07 Hz in this circuit, 20/20 seeds passed at noise=0 --
    docs/full_circuit_reliability_30hz_results.json). Supersedes the earlier 20.9 pA /
    25 Hz pick (calibrated in Phase-1's reduced circuit), which failed reproducibly at
    noise=0 on seed 44 (docs/diag_seed44_results.json, ratio ~1.015). At
    md_signal_rate=0 / noise_level=0 (Phase 2B's baseline condition) nothing else
    synaptically drives SOM, so this bias produces the same isolated-neuron rate here as
    in the reduced circuit; this is NOT assumed to hold once MD/VIP or noise actively
    inhibit or perturb SOM, which is the point of those sweeps.
    """
    seed(seed_val)
    p = dict(params)
    for d in (plasticity_params, pv_params, som_params, vip_params, md_params):
        p.update(d)
    # param_overrides (2026-09-15): override ANY parameters.py value for exploration
    # (experiments/model_explorer.py). Applied here -- before derived quantities such as
    # norm_factor_Ca and the gcouple/noise assignments -- so overriding a raw constant
    # (a tau, threshold, gamma, gNMDA, gGABA, kappa_Ca_NMDA, ...) correctly propagates to
    # everything computed from it. Values must be plain Brian2 quantities/floats matching
    # the original units. Function args (gcouple_nS, som_bias_pA, noise_level, ...) still
    # take precedence for the specific quantities they set, by design.
    if param_overrides:
        for k, v in param_overrides.items():
            if k not in p:
                raise KeyError(f"param_overrides key '{k}' is not a known model parameter")
            p[k] = v

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
    # SOM bias: see the som_bias_pA docstring above and model/parameters.py's
    # iBaseline_som comment for the full 2026-08-30 SOM-rate sweep story. This function's
    # own default (20.9 pA) intentionally overrides p['iBaseline_som'] rather than reading
    # it, since that parameter's calibration is documented for Phase-1's reduced circuit
    # specifically and this circuit's own SOM rate should be checked, not assumed.
    SOM.V = p['vRest_som']; SOM.iBaseline_som = som_bias_pA * pA
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
    # acc_eqs/accumulate: same compiled-counter trick as experiments/phase1_analytical.py
    # -- O(1) memory, integrated at the full sim_dt rather than a coarser record_dt,
    # reset every epoch so alpha_d/alpha_p measure only the current epoch's calcium.
    acc_eqs = '\nad_acc : second\nap_acc : second\n'
    accumulate = ('ad_acc = ad_acc + int(c_total > theta_d)*dt\n'
                  'ap_acc = ap_acc + int(c_total > theta_p)*dt')

    exc0 = PoissonGroup(20, rates=exc_rate * Hz)
    sb0 = Synapses(exc0, Dend, model=eqs_synapse_plasticity + acc_eqs, on_pre=on_pre_plasticity,
                    method='heun', namespace=p)
    sb0.connect(j='0'); sb0.rho = 0.5; attach_rho_clipper(sb0)
    sb0.run_regularly(accumulate, when='end')
    exc1 = PoissonGroup(20, rates=exc_rate * Hz)
    sb1 = Synapses(exc1, Dend, model=make_eqs_synapse_plasticity(2) + acc_eqs,
                    on_pre=on_pre_plasticity, method='heun', namespace=p)
    sb1.connect(j='1'); sb1.rho = 0.5; attach_rho_clipper(sb1)
    sb1.run_regularly(accumulate, when='end')
    net.add([exc0, sb0, exc1, sb1])

    mons = {'pv': SpikeMonitor(PV), 'som': SpikeMonitor(SOM), 'vip': SpikeMonitor(VIP),
            'pyr': SpikeMonitor(Soma)}
    net.add(list(mons.values()))

    # Sub-epoch diagnostic (2026-10-13): optional fine monitors for the "why does
    # branch-0 ap0 differ across seeds at identical mean SOM rate?" question (the
    # upstream half of across_seed_diag.py). Records, during EPOCH 0 only, the full
    # c_total trace of both dendritic branches plus SOM and exc0 spike times, so the
    # sub-epoch alignment of SOM inhibition gaps vs exc0 bursts on the inhibited branch
    # can be compared between a passing and a failing seed. Monitors are passive (they
    # draw no RNG and add no synapses), so when monitor_epoch0=False the RNG stream and
    # all returned numbers are byte-identical to before -- verified against the committed
    # docs/across_seed_diag_results.json (seed 42 ratio 4.068, seeds 44/53 fail).
    ep0_mon = None
    if monitor_epoch0:
        # c_total = c + bAPCa_post is a per-synapse subexpression that mixes a synapse
        # var (c, NMDA calcium) with a POSTSYNAPTIC dendrite var (bAPCa). Brian 2 cannot
        # StateMonitor such a subexpression directly (changeable postsynaptic index), so
        # record the two components separately and reconstruct c_total in Python:
        #   c_total[branch] = c[synapses on branch] + bAPCa[branch].
        # The 20 synapses on a branch all read that branch's single bAPCa, so the
        # branch-mean c_total = mean_syn(c) + bAPCa[branch]. Both `c` (synapse) and
        # `bAPCa` (Dend) are plain recordable state variables.
        ep0_mon = {
            'c0': StateMonitor(sb0, 'c', record=True, dt=monitor_dt_ms * ms),
            'c1': StateMonitor(sb1, 'c', record=True, dt=monitor_dt_ms * ms),
            'bap': StateMonitor(Dend, 'bAPCa', record=True, dt=monitor_dt_ms * ms),
            # E/I-balance diagnostic: branch voltage V (drives the NMDA Mg-gate and
            # thus the calcium dc/dt), the GABA conductance actually reaching each
            # branch (SOM inhibition; only branch 0 is wired), and the NMDA current.
            'dend': StateMonitor(Dend, ('V', 'gTotGABA', 'iTotNMDA'), record=True,
                                 dt=monitor_dt_ms * ms),
            'som': SpikeMonitor(SOM),
            'exc0': SpikeMonitor(exc0),
        }

    ykw = dict(sigma=float(p['sigma']), tau=float(p['tau'] / second),
               gamma_d=float(p['gamma_d']), gamma_p=float(p['gamma_p']),
               w0=float(p['w0']), w1=float(p['w1']), rho_star=float(p['rhoStar']))

    # Epoch loop: rho is held fixed during each T-second epoch while calcium
    # accumulates, then updated analytically per synapse and written back into Brian 2
    # (same pattern as experiments/phase1_analytical.py's run_gating_analytical).
    # trace (optional, 2026-09-03): per-epoch record for the across-seed-escape diagnosis
    # (docs/across_seed_diag.py). Records the inhibited (branch 0) and free (branch 1)
    # mean rho AND the mean alpha_p/alpha_d that drove each epoch's update, so we can see
    # WHEN branch 0 escapes and whether it is an early bistable lock-in.
    trace = [] if return_trace else None
    ep0_data = None
    if monitor_epoch0:
        net.add(list(ep0_mon.values()))
    for e in range(n_epochs):
        sb0.ad_acc = 0 * second; sb0.ap_acc = 0 * second
        sb1.ad_acc = 0 * second; sb1.ap_acc = 0 * second
        net.run(T * second)

        if monitor_epoch0 and e == 0:
            # c_total traces: shape (n_synapses, n_time). Average over the 20 synapses
            # per branch to get the branch-mean c_total(t) -- the same per-branch mean
            # the accumulator's np.mean(ap0) reduces to. time axis shared.
            # reconstruct per-synapse c_total = c + bAPCa[branch]
            bap = np.asarray(ep0_mon['bap'].bAPCa)       # shape (2, n_time): branch bAP Ca
            c0_arr = np.asarray(ep0_mon['c0'].c) + bap[0][None, :]   # branch 0 (inhibited)
            c1_arr = np.asarray(ep0_mon['c1'].c) + bap[1][None, :]   # branch 1 (free)
            t_arr = np.asarray(ep0_mon['c0'].t / second)
            c0m = c0_arr.mean(axis=0); c1m = c1_arr.mean(axis=0)
            theta_p = float(p['theta_p']); theta_d = float(p['theta_d'])
            dt_s = monitor_dt_ms * 1e-3
            # time-above-threshold computed per synapse then averaged (matches the
            # accumulator, which thresholds each synapse's own c_total), not on the mean
            ap0_per_syn = (c0_arr > theta_p).sum(axis=1) * dt_s
            ad0_per_syn = (c0_arr > theta_d).sum(axis=1) * dt_s
            # E/I balance on each branch (mV, nS, pA). Branch 0 is the inhibited one.
            Vb = np.asarray(ep0_mon['dend'].V)          # (2, n_time) volts
            gG = np.asarray(ep0_mon['dend'].gTotGABA)   # (2, n_time) siemens
            iN = np.asarray(ep0_mon['dend'].iTotNMDA)   # (2, n_time) amps
            ep0_data = dict(
                t=t_arr.tolist(),
                c0=c0m.tolist(), c1=c1m.tolist(),
                theta_p=theta_p, theta_d=theta_d,
                som_spikes=np.asarray(ep0_mon['som'].t / second).tolist(),
                exc0_spikes=np.asarray(ep0_mon['exc0'].t / second).tolist(),
                ap0_from_trace=float(np.mean(ap0_per_syn)),
                ad0_from_trace=float(np.mean(ad0_per_syn)),
                c0_max=float(c0_arr.max()), c0_mean=float(c0_arr.mean()),
                n_som=int(len(ep0_mon['som'].t)), n_exc0=int(len(ep0_mon['exc0'].t)),
                # branch-0 (inhibited) E/I summaries
                V0_mean_mV=float(Vb[0].mean() * 1e3), V0_max_mV=float(Vb[0].max() * 1e3),
                V1_mean_mV=float(Vb[1].mean() * 1e3),
                gGABA0_mean_nS=float(gG[0].mean() * 1e9), gGABA0_max_nS=float(gG[0].max() * 1e9),
                iNMDA0_mean_pA=float(iN[0].mean() * 1e12), iNMDA0_max_pA=float(iN[0].max() * 1e12),
                iNMDA1_mean_pA=float(iN[1].mean() * 1e12),
            )
            # stop recording after epoch 0 to bound memory
            net.remove(list(ep0_mon.values()))

        ad0 = np.asarray(sb0.ad_acc[:] / second); ap0 = np.asarray(sb0.ap_acc[:] / second)
        ad1 = np.asarray(sb1.ad_acc[:] / second); ap1 = np.asarray(sb1.ap_acc[:] / second)
        r0_syn = np.asarray(sb0.rho[:]); r1_syn = np.asarray(sb1.rho[:])
        if return_trace:
            trace.append(dict(epoch=e,
                              rho0_before=float(np.mean(r0_syn)),
                              rho1_before=float(np.mean(r1_syn)),
                              ap0=float(np.mean(ap0)), ad0=float(np.mean(ad0)),
                              ap1=float(np.mean(ap1)), ad1=float(np.mean(ad1))))
        r0_new = np.array([yang_synapse_update(ad0[k], ap0[k], r0_syn[k], **ykw)['rho_new']
                           for k in range(len(r0_syn))])
        r1_new = np.array([yang_synapse_update(ad1[k], ap1[k], r1_syn[k], **ykw)['rho_new']
                           for k in range(len(r1_syn))])
        sb0.rho[:] = r0_new
        sb1.rho[:] = r1_new
        if return_trace:
            trace[-1]['rho0_after'] = float(np.mean(r0_new))
            trace[-1]['rho1_after'] = float(np.mean(r1_new))

    T_total = n_epochs * T
    w0 = float(np.mean(sb0.w[:])); w1 = float(np.mean(sb1.w[:]))
    r0 = float(np.mean(sb0.rho[:])); r1 = float(np.mean(sb1.rho[:]))
    ratio = r1 / r0 if r0 > 1e-6 else float('inf')
    n_pv, n_som, n_vip = p['n_pv'], p['n_som_spike'], p['n_vip_spike']
    out = dict(
        r0=r0, r1=r1, w0=w0, w1=w1, ratio=ratio,
        pv_rate=len(mons['pv'].t) / T_total / n_pv,
        som_rate=len(mons['som'].t) / T_total / n_som,
        vip_rate=len(mons['vip'].t) / T_total / n_vip,
        pyr_rate=len(mons['pyr'].t) / T_total,
    )
    if return_trace:
        out['trace'] = trace
    if monitor_epoch0:
        out['ep0'] = ep0_data
    return out
