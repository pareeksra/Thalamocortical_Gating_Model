"""
InterneuronalCircuit.py — Python 3 port of Yang et al. 2016 analytical network model.

This module computes gating selectivity using analytical I/O functions
fitted to the multi-compartmental model, WITHOUT running spike-level simulations.
All computation is pure NumPy matrix math.

Original: Guangyu Robert Yang (2015)
Ported to Python 3: 2026
"""
import numpy as np
import copy
import time

# Analytical I/O functions fitted to the multi-compartmental model
def dend_IO(exc, inh):
    """Dendritic voltage as a function of excitatory and inhibitory conductance (nS)."""
    q = [5.5592051, 9.64361681, 6.5386557, 0.7779744]
    mid_point = q[0] * (4 + inh)
    spread = q[1] * np.exp(inh / q[2])
    v = 30 * (1 + np.tanh((exc - mid_point) / spread)) + q[3] - 70
    return v

def soma_fv(v):
    """Somatic firing rate (Hz) as a function of averaged dendritic voltage (mV)."""
    dv = v + 70
    fr = 2.59035567 + 0.13104463 * (dv ** 2.07809856)
    return fr

def soma_fI(I):
    """Somatic firing rate (Hz) as a function of injection current (pA)."""
    fr = ((I + 174.85951028) * (I > -174.85951028) / 45.16030095) ** 2.89003711
    return fr


