"""
yang_figures.py -- spiking simulations behind notebooks/yang_replication.ipynb: every Yang,
Murray & Wang 2016 figure that can be reproduced with THIS project's model (2026-11-19).

Parts (all from model/parameters.py + model/equations.py; canonical synapse = NMDA-only, w = 3 rho):
  supp4_dend  Supp. Fig. 4b: mean dendritic voltage vs excitatory conductance g_E for inhibitory
              input rates 0-100 Hz (15 NMDA synapses at 30 Hz, per-synapse conductance
              0.25-5 nS; soma clamped at -60 mV, as in Yang's Methods). The notebook fits Yang's
              sigmoid family (Eqs. 20-22) to it -> OUR rate dendrite.
  supp4_soma  Supp. Fig. 4c: soma rate vs input current from the dendrites I = Gc (V_D - E_reset)
              (dendritic voltage held at V_D, Gc = 8 nS as Yang), for several soma background
              rates. The notebook fits Yang's power law -> OUR rate soma. The background that
              gives Yang's ~1.8 Hz at rest is used for Fig. 3.
  fig2        Fig. 2b,c,e-g and Supp. Fig. 1f-h (plotting/yang_fig2_supp1.py, defaults).
  supp3       Supp. Fig. 3c: gating selectivity vs AMPA fraction g_AMPA/(g_AMPA + g_NMDA), sum
              2.5 nS, in the Fig. 2e protocol.
  fig3        Fig. 3b,c on a SPIKING neuron with N_dend = 10, 20, 30 dendrites (Yang used the
              rate model): pathway 1 targets N_disinh random dendrites (15 NMDA synapses each,
              40 Hz = preferred stimulus), gate k disinhibits its pathway's dendrites (5 Hz vs
              5 + D Hz inhibition, D = 10, 20, 30 Hz); gate 2's dendrites are drawn independently,
              so the patterns overlap. Total soma-dendrite coupling fixed at 8 nS (Yang Methods).
              r_on, r_off baseline-corrected and averaged over 32 random draws (4 s each).
              'disjoint' = gate 2's dendrites drawn from the complement (Yang's diamonds).
  fig7        Fig. 7c-e with the canonical circuit (MD -> VIP -> SOM -> branch, our plasticity):
              learn pattern A in context A then B in context B (8 x 3 s each at 50 Hz, Yang's
              rate), then frozen readout: tuning to pathway 1 (u = U exp(-z^2)) with gate 1 or
              gate 2 open, and the 2-D tuning with gate 1 open. Yang equalised the excitatory
              conductance before/after learning (8 vs 5 of 15 synapses active); here U_after =
              10 Hz (our readout window) and U_before = U_after x sum(w_after) / sum(w_before).
Not reproducible with this model: Fig. 1 (schematic), Fig. 8 and Supp. Fig. 8 (fits to monkey
behaviour, Mante et al. 2013, plus a separate decision network), Supp. Fig. 7 (fit to Sjostrom
et al. 2001 data), Supp. Fig. 1a-d (reconstructed NEURON morphology). Figs. 4-6 and Supp.
Figs. 5-6 are rate-network results in Yang too; the notebook computes them with the rate model
fitted here (plotting/yang_rate_model.py).

Run:  <py> -I experiments/yang_figures.py run [n_workers]     (stage A fits, then stage B)
Out:  results/current/yang_figures.json
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments'), os.path.join(PROOT, 'plotting')]
OUT = os.path.join(PROOT, 'results', 'current', 'yang_figures.json')

GC_TOT_NS = 8.0                       # Yang: total soma-dendrite coupling, fixed when N_dend varies
SOMA_BG = [300.0, 400.0, 500.0, 600.0]   # soma background AMPA rates tried (x 2.5 nS), + 150 Hz x 4 nS GABA
TARGET_BASE_HZ = 1.8                  # Yang's power law at rest: [(8 nS x -15 mV + 174.86)/45.16]^2.89
FIG3_ND = {10: list(range(1, 11)), 20: [1, 2, 4, 6, 8, 10, 12, 14, 17, 20], 30: [1, 3, 6, 9, 12, 15, 18, 21, 25, 30]}
FIG3_D = [10.0, 20.0, 30.0]
N_DRAW = 32
AMPA_FRAC = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
F7_SEEDS = [42, 43, 44, 45, 46]
F7_U_AFTER = 10.0
Z1D = np.linspace(-2.4, 2.4, 9)
Z2D = np.linspace(-2.4, 2.4, 7)


def _prefs():
    from brian2 import prefs, BrianLogger
    prefs.codegen.target = 'cython'
    BrianLogger.suppress_name('resolution_conflict', 'base')


# ---------------------------------------------------------------- stage A: rate-model fit data
def s_nmda_bar(rate_hz):
    """Yang Eq. 25: time-averaged NMDA gating of one synapse at Poisson rate r (our constants)."""
    from parameters import params
    from brian2 import second
    a = float(params['alphaNMDA'] * second); tr = float(params['tauNMDARise'] / second); td = float(params['tauNMDADecay'] / second)
    return 1.0 - 1.0 / (1.0 + rate_hz * tr * td * a)


def job_supp4_dend(seed=1, T=3.0, n_rep=4):
    _prefs()
    from brian2 import NeuronGroup, PoissonGroup, Synapses, StateMonitor, Network, seed as bseed, second, mV, nS, Hz, ms
    from yang_fig2_supp1 import model_params
    from equations import eqs_dend, eqs_synapse_plasticity, on_pre_plasticity
    from context_circuit import _syn_model
    bseed(seed)
    g_syn = np.round(np.linspace(0.25, 5.0, 20), 3)          # per-synapse NMDA conductance (nS)
    inh = np.arange(0, 101, 10.0)                             # inhibitory input rate (Hz), one 4 nS synapse
    G, I = np.meshgrid(g_syn, inh, indexing='ij')
    G = np.repeat(G.ravel(), n_rep); I = np.repeat(I.ravel(), n_rep)
    n, n_exc, rate = len(G), 15, 30.0
    p = model_params({'gAMPA': 0 * nS}, 0.8, 1)
    D = NeuronGroup(n, eqs_dend, method='euler', namespace=p)
    D.V = p['vRest_pyr']; D.vSoma = -60 * mV
    P = PoissonGroup(n * n_exc, rates=rate * Hz)
    S = Synapses(P, D, model=_syn_model(eqs_synapse_plasticity, True), on_pre=on_pre_plasticity, method='heun', namespace=p)
    S.connect(j=f'i // {n_exc}')
    S.rho = np.repeat(G / (3 * float(p['gNMDA'] / nS)), n_exc)      # w = 3 rho = g_syn / 2.5 nS
    PI = PoissonGroup(n, rates=I * Hz)
    SI = Synapses(PI, D, on_pre='gTotGABA_post += gGABA', namespace=p); SI.connect(j='i')
    M = StateMonitor(D, 'V', record=True, dt=1 * ms)
    Network(D, P, S, PI, SI, M).run(T * second)
    t = np.asarray(M.t / ms); V = np.asarray(M.V / mV)[:, t > 200].mean(1)
    gE = 15 * s_nmda_bar(rate) * G
    gI = I * float(p['tauGABA'] / second) * float(p['gGABA'] / nS)
    return dict(g_syn=G.tolist(), inh_hz=I.tolist(), gE=gE.tolist(), gI=gI.tolist(), VD=V.tolist(),
                s_bar=s_nmda_bar(rate), soma_clamp_mV=-60.0)


def job_supp4_soma(bg, seed=1, T=6.0, n_rep=8):
    _prefs()
    from brian2 import NeuronGroup, PoissonInput, SpikeMonitor, Network, seed as bseed, second, mV, nS, Hz
    from yang_fig2_supp1 import model_params, YANG
    from equations import eqs_soma
    bseed(seed)
    vd = np.arange(-70.0, -19.0, 2.5)
    VD = np.repeat(vd, n_rep)
    p = model_params({'gAMPA': 0 * nS}, GC_TOT_NS, 1)          # gTotCouple = Gc
    p['gTotNMDA'] = 0 * nS
    Soma = NeuronGroup(len(VD), eqs_soma.replace('gTotNMDA : siemens', ''), threshold='V > vThres_pyr',
                       reset='V = vReset_pyr', refractory=p['refracTime_pyr'], method='euler', namespace=p)
    Soma.V = p['vRest_pyr']; Soma.vShadow = p['vRest_pyr']; Soma.vAveDend = VD * mV
    bge = PoissonInput(Soma, 'gTotAMPA', 1, bg * Hz, weight=YANG['bg_exc_nS'] * nS)
    bgi = PoissonInput(Soma, 'gTotGABA', 1, YANG['bg_inh_hz'] * Hz, weight=YANG['bg_inh_nS'] * nS)
    M = SpikeMonitor(Soma)
    Network(Soma, bge, bgi, M).run(T * second)
    r = np.bincount(np.asarray(M.i), minlength=len(VD)) / T
    r = r.reshape(len(vd), n_rep).mean(1)
    E_reset = float(p['vReset_pyr'] / mV)
    return dict(bg=bg, VD=vd.tolist(), I_pA=(GC_TOT_NS * (vd - E_reset)).tolist(), rate=r.tolist(), E_reset=E_reset)


# ---------------------------------------------------------------- stage B
def job_fig2():
    _prefs()
    import yang_fig2_supp1 as Y
    P = dict(Y.DEFAULTS)
    d2 = Y.fig2_data(P); d1 = Y.supp1_data(P)
    tol = lambda x: x.tolist() if isinstance(x, np.ndarray) else x
    fig2 = dict(volley_n=d2['volley_n'], rates=d2['rates'], b_t=tol(d2['b']['t_ms']), b_V=tol(d2['b']['V']),
                c=tol(d2['c']), z=tol(d2['z']), e1=tol(d2['e'][1]), e2=tol(d2['e'][2]), base=d2['e']['base'],
                z2=tol(d2['z2']), fg_none=tol(d2['fg'][None]), fg_1=tol(d2['fg'][1]), S=d2['S'])
    supp1 = dict(volley_n=d1['volley_n'], rates=d1['rates'], f_t=tol(d1['f']['t_ms']), f_V=tol(d1['f']['V']),
                 g=tol(d1['g']), h=tol(d1['h']))
    return dict(fig2=fig2, supp1=supp1, params={k: (v if isinstance(v, (int, float, list, str)) else repr(v)) for k, v in P.items()})


def job_supp3(a, n_rep=8):
    _prefs()
    import yang_fig2_supp1 as Y
    from brian2 import nS
    P = Y.DEFAULTS
    ov = {'gNMDA': (1 - a) * 2.5 * nS, 'gAMPA': a * 2.5 * nS}
    z1 = [0.0] * n_rep + [None] * n_rep
    kw = dict(T=P['T_neuron'], receptor='both', model_overrides=ov, couple_nS=P['couple_vivo_nS'],
              bg_exc_hz=P['bg_exc_hz'], bg_inh_hz=P['bg_inh_hz'], seed_val=1)
    r1 = Y.sim_neurons(z1, [None] * len(z1), gate=1, **kw)
    r2 = Y.sim_neurons(z1, [None] * len(z1), gate=2, **kw)
    on = r1[:n_rep].mean() - r1[n_rep:].mean(); off = r2[:n_rep].mean() - r2[n_rep:].mean()
    S = (on - off) / (on + off) if on + off > 0 else float('nan')
    return dict(a=a, r_on=float(on), r_off=float(off), S=float(S), base=[float(r1[n_rep:].mean()), float(r2[n_rep:].mean())])


def sim_multi(exc_hz, inh_hz, bg_exc_hz, T=3.0, n_exc=15, seed_val=1):
    """N spiking neurons (rows) x nd dendrites (cols): per-dendrite excitatory rate (n_exc NMDA
    synapses each, w = 1) and inhibitory rate (one 4 nS GABA synapse). Returns soma rates (Hz)."""
    from brian2 import (NeuronGroup, PoissonGroup, PoissonInput, Synapses, SpikeMonitor, Network,
                        seed as bseed, second, nS, Hz)
    from yang_fig2_supp1 import model_params, YANG
    from equations import eqs_dend, eqs_soma, eqs_synapse_plasticity, on_pre_plasticity
    from context_circuit import _syn_model
    bseed(seed_val)
    N, nd = exc_hz.shape
    p = model_params({'gAMPA': 0 * nS}, GC_TOT_NS / nd, nd)
    p['gTotNMDA'] = 0 * nS
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
    P = PoissonGroup(N * nd * n_exc, rates=np.repeat(np.asarray(exc_hz, float).ravel(), n_exc) * Hz)
    S = Synapses(P, D, model=_syn_model(eqs_synapse_plasticity, False), on_pre=on_pre_plasticity,
                 method='heun', namespace=p)
    S.connect(j=f'i // {n_exc}'); S.rho = 1 / 3
    I = PoissonGroup(N * nd, rates=np.asarray(inh_hz, float).ravel() * Hz)
    SI = Synapses(I, D, on_pre='gTotGABA_post += gGABA', namespace=p); SI.connect(j='i')
    bge = PoissonInput(Soma, 'gTotAMPA', 1, bg_exc_hz * Hz, weight=YANG['bg_exc_nS'] * nS)
    bgi = PoissonInput(Soma, 'gTotGABA', 1, YANG['bg_inh_hz'] * Hz, weight=YANG['bg_inh_nS'] * nS)
    M = SpikeMonitor(Soma)
    Network(Soma, D, d2s, s2d, P, S, I, SI, bge, bgi, M).run(T * second)
    return np.bincount(np.asarray(M.i), minlength=N) / T


def job_fig3(nd, D, k, bg, seed=7, T=4.0, u_pref=40.0, inh_open=5.0):
    _prefs()
    rng = np.random.default_rng(seed * 1000 + nd * 10 + k + int(D))
    rows_e, rows_i, tags = [], [], []
    for mode in ('random', 'disjoint'):
        if mode == 'disjoint' and 2 * k > nd:
            continue
        for _ in range(N_DRAW):
            T1 = rng.choice(nd, k, replace=False)
            T2 = rng.choice(np.setdiff1d(np.arange(nd), T1), k, replace=False) if mode == 'disjoint' else rng.choice(nd, k, replace=False)
            ex = np.zeros(nd); ex[T1] = u_pref
            for gate, Tg in (('g1', T1), ('g2', T2)):
                ih = np.full(nd, inh_open + D); ih[Tg] = inh_open
                for stim, e_ in (('on', ex), ('base', np.zeros(nd))):
                    rows_e.append(e_); rows_i.append(ih); tags.append((mode, gate, stim))
    r = sim_multi(np.array(rows_e), np.array(rows_i), bg, T=T, seed_val=seed + k)
    tags = np.array(tags)
    out = dict(nd=nd, D=D, k=k, frac=k / nd, bg=bg)
    for mode in ('random', 'disjoint'):
        sel = tags[:, 0] == mode
        if not sel.any():
            continue
        m = lambda g, s: float(r[sel & (tags[:, 1] == g) & (tags[:, 2] == s)].mean())
        on = m('g1', 'on') - m('g1', 'base'); off = m('g2', 'on') - m('g2', 'base')
        out[mode] = dict(r_on=on, r_off=off, base=[m('g1', 'base'), m('g2', 'base')],
                         S=(on - off) / (on + off) if on + off > 0 else float('nan'))
    return out


def job_fig7(seed, state, kind):
    _prefs()
    from context_circuit import run_context_protocol, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA
    t0 = time.time()
    lt = run_context_protocol([0] * 8 + [1] * 8, T=3.0, input_mode='patterns', overlap=0.0, exc_rate=50.0, seed_val=seed)
    tr = lt['traj']
    A, B = np.array(lt['idx_A']), np.array(lt['idx_B'])
    r0, r1 = np.array(tr[-1]['rho0_syn']), np.array(tr[-1]['rho1_syn'])
    n = len(r0)
    w_after = 3 * (r0[A].sum() + r1[A].sum() + r0[B].sum() + r1[B].sum()) / 2
    w_before = 3 * (1 / 3) * 2 * len(A)
    if state == 'before':
        rho = ([1 / 3] * n, [1 / 3] * n); U = F7_U_AFTER * w_after / w_before
    else:
        rho = (r0.tolist(), r1.tolist()); U = F7_U_AFTER
    u = lambda z: U * np.exp(-z ** 2)
    sch, sr = [], []
    if kind == '1d':
        for g in (0, 1):
            sch.append(g); sr.append((0.0, 0.0))
            for z in Z1D:
                sch.append(g); sr.append((float(u(z)), 0.0))
    else:
        sch.append(0); sr.append((0.0, 0.0))
        for z1 in Z2D:
            for z2 in Z2D:
                sch.append(0); sr.append((float(u(z1)), float(u(z2))))
    rd = run_context_protocol(sch, T=3.0, input_mode='patterns', overlap=0.0, stim_rates=sr, plastic=False,
                              rho_init_syn=rho, bap_source='soma', seed_val=seed,
                              param_overrides={'gGABA_pv2soma': BALANCED_SOMA_G_PV2SOMA}, **BALANCED_SOMA_KW)
    rates = [t['pyr_hz'] for t in rd['traj']]
    out = dict(seed=seed, state=state, kind=kind, U=U, rates=rates, schedule=sch, stim_rates=sr,
               wall_s=round(time.time() - t0, 1))
    if kind == '1d':
        nz = len(Z1D)
        out['base'] = [rates[0], rates[1 + nz]]
        out['gate1'] = rates[1:1 + nz]; out['gate2'] = rates[2 + nz:2 + 2 * nz]
        on = out['gate1'][nz // 2] - out['base'][0]; off = out['gate2'][nz // 2] - out['base'][1]
        out['S'] = (on - off) / (on + off) if on + off > 0 else float('nan')
        if state == 'after':
            out['learn_rho0'] = [t['rho0_syn'] for t in tr]; out['learn_rho1'] = [t['rho1_syn'] for t in tr]
            out['idx_A'] = A.tolist(); out['idx_B'] = B.tolist()
    else:
        out['base'] = rates[0]
        out['grid'] = np.array(rates[1:]).reshape(len(Z2D), len(Z2D)).tolist()
    return out


# ---------------------------------------------------------------- driver
def _pool(jobs, nw, done, tag):
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(f, *a): k for k, f, a in jobs}
        for fu in as_completed(futs):
            k = futs[fu]
            try:
                done[k] = fu.result()
            except Exception as e:
                print(k, 'ERROR', repr(e), flush=True); continue
            json.dump(done, open(OUT, 'w'))
            print(f'[{tag}] {k} done', flush=True)


def choose_bg(done):
    """Soma background whose rate with the dendrites at rest (V_D = -70 mV) is closest to Yang's 1.8 Hz."""
    best = min(SOMA_BG, key=lambda b: abs(done[f'supp4_soma_{b}']['rate'][0] - TARGET_BASE_HZ))
    return best


def run(nw):
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    JA = [('supp4_dend', job_supp4_dend, ())] + [(f'supp4_soma_{b}', job_supp4_soma, (b,)) for b in SOMA_BG]
    JA = [j for j in JA if j[0] not in done]
    _pool(JA, nw, done, 'A')
    bg = choose_bg(done)
    done['fig3_bg'] = bg
    print('soma background for Fig. 3:', bg, 'Hz', flush=True)
    JB = [('fig2', job_fig2, ())] + [(f'supp3_{a}', job_supp3, (a,)) for a in AMPA_FRAC]
    JB += [(f'fig7_{s}_{st}_{k}', job_fig7, (s, st, k)) for s in F7_SEEDS for st in ('before', 'after') for k in ('1d', '2d')]
    JB += [(f'fig3_{nd}_{D}_{k}', job_fig3, (nd, D, k, bg)) for nd, ks in FIG3_ND.items() for D in FIG3_D for k in ks]
    JB = [j for j in JB if j[0] not in done]
    print(len(JB), 'stage-B jobs', flush=True)
    _pool(JB, nw, done, 'B')
    print('done', flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(int(sys.argv[2]) if len(sys.argv) > 2 else 38)
