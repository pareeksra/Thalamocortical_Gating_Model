# Brian 2 native string equations. Membrane, synapse and calcium equations follow
# Yang, Murray & Wang (2016), Nat. Commun. 7:12815, Methods pp. 10-12: Eq. 13 (NMDA
# calcium = leaky integral of I_NMDA), Eq. 14 (VGCC/bAP calcium = per-spike bumps),
# Eqs. 20-22 (dendritic I/O). An earlier note cited a `data/equations.txt` that never
# existed in any commit.
# Parameters are defined in parameters.py and passed into the Brian 2 namespace.

eqs_soma = '''
dV/dt = (iL + iSyn + iCoupleDend)/cSoma_pyr : volt (unless refractory)
iL = -gLSoma_pyr*(V-vRest_pyr) : amp
iAMPA = -gTotAMPA*(V-vE_pyr) : amp
iNMDA = -gTotNMDA*(V-vE_pyr)/(1+exp(-(V-vHalfNMDA)/vSpreadNMDA)) : amp
iGABA = -gTotGABA*(V-vI_pyr) : amp
iSyn = iAMPA + iNMDA + iGABA : amp

# Coupling from dendrite
iCoupleDend = -gTotCouple_pyr*(V-vAveDend) : amp

dvShadow/dt = (iShadowL + iShadowSyn - gTotCouple_pyr*(vShadow-vAveDend))/cSoma_pyr : volt
iShadowL = -gLSoma_pyr*(vShadow-vRest_pyr) : amp
iShadowAMPA = -gTotAMPA*(vShadow-vE_pyr) : amp
iShadowNMDA = -gTotNMDA*(vShadow-vE_pyr)/(1+exp(-(vShadow-vHalfNMDA)/vSpreadNMDA)) : amp
iShadowGABA = -gTotGABA*(vShadow-vI_pyr) : amp
iShadowSyn = iShadowAMPA + iShadowNMDA + iShadowGABA: amp

dgTotAMPA/dt = -gTotAMPA/tauAMPA : siemens
dgTotGABA/dt = -gTotGABA/tauGABA_soma : siemens
gTotNMDA : siemens
vAveDend : volt

# NOTE: the bAP calcium trace used to be duplicated here on the soma, driven by the
# reset, and read by nothing. It now lives on the dendrite (eqs_dend), where the
# plasticity rule actually consumes it via bAPCa_post, and is triggered by the bAP
# synapse using the existing bAP_delay. Do not re-add a somatic copy.
'''

eqs_dend = '''
dV/dt = (iDendL + iDendSyn - gEachCouple_pyr*(V-vSoma))/cDend_pyr : volt
iDendL = -gLDend_pyr*(V-vRest_pyr) : amp
iDendAMPA = -gTotAMPA*(V-vE_pyr) : amp
iDendGABA = -gTotGABA*(V-vI_pyr) : amp
iDendGABAB = -gTotGABAB*(0.03333*volt)*(0.5-2/(1+exp((V/mV + 98.73)/12.5))) : amp
iDendSyn = iDendAMPA + iTotNMDA + iDendGABA + iDendGABAB: amp

dgTotAMPA/dt = -gTotAMPA/tauAMPA : siemens
dgTotGABA/dt = -gTotGABA/tauGABA : siemens

# Summed-variable targets for the two afferent NMDA pathways. Synapses write into
# these with `iTotNMDA1_post = ... : amp (summed)`; see eqs_synapse_plasticity.
# Both were declared here from the first commit but nothing ever assigned them, so the
# branch carried no NMDA current at all and could not leave the Mg2+-blocked range.
iTotNMDA = iTotNMDA1 + iTotNMDA2: amp
iTotNMDA1 : amp
iTotNMDA2 : amp
vSoma : volt

dgTotGABAB/dt = (-gTotGABAB+norm_factor_GABAB*gTotGABABRise)/tauGABABDecay : siemens
dgTotGABABRise/dt = -gTotGABABRise/tauGABABRise : siemens

# Back-propagating-AP calcium transient, per dendritic branch.
# These two lines already existed in eqs_dend_only but eqs_dend -- the equation set
# every experiment actually uses -- did not carry them, so the postsynaptic half of the
# Graupner-Brunel calcium signal had nowhere to live. Driven by the bAP synapse
# (Soma->Dend, delay = bAP_delay), which injects norm_factor_Ca into bAPCa_rise.
# norm_factor_Ca is chosen so a single bAP produces a peak of exactly 1.0, i.e. the
# same calcium scale as C_pre. That normalisation is why no separate C_post constant
# was ever needed.
dbAPCa/dt = (-bAPCa+bAPCa_rise)/tau_Ca_bAP_decay : 1
dbAPCa_rise/dt = -bAPCa_rise/tau_Ca_bAP_rise : 1
'''

