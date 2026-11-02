"""
yang_supp_replication.py -- FAITHFUL replication of Yang (2016) Supplementary Figs 1 & 2
=========================================================================================
2026-09-17 (Raghav provided the actual Supplementary PDF). Unlike the earlier analytical
sketch (docs/yang_supp_reconstruction.py), this reproduces Yang's ACTUAL supplementary
panels: a single-dendrite spiking simulation driven by Poisson NMDA/AMPA/GABA synapses,
with Yang's own equations (Methods Eqs. 6-12) and this project's Yang-calibrated
constants (model/parameters.py), plotting the same quantities on the same axes as Yang.

Scope (what we reproduce, per the real panels):
  Supp Fig 1 (reduced model, panels e-h):
    f  NMDA plateau potential: V_D(t) as the number of activated synapses increases.
    g  NMDA input: mean dendritic voltage vs input RATE (Hz), inhibition 0 vs 30 Hz.
    h  AMPA input: same axes, showing inhibition barely gates AMPA (g_AMPA = 2.5 nS).
  Supp Fig 2 (panels a-d):
    a  Saturating NMDA model:   mean V_D vs rate (0-300 Hz), inhibition 0 vs 30 Hz.
    b  Non-saturating NMDA model: same, weaker inhibitory control.
    c  Bistability: steady-state V vs effective input g_NMDA/(g_L+g_GABA) (constant g).
    d  NMDA conductance saturation vs rate, for g_GABA/g_L = 0 and 0.6.
  NOT reproduced: the reconstructed-morphology panels (1a-d, a NEURON model this project
  does not have) and the stochastic-switching panels (2e-h) -- left for a follow-up.

Yang constants (Methods; identical to parameters.py): C=20 pF, g_L,D=4 nS, E_L=E_I=-70 mV,
E_E=0 mV, g_NMDA=2.5 nS, tau_NMDA,rise=2 ms, tau_NMDA,decay=100 ms, alpha_NMDA=0.3/ms,
V_half=-19.9 mV, V_width=12.48 mV, g_GABA=4 nS, tau_GABA,dend=20 ms, g_AMPA(supp)=2.5 nS.
Reduced model uses 15 excitatory synapses (Yang caption g,h). Inhibition = 10 GABA
synapses (10 x 4 nS = G_SOM->dend = 40 nS total, Yang's default) at the stated rate.
"""
import os, sys
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from brian2 import *
from scipy.optimize import brentq

BrianLogger.suppress_name('resolution_conflict', 'base')

# --- Yang constants (Methods / parameters.py) ---
C = 20 * pF
gL = 4 * nS
EL = -70 * mV
EE = 0 * mV
EI = -70 * mV
gNMDA_bar = 2.5 * nS
tauRise = 2 * ms
tauDecay = 100 * ms
alphaNMDA = 0.3 / ms
vHalf = -19.9 * mV
vSpread = 12.48 * mV
gGABA_bar = 4 * nS
tauGABA = 20 * ms
tauAMPA = 2 * ms
gAMPA_bar = 2.5 * nS       # Yang Supp Fig 1d,h value (not the project's 0.4 nS default)
N_EXC = 15                 # Yang reduced-model excitatory synapses (caption g,h)
N_INH = 10                 # 10 x 4 nS = 40 nS = Yang's G_SOM->dend

NS = dict(gL=gL, EL=EL, EE=EE, EI=EI, gNMDA_bar=gNMDA_bar, tauRise=tauRise,
          tauDecay=tauDecay, alphaNMDA=alphaNMDA, vHalf=vHalf, vSpread=vSpread,
          gGABA_bar=gGABA_bar, tauGABA=tauGABA, tauAMPA=tauAMPA, gAMPA_bar=gAMPA_bar, C=C)

DEND_EQS = '''
dV/dt = (-gL*(V-EL) - gNMDA_bar*s_nmda_sum*fMg*(V-EE) - gAMPA_sum*(V-EE) - gGABA_sum*(V-EI))/C : volt
fMg = 1.0/(1.0 + exp(-(V - vHalf)/vSpread)) : 1
s_nmda_sum : 1
gAMPA_sum : siemens
gGABA_sum : siemens
'''


