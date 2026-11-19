"""
yang_rate_model.py -- Yang, Murray & Wang 2016's multi-compartment RATE model and interneuron
networks (Methods; Figs. 3-6, Supp. Figs. 2, 4-6), with the pyramidal rate model REFIT to this
project's spiking neuron (experiments/yang_figures.py, supp4_*). Used by
notebooks/yang_replication.ipynb (2026-11-19).

Pyramidal rate neuron (Yang Eqs. 20-23):
  V_D = E_L + V0 + 30 [tanh((g_E - g_half)/b) - tanh(-g_half/b)],  g_half = b_g (g_L,D + g_I),
        b = k exp(g_I / gamma)
  (re-referenced so that V_D(g_E = 0) = E_L + V0 for every g_I, as model/dendritic_io.py: with
   E_I = E_L inhibition is purely shunting. Yang's printed form lets heavily inhibited, unexcited
   dendrites depolarise for g_I > ~2.5 nS; the network figures reach g_I ~ 18 nS.)
  soma: I = G_c (<V_D> - E_reset) + dI_PV,  r = [max(0, I - I0) / c]^p
Interneurons, connectivity and control exactly as Yang's Methods (rate SOM, VIP, PV; each
dendrite targeted by exactly N_SOM->dend SOM cells, non-integer values interpolated; total
SOM->dendrite conductance 40 nS; excitation aligned with the gate-1 disinhibition pattern,
Eq. 31). Both our fit and Yang's published fit can be used (`YANG_FIT`).
"""
import numpy as np

GLD, EL, E_RESET, GC = 4.0, -70.0, -55.0, 8.0          # nS, mV, mV, nS (Yang = ours)
TAU_GABA = 0.020                                        # s
YANG_FIT = dict(dend=dict(bg=5.56, k=9.64, gamma=6.54, V0=0.78), soma=dict(I0=-174.86, c=45.16, p=2.89))
# Yang network constants (Methods)
G_SOM_DEND, G_I_TH, G_E_MAX = 40.0, 4.0, 25.0           # nS
BETA_SOM, I_RH_SOM, I_SOM_DEFAULT = 0.090, 40.0, 150.0  # Hz/pA, pA, pA
W_VIP_SOM_TOT, VIP_MEAN_HZ, CTRL_SOM_PA = 30.0, 5.0, 75.0
BETA_PV, W_PV_PV_TOT, W_PV_SOMA_TOT = 0.220, 30.0, 30.0  # Hz/pA, pA/Hz, pA/Hz
P_SOM_PV, P_PV_PV, P_PV_SOMA = 0.8, 0.9, 0.6


# ------------------------------------------------------------------ pyramidal rate model
def fV(gE, gI, d):
    gE, gI = np.asarray(gE, float), np.asarray(gI, float)
    gh = d['bg'] * (GLD + gI); b = d['k'] * np.exp(gI / d['gamma'])
    return EL + d['V0'] + 30.0 * (np.tanh((gE - gh) / b) - np.tanh(-gh / b))


def f_soma(I, s):
    return (np.maximum(0.0, np.asarray(I, float) - s['I0']) / s['c']) ** s['p']


def pyr_rate(gE, gI, fit, dI=0.0):
    """gE, gI: (..., n_dend) conductances (nS). Returns soma rate (Hz)."""
    VD = fV(gE, gI, fit['dend']).mean(-1)
    return f_soma(GC * (VD - E_RESET) + dI, fit['soma'])


def fit_dendrite(d):
    """Fit Yang's sigmoid family (re-referenced) to supp4_dend data -> dict(bg, k, gamma, V0)."""
    from scipy.optimize import curve_fit
    gE, gI, V = (np.asarray(d[k], float) for k in ('gE', 'gI', 'VD'))
    f = lambda X, bg, k, gamma, V0: fV(X[0], X[1], dict(bg=bg, k=k, gamma=gamma, V0=V0))
    p, _ = curve_fit(f, np.vstack([gE, gI]), V, p0=[5.5, 9.6, 6.5, 0.8], bounds=([1, 0.5, 0.5, -5], [20, 60, 100, 10]))
    rmse = float(np.sqrt(np.mean((f(np.vstack([gE, gI]), *p) - V) ** 2)))
    return dict(bg=p[0], k=p[1], gamma=p[2], V0=p[3], rmse_mV=rmse)