eqs_dend_only = '''
dV/dt = (iDendL + iDendSyn - gEachCouple_pyr*(V-vSoma))/cDend_pyr : volt
iDendL = -gLDend_pyr*(V-vRest_pyr) : amp
iDendAMPA = -gTotAMPA*(V-vE_pyr) : amp
iDendGABA = -gTotGABA*(V-vI_pyr) : amp
iDendSyn = iDendAMPA + iTotNMDA + iDendGABA: amp

dgTotAMPA/dt = -gTotAMPA/tauAMPA : siemens
dgTotGABA/dt = -gTotGABA/tauGABA : siemens

iTotNMDA = iTotNMDA1 + iTotNMDA2: amp
iTotNMDA1 : amp
iTotNMDA2 : amp
vSoma : volt

dbAPCa/dt = (-bAPCa+bAPCa_rise)/tau_Ca_bAP_decay : 1
dbAPCa_rise/dt = -bAPCa_rise/tau_Ca_bAP_rise : 1
'''

eqs_soma_only = '''
dV/dt = (iL + iSyn + iClamp)/cSoma_pyr : volt (unless refractory)
iL = -gLSoma_pyr*(V-vRest_pyr) : amp
iAMPA = -gTotAMPA*(V-vE_pyr) : amp
iNMDA = -gTotNMDA*(V-vE_pyr)/(1+exp(-(V-vHalfNMDA)/vSpreadNMDA)) : amp
iGABA = -gTotGABA*(V-vI_pyr) : amp
iSyn = iAMPA + iNMDA + iGABA : amp

dgTotAMPA/dt = -gTotAMPA/tauAMPA : siemens
dgTotGABA/dt = -gTotGABA/tauGABA_soma : siemens
gTotNMDA : siemens
iClamp : amp
'''

