import numpy as np
from brian2 import *
from parameters import params, plasticity_params
from equations import eqs_soma, eqs_dend, eqs_soma_only, eqs_dend_only, eqs_synapse_plasticity, on_pre_plasticity, on_post_plasticity

# Set Brian 2 preferences for code generation
prefs.codegen.target = 'numpy'  # or 'cython' for performance

class Model(Network):
    """
    Brian 2 implementation of the Multi-Compartmental Model.
    Inherits from brian2.Network to manage all objects.
    """
    def __init__(self, outsidePara=dict(), rndSeed=None):
        super(Model, self).__init__()
        
        # Merge parameters
        self.p = params.copy()
        self.p.update(plasticity_params)
        for key, val in outsidePara.items():
            self.p[key] = val
            
        if rndSeed is not None:
            np.random.seed(324823 + rndSeed)
            seed(324823 + rndSeed) # Brian2 random seed
            
        self.n = dict()
        self.mon = dict()
        
    def make_model(self, num_soma=1, condition='invitro', clamped_dendvolt=None, record_all=True):
        p = self.p
        p['num_Soma'] = num_soma
        p['num_Dend'] = p['num_DendEach'] * num_soma
        
        if condition == 'invivo':
            p['gEachCouple_pyr'] = p['gEachCouple_pyr_vivo']
        p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * p['num_DendEach']
        
        temp = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']
        p['norm_factor_Ca'] = temp ** (1 / (temp - 1))
        
        temp = p['tauGABABRise'] / p['tauGABABDecay']
        p['norm_factor_GABAB'] = temp ** (1 / (temp - 1))
        
        # Soma Group
        # Custom refractoriness is handled differently in Brian 2.
        # We specify the reset explicitly.
        reset_eqs = '''
        V = vReset_pyr
        '''
        
        self.n['Soma'] = NeuronGroup(p['num_Soma'], eqs_soma, threshold='V > vThres_pyr',
                                     reset=reset_eqs, refractory=p['refracTime_pyr'],
                                     method='euler', namespace=p)
        self.n['Soma'].V = p['vRest_pyr']
        self.n['Soma'].vShadow = p['vRest_pyr']
        self.n['Soma'].vAveDend = p['vRest_pyr']
        
        # Dendrite Group
        self.n['Dend'] = NeuronGroup(p['num_Dend'], eqs_dend, method='euler', namespace=p)
        self.n['Dend'].V = p['vRest_pyr']
        self.n['Dend'].vSoma = p['vRest_pyr']
        
        # Brian 2 Network Operation for coupling
        if clamped_dendvolt is not None:
            @network_operation(dt=p['sim_dt'])
            def ClampedDend():
                self.n['Soma'].vAveDend = clamped_dendvolt
                # repeat equivalent for Brian 2 variables
                self.n['Dend'].vSoma = np.repeat(self.n['Soma'].vShadow[:], p['num_DendEach'])
            self.add(ClampedDend)
        else:
            @network_operation(dt=p['sim_dt'])
            def SomaDendCoupling():
                temp = self.n['Dend'].V[:].reshape((p['num_Soma'], p['num_DendEach']))
                self.n['Soma'].vAveDend = np.mean(temp, axis=1)
                self.n['Dend'].vSoma = np.repeat(self.n['Soma'].vShadow[:], p['num_DendEach'])
            self.add(SomaDendCoupling)
            
        # bAP: When soma spikes, deliver voltage kick to dendrite
        self.n['bAP'] = Synapses(self.n['Soma'], self.n['Dend'], on_pre='V_post += bAP_amp\nbAPCa_rise_post += norm_factor_Ca', delay=p['bAP_delay'], namespace=p)
        # Connect soma to its corresponding dendrites
        self.n['bAP'].connect(j='i*num_DendEach + k for k in range(num_DendEach)')
        
        if record_all:
            self.mon['MvDend'] = StateMonitor(self.n['Dend'], 'V', record=True, dt=p['record_dt'])
            self.mon['MvSoma'] = StateMonitor(self.n['Soma'], 'V', record=True, dt=p['record_dt'])
            self.mon['MiNMDA'] = StateMonitor(self.n['Dend'], 'iTotNMDA', record=True, dt=p['record_dt'])
            
        self.mon['MSpike'] = SpikeMonitor(self.n['Soma'])
        
        # Add all objects to the network
        self.add([self.n['Soma'], self.n['Dend'], self.n['bAP'], self.mon['MSpike']])
        if record_all:
            self.add([self.mon['MvDend'], self.mon['MvSoma'], self.mon['MiNMDA']])

    def add_plastic_synapses(self, source_group, target_dendrites, p_connect=1.0):
        """
        Helper method for Option B: adding Graupner-Brunel synapses.
        """
        # Create synapses using the native equations
        syn = Synapses(source_group, target_dendrites, model=eqs_synapse_plasticity,
                       on_pre=on_pre_plasticity, method='heun', namespace=self.p)
        syn.connect(p=p_connect)
        syn.rho = 0
        return syn

# Helper IO functions for plotting logic.
# NOTE: the duplicate `dend_IO` that used to live here was removed -- it was imported
# by nothing. The single canonical definition is in `dendritic_io.py` at the project
# root. Do not re-add a local copy.

def soma_fv(v):
    dv = v + 70
    fr = 2.59035567 + 0.13104463 * (dv ** 2.07809856)
    return fr
