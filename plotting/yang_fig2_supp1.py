"""
yang_fig2_supp1.py -- simulation + plotting library for the notebook
notebooks/yang_fig2_supp1.ipynb (2026-11-02).

Replicates, with THIS PROJECT'S model (model/parameters.py + model/equations.py), the
reduced-model panels of
  Yang, Murray & Wang 2016, Fig. 2   (b NMDA plateau, c disinhibition opens the gate,
                                      e tuning curve gate 1 vs gate 2, f,g 2-D tuning)
  Yang 2016 Supplementary Fig. 1e-h  (f plateau vs number of synapses, g NMDA input vs rate
                                      with/without inhibition, h same with AMPA input)

Nothing here re-declares the biophysics: the dendrite is `eqs_dend`, the soma `eqs_soma`,
the excitatory synapse `eqs_synapse_plasticity` + `on_pre_plasticity` (plasticity frozen,
rho fixed), all with parameter values from `model/parameters.py`. Any entry of those
parameter dicts can be overridden through `model_overrides` (e.g. {'gNMDA': 3*nS}).
Protocol numbers that are not model parameters (synapse counts, rates, durations, the
tuning curve) come from Yang's Methods and are arguments with Yang's values as defaults.

Yang Methods used:
  * Fig. 2d-g: each pathway targets 2 dendrites with 15 NMDAR synapses each, no overlap;
    input rate u_E = 40 exp(-z^2) Hz, z in [-2.4, 2.4]; inhibition 35 Hz on inhibited and
    5 Hz on disinhibited dendrites (disinhibition level 30 Hz); in-vivo set: soma-dendrite
    coupling 0.8 nS, soma background 500 Hz x 2.5 nS AMPA + 150 Hz x 4 nS GABA (~3 Hz).
  * Supp. Fig. 1f-h: 15 excitatory synapses; NMDA (g) or AMPA 2.5 nS (h) input; inhibition
    0 vs 30 Hz. Inhibition here = n_inh Poisson GABA synapses of gGABA each (10 x 4 nS =
    Yang's G_SOM->dend 40 nS).
  * Inhibition rate r_I is the TOTAL rate onto a dendrite, each event 4 nS (gGABA), tau 20 ms:
    g_I = r_I tau_GABA g_GABA (Yang Methods), i.e. 35 Hz -> 2.8 nS, 5 Hz -> 0.4 nS (n_inh = 1).
Deviations (each a parameter, so it can be changed in the notebook):
  * Fig. 2b/c and Supp. 1f-h use one dendrite coupled to a soma clamped at rest. Yang's soma
    was free; clamping it with the in-vitro 4 nS coupling loads the branch so much that no
    plateau forms, so the default coupling here is the in-vivo 0.8 nS (couple_dend_nS).
  * Soma background: Yang's 500 Hz x 2.5 nS drives OUR soma to ~20 Hz; 300 Hz gives Yang's
    ~3-4 Hz baseline (bg_exc_hz). Panels a/d/e(schematic) and the reconstructed-
morphology panels (Supp. 1a-d, a NEURON model) are not reproduced.
"""
import os, sys
import numpy as np
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(PROOT, 'model'), PROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from brian2 import (NeuronGroup, PoissonGroup, SpikeGeneratorGroup, Synapses, StateMonitor,
                    SpikeMonitor, PoissonInput, Network, seed, prefs, second, ms, mV, nS, Hz,
                    BrianLogger)
from parameters import params, plasticity_params
from equations import eqs_dend, eqs_soma, eqs_synapse_plasticity, on_pre_plasticity
from context_circuit import _syn_model

prefs.codegen.target = 'cython'
BrianLogger.suppress_name('resolution_conflict', 'base')

YANG = dict(n_exc=15, n_inh=1, rho=1 / 3,            # rho = 1/3 -> w = 1 (Yang's pre-learning weight)
            g_ampa_supp_nS=2.5,                       # Supp. 1d,h AMPA conductance
            inh_off_hz=0.0, inh_on_hz=30.0,           # Supp. 1g,h
            inh_closed_hz=35.0, inh_open_hz=5.0,      # Fig. 2c,e-g
            couple_vitro_nS=4.0, couple_vivo_nS=0.8,
            couple_dend_nS=0.8,                       # used for the isolated-dendrite panels (see notes)
            n_dend_per_path=2, u_max_hz=40.0,
            bg_exc_hz=500.0, bg_exc_nS=2.5, bg_inh_hz=150.0, bg_inh_nS=4.0,
            bg_exc_hz_model=300.0)                    # our soma: 300 Hz gives Yang's ~3-4 Hz baseline