def _mg(Vmv):
    return 1.0 / (1.0 + np.exp(-(Vmv - (-19.9)) / 12.48))


def run_dendrite(exc_rate_hz, inh_rate_hz, exc='nmda', saturating=True, T=1.0, skip=0.4, seed_val=1):
    """Single-dendrite sim; return mean dendritic voltage (mV) over [skip, T]."""
    seed(seed_val)
    net = Network()
    dend = NeuronGroup(1, DEND_EQS, method='euler', namespace=NS, dt=0.02*ms)
    dend.V = EL
    net.add(dend)

    exc_src = PoissonGroup(N_EXC, rates=exc_rate_hz * Hz)
    if exc == 'nmda':
        sat = '*(1-s)' if saturating else ''
        model = f'''
        ds/dt = -s/tauDecay + alphaNMDA*x*(1{sat}) : 1 (clock-driven)
        dx/dt = -x/tauRise : 1 (clock-driven)
        s_nmda_sum_post = s : 1 (summed)
        '''
        syn = Synapses(exc_src, dend, model=model, on_pre='x += 1', method='euler', namespace=NS)
    else:  # ampa
        model = '''
        ds/dt = -s/tauAMPA : 1 (clock-driven)
        gAMPA_sum_post = gAMPA_bar*s : siemens (summed)
        '''
        syn = Synapses(exc_src, dend, model=model, on_pre='s += 1', method='euler', namespace=NS)
    syn.connect()
    net.add(exc_src, syn)

    if inh_rate_hz > 0:
        inh_src = PoissonGroup(N_INH, rates=inh_rate_hz * Hz)
        gaba = Synapses(inh_src, dend, model='''
            ds/dt = -s/tauGABA : 1 (clock-driven)
            gGABA_sum_post = gGABA_bar*s : siemens (summed)''',
            on_pre='s += 1', method='euler', namespace=NS)
        gaba.connect()
        net.add(inh_src, gaba)

    mon = StateMonitor(dend, 'V', record=True, dt=0.5*ms)
    net.add(mon)
    net.run(T * second)
    v = np.asarray(mon.V[0] / mV)
    t = np.asarray(mon.t / second)
    return float(np.mean(v[t >= skip]))


def run_plateau(n_active, T=0.15, seed_val=1):
    """N NMDA synapses each fire a short 40 Hz volley over [20,120] ms (5 spikes), then
    stop; return t(ms), V(t)(mV). A single spike is too little sustained NMDA drive to
    cross the Mg-unblock threshold; a brief train triggers the regenerative plateau, which
    then decays after the stimulus (matching Yang's Supp Fig 1b/f rise-plateau-decay)."""
    seed(seed_val)
    net = Network()
    dend = NeuronGroup(1, DEND_EQS, method='euler', namespace=NS, dt=0.02*ms)
    dend.V = EL
    net.add(dend)
    volley = np.array([20, 45, 70, 95, 120])  # ms, 40 Hz for 100 ms
    idx = np.repeat(np.arange(n_active), len(volley))
    times = np.tile(volley, n_active)
    src = SpikeGeneratorGroup(max(n_active, 1), idx, times * ms)
    model = '''
    ds/dt = -s/tauDecay + alphaNMDA*x*(1-s) : 1 (clock-driven)
    dx/dt = -x/tauRise : 1 (clock-driven)
    s_nmda_sum_post = s : 1 (summed)
    '''
    syn = Synapses(src, dend, model=model, on_pre='x += 1', method='euler', namespace=NS)
    syn.connect()
    net.add(src, syn)
    mon = StateMonitor(dend, 'V', record=True, dt=0.1*ms)
    net.add(mon)
    net.run(T * second)
    return np.asarray(mon.t/ms), np.asarray(mon.V[0]/mV)


