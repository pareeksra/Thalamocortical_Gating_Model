"""
v1_dendrite_io_measured.py -- audit Problem 6 (2026-11-01): a NON-circular V1.

The old V1 (validate_vs_papers.py) plotted model/dendritic_io.dend_IO -- the Yang Eq. 20-22
fit itself -- and marked its io_midpoint, which IS 5.56*(4+g_inh). "Matched Yang to the
digit" was therefore a tautology, and Model A's Brian 2 dendrite (eqs_dend: conductance-
based, saturating NMDA + Mg block) does not use dend_IO at all.

This script measures the I/O of the ACTUAL Brian 2 dendrite:
  * one dendritic branch (eqs_dend) coupled at Yang's in-vivo 0.8 nS to a soma clamped at
    rest (isolates the branch transfer function, as in Yang Fig. 2c);
  * 20 excitatory synapses with the model's own AMPA + saturating NMDA (rho = 0.5, w=1.5),
    Poisson at rate r (sweep);
  * TONIC dendritic GABA_A conductance g_inh held constant (Yang's I/O is defined for a
    static inhibitory conductance), at Yang's Fig. 2c levels 0, 2, 10, 20, 35 nS;
  * x-axis = measured mean excitatory conductance g_E = <gAMPA_tot> + gNMDA*<sum s_nmda>
    (unblocked, as in Yang's g_E), y = mean branch voltage (last 1.5 s of 2 s).
For each g_inh the half-activation g_1/2 is read off the measured curve (V halfway between
the curve's min and max) and compared with Yang's law g_1/2 = 5.56*(4 + g_inh).

Run:  <venv>/python experiments/v1_dendrite_io_measured.py
Out:  figures/validation_vs_papers/v1_dendritic_io_measured.png, docs/audit/v1_dendrite_io.json
"""
import os, sys, json
import numpy as np
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT]
from brian2 import (NeuronGroup, PoissonGroup, Synapses, StateMonitor, Network, seed, prefs,
                    second, ms, mV, nS, Hz, defaultclock)
prefs.codegen.target = 'cython'
from parameters import params, plasticity_params
from equations import eqs_dend, eqs_synapse_plasticity, on_pre_plasticity

INH = [0.0, 2.0, 10.0, 20.0, 35.0]
RATES = [0, 2, 5, 10, 15, 20, 30, 40, 60, 80, 100, 150, 200, 300, 400]
N_SYN = 20


def measure(seed_val=1):
    seed(seed_val)
    p = dict(params); p.update(plasticity_params)
    p['num_DendEach'] = 1; p['gEachCouple_pyr'] = 0.8 * nS
    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']; p['norm_factor_Ca'] = t ** (1 / (t - 1))
    t = p['tauGABABRise'] / p['tauGABABDecay']; p['norm_factor_GABAB'] = t ** (1 / (t - 1))
    combos = [(g, r) for g in INH for r in RATES]
    n = len(combos)
    D = NeuronGroup(n, eqs_dend + '\ng_inh_tonic : siemens', method='euler', namespace=p)
    D.V = p['vRest_pyr']; D.vSoma = p['vRest_pyr']          # soma clamped at rest
    D.g_inh_tonic = np.array([c[0] for c in combos]) * nS
    D.run_regularly('gTotGABA = g_inh_tonic', when='before_groups')
    P = PoissonGroup(n * N_SYN, rates=np.repeat([c[1] for c in combos], N_SYN) * Hz)
    S = Synapses(P, D, model=eqs_synapse_plasticity, on_pre=on_pre_plasticity, method='heun', namespace=p)
    S.connect(j='i // %d' % N_SYN); S.rho = 0.5
    mV_ = StateMonitor(D, ['V', 'gTotAMPA'], record=True, dt=1 * ms)
    mS = StateMonitor(S, 's_nmda', record=True, dt=1 * ms)
    net = Network(D, P, S, mV_, mS)
    net.run(2.0 * second)
    keep = np.asarray(mV_.t / ms) >= 500
    V = np.asarray(mV_.V / mV)[:, keep].mean(1)
    gA = np.asarray(mV_.gTotAMPA / nS)[:, keep].mean(1)
    s = np.asarray(mS.s_nmda)[:, keep].mean(1)
    sj = np.asarray(S.j[:])
    gN = np.array([s[sj == k].sum() for k in range(n)]) * float(p['gNMDA'] / nS)
    return combos, V, gA + gN, gN