def model_params(model_overrides=None, couple_nS=4.0, ndend=1):
    """Project parameter dict (parameters.py) with derived constants, plus overrides."""
    p = dict(params); p.update(plasticity_params)
    for k, v in (model_overrides or {}).items():
        if k not in p:
            raise KeyError(f"unknown model parameter {k!r}")
        p[k] = v
    p['num_DendEach'] = ndend; p['num_Dend'] = ndend; p['num_Soma'] = 1
    p['gEachCouple_pyr'] = couple_nS * nS; p['gTotCouple_pyr'] = couple_nS * nS * ndend
    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']; p['norm_factor_Ca'] = t ** (1 / (t - 1))
    t = p['tauGABABRise'] / p['tauGABABDecay']; p['norm_factor_GABAB'] = t ** (1 / (t - 1))
    return p


def _receptor_overrides(receptor, model_overrides, g_ampa_nS):
    """'nmda': NMDA-only input (AMPA off). 'ampa': AMPA-only at g_ampa_nS (NMDA off).
    'both': the project's default synapse (AMPA 0.4 nS x w plus NMDA)."""
    ov = dict(model_overrides or {})
    if receptor == 'nmda':
        ov.setdefault('gAMPA', 0 * nS)
    elif receptor == 'ampa':
        ov['gNMDA'] = 0 * nS; ov['gAMPA'] = g_ampa_nS * nS
    return ov


# ----------------------------------------------------------------------------------
# isolated dendrite (soma clamped at rest): Fig. 2b,c and Supp. Fig. 1f-h
# ----------------------------------------------------------------------------------
def sim_dendrites(conds, T=1.0, receptor='nmda', n_exc=YANG['n_exc'], n_inh=YANG['n_inh'],
                  rho=YANG['rho'], couple_nS=YANG['couple_dend_nS'], g_ampa_nS=YANG['g_ampa_supp_nS'],
                  model_overrides=None, nmda_plastic=False, seed_val=1, record_dt_ms=0.5):
    """One dendrite per condition. conds: list of dicts with keys
         rate (Hz Poisson per excitatory synapse) OR volley (number of synapses that each fire
         one spike at t = 50 ms); inh (Hz per inhibitory synapse, default 0).
    Returns dict(t_ms, V (n_cond x n_t, mV), mean_V (mV, t > 200 ms), peak_V)."""
    seed(seed_val)
    p = model_params(_receptor_overrides(receptor, model_overrides, g_ampa_nS), couple_nS, 1)
    n = len(conds)
    D = NeuronGroup(n, eqs_dend, method='euler', namespace=p)
    D.V = p['vRest_pyr']; D.vSoma = p['vRest_pyr']             # soma clamped at rest
    syn_model = _syn_model(eqs_synapse_plasticity, nmda_plastic)
    objs = [D]
    rates = np.array([c.get('rate', 0.0) for c in conds])
    if np.any(rates > 0):
        P = PoissonGroup(n * n_exc, rates=np.repeat(rates, n_exc) * Hz)
        S = Synapses(P, D, model=syn_model, on_pre=on_pre_plasticity, method='heun', namespace=p)
        S.connect(j=f'i // {n_exc}'); S.rho = rho
        objs += [P, S]
    vol = [(k, c['volley']) for k, c in enumerate(conds) if c.get('volley')]
    if vol:
        idx = np.concatenate([np.arange(k * n_exc, k * n_exc + min(m, n_exc)) for k, m in vol])
        G = SpikeGeneratorGroup(n * n_exc, idx, np.full(len(idx), 50.0) * ms)
        S2 = Synapses(G, D, model=syn_model, on_pre=on_pre_plasticity, method='heun', namespace=p)
        S2.connect(j=f'i // {n_exc}'); S2.rho = rho
        objs += [G, S2]
    inh = np.array([c.get('inh', 0.0) for c in conds])
    if np.any(inh > 0) and n_inh > 0:
        I = PoissonGroup(n * n_inh, rates=np.repeat(inh, n_inh) * Hz)
        SI = Synapses(I, D, on_pre='gTotGABA_post += gGABA', namespace=p)
        SI.connect(j=f'i // {n_inh}')
        objs += [I, SI]
    M = StateMonitor(D, 'V', record=True, dt=record_dt_ms * ms)
    net = Network(*objs, M)
    net.run(T * second)
    t = np.asarray(M.t / ms); V = np.asarray(M.V / mV)
    late = t > 200
    return dict(t_ms=t, V=V, mean_V=V[:, late].mean(1), peak_V=V.max(1))