# The biggest change (Option B): natively expressing the Graupner-Brunel synaptic weight dynamics
# in Brian 2 Synapses formulation instead of arbitrary Python loops.
#
# Graupner-Brunel Plasticity (Synapses equation):
eqs_synapse_plasticity_template = '''
# --- Calcium at this synapse -------------------------------------------------
# NMDA calcium, local to the synapse. This is Yang et al. (2016) Eq. 13:
#   tau_Ca * dc/dt = -c + kappa_Ca_NMDA * I_NMDA_local ,
# i.e. calcium is the LEAKY INTEGRAL of the local NMDA current, NOT a fixed per-spike
# jump. This matters because the NMDA current is regenerative under a dendritic plateau:
# a disinhibited branch reaches the plateau, sustains a large I_NMDA, and integrates
# calcium above theta_p (LTP) at realistic input rates; an inhibited (shunted) branch
# never plateaus, so I_NMDA and calcium stay low. The previous per-spike form
# (c += C_pre*mg on each spike) was only proportional to spike count and needed
# unrealistically high rates (~200 Hz) to cross theta_p -- see ROADMAP.md Bug 2.
# I_NMDA_local = gNMDA*s_nmda*mg_gate*(vE_pyr - V_post)  (inward, >0 since V_post<vE_pyr).
dc/dt = (-c + kappa_Ca_NMDA*gNMDA*s_nmda*mg_gate*(vE_pyr - V_post))/tau_Ca_NMDA : 1 (clock-driven)

# POSTSYNAPTIC component: the bAP calcium transient of the branch this synapse sits on.
# It is read from the dendrite rather than injected by an on_post handler, because the
# postsynaptic group (Dend) has no threshold and never spikes -- an on_post rule on this
# Synapses object can never fire. `on_post_plasticity` in this file is unusable for that
# reason; see the note beside it.
#
# Total calcium is the sum of the two, which is what makes plasticity here
# coincidence-dependent (Hebbian) rather than a pure function of presynaptic rate.
c_total = c + bAPCa_post : 1

# NMDA Mg2+ block, evaluated at the postsynaptic branch voltage. This is what makes
# the calcium influx depend on DENDRITIC STATE, and therefore what lets SOM inhibition
# gate plasticity: a shunted branch stays hyperpolarised, the block stays closed, and
# presynaptic spikes deposit almost no calcium there.
#
# The functional form and both constants are the project's own: eqs_soma already uses
# 1/(1+exp(-(V-vHalfNMDA)/vSpreadNMDA)) for its iNMDA term, with vHalfNMDA = -19.9 mV
# and vSpreadNMDA = 12.48 mV in parameters.py. That is the same Mg2+ block the NumPy
# models write as 1/(1+exp(-0.062*V)/3.57) -- half-activation -20.53 mV vs -19.9 mV,
# agreeing to within 0.064 across the physiological range. Using the Brian 2 constants
# keeps one parameterisation rather than importing a second.
mg_gate = 1.0/(1.0 + exp(-(V_post - vHalfNMDA)/vSpreadNMDA)) : 1

# --- Dendritic NMDA conductance ---------------------------------------------
# Saturating NMDA gating, the formulation the declared parameters belong to:
#     dx/dt = -x/tauNMDARise                  x += 1 on each presynaptic spike
#     ds/dt = -s/tauNMDADecay + alphaNMDA*x*(1-s)
#     iNMDA = -gNMDA*s*(V_post - vE_pyr)*mg_gate      summed onto the branch
#
# Why this formulation and not a GABA_B-style linear double exponential (the other
# pattern in this file): with the declared values a linear conductance reaches
# gNMDA*n*rate*tauDecay = 2.5*30*80*0.1 = 600 nS, 150x the dendritic leak, which would
# pin the branch at vE. The saturating form bounds s in [0,1], giving 62 nS at 80 Hz
# against a 75 nS ceiling. `alphaNMDA` (0.3/ms) exists only in the saturating form and
# is otherwise unused anywhere in the project, which is what identifies it.
#
# `iTotNMDA1` / `iTotNMDA2` were already declared as bare parameters on the dendrite.
# In Brian 2 that is precisely the signature of a summed-variable target: a NeuronGroup
# parameter that Synapses write into with `(summed)`. The two slots are two afferent
# pathways, matching the pathway-specific gating design. This synapse population uses
# slot 1; slot 2 is left free for a second pathway.
#
# NMDA is deliberately NOT scaled by the plastic weight w. In Graupner-Brunel, w is the
# AMPA efficacy that learning changes, while NMDA is the coincidence detector that
# reports dendritic state. Making NMDA plastic would also close a runaway loop
# (w up -> more NMDA -> more depolarisation -> more calcium -> more w).
dx_nmda/dt = -x_nmda/tauNMDARise : 1 (clock-driven)
ds_nmda/dt = -s_nmda/tauNMDADecay + alphaNMDA*x_nmda*(1 - s_nmda) : 1 (clock-driven)
iTotNMDA{nmda_slot}_post = -gNMDA*s_nmda*(V_post - vE_pyr)*mg_gate : amp (summed)

# Bistable weight dynamic components
# In Brian 2, we can represent heaviside step functions using inequality booleans (e.g., int(c > theta_p))
# AlphaP and AlphaD in the original loop represented time spent above threshold.
# Here we represent them as continuous rates.
#
# NOTE (unresolved, flagged by the provenance review): these terms carry 1/second where
# canonical Graupner-Brunel divides the whole right-hand side by tau, which makes them
# tau/(1 s) = 346x stronger than the double-well term while the noise term sits at
# canonical amplitude. Left exactly as found -- correcting it is a calibration decision,
# not part of connecting the calcium pathway.
ind_p = int(c_total > theta_p) : 1
ind_d = int(c_total > theta_d) : 1
rate_p = ind_p * 1/second : Hz
rate_d = ind_d * 1/second : Hz

# The bistable double-well potential
# NOTE ON THE INTEGRATOR: gating the noise makes it state-dependent, i.e. multiplicative,
# which Brian 2's `euler` state updater refuses. The plastic Synapses objects therefore
# use method='heun' (stochastic Heun, which supports multiplicative noise). This is a
# strictly better integrator for this equation, not a workaround.
#
# Noise is GATED on calcium activity via sqrt(ind_p + ind_d). Canonical
# Graupner-Brunel does this; the previous unconditional sigma*sqrt(1/tau)*xi meant a
# completely silent synapse random-walked away from its initial value -- measured
# drifting 0.500 -> 0.784, i.e. potentiation out of no input at all. With the gate a
# silent synapse holds still, so the inhibited branch is a real control condition.
drho/dt = -rho*(1-rho)*(0.5-rho)/tau + gamma_p*(1-rho)*rate_p - gamma_d*rho*rate_d + sigma*sqrt(1.0*(ind_p + ind_d))*sqrt(1/tau)*xi : 1 (clock-driven)

# Clipping w alone is not enough: it hides excursions of the STATE variable rho, which
# is what actually integrates. rho was observed at -0.011 and later at +1.562 while w
# stayed dutifully inside [0, 3]. The double-well term would restore rho on its own, but
# it is divided by tau = 346 s while the calcium terms are not (see the units note
# above), so its restoring force is ~5 orders of magnitude too weak to confine rho.
# `attach_rho_clipper` below clamps rho itself each timestep.
w = w0 + (w1-w0)*clip(rho, 0.0, 1.0) : 1
'''