def bistability_curve():
    """Panel 2c: steady-state V solving 0 = -gL(V-EL) - gN*fMg(V)*(V-EE) - gGABA_c*(V-EI),
    sweeping constant NMDA conductance gN. x-axis = gN/(gL+gGABA_c). gGABA_c=0 here."""
    gL_n, EL_n, EE_n, EI_n = 4.0, -70.0, 0.0, -70.0
    gGABA_c = 0.0
    def f(Vmv, gN):
        return (-gL_n*(Vmv-EL_n) - gN*_mg(Vmv)*(Vmv-EE_n) - gGABA_c*(Vmv-EI_n))
    gN_vals = np.linspace(0.01, 60, 400)
    xs, vs_low, vs_high = [], [], []
    for gN in gN_vals:
        roots = []
        grid = np.linspace(-70, 0, 400)
        fg = np.array([f(v, gN) for v in grid])
        for i in range(len(grid)-1):
            if fg[i] == 0 or fg[i]*fg[i+1] < 0:
                try:
                    roots.append(brentq(f, grid[i], grid[i+1], args=(gN,)))
                except Exception:
                    pass
        x = gN / (gL_n + gGABA_c)
        xs.append(x)
        vs_low.append(min(roots) if roots else np.nan)
        vs_high.append(max(roots) if roots else np.nan)
    return np.array(xs), np.array(vs_low), np.array(vs_high)


def nmda_saturation_vs_rate(rates, saturating=True):
    """Panel 2d helper: effective summed NMDA conductance g_NMDA*<s>*N_exc vs rate (nS)."""
    out = []
    for r in rates:
        seed(1)
        net = Network()
        dummy = NeuronGroup(1, 's_nmda_sum : 1', namespace=NS)
        src = PoissonGroup(N_EXC, rates=r*Hz)
        sat = '*(1-s)' if saturating else ''
        model = f'''
        ds/dt = -s/tauDecay + alphaNMDA*x*(1{sat}) : 1 (clock-driven)
        dx/dt = -x/tauRise : 1 (clock-driven)
        s_nmda_sum_post = s : 1 (summed)
        '''
        syn = Synapses(src, dummy, model=model, on_pre='x += 1', method='euler', namespace=NS, dt=0.02*ms)
        syn.connect()
        mon = StateMonitor(dummy, 's_nmda_sum', record=True, dt=1*ms)
        net.add(dummy, src, syn, mon)
        net.run(1.0*second)
        s = np.asarray(mon.s_nmda_sum[0]); tt = np.asarray(mon.t/second)
        geff = 2.5 * np.mean(s[tt >= 0.4])   # nS, total = gNMDA_bar * sum(s)
        out.append(geff)
    return np.array(out)


