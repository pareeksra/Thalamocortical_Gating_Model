from brian2 import *

# Based on data/parameters.txt
params = {
    'sim_dt': 0.02 * ms,
    'record_dt': 0.5 * ms,
    'num_DendEach': 10,

    # Reversal potentials
    'vE': 0.0 * mV,
    'vI': -70.0 * mV,

    # Gating variable time constants
    'tauAMPA': 2.0 * ms,
    'tauGABA': 20.0 * ms,
    'tauGABABDecay': 80.0 * ms,
    'tauGABABRise': 30.0 * ms,
    'tauNMDADecay': 100.0 * ms,
    'tauNMDARise': 2.0 * ms,

    # Pyramidal soma and dendrite properties
    'areaSoma_pyr': 5.0 * 10**-5 * cm**2,
    'areaDend_pyr': 2.0 * 10**-5 * cm**2,
    'gLSoma_pyr': 2.5 * nS,
    'gLDend_pyr': 4.0 * nS,
    'cSoma_pyr': 50.0 * pF,
    'cDend_pyr': 20.0 * pF,

    # NMDA
    'alphaNMDA': 0.3 / ms,
    'vHalfNMDA': -19.9 * mV,
    'vSpreadNMDA': 12.48 * mV,

    # Cellular dynamics
    'vThres_pyr': -50.0 * mV,
    'vReset_pyr': -55.0 * mV,
    'vRest_pyr': -70.0 * mV,
    'vE_pyr': 0.0 * mV,
    'vI_pyr': -70.0 * mV,
    'refracTime_pyr': 2.0 * ms,

    # Coupling
    'gEachCouple_pyr': 4.0 * nS,
    'gEachCouple_pyr_vivo': 0.8 * nS,

    # bAP (back-propagating AP)
    'bAP_amp': 10.0 * mV,
    'bAP_delay': 3.0 * ms,

    # Calcium dynamics
    'tau_Ca_bAP_decay': 30 * ms,
    'tau_Ca_bAP_rise': 2 * ms,
    'tau_Ca_NMDA': 30 * ms,

    # Single synapse conductances
    'gAMPA': 0.4 * nS,
    'gNMDA': 2.5 * nS,
    'gGABA': 4.0 * nS,

    # Background input
    'rate_bgE': 500 * Hz,
    'rate_bgI': 150 * Hz,
    'weight_bgE': 2.5 * nS,
    'weight_bgI': 4.0 * nS,

    'tauGABA_soma': 10.0 * ms,
}

# Plasticity parameters (Graupner-Brunel, typical values)
plasticity_params = {
    'theta_d': 1.0,
    'theta_p': 2.78,
    'gamma_d': 39.949,
    'gamma_p': 177.552,
    'tau': 346.36 * second,
    'sigma': 3.35,
    'rhoStar': 0.5,
    'w0': 0.0,
    'w1': 3.0,
    'C_pre': 1.0,
}

# ============================================================
# Phase 2: Interneuron & MD Thalamus Parameters
# ============================================================

pv_params = {
    # PV fast-spiking interneuron (literature values)
    'C_pv': 10.0 * pF,        # Small capacitance → fast dynamics
    'gL_pv': 1.0 * nS,
    'vRest_pv': -70.0 * mV,
    'vThres_pv': -50.0 * mV,
    'vReset_pv': -55.0 * mV,
    'vE_pv': 0.0 * mV,
    'vI_pv': -70.0 * mV,
    'refrac_pv': 1.0 * ms,    # Short refractory → high max rate
    'tauAMPA_pv': 2.0 * ms,
    'tauGABA_pv': 10.0 * ms,
    'gAMPA_pv': 0.12 * nS,     # MD→PV synapse weight
    'gGABA_pv': 2.0 * nS,     # SOM→PV synapse weight
    'gGABA_pv2soma': 5.0 * nS, # PV→Pyramidal soma

    # ---- Tonic background drive to PV -------------------------------------
    # PV had no baseline mechanism at all, while SOM has a bias current
    # (iBaseline_som). Without one, PV had to reach threshold on thalamic drive alone
    # and was silent across the whole operating range: 0 Hz at 5 and 25 Hz MD, 4 Hz at
    # 40 Hz, then 132 Hz by 80 Hz.
    #
    # A tonic CURRENT cannot fix this. PV's f-I curve is a near-step because
    # vThres - vReset is only 5 mV with tau_m = 10 ms: rheobase is 20.0 pA, a 10 Hz
    # baseline needs 20.0003 pA and 40 Hz needs 20.5 pA. There is no tunable range, so
    # copying SOM's 22 pA would give 74 Hz rather than a baseline (SOM's own tau_m is
    # twice PV's, which is why the same current behaves completely differently).
    #
    # A background CONDUCTANCE does work, and it is this project's own declared
    # mechanism (rate_bgE / weight_bgE in params, previously never used anywhere).
    # Poisson conductance fluctuations smooth the f-I curve, so the rate becomes graded
    # instead of step-like. rate_bg_pv reuses the declared rate_bgE = 500 Hz; the weight
    # is derived for PV rather than inherited, placing the mean background conductance
    # (w * rate * tauAMPA_pv = 0.25 nS) just BELOW the ~0.4 nS needed for
    # V_inf = vThres, so firing is fluctuation-driven.
    #
    # Measured result: 7.5 Hz at rest -> 13.6 (MD 5) -> 52.5 (MD 20) -> 129 Hz (MD 40),
    # monotonic, non-saturating, and inside the 200 Hz ceiling across the operating
    # range. p_md2pv, n_md and gAMPA_pv are deliberately untouched, so the
    # many-weak-contacts-to-PV vs few-strong-to-VIP asymmetry is preserved.
    'rate_bg_pv': 500 * Hz,
    'weight_bg_pv': 0.25 * nS,
}

som_params = {
    # SOM regular-spiking interneuron
    'C_som': 20.0 * pF,
    'gL_som': 1.0 * nS,
    'vRest_som': -70.0 * mV,
    'vThres_som': -50.0 * mV,
    'vReset_som': -55.0 * mV,
    'vI_som': -70.0 * mV,
    'refrac_som': 2.0 * ms,
    'tauGABA_som_cell': 20.0 * ms,
    'gGABA_som': 3.0 * nS,    # VIP→SOM synapse weight
}

vip_params = {
    # VIP regular-spiking interneuron
    'C_vip': 20.0 * pF,
    'gL_vip': 1.0 * nS,
    'vRest_vip': -70.0 * mV,
    'vThres_vip': -50.0 * mV,
    'vReset_vip': -55.0 * mV,
    'vE_vip': 0.0 * mV,
    'refrac_vip': 2.0 * ms,
    'tauAMPA_vip': 2.0 * ms,
    'gAMPA_vip': 0.5 * nS,    # MD→VIP synapse weight
}

md_params = {
    # MD Thalamus projection parameters
    'n_md': 50,                # Number of MD relay cells
    'n_pv': 20,                # PV population size (demo scale)
    'n_som_spike': 20,         # SOM population size (demo scale)
    'n_vip_spike': 20,         # VIP population size (demo scale)
    'p_md2pv': 0.5,            # MD→PV connection probability
    'p_md2vip': 0.3,           # MD→VIP connection probability
    'p_vip2som_spike': 0.6,    # VIP→SOM connection probability
    'p_som2dend_spike': 0.5,   # SOM→Dendrite connection probability
    'p_pv2soma': 0.6,          # PV→Pyramidal soma connection probability
}