# ----------------------------------------------------------------------------------
# whole neuron (soma + 2 pathways x n_dend_per_path dendrites): Fig. 2e-g
# ----------------------------------------------------------------------------------
def sim_neurons(z1, z2, gate, T=3.0, n_exc=YANG['n_exc'], n_inh=YANG['n_inh'], rho=YANG['rho'],
                n_dend_per_path=YANG['n_dend_per_path'], u_max_hz=YANG['u_max_hz'],
                inh_closed_hz=YANG['inh_closed_hz'], inh_open_hz=YANG['inh_open_hz'],
                couple_nS=YANG['couple_vivo_nS'], receptor='nmda', model_overrides=None,
                nmda_plastic=False, bg_exc_hz=YANG['bg_exc_hz_model'], bg_inh_hz=YANG['bg_inh_hz'], seed_val=1):
    """One neuron per (z1[k], z2[k]) pair. gate: None (all dendrites inhibited, 'default
    context'), 1 or 2 (that pathway's dendrites disinhibited). Pathway input z = None means
    the pathway is silent. Returns the somatic output rate per neuron (Hz)."""
    seed(seed_val)
    nd = 2 * n_dend_per_path
    p = model_params(_receptor_overrides(receptor, model_overrides, YANG['g_ampa_supp_nS']), couple_nS, nd)
    p['gTotNMDA'] = 0 * nS
    N = len(z1)
    Soma = NeuronGroup(N, eqs_soma.replace('gTotNMDA : siemens', ''), threshold='V > vThres_pyr',
                       reset='V = vReset_pyr', refractory=p['refracTime_pyr'], method='euler', namespace=p)
    Soma.V = p['vRest_pyr']; Soma.vShadow = p['vRest_pyr']; Soma.vAveDend = p['vRest_pyr']
    D = NeuronGroup(N * nd, eqs_dend, method='euler', namespace=p)
    D.V = p['vRest_pyr']; D.vSoma = p['vRest_pyr']
    ns = dict(p); ns['n_dend_cpl'] = float(nd)
    d2s = Synapses(D, Soma, model='vAveDend_post = V_pre / n_dend_cpl : volt (summed)', namespace=ns)
    d2s.connect(j=f'i // {nd}')
    s2d = Synapses(Soma, D, model='vSoma_post = vShadow_pre : volt (summed)', namespace=ns)
    s2d.connect(i=np.arange(N * nd) // nd, j=np.arange(N * nd))
    objs = [Soma, D, d2s, s2d]
    # pathway of each dendrite: first n_dend_per_path -> pathway 1, rest -> pathway 2
    path = np.tile(np.repeat([1, 2], n_dend_per_path), N)
    zz = np.where(path == 1, np.repeat(np.asarray(z1, dtype=object), nd), np.repeat(np.asarray(z2, dtype=object), nd))
    u = np.array([0.0 if z is None else u_max_hz * np.exp(-float(z) ** 2) for z in zz])
    P = PoissonGroup(N * nd * n_exc, rates=np.repeat(u, n_exc) * Hz)
    S = Synapses(P, D, model=_syn_model(eqs_synapse_plasticity, nmda_plastic), on_pre=on_pre_plasticity,
                 method='heun', namespace=p)
    S.connect(j=f'i // {n_exc}'); S.rho = rho
    inh = np.where(path == gate, inh_open_hz, inh_closed_hz) if gate in (1, 2) else np.full(N * nd, inh_closed_hz)
    I = PoissonGroup(N * nd * n_inh, rates=np.repeat(inh, n_inh) * Hz)
    SI = Synapses(I, D, on_pre='gTotGABA_post += gGABA', namespace=p)
    SI.connect(j=f'i // {n_inh}')
    objs += [P, S, I, SI]
    if bg_exc_hz > 0:
        objs.append(PoissonInput(Soma, 'gTotAMPA', 1, bg_exc_hz * Hz, weight=YANG['bg_exc_nS'] * nS))
    if bg_inh_hz > 0:
        objs.append(PoissonInput(Soma, 'gTotGABA', 1, bg_inh_hz * Hz, weight=YANG['bg_inh_nS'] * nS))
    M = SpikeMonitor(Soma)
    net = Network(*objs, M)
    net.run(T * second)
    return np.bincount(np.asarray(M.i), minlength=N) / T


# ----------------------------------------------------------------------------------
# figures
# ----------------------------------------------------------------------------------
def supp1_data(P):
    """Supplementary Fig. 1f-h data for parameter dict P (see the notebook)."""
    ns = list(P['volley_n'])
    f = sim_dendrites([dict(volley=k) for k in ns], T=P['T_trace'], receptor='nmda', n_exc=max(ns),
                      n_inh=P['n_inh'], rho=P['rho'], couple_nS=P['couple_dend_nS'],
                      model_overrides=P['model_overrides'], nmda_plastic=P['nmda_plastic'], seed_val=P['seed'])
    rates = list(P['rates'])
    out = dict(f=f, volley_n=ns, rates=rates)
    for key, rec in (('g', 'nmda'), ('h', 'ampa')):
        conds = [dict(rate=r, inh=i) for i in (P['inh_off_hz'], P['inh_on_hz']) for r in rates]
        out[key] = sim_dendrites(conds, T=P['T_rate'], receptor=rec, n_exc=P['n_exc'], n_inh=P['n_inh'],
                                 rho=P['rho'], couple_nS=P['couple_dend_nS'], g_ampa_nS=P['g_ampa_supp_nS'],
                                 model_overrides=P['model_overrides'], nmda_plastic=P['nmda_plastic'],
                                 seed_val=P['seed'])['mean_V'].reshape(2, len(rates))
    return out


def plot_supp1(P, data=None):
    import matplotlib.pyplot as plt
    d = data or supp1_data(P)
    fig, ax = plt.subplots(1, 3, figsize=(14, 4))
    cm = plt.cm.Blues(np.linspace(0.35, 1, len(d['volley_n'])))
    for c, k, v in zip(cm, d['volley_n'], d['f']['V']):
        ax[0].plot(d['f']['t_ms'], v, color=c, lw=1.4, label=f'{k}')
    ax[0].set(xlabel='time (ms)', ylabel='$V_D$ (mV)', title='f  NMDA plateau vs # activated synapses')
    ax[0].legend(title='# synapses', fontsize=7, frameon=False, ncol=2)
    for a, key, t in ((ax[1], 'g', 'g  NMDA input'), (ax[2], 'h', 'h  AMPA input')):
        a.plot(d['rates'], d[key][0], 'o-', color='#6BAED6', label=f"inhibition {P['inh_off_hz']:g} Hz")
        a.plot(d['rates'], d[key][1], 'o-', color='#08306B', label=f"inhibition {P['inh_on_hz']:g} Hz")
        a.set(xlabel='excitatory input rate (Hz)', ylabel=r'mean $V_D$ (mV)', title=t, ylim=(-75, 0))
        a.legend(fontsize=8, frameon=False)
    for a in ax:
        a.spines[['top', 'right']].set_visible(False)
    fig.suptitle('Yang 2016 Supplementary Fig. 1f-h, reproduced with Model A (reduced model)', fontsize=11)
    fig.tight_layout()
    return fig, d


def fig2_data(P):
    """Fig. 2b,c,e,f,g data."""
    ns = list(P['volley_n'])
    b = sim_dendrites([dict(volley=k) for k in ns], T=P['T_trace'], receptor='nmda', n_exc=max(ns),
                      n_inh=P['n_inh'], rho=P['rho'], couple_nS=P['couple_dend_nS'],
                      model_overrides=P['model_overrides'], nmda_plastic=P['nmda_plastic'], seed_val=P['seed'])
    rates = list(P['rates'])
    c = sim_dendrites([dict(rate=r, inh=i) for i in (P['inh_closed_hz'], P['inh_open_hz']) for r in rates],
                      T=P['T_rate'], receptor='nmda', n_exc=P['n_exc'], n_inh=P['n_inh'], rho=P['rho'],
                      couple_nS=P['couple_dend_nS'], model_overrides=P['model_overrides'],
                      nmda_plastic=P['nmda_plastic'], seed_val=P['seed'])['mean_V'].reshape(2, len(rates))
    kw = dict(T=P['T_neuron'], n_exc=P['n_exc'], n_inh=P['n_inh'], rho=P['rho'],
              n_dend_per_path=P['n_dend_per_path'], u_max_hz=P['u_max_hz'], inh_closed_hz=P['inh_closed_hz'],
              inh_open_hz=P['inh_open_hz'], couple_nS=P['couple_vivo_nS'], model_overrides=P['model_overrides'],
              nmda_plastic=P['nmda_plastic'], bg_exc_hz=P['bg_exc_hz'], bg_inh_hz=P['bg_inh_hz'],
              seed_val=P['seed'])
    z = np.linspace(-2.4, 2.4, P['n_z'])
    e = {g: sim_neurons(z, [None] * len(z), gate=g, **kw) for g in (1, 2)}
    e['base'] = {g: float(sim_neurons([None], [None], gate=g, **kw)[0]) for g in (1, 2)}
    z2 = np.linspace(-2.4, 2.4, P['n_z2d'])
    Z1, Z2 = np.meshgrid(z2, z2, indexing='ij')
    fg = {g: sim_neurons(Z1.ravel(), Z2.ravel(), gate=g, **kw).reshape(Z1.shape) for g in (None, 1)}
    on = e[1][len(z) // 2] - e['base'][1]; off = e[2][len(z) // 2] - e['base'][2]
    S = (on - off) / (on + off) if on + off > 0 else float('nan')
    return dict(b=b, volley_n=ns, rates=rates, c=c, z=z, e=e, z2=z2, fg=fg, S=S)


def plot_fig2(P, data=None):
    import matplotlib.pyplot as plt
    d = data or fig2_data(P)
    fig = plt.figure(figsize=(15, 8.5))
    gs = fig.add_gridspec(2, 3)
    a = fig.add_subplot(gs[0, 0])
    cm = plt.cm.Blues(np.linspace(0.35, 1, len(d['volley_n'])))
    for c, k, v in zip(cm, d['volley_n'], d['b']['V']):
        a.plot(d['b']['t_ms'], v, color=c, lw=1.4, label=f'{k}')
    a.set(xlabel='time (ms)', ylabel='$V_D$ (mV)', title='b  NMDA plateau potential')
    a.legend(title='# synapses', fontsize=7, frameon=False, ncol=2)
    a = fig.add_subplot(gs[0, 1])
    a.plot(d['rates'], d['c'][1], 'o-', color='#6BAED6', label=f"disinhibited ({P['inh_open_hz']:g} Hz)")
    a.plot(d['rates'], d['c'][0], 'o-', color='#08306B', label=f"inhibited ({P['inh_closed_hz']:g} Hz)")
    a.set(xlabel='excitatory input rate (Hz)', ylabel=r'mean $V_D$ (mV)', ylim=(-75, 0),
          title='c  disinhibition opens the gate')
    a.legend(fontsize=8, frameon=False)
    a = fig.add_subplot(gs[0, 2])
    a.plot(d['z'], d['e'][1], 'o-', color='#6BAED6', label='gate 1 open')
    a.plot(d['z'], d['e'][2], 'o-', color='#08306B', label='gate 2 open')
    a.set(xlabel='stimulus z (pathway 1 only)', ylabel='output rate (Hz)',
          title=f"e  tuning to pathway 1   (gating selectivity S = {d['S']:.2f})")
    a.legend(fontsize=8, frameon=False)
    vmax = max(d['fg'][None].max(), d['fg'][1].max())
    for col, g, t in ((0, None, 'f  2-D tuning, default context (all gates closed)'),
                      (1, 1, 'g  2-D tuning, gate 1 open')):
        a = fig.add_subplot(gs[1, col])
        im = a.imshow(d['fg'][g].T, origin='lower', extent=[-2.4, 2.4, -2.4, 2.4], vmin=0, vmax=vmax,
                      cmap='viridis', aspect='auto')
        a.set(xlabel='pathway 1 stimulus', ylabel='pathway 2 stimulus', title=t)
        fig.colorbar(im, ax=a, label='output rate (Hz)')
    for ax_ in fig.axes:
        if ax_.get_label() != '<colorbar>':
            ax_.spines[['top', 'right']].set_visible(False)
    fig.suptitle('Yang 2016 Fig. 2b,c,e-g, reproduced with Model A (reduced compartmental neuron)', fontsize=12)
    fig.tight_layout()
    return fig, d


DEFAULTS = dict(
    seed=1, rho=YANG['rho'], nmda_plastic=False, model_overrides={},
    # Supp. 1f / Fig. 2b
    volley_n=[5, 10, 15, 20, 25, 30, 35, 40], T_trace=0.4,
    # Supp. 1g,h / Fig. 2c
    rates=[0, 5, 10, 20, 30, 40, 60, 80, 100], T_rate=2.0, n_exc=YANG['n_exc'], n_inh=YANG['n_inh'],
    inh_off_hz=YANG['inh_off_hz'], inh_on_hz=YANG['inh_on_hz'], g_ampa_supp_nS=YANG['g_ampa_supp_nS'],
    couple_dend_nS=YANG['couple_dend_nS'],
    # Fig. 2c,e-g
    inh_closed_hz=YANG['inh_closed_hz'], inh_open_hz=YANG['inh_open_hz'],
    n_dend_per_path=YANG['n_dend_per_path'], u_max_hz=YANG['u_max_hz'], couple_vivo_nS=YANG['couple_vivo_nS'],
    bg_exc_hz=YANG['bg_exc_hz_model'], bg_inh_hz=YANG['bg_inh_hz'],
    n_z=13, n_z2d=9, T_neuron=3.0,
)