def fit_soma(s, r_max=100.0):
    """Fit r = [max(0, I - I0)/c]^p to supp4_soma data -> dict(I0, c, p). Fitted where r <= r_max:
    the networks of Figs. 3-6 drive the soma below ~100 Hz, and our LIF soma bends below a power
    law at higher rates (refractoriness), which otherwise drags the fit into a bad optimum."""
    from scipy.optimize import curve_fit
    I, r = np.asarray(s['I_pA'], float), np.asarray(s['rate'], float)
    m = r <= r_max
    f = lambda I, I0, c, p: f_soma(I, dict(I0=I0, c=c, p=p))
    p, _ = curve_fit(f, I[m], r[m], p0=[-175, 45, 2.9], bounds=([-600, 1, 0.5], [-121, 500, 6]), maxfev=20000)
    return dict(I0=p[0], c=p[1], p=p[2], r_max=r_max, rmse_hz=float(np.sqrt(np.mean((f(I[m], *p) - r[m]) ** 2))))


# ------------------------------------------------------------------ Fig. 3: single neuron
def fig3_rate(nd, k, D, fit, gE_on=G_E_MAX, inh_open=5.0, disjoint=False):
    """Selectivity of one rate neuron, averaged over all projection patterns (Yang Methods):
    the overlap m between gate 1's and gate 2's k dendrites is hypergeometric."""
    from scipy.stats import hypergeom
    g = lambda hz: hz * TAU_GABA * 4.0                 # one 4 nS GABA synapse per dendrite
    gO, gC = g(inh_open), g(inh_open + D)
    base = pyr_rate(np.zeros(nd), np.r_[np.full(k, gO), np.full(nd - k, gC)], fit)
    on = pyr_rate(np.r_[np.full(k, gE_on), np.zeros(nd - k)], np.r_[np.full(k, gO), np.full(nd - k, gC)], fit) - base
    ms = [0] if disjoint else range(0, k + 1)
    pm = [1.0] if disjoint else hypergeom(nd, k, k).pmf(list(ms))
    off = 0.0
    for m, w in zip(ms, pm):
        if (2 * k - m) > nd or w == 0:
            continue
        # dendrites: m (exc + open), k-m (exc + closed), k-m (open), rest closed
        gE = np.r_[np.full(k, gE_on), np.zeros(nd - k)]
        gI = np.r_[np.full(m, gO), np.full(k - m, gC), np.full(k - m, gO), np.full(nd - 2 * k + m, gC)]
        off += w * (pyr_rate(gE, gI, fit) - base)
    return (on - off) / (on + off) if on + off > 0 else np.nan


# ------------------------------------------------------------------ circuit construction
def _targets(n_post, n_pre, n_in, rng):
    """Each post cell gets ceil(n_in) distinct random pre cells; weights (fractions of the total)
    1/n_in, with one partial weight 1 - floor(n_in)/n_in when n_in is not an integer (Yang)."""
    n_in = float(n_in)
    nc = int(np.ceil(n_in - 1e-9)); nf = int(np.floor(n_in + 1e-9))
    idx = np.argsort(rng.random((n_post, n_pre)), axis=1)[:, :nc]
    w = np.full(nc, 1.0 / n_in)
    if nc > nf:
        w[-1] = 1.0 - nf / n_in
    return idx, np.broadcast_to(w, idx.shape)


def n_som_dend(N_SOM, P, nd):
    """Yang Fig. 4 caption: N_SOM->dend = N_SOM [1 - (1 - P_SOM->pyr)^(1/N_dend)]."""
    return N_SOM * (1 - (1 - P) ** (1 / nd))