class Study:
    def __init__(self, figpath='figures/', datapath='data/', version=None):
        self.figpath = figpath
        self.datapath = datapath
        if version is None:
            import datetime
            version = '_' + str(datetime.date.today())
        self.version = version

        # Default coupling conductance (from parameters.txt)
        # gCouple = num_DendEach * gEachCouple_pyr_vivo * 1e9
        # With num_DendEach=30, gEachCouple_pyr_vivo=0.8 nS: gCouple = 24 nS
        self.tauGABA = 20.0  # ms, from parameters
        self.gCouple = 30 * 0.8  # nS, num_DendEach * gEachCouple_pyr_vivo

    def get_exc(self, p, inh):
        """
        Compute excitatory conductance given inhibitory conductance.
        Models how disinhibition (low inh) enables excitation.

        Parameters:
            p: parameter dict with 'exc_type', 'inh_threshold', 'g_exc', 'inh_spread'
            inh: array of inhibitory conductances (nS) on each dendrite

        Returns:
            exc: array of excitatory conductances (nS)
        """
        if p['exc_type'] == 'binary':
            exc = (inh < p['inh_threshold']) * p['g_exc']
        elif p['exc_type'] == 'invprop_inh':
            exc = (p['inh_threshold'] - inh) * (p['inh_threshold'] > inh) / p['inh_threshold'] * p['g_exc']
        elif p['exc_type'] == 'sigmoid':
            exc = p['g_exc'] / (1 + np.exp((inh - p['inh_threshold']) / p['inh_spread']))
        return exc

    def generate_W(self, n_from, n_to, conn_density, syn_weight_total, method='strict'):
        """
        Generate connectivity matrix (n_to x n_from).

        Parameters:
            n_from: number of presynaptic neurons
            n_to: number of postsynaptic neurons
            conn_density: connection probability
            syn_weight_total: total synaptic weight onto one postsynaptic neuron
            method: 'strict', 'strict_interp', 'random', etc.

        Returns:
            W: connectivity matrix (n_to x n_from)
        """
        n_from2to = conn_density * n_from
        if method == 'strict':
            syn_weight = syn_weight_total / round(n_from2to)
        else:
            syn_weight = syn_weight_total / n_from2to

        if method == 'strict':
            W = np.zeros((n_to, n_from))
            W[:, :round(conn_density * n_from)] = syn_weight
            for row in W:
                np.random.shuffle(row)
        elif method == 'strict_interp':
            W = np.zeros((n_to, n_from))
            n_from_conn = int(np.floor(conn_density * n_from))
            W[:, :n_from_conn] = syn_weight
            if n_from_conn < n_from:
                W[:, n_from_conn] = syn_weight * (conn_density * n_from - n_from_conn)
            for row in W:
                np.random.shuffle(row)
        elif method == 'random':
            W = np.zeros(n_to * n_from)
            W[:round(conn_density * n_to * n_from)] = syn_weight
            np.random.shuffle(W)
            W = np.reshape(W, (n_to, n_from))
        return W

    def fI_SOM(self, current):
        """SOM interneuron f-I curve. current in pA, returns rate in Hz."""
        rheobase = 40  # pA
        fIslope = 90. / 1000  # Hz/pA
        rate = (current - rheobase) * fIslope
        rate = rate * (rate > 0)  # Rectify
        return rate

    def get_r_som(self, p):
        """Compute SOM firing rates given VIP-mediated disinhibition."""
        Exc2som_list = []
        Inh2som_list = []
        r_som_list = []

        n_exc2som = round(p['p_exc2som'] * p['n_som'])
        n_exc2vip = round(p['p_exc2vip'] * p['n_vip'])

        n_vip2som = p['p_vip2som'] * p['n_vip']
        p['w_vip2som'] = p['w_vip2som_total'] / n_vip2som
        W_vip2som = self.generate_W(p['n_vip'], p['n_som'], p['p_vip2som'],
                                    p['w_vip2som_total'], method='strict_interp')

        for i_path in range(p['n_path']):
            Exc2som = np.zeros(p['n_som'])
            Exc2som[:n_exc2som] = p['exc_som_mean'] * p['n_som'] / n_exc2som
            np.random.shuffle(Exc2som)

            r_vip = np.zeros(p['n_vip'])
            r_vip[:n_exc2vip] = p['r_vip_mean'] * p['n_vip'] / n_exc2vip
            np.random.shuffle(r_vip)
            Inh2som = np.dot(W_vip2som, r_vip)
            input2som = Exc2som - Inh2som + p['Exc2som0']

            r_som_list.append(self.fI_SOM(input2som))
            Exc2som_list.append(Exc2som)
            Inh2som_list.append(Inh2som)

        return r_som_list, Exc2som_list, Inh2som_list

    def get_r_som_novip(self, p):
        """Compute SOM firing rates without VIP (direct control of SOM)."""
        Exc2som_list = []
        Inh2som_list = []
        r_som_list = []

        n_exc2som = round(p['p_exc2som'] * p['n_som'])

        for i_path in range(p['n_path']):
            Inh2som = np.ones(p['n_som']) * p['Exc2som0']
            Exc2som = np.zeros(p['n_som'])
            Exc2som[:n_exc2som] = p['Exc2som0']
            np.random.shuffle(Exc2som)
            input2som = Exc2som - Inh2som + p['Exc2som0']

            r_som_list.append(self.fI_SOM(input2som))
            Exc2som_list.append(Exc2som)
            Inh2som_list.append(Inh2som)

        return r_som_list, Exc2som_list, Inh2som_list

    def Get_r_fromV(self, Exc, Inh, n_dend_each):
        """Get pyramidal firing rate from dendritic voltage (no somatic inhibition)."""
        DendV = dend_IO(Exc, Inh)
        MeanDendV = DendV.reshape(len(DendV) // n_dend_each, n_dend_each).mean(axis=1)
        SomaR = soma_fv(MeanDendV)
        return SomaR

    def Get_r(self, Exc, Inh, Inh2soma, n_dend_each):
        """Get pyramidal firing rate from injection current (with somatic inhibition)."""
        DendV = dend_IO(Exc, Inh)
        MeanDendV = DendV.reshape(len(DendV) // n_dend_each, n_dend_each).mean(axis=1)
        vSoma = -55  # Assume somatic voltage near reset
        SomaR = soma_fI(self.gCouple * (MeanDendV - vSoma) - Inh2soma)
        return SomaR

    def get_inh2soma(self, r_som, p):
        """
        Compute somatic inhibition via PV interneurons.

        The SOM→PV→Pyramidal pathway:
        - SOM inhibits PV (reducing PV activity)
        - PV inhibits Pyramidal soma
        - So SOM disinhibition of PV leads to increased somatic inhibition
        """
        Inh_pv2pyr = p['I_PV']  # Direct somatic inhibition (pA)
        Inh_som2pv = 0
        dr_pv = 0

        if p['with_PV']:
            fIslope_pv = 220. / 1000  # Hz/pA for PV neurons
            r_som0 = self.fI_SOM(p['Exc2som0'])
            dr_som = r_som - r_som0  # Change in SOM rate (primarily negative)
            Inh_som2pv = np.dot(p['W_som2pv'], dr_som)
            temp_mat = np.eye(p['n_pv']) / fIslope_pv + p['W_pv2pv']
            dr_pv = np.linalg.solve(temp_mat, -Inh_som2pv)  # Should be positive
            Inh_pv2pyr += np.dot(p['W_pv2pyr'], dr_pv)
            if p['I_PV'] > 0:
                print('WARNING: Direct I_PV not zero, though PV circuit is used')

        return Inh_pv2pyr, Inh_som2pv, dr_pv

    def get_gatingselectivity(self, p, verbose=False):
        """
        Main computation: compute the gating selectivity index.

        This measures how well the disinhibitory circuit can selectively
        gate specific input pathways to a pyramidal neuron.

        Returns:
            result dict with 'gs' (scalar), 'gs_list' (per-neuron), firing rates, etc.
        """
        result = dict()

        # Derived parameters
        p['n_dend'] = p['n_dend_each'] * p['n_pyr']
        p['p_som2dend'] = 1 - (1 - p['p_som2pyr']) ** (1. / p['n_dend_each'])
        p['n_som2dend'] = p['p_som2dend'] * p['n_som']

        start = time.time()
        W_som2dend = self.generate_W(p['n_som'], p['n_dend'], p['p_som2dend'],
                                     p['g_total'], method=p['gen_W_method'])

        # Activity pattern of SOM cells
        if not p['with_VIP']:
            r_som_list, Exc2som_list, Inh2som_list = self.get_r_som_novip(p)
        else:
            r_som_list, Exc2som_list, Inh2som_list = self.get_r_som(p)

        # PV neurons
        if p['with_PV']:
            p['W_som2pv'] = self.generate_W(p['n_som'], p['n_pv'], p['p_som2pv'],
                                            p['w_som2pv_total'], method=p['gen_W_method'])
            p['W_pv2pv'] = self.generate_W(p['n_pv'], p['n_pv'], p['p_pv2pv'],
                                           p['w_pv2pv_total'], method=p['gen_W_method'])
            p['W_pv2pyr'] = self.generate_W(p['n_pv'], p['n_pyr'], p['p_pv2pyr'],
                                            p['w_pv2pyr_total'], method=p['gen_W_method'])

        Exc2dend_list = []
        Inh2dend_list = []
        Exc2dend_total = 0

        Inh2soma_list = []
        Inh_som2pv_list = []
        dr_pv_list = []

        for i_path in range(p['n_path']):
            Inh2dend = np.dot(W_som2dend, r_som_list[i_path]) * self.tauGABA  # nS
            Exc2dend = self.get_exc(p, Inh2dend)  # nS
            Exc2dend_list.append(Exc2dend)
            Inh2dend_list.append(Inh2dend)
            Exc2dend_total += Exc2dend

            Inh2soma, Inh_som2pv, dr_pv = self.get_inh2soma(r_som_list[i_path], p)  # pA
            Inh2soma_list.append(Inh2soma)
            Inh_som2pv_list.append(Inh_som2pv)
            dr_pv_list.append(dr_pv)

        get_r = lambda exc, inh, inh2soma: self.Get_r(exc, inh, inh2soma, p['n_dend_each'])
        Exc0 = Exc2dend_list[0] * 0
        ron, roff, rnone, rboth = 0, 0, 0, 0
        for i_path in range(p['n_path']):
            ron += get_r(Exc2dend_list[i_path], Inh2dend_list[i_path],
                         Inh2soma_list[i_path]) / p['n_path']
            roff += get_r(Exc2dend_total - Exc2dend_list[i_path], Inh2dend_list[i_path],
                          Inh2soma_list[i_path]) / p['n_path']
            rnone += get_r(Exc0, Inh2dend_list[i_path],
                           Inh2soma_list[i_path]) / p['n_path']
            rboth += get_r(Exc2dend_total, Inh2dend_list[i_path],
                           Inh2soma_list[i_path]) / p['n_path']

        dron = ron - rnone
        droff = roff - rnone
        eps = 1e-5
        gs_list = np.array((dron - droff) / (dron + droff + eps))
        gs_list = (gs_list > 0) * (gs_list < 1) * gs_list + (gs_list > 1) * 1.

        gs1 = gs_list.mean()
        gs2 = (dron.mean() - droff.mean()) / (dron.mean() + droff.mean() + eps)

        if p['gating_selectivity_type'] == 'gs_of_mean':
            gs = gs2
        elif p['gating_selectivity_type'] == 'mean_of_gs':
            gs = gs1

        result['param'] = p
        for temp_list, name in zip(
            [gs, gs_list, ron, roff, rnone, rboth, W_som2dend,
             Exc2dend_list, Inh2dend_list, r_som_list,
             Exc2som_list, Inh2som_list, Inh2soma_list,
             Inh_som2pv_list, dr_pv_list],
            ['gs', 'gs_list', 'ron', 'roff', 'rnone', 'rboth', 'W_som2dend',
             'Exc2dend_list', 'Inh2dend_list', 'r_som_list',
             'Exc2som_list', 'Inh2som_list', 'Inh2soma_list',
             'Inh_som2pv_list', 'dr_pv_list']):
            result[name] = np.array(temp_list)

        if verbose:
            print('n_som2dend = %0.2f' % p['n_som2dend'])
            print('time taken %0.7f s' % (time.time() - start))
            print('gs1 is %0.5f, gs2 is %0.5f' % (gs1, gs2))

        return result

    def vary_x(self, param, var_name, var_plot):
        """Run parameter sweep over a single variable."""
        p = copy.deepcopy(param)
        gs_plot = []
        gs_low_plot = []
        gs_high_plot = []
        for var in var_plot:
            p[var_name] = var
            result = self.get_gatingselectivity(p)
            gs_plot.append(result['gs'])
            gs_list_sorted = np.sort(result['gs_list'])
            gs_low_plot.append(gs_list_sorted[round(0.1 * len(gs_list_sorted))])
            gs_high_plot.append(gs_list_sorted[round(0.9 * len(gs_list_sorted))])
            print('%s=%0.3f, gs=%0.3f' % (var_name, var, result['gs']))

        return np.array(gs_plot), np.array(gs_low_plot), np.array(gs_high_plot)

    def vary_x2(self, param, var_name_1, var_plot_1, var_name_2, var_plot_2):
        """Run parameter sweep over two co-varying variables."""
        p = copy.deepcopy(param)
        gs_plot = []
        gs_low_plot = []
        gs_high_plot = []
        for var_1, var_2 in zip(var_plot_1, var_plot_2):
            p[var_name_1] = var_1
            p[var_name_2] = var_2
            result = self.get_gatingselectivity(p)
            gs_plot.append(result['gs'])
            gs_list_sorted = np.sort(result['gs_list'])
            gs_low_plot.append(gs_list_sorted[round(0.1 * len(gs_list_sorted))])
            gs_high_plot.append(gs_list_sorted[round(0.9 * len(gs_list_sorted))])
            print('%s=%0.3f, %s=%0.3f, gs=%0.3f' % (var_name_1, var_1, var_name_2, var_2, result['gs']))

        return np.array(gs_plot), np.array(gs_low_plot), np.array(gs_high_plot)

    def get_p(self, modeltype, outside_params=None):
        """
        Get default parameter dictionary for a given model type.

        Model types:
            'SOM_alone': Direct control of SOM, no VIP
            'Control2VIPSOM': Control targets both VIP and SOM (default in paper)
            'Control2VIP': Control targets only VIP
        """
        if outside_params is None:
            outside_params = {}

        p = dict()
        # Population sizes in 400μm × 400μm of L2/3
        p['n_som'] = 160
        p['n_vip'] = 140
        p['n_pyr'] = 3000
        p['n_dend_each'] = 30
        p['p_vip2som'] = 0.6
        p['p_som2pyr'] = 0.6
        p['gen_W_method'] = 'strict_interp'
        p['g_total'] = 40  # nS, total inhibitory conductance per dendrite
        p['exc_type'] = 'invprop_inh'
        p['inh_threshold'] = 4.0  # nS
        p['Exc2som0'] = 150  # pA, baseline excitation keeping SOM firing
        p['g_exc'] = 25  # nS
        p['disinh_prop'] = 0.5
        p['type_som'] = 'random_overlap'
        p['gating_selectivity_type'] = 'mean_of_gs'
        p['n_path'] = 2
        p['r_vip_mean'] = 5  # Hz

        if modeltype == 'SOM_alone':
            p['with_VIP'] = False
            p['p_exc2som'] = 0.5
        elif modeltype == 'Control2VIPSOM':
            p['exc_som_mean'] = 75  # pA
            p['w_vip2som_total'] = 30  # pA/Hz
            p['p_exc2som'] = 0.5
            p['p_exc2vip'] = 0.5
            p['with_VIP'] = True
        elif modeltype == 'Control2VIP':
            p['exc_som_mean'] = 0  # pA
            p['w_vip2som_total'] = 30  # pA/Hz
            p['p_exc2som'] = 1
            p['p_exc2vip'] = 0.1
            p['with_VIP'] = True
            p['p_vip2som'] = 0.1

        # PV parameters
        p['with_PV'] = False
        p['I_PV'] = 0  # pA
        p['n_pv'] = 200
        p['p_som2pv'] = 0.8
        p['p_pv2pv'] = 0.9
        p['p_pv2pyr'] = 0.6
        p['w_som2pv_total'] = 20  # pA/Hz
        p['w_pv2pv_total'] = 30  # pA/Hz
        p['w_pv2pyr_total'] = 30  # pA/Hz

        p['modeltype'] = modeltype
        for key in outside_params:
            p[key] = outside_params[key]
        return p