def half_point(gE, V):
    """g_E where V crosses halfway between its min and max (linear interpolation)."""
    vh = 0.5 * (V.min() + V.max())
    for k in range(len(V) - 1):
        if (V[k] - vh) * (V[k + 1] - vh) <= 0 and V[k + 1] != V[k]:
            return float(gE[k] + (vh - V[k]) * (gE[k + 1] - gE[k]) / (V[k + 1] - V[k])), float(vh)
    return None, float(vh)


def main():
    combos, V, gE, gN = measure()
    out = {}
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.8))
    cols = plt.cm.viridis(np.linspace(0, 0.85, len(INH)))
    for c, g in zip(cols, INH):
        idx = [k for k, cb in enumerate(combos) if cb[0] == g]
        x, y = gE[idx], V[idx]
        gh, vh = half_point(x, y)
        out[str(g)] = dict(rates_hz=RATES, gE_nS=x.tolist(), V_mV=y.tolist(),
                           g_half_measured_nS=gh, V_half_mV=vh, V_range_mV=[float(y.min()), float(y.max())],
                           g_half_yang_nS=5.56 * (4 + g))
        ax[0].plot(x, y, 'o-', color=c, ms=3, label=f'g_inh = {g:g} nS')
        if gh:
            ax[0].plot(gh, vh, 's', color=c, ms=8, mec='k')
    ax[0].set_xscale('symlog', linthresh=1); ax[0].set_xlabel('measured mean excitatory conductance $g_E$ (nS)')
    ax[0].set_ylabel('mean branch voltage (mV)'); ax[0].legend(fontsize=8, frameon=False)
    ax[0].set_title('Model A Brian 2 dendrite, measured (squares = half-activation)')
    gi = np.array(INH)
    meas = np.array([out[str(g)]['g_half_measured_nS'] or np.nan for g in INH])
    ax[1].plot(gi, 5.56 * (4 + gi), 'k--', label='Yang: $g_{1/2}=5.56(4+g_{inh})$')
    ax[1].plot(gi, meas, 'o-', color='C3', label='Model A measured')
    ok = np.isfinite(meas)
    if ok.sum() >= 2:
        sl, ic = np.polyfit(gi[ok], meas[ok], 1)
        out['linear_fit'] = dict(slope=float(sl), intercept=float(ic),
                                 implied_g0_nS=float(ic / sl) if sl else None)
        ax[1].plot(gi, sl * gi + ic, ':', color='C3', label=f'fit: {sl:.2f} g_inh + {ic:.1f}')
    ax[1].set_xlabel('$g_{inh}$ (nS)'); ax[1].set_ylabel('$g_{1/2}$ (nS)'); ax[1].legend(fontsize=8, frameon=False)
    ax[1].set_title('Half-activation vs inhibition')
    fig.tight_layout()
    os.makedirs(os.path.join(PROOT, 'figures', 'validation_vs_papers'), exist_ok=True)
    fp = os.path.join(PROOT, 'figures', 'validation_vs_papers', 'v1_dendritic_io_measured.png')
    fig.savefig(fp, dpi=150, facecolor='white')
    os.makedirs(os.path.join(PROOT, 'docs', 'audit'), exist_ok=True)
    json.dump(out, open(os.path.join(PROOT, 'docs', 'audit', 'v1_dendrite_io.json'), 'w'), indent=1)
    print(f"{'g_inh':>6} {'g1/2 meas':>10} {'g1/2 Yang':>10} {'V range (mV)':>18}")
    for g in INH:
        o = out[str(g)]
        gh = o['g_half_measured_nS']
        print(f"{g:>6g} {gh if gh is None else round(gh, 2):>10} {o['g_half_yang_nS']:>10.2f} "
              f"{o['V_range_mV'][0]:>8.1f} .. {o['V_range_mV'][1]:.1f}")
    if 'linear_fit' in out:
        print('linear fit:', out['linear_fit'])
    print('saved', fp)


if __name__ == '__main__':
    main()
