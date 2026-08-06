# Brian 2 native string equations based on data/equations.txt
# Notice that parameters are defined in parameters.py and passed into Brian 2 namespace or defined directly.

eqs_soma = '''
dV/dt = (iL + iSyn + iCoupleDend)/cSoma_pyr : volt
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

dbAPCa/dt = (-bAPCa+bAPCa_rise)/tau_Ca_bAP_decay : 1
dbAPCa_rise/dt = -bAPCa_rise/tau_Ca_bAP_rise : 1
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

iTotNMDA = iTotNMDA1 + iTotNMDA2: amp
iTotNMDA1 : amp
iTotNMDA2 : amp
vSoma : volt

dgTotGABAB/dt = (-gTotGABAB+norm_factor_GABAB*gTotGABABRise)/tauGABABDecay : siemens
dgTotGABABRise/dt = -gTotGABABRise/tauGABABRise : siemens
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
dV/dt = (iL + iSyn + iClamp)/cSoma_pyr : volt
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
eqs_synapse_plasticity = '''
# Calcium dynamics at this specific synapse
dc/dt = -c/tau_Ca_NMDA : 1 (clock-driven)

# Bistable weight dynamic components
# In Brian 2, we can represent heaviside step functions using inequality booleans (e.g., int(c > theta_p))
# AlphaP and AlphaD in the original loop represented time spent above threshold.
# Here we represent them as continuous rates.

rate_p = int(c > theta_p) * 1/second : Hz
rate_d = int(c > theta_d) * 1/second : Hz

# The bistable double-well potential
drho/dt = -rho*(1-rho)*(0.5-rho)/tau + gamma_p*(1-rho)*rate_p - gamma_d*rho*rate_d + sigma*sqrt(1/tau)*xi : 1 (clock-driven)

# Update weight based on rho state (clamped to prevent out-of-bounds due to noise)
w = w0 + (w1-w0)*clip(rho, 0.0, 1.0) : 1
'''

# When pre-synaptic spikes arrive:
on_pre_plasticity = '''
c += C_pre
gTotAMPA_post += w * gAMPA
'''

# When post-synaptic bAPs arrive (mediated by bAPCa variable in dendrite):
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
dV/dt = (iL + iAMPA + iGABA) / C_pv : volt
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
dV/dt = (iL + iExc + iGABA) / C_som : volt
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
dV/dt = (iL + iAMPA) / C_vip : volt
iL = -gL_vip * (V - vRest_vip) : amp
iAMPA = -gTotAMPA * (V - vE_vip) : amp
dgTotAMPA/dt = -gTotAMPA / tauAMPA_vip : siemens
'''