class Circuit:
    """Yang's interneuronal network. Rates in Hz, currents in pA, conductances in nS."""

    def __init__(self, n_pyr=1000, nd=30, n_som=160, nsd=None, n_vip=140, p_vip_som=0.6, n_pv=200,
                 w_som_pv=0.0, seed=0):
        rng = np.random.default_rng(seed)
        self.rng, self.n_pyr, self.nd, self.n_som, self.n_vip, self.n_pv = rng, n_pyr, nd, n_som, n_vip, n_pv
        self.nsd = n_som_dend(n_som, 0.6, nd) if nsd is None else nsd
        self.sd_idx, self.sd_w = _targets(n_pyr * nd, n_som, self.nsd, rng)            # SOM -> dendrite
        self.vs_idx, self.vs_w = _targets(n_som, n_vip, max(n_vip * p_vip_som, 1e-6), rng)   # VIP -> SOM
        self.w_som_pv = w_som_pv
        if w_som_pv > 0:   # dense PV block (Eqs. 29-30); per-connection SOM->PV weight w_som_pv
            self.W_sp = (rng.random((n_pv, n_som)) < P_SOM_PV) * w_som_pv
            k = round(n_pv * P_PV_PV); self.W_pp = np.zeros((n_pv, n_pv))
            for i in range(n_pv):
                self.W_pp[i, rng.choice(n_pv, k, replace=False)] = W_PV_PV_TOT / k
            k = round(n_pv * P_PV_SOMA); self.W_ps = np.zeros((n_pyr, n_pv))
            for i in range(n_pyr):
                self.W_ps[i, rng.choice(n_pv, k, replace=False)] = W_PV_SOMA_TOT / k

    def som_rates(self, I):
        return np.maximum(0.0, BETA_SOM * (I - I_RH_SOM))

    def context(self, mode='fig4', p_ctrl_vip=0.1, p_ctrl_som=0.0, frac_suppressed=0.5):
        """SOM rates (and currents) in one context. 'fig4': a random fraction of SOM silenced.
        'vip_som': control to a random subset of VIP (and SOM) cells (Fig. 5)."""
        rng = self.rng
        out = {}
        if mode == 'fig4':
            r = np.full(self.n_som, self.som_rates(I_SOM_DEFAULT))
            r[rng.choice(self.n_som, round(frac_suppressed * self.n_som), replace=False)] = 0.0
            out['r_som'] = r
            return out
        r_vip = np.zeros(self.n_vip)
        nc = round(self.n_vip * p_ctrl_vip)
        if nc > 0:
            r_vip[rng.choice(self.n_vip, nc, replace=False)] = VIP_MEAN_HZ * self.n_vip / nc
        I_inh = W_VIP_SOM_TOT * (self.vs_w * r_vip[self.vs_idx]).sum(1)
        I_exc = np.zeros(self.n_som)
        ns = round(self.n_som * p_ctrl_som)
        if ns > 0:
            I_exc[rng.choice(self.n_som, ns, replace=False)] = CTRL_SOM_PA * self.n_som / ns
        out.update(r_vip=r_vip, I_inh=I_inh, I_exc=I_exc, r_som=self.som_rates(I_SOM_DEFAULT - I_inh + I_exc))
        return out

    def gI(self, r_som):
        return (TAU_GABA * G_SOM_DEND * (self.sd_w * r_som[self.sd_idx]).sum(1)).reshape(self.n_pyr, self.nd)

    def dI_soma(self, r_som):
        """Change of somatic PV inhibition relative to the default state (Eqs. 29-30)."""
        if self.w_som_pv <= 0:
            return 0.0, None
        dr_som = r_som - self.som_rates(I_SOM_DEFAULT)
        A = np.eye(self.n_pv) / BETA_PV + self.W_pp
        dr_pv = np.linalg.solve(A, -self.W_sp @ dr_som)
        return -self.W_ps @ dr_pv, dict(dI_pv=-self.W_sp @ dr_som, dr_pv=dr_pv)

    def selectivity(self, fit, c1, c2):
        """Per-neuron gating selectivity of pathway 1 (aligned with context 1's disinhibition)."""
        g1, g2 = self.gI(c1['r_som']), self.gI(c2['r_som'])
        gE = np.where(g1 < G_I_TH, (1 - g1 / G_I_TH) * G_E_MAX, 0.0)
        d1, _ = self.dI_soma(c1['r_som']); d2, _ = self.dI_soma(c2['r_som'])
        on = pyr_rate(gE, g1, fit, d1) - pyr_rate(0 * gE, g1, fit, d1)
        off = pyr_rate(gE, g2, fit, d2) - pyr_rate(0 * gE, g2, fit, d2)
        with np.errstate(invalid='ignore', divide='ignore'):
            S = np.where((on + off) > 1e-9, (on - off) / (on + off), 0.0)
        # neurons that pathway 1 does not reach at all are excluded; neurons it reaches but whose
        # responses are fully suppressed (e.g. by strong PV inhibition, Fig. 6b) count as S = 0
        return S[gE.sum(-1) > 0]


def S_stats(S):
    return float(np.nanmean(S)), float(np.nanpercentile(S, 10)), float(np.nanpercentile(S, 90))


def run_circuit(fit, n_rep=3, mode='fig4', ckw=None, xkw=None, n_pyr=1000):
    """Mean and 10-90% band of S over n_rep circuit draws (contexts 1 and 2 drawn independently)."""
    allS = []
    for rep in range(n_rep):
        C = Circuit(n_pyr=n_pyr, seed=rep, **(ckw or {}))
        allS.append(C.selectivity(fit, C.context(mode, **(xkw or {})), C.context(mode, **(xkw or {}))))
    return S_stats(np.concatenate(allS))


# ------------------------------------------------------------------ Supp. Fig. 2c,d (analytic)
def vss_branches(x_eff, gL_tot=GLD):
    """Steady states of one dendrite under constant conductances (Yang Eq. 24): returns the
    roots V of 0 = -(V - E_L) - x (V - E_E) fMg(V) for effective input x = g_NMDA/(g_L + g_GABA)
    (with E_I = E_L the GABA term merges with the leak). Our Mg block: 1/(1+exp(-(V+19.9)/12.48))."""
    V = np.linspace(-80, 5, 20001)
    fMg = 1 / (1 + np.exp(-(V + 19.9) / 12.48))
    F = -(V - EL) - x_eff * (V - 0.0) * fMg
    s = np.where(np.diff(np.sign(F)) != 0)[0]
    return V[s]