# ===========================================================================
def make_fig1():
    rates = np.array([0, 5, 10, 15, 20, 25, 30, 40, 50, 60], float)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    # (f) plateau traces
    for n, c in zip([5, 10, 15, 20, 25], plt.cm.viridis(np.linspace(0, 0.9, 5))):
        t, v = run_plateau(n)
        axes[0].plot(t, v, color=c, lw=1.5, label=f'{n} syn')
    axes[0].set_title('(f) NMDA plateau potential'); axes[0].set_xlabel('time (ms)')
    axes[0].set_ylabel('V$_D$ (mV)'); axes[0].legend(fontsize=8); axes[0].grid(alpha=0.2)

    # (g) NMDA input I/O
    for inh, c, lab in [(0, '#3bbfd0', 'Inh. 0 Hz'), (30, '#1f3a8a', 'Inh. 30 Hz')]:
        vbar = [run_dendrite(r, inh, exc='nmda') for r in rates]
        axes[1].plot(rates, vbar, 'o-', color=c, lw=2, label=lab)
    axes[1].set_title('(g) NMDA input'); axes[1].set_xlabel('rate (Hz)')
    axes[1].set_ylabel(r'$\bar{V}_D$ (mV)'); axes[1].legend(fontsize=8); axes[1].grid(alpha=0.2)

    # (h) AMPA input I/O
    for inh, c, lab in [(0, '#3bbfd0', 'Inh. 0 Hz'), (30, '#1f3a8a', 'Inh. 30 Hz')]:
        vbar = [run_dendrite(r, inh, exc='ampa') for r in rates]
        axes[2].plot(rates, vbar, 'o-', color=c, lw=2, label=lab)
    axes[2].set_title('(h) AMPA input'); axes[2].set_xlabel('rate (Hz)')
    axes[2].set_ylabel(r'$\bar{V}_D$ (mV)'); axes[2].legend(fontsize=8); axes[2].grid(alpha=0.2)

    fig.suptitle('Replication of Yang (2016) Supplementary Fig. 1 (reduced model, panels f–h): '
                 'inhibition gates NMDAR but not AMPAR dendritic input', fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = os.path.join(PROOT, 'figures', 'pre_audit', 'yang_supp1_replication.png')
    fig.savefig(out, dpi=150); plt.close(fig); print(f"Saved {out}", flush=True)


def make_fig2():
    rates_wide = np.array([0, 10, 20, 30, 50, 75, 100, 150, 200, 250, 300], float)
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.3))

    # (a) saturating NMDA
    for inh, c, lab in [(0, '#3bbfd0', 'Inh. 0 Hz'), (30, '#1f3a8a', 'Inh. 30 Hz')]:
        vbar = [run_dendrite(r, inh, exc='nmda', saturating=True) for r in rates_wide]
        axes[0].plot(rates_wide, vbar, 'o-', color=c, lw=2, label=lab)
    axes[0].set_title('(a) Saturating NMDA model'); axes[0].set_xlabel('rate (Hz)')
    axes[0].set_ylabel(r'$\bar{V}_D$ (mV)'); axes[0].legend(fontsize=8); axes[0].grid(alpha=0.2)

    # (b) non-saturating NMDA
    for inh, c, lab in [(0, '#3bbfd0', 'Inh. 0 Hz'), (30, '#1f3a8a', 'Inh. 30 Hz')]:
        vbar = [run_dendrite(r, inh, exc='nmda', saturating=False) for r in rates_wide]
        axes[1].plot(rates_wide, vbar, 'o-', color=c, lw=2, label=lab)
    axes[1].set_title('(b) Non-saturating NMDA model'); axes[1].set_xlabel('rate (Hz)')
    axes[1].set_ylabel(r'$\bar{V}_D$ (mV)'); axes[1].legend(fontsize=8); axes[1].grid(alpha=0.2)

    # (c) bistability
    xs, vlo, vhi = bistability_curve()
    axes[2].plot(xs, vlo, color='k', lw=2)
    axes[2].plot(xs, vhi, color='k', lw=2)
    axes[2].set_title('(c) Steady-state bistability'); axes[2].set_xlabel(r'$g_{NMDA}/(g_L+g_{GABA})$')
    axes[2].set_ylabel(r'$V_{ss}$ (mV)'); axes[2].grid(alpha=0.2)

    # (d) NMDA conductance saturation vs rate, gGABA/gL = 0 and 0.6
    for ratio, c, lab in [(0.0, '#3bbfd0', r'$g_{GABA}/g_L$ = 0'), (0.6, '#1f3a8a', r'$g_{GABA}/g_L$ = 0.6')]:
        geff = nmda_saturation_vs_rate(rates_wide, saturating=True)   # nS summed
        denom = 4.0 * (1.0 + ratio)   # gL + gGABA
        axes[3].plot(rates_wide, geff / denom, 'o-', color=c, lw=2, label=lab)
    axes[3].set_title('(d) NMDA saturation'); axes[3].set_xlabel('NMDA input rate (Hz)')
    axes[3].set_ylabel(r'$g_{NMDA}/(g_L+g_{GABA})$'); axes[3].legend(fontsize=8); axes[3].grid(alpha=0.2)

    fig.suptitle('Replication of Yang (2016) Supplementary Fig. 2 (panels a–d): '
                 'NMDA saturation enables strong inhibitory control; bistability', fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = os.path.join(PROOT, 'figures', 'pre_audit', 'yang_supp2_replication.png')
    fig.savefig(out, dpi=150); plt.close(fig); print(f"Saved {out}", flush=True)


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'both'
    if which in ('1', 'both'):
        print("Generating Supplementary Figure 1 ...", flush=True); make_fig1()
    if which in ('2', 'both'):
        print("Generating Supplementary Figure 2 ...", flush=True); make_fig2()