# When pre-synaptic spikes arrive:
on_pre_plasticity = '''
gTotAMPA_post += w * gAMPA
x_nmda += 1
'''
# NOTE: calcium is no longer incremented per spike here. Under the Yang Eq. 13 model
# (see eqs_synapse_plasticity_template) calcium is the leaky integral of the NMDA
# current, driven by s_nmda (which x_nmda advances). C_pre is retained in parameters.py
# only for backward reference; it no longer scales the calcium.

# UNUSABLE as an on_post rule -- kept only for reference.
#
# The plastic synapses run from the pathway PoissonGroup onto `Dend`, and `Dend` is
# built with no threshold and no reset: it never emits a spike. An `on_post` pathway on
# that Synapses object therefore never fires, which is why this rule was never attached
# anywhere. `C_post_eff` was correspondingly never defined in parameters.py.
#
# The postsynaptic calcium contribution is instead taken from `bAPCa_post` inside
# eqs_synapse_plasticity, driven through the existing bAP synapse. Do not attach this
# rule expecting it to work.
on_post_plasticity = '''
c += C_post_eff
'''

# ============================================================
# Phase 2: Interneuron Equations (Zhang 2025 integration)
# ============================================================

# PV Interneuron — Fast-spiking LIF
# Receives: AMPA from MD Thalamus (excitatory), GABA from SOM (inhibitory)
# Projects: GABA onto Pyramidal soma
eqs_pv = '''
dV/dt = (iL + iAMPA + iGABA) / C_pv : volt (unless refractory)
iL = -gL_pv * (V - vRest_pv) : amp
iAMPA = -gTotAMPA * (V - vE_pv) : amp
iGABA = -gTotGABA * (V - vI_pv) : amp
dgTotAMPA/dt = -gTotAMPA / tauAMPA_pv : siemens
dgTotGABA/dt = -gTotGABA / tauGABA_pv : siemens
'''

# SOM Interneuron — Regular-spiking LIF
# Receives: baseline excitation, GABA from VIP (inhibitory)
# Projects: GABA onto Pyramidal dendrites
eqs_som = '''
dV/dt = (iL + iExc + iGABA) / C_som : volt (unless refractory)
iL = -gL_som * (V - vRest_som) : amp
iExc = iBaseline_som : amp
iGABA = -gTotGABA * (V - vI_som) : amp
dgTotGABA/dt = -gTotGABA / tauGABA_som_cell : siemens
iBaseline_som : amp
'''

# VIP Interneuron — Regular-spiking LIF
# Receives: AMPA from MD Thalamus (excitatory)
# Projects: GABA onto SOM (disinhibitory pathway)
eqs_vip = '''
dV/dt = (iL + iAMPA) / C_vip : volt (unless refractory)
iL = -gL_vip * (V - vRest_vip) : amp
iAMPA = -gTotAMPA * (V - vE_vip) : amp
dgTotAMPA/dt = -gTotAMPA / tauAMPA_vip : siemens
'''



# ============================================================
# Helper: keep rho inside its double well
# ============================================================
def attach_rho_clipper(syn):
    """Clamp `rho` to [0, 1] at the end of every timestep.

    `eqs_synapse_plasticity` clips only the derived weight `w`, so excursions of the
    integrated state `rho` were invisible in `w` but corrupted the dynamics (observed
    rho = -0.011 and +1.562). Because the confining double-well term is divided by tau
    while the calcium terms are not, the well cannot hold rho on its own.

    Brian 2 attaches the operation to the Synapses object's contained_objects, so adding
    the Synapses to a Network is enough -- no separate net.add() is needed.
    """
    syn.run_regularly('rho = clip(rho, 0.0, 1.0)', when='end')
    return syn


eqs_synapse_plasticity = eqs_synapse_plasticity_template.format(nmda_slot=1)


def make_eqs_synapse_plasticity(nmda_slot=1):
    """Plasticity equations writing their NMDA current into `iTotNMDA<slot>`.

    Brian 2 allows only ONE Synapses object to write a given summed variable on a target
    group, which is exactly why the dendrite declares two slots: `iTotNMDA1` and
    `iTotNMDA2`. Two afferent pathways onto the same branches therefore take slot 1 and
    slot 2 respectively -- the pathway-specific arrangement the declarations were for.

    `eqs_synapse_plasticity` remains the slot-1 string, so existing callers are
    unaffected.
    """
    if nmda_slot not in (1, 2):
        raise ValueError(f'nmda_slot must be 1 or 2, got {nmda_slot!r}')
    return eqs_synapse_plasticity_template.format(nmda_slot=nmda_slot)
