"""
validate_vs_papers.py
=====================
Validate Model A (Brian 2) against the key figures of the two source papers.

Yang, Murray & Wang (2016), Nat. Commun. 7:12815  -- quantitative, same model class:
  V1  Dendritic I/O transfer function        vs Yang Fig. 2c
  V2  LTP/LTD vs presynaptic rate (thresh.)  vs Yang Fig. 7b  (inhibition shifts threshold)
  V3  Branch-specific gating (free vs inh.)  vs Yang Fig. 7d-e

Zhang et al. (2025), Nat. Commun. 16:2640  -- qualitative only (Zhang is a trained rate
RNN; we borrow wiring labels, so we check the *mechanism*, not psychometrics):
  V4  MD-drive control of interneuron rates  (MD->VIP->SOM disinhibition; MD->PV gain)

Outputs PNGs to figures/validation_vs_papers/ and a results.json with measured numbers.
Run:  python experiments/validate_vs_papers.py
"""
import sys, os, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
sys.path.insert(0, os.path.join(PROOT))
sys.path.insert(0, os.path.join(PROOT, 'experiments'))

from brian2 import *
prefs.codegen.target = 'numpy'
from dendritic_io import dend_IO, io_midpoint
from phase1_analytical import run_gating_analytical
# 2026-08-30 migration: V2/V3 used to call phase1_single_neuron_gating.run_gating, a
# single net.run() that read rho straight after -- now broken (rho frozen at 0.5, ratio
# = 1.0 always) since model/equations.py's drho/dt was commented out in favor of the
# analytical epoch update. Switched to run_gating_analytical (15 epochs, matching the
# validated Phase 1 protocol) instead. V1 (no plasticity) and V4 (rates only, never
# reads rho) are unaffected and untouched.

OUTDIR = os.path.join(PROOT, 'figures', 'validation_vs_papers')
os.makedirs(OUTDIR, exist_ok=True)
results = {}

# ---------------------------------------------------------------------------
# V1 -- Dendritic I/O transfer function  (Yang Fig. 2c)
# ---------------------------------------------------------------------------
def v1_dendritic_io():
    print('\n[V1] Dendritic I/O transfer function (Yang Fig. 2c)')
    g_exc = np.linspace(0, 80, 400)
    inh_levels = [0.0, 2.0, 10.0, 20.0, 35.0]
    fig, ax = plt.subplots(figsize=(7, 5))
    cmap = plt.cm.viridis(np.linspace(0, 0.85, len(inh_levels)))
    for c, ginh in zip(cmap, inh_levels):
        v = dend_IO(g_exc, ginh)
        ax.plot(g_exc, v, color=c, lw=2, label=f'g_inh = {ginh:.0f} nS')
        ghalf = float(io_midpoint(ginh))
        if ghalf <= g_exc.max():
            ax.plot(ghalf, float(dend_IO(ghalf, ginh)), 'o', color=c, ms=6)
    ax.axvline(25, ls='--', color='0.4', lw=1)
    ax.text(25.5, -68, "Yang g_E,max = 25 nS", rotation=90, va='bottom', fontsize=8, color='0.4')
    ax.set_xlabel('Excitatory conductance $g_E$ (nS)')
    ax.set_ylabel('Dendritic voltage $V_D$ (mV)')
    # 2026-11-01 (audit Problem 6): this panel plots Yang's FITTED formula (dendritic_io),
    # not Model A -- the Brian 2 dendrite does not use dend_IO. It is a reference curve,
    # not a test. The real test is v1_measured() below (experiments/v1_dendrite_io_measured.py).
    ax.set_title('V1 reference: Yang 2016 Eq. 20-22 fit (NOT a model measurement)\n'
                 r'$g_{1/2}=5.56\,(4+g_{inh})$; see v1_dendritic_io_measured.png for Model A', fontsize=10)
    ax.legend(fontsize=8, loc='lower right')
    ax.grid(alpha=0.25)
    fig.tight_layout()
    p = os.path.join(OUTDIR, 'v1_dendritic_io.png')
    fig.savefig(p, dpi=200); plt.close(fig)
    results['V1_reference_formula'] = {'note': 'Yang fit evaluated directly; not a model test',
                     'inh_levels_nS': inh_levels,
                     'g_half_nS': {str(g): float(io_midpoint(g)) for g in inh_levels},
                     'V_at_25nS_mV': {str(g): float(dend_IO(25.0, g)) for g in inh_levels}}
    print('   g_half (formula):', results['V1_reference_formula']['g_half_nS'])
    print('   saved', p)

# ---------------------------------------------------------------------------
# V2 -- LTP/LTD vs presynaptic rate; inhibition shifts the threshold (Yang Fig. 7b)
# V3 -- Branch-specific gating bar (Yang Fig. 7d-e), taken from the 80 Hz operating point
# ---------------------------------------------------------------------------
def v1_measured():
    print('\n[V1] Dendritic I/O MEASURED on the Brian 2 dendrite (Yang Fig. 2c)')
    import v1_dendrite_io_measured as v1m
    v1m.main()
    results['V1'] = json.load(open(os.path.join(PROOT, 'docs', 'audit', 'v1_dendrite_io.json')))


V2_RATES = [2.0, 5.0, 10.0, 20.0, 40.0, 80.0, 120.0, 160.0, 240.0]
V2_SOM = {15: 20.20522, 30: 21.319034}     # SOM rate (Hz) -> bias (pA), desynchronised


def _v2_point(args):
    r, som_hz = args
    d = run_gating_analytical(n_epochs=15, T=3.0, exc_rate=r, post_rate=10.0, gcouple_nS=0.8,
                              som_bias_pA=V2_SOM[som_hz], seed_val=42, verbose=False,
                              resume=False, run_tag=f'validate_rate_{int(r)}_som{som_hz}')
    try:
        os.remove(os.path.join(PROOT, 'docs', f'phase1_analytical_state_validate_rate_{int(r)}_som{som_hz}.json'))
    except OSError:
        pass
    return r, som_hz, d['rho1'], d['rho0']


def _crossing(x, y, level=0.5):
    for k in range(len(x) - 1):
        if (y[k] - level) * (y[k + 1] - level) < 0:
            return float(x[k] + (level - y[k]) * (x[k + 1] - x[k]) / (y[k + 1] - y[k]))
    return None


def v2_v3_plasticity_sweep():
    # 2026-11-01 (audit Problem 7): the old sweep (20-120 Hz, one SOM level) had the free
    # branch already potentiated at 20 Hz and the inhibited branch only depressing, so no
    # LTP threshold existed to shift. Now: 2-240 Hz, two SOM inhibition levels, and the
    # LTP threshold (rate where rho crosses 0.5) is measured for each curve.
    print('\n[V2] LTP/LTD vs presynaptic rate (Yang Fig. 7b) -- running Brian 2 sweep...')
    from concurrent.futures import ProcessPoolExecutor
    jobs = [(r, s) for s in V2_SOM for r in V2_RATES]
    with ProcessPoolExecutor(max_workers=int(os.environ.get('V2_WORKERS', 9)),
                             max_tasks_per_child=1) as ex:
        out = list(ex.map(_v2_point, jobs))
    rates = np.array(V2_RATES)
    curves = {'free': np.array([o[2] for o in out if o[1] == 30])}
    for s in V2_SOM:
        curves[f'SOM {s} Hz'] = np.array([o[3] for o in out if o[1] == s])
    rho_free = curves['free']; rho_inh = curves['SOM 30 Hz']
    thresholds = {k: _crossing(rates, v) for k, v in curves.items()}
    print('   LTP thresholds (rate where rho crosses 0.5):', thresholds)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(rates, rho_free, 'o-', color='#2E7D32', lw=2, label='Disinhibited (free) branch')
    ax.plot(rates, curves['SOM 15 Hz'], 's-', color='#EF6C00', lw=2, label='SOM 15 Hz (weaker inhibition)')
    ax.plot(rates, rho_inh, 's-', color='#C62828', lw=2, label='SOM 30 Hz (baseline inhibition)')
    ax.set_xscale('log')
    ax.axhline(0.5, ls='--', color='0.5', lw=1)
    ax.text(rates.min(), 0.51, r'$\rho^\ast=0.5$ (start)', fontsize=8, color='0.4')
    ax.set_xlabel('Presynaptic pathway rate (Hz)   [post fixed at Yang 10 Hz]')
    ax.set_ylabel(r'Steady-state $\rho$ (0 = LTD, 1 = LTP)')
    ax.set_title('V2  Plasticity vs input rate  (Model A)  vs  Yang 2016 Fig. 7b\n'
                 'Inhibition shifts the LTP threshold to higher rates', fontsize=10)
    ax.set_ylim(-0.05, 1.05); ax.legend(fontsize=9); ax.grid(alpha=0.25)
    fig.tight_layout()
    p2 = os.path.join(OUTDIR, 'v2_ltp_vs_rate.png')
    fig.savefig(p2, dpi=200); plt.close(fig)
    print('   saved', p2)

    # V3: branch-gating bar at the 80 Hz operating point
    i80 = list(rates).index(80.0)
    rf, ri = float(rho_free[i80]), float(rho_inh[i80])
    ratio = rf / ri if ri > 1e-6 else float('inf')
    fig, ax = plt.subplots(figsize=(5, 5))
    bars = ax.bar(['Disinhibited\n(free)', 'SOM-inhibited'], [rf, ri],
                  color=['#2E7D32', '#C62828'], width=0.6)
    for b, val in zip(bars, [rf, ri]):
        ax.text(b.get_x()+b.get_width()/2, val+0.02, f'{val:.3f}', ha='center', fontsize=11)
    ax.axhline(0.5, ls='--', color='0.5', lw=1)
    ax.set_ylabel(r'Steady-state $\rho$')
    ax.set_ylim(0, 1.05)
    ax.set_title(f'V3  Branch-specific gating  (Model A)  vs  Yang Fig. 7d-e\n'
                 f'exc 80 Hz, post 10 Hz, coupling 0.8 nS   |   free/inh ratio = {ratio:.1f}', fontsize=10)
    fig.tight_layout()
    p3 = os.path.join(OUTDIR, 'v3_branch_gating.png')
    fig.savefig(p3, dpi=200); plt.close(fig)
    print('   saved', p3)

    results['V2'] = {'rates_Hz': rates.tolist(), 'som_phase': 'random',
                     **{f'rho_{k}': v.tolist() for k, v in curves.items()},
                     'ltp_threshold_Hz': thresholds}
    results['V3'] = {'exc_Hz': 80, 'post_Hz': 10, 'rho_free': rf, 'rho_inh': ri, 'ratio': ratio}
    print(f'   V3: free={rf:.3f} inh={ri:.3f} ratio={ratio:.1f}')

# ---------------------------------------------------------------------------
# V4 -- MD drive controls interneuron rates (Zhang qualitative: disinhibition + gain)
# ---------------------------------------------------------------------------
def build_network(p):
    from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
    from equations import (attach_rho_clipper, eqs_soma, eqs_dend, eqs_pv, eqs_som, eqs_vip,
                           eqs_synapse_plasticity, on_pre_plasticity)
    num_pyr, ndend = 1, 2
    p['num_Soma'] = num_pyr; p['num_DendEach'] = ndend; p['num_Dend'] = ndend
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * ndend
    t = p['tau_Ca_bAP_rise']/p['tau_Ca_bAP_decay']; p['norm_factor_Ca'] = t**(1/(t-1))
    t = p['tauGABABRise']/p['tauGABABDecay']; p['norm_factor_GABAB'] = t**(1/(t-1))
    net = Network()
    Soma = NeuronGroup(num_pyr, eqs_soma, threshold='V>vThres_pyr', reset='V=vReset_pyr',
                       refractory=p['refracTime_pyr'], method='euler', namespace=p)
    Soma.V = p['vRest_pyr']; Soma.vShadow = p['vRest_pyr']; Soma.vAveDend = p['vRest_pyr']
    Dend = NeuronGroup(ndend, eqs_dend, method='euler', namespace=p)
    Dend.V = p['vRest_pyr']; Dend.vSoma = p['vRest_pyr']
    bAP = Synapses(Soma, Dend, on_pre='V_post+=bAP_amp\nbAPCa_rise_post+=norm_factor_Ca',
                   delay=p['bAP_delay'], namespace=p); bAP.connect(j='k for k in range(2)')
    net.add([Soma, Dend, bAP])
    from circuit_helpers import add_compiled_coupling, som_initial_voltages
    add_compiled_coupling(net, Soma, Dend, ndend, p)
    PV = NeuronGroup(p['n_pv'], eqs_pv, threshold='V>vThres_pv', reset='V=vReset_pv',
                     refractory=p['refrac_pv'], method='euler', namespace=p); PV.V = p['vRest_pv']
    BG = PoissonGroup(p['n_pv'], rates=p['rate_bg_pv'])
    sbg = Synapses(BG, PV, on_pre='gTotAMPA_post+=weight_bg_pv', namespace=p); sbg.connect(j='i')
    SOM = NeuronGroup(p['n_som_spike'], eqs_som, threshold='V>vThres_som', reset='V=vReset_som',
                      refractory=p['refrac_som'], method='euler', namespace=p)
    # 2026-08-30: updated to the SOM-rate sweep's calibrated default (see
    # model/parameters.py's iBaseline_som comment); V4 doesn't read rho so this only
    # affects the reported SOM/downstream rates, not any plasticity result.
    # 2026-11-01: desynchronised SOM (audit Problem 1), seed-42 phases
    SOM.V = som_initial_voltages(p['n_som_spike'], p, 21.32, 'random', 42); SOM.iBaseline_som = 21.32*pA
    VIP = NeuronGroup(p['n_vip_spike'], eqs_vip, threshold='V>vThres_vip', reset='V=vReset_vip',
                      refractory=p['refrac_vip'], method='euler', namespace=p); VIP.V = p['vRest_vip']
    MD = PoissonGroup(p['n_md'], rates=5*Hz)
    net.add([PV, BG, sbg, SOM, VIP, MD])
    s1 = Synapses(MD, PV, on_pre='gTotAMPA_post+=gAMPA_pv', namespace=p); s1.connect(p=p['p_md2pv'])
    s2 = Synapses(MD, VIP, on_pre='gTotAMPA_post+=gAMPA_vip', namespace=p); s2.connect(p=p['p_md2vip'])
    s3 = Synapses(VIP, SOM, on_pre='gTotGABA_post+=gGABA_som', namespace=p); s3.connect(p=p['p_vip2som_spike'])
    s4 = Synapses(SOM, Dend, on_pre='gTotGABA_post+=gGABA', namespace=p); s4.connect(p=p['p_som2dend_spike'])
    s5 = Synapses(PV, Soma, on_pre='gTotGABA_post+=gGABA_pv2soma', namespace=p); s5.connect(p=p['p_pv2soma'])
    # 2026-11-01 (audit): SOM->PV (p=0.8, the 2026-08-27 divergence fix) is wired in every
    # canonical builder but was missing here, so V4's PV rates were not those of the model.
    s6 = Synapses(SOM, PV, on_pre='gTotGABA_post+=gGABA_pv', namespace=p); s6.connect(p=p['p_som2pv'])
    path = PoissonGroup(30, rates=80*Hz)
    sp = Synapses(path, Dend, model=eqs_synapse_plasticity, on_pre=on_pre_plasticity,
                  method='heun', namespace=p); sp.connect(); sp.rho = 0.5; attach_rho_clipper(sp)
    net.add([s1, s2, s3, s4, s5, s6, path, sp])
    mons = {'pv': SpikeMonitor(PV), 'som': SpikeMonitor(SOM),
            'vip': SpikeMonitor(VIP), 'pyr': SpikeMonitor(Soma)}
    net.add(list(mons.values()))
    return net, MD, mons, dict(n_pv=p['n_pv'], n_som=p['n_som_spike'],
                               n_vip=p['n_vip_spike'], n_pyr=num_pyr)

def v4_md_sweep():
    print('\n[V4] MD-drive control of interneuron rates (Zhang qualitative)')
    from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
    md_rates = [0.0, 5.0, 10.0, 20.0, 30.0, 40.0]
    T = 1.5
    rec = {k: [] for k in ('pv', 'som', 'vip', 'pyr')}
    for mr in md_rates:
        print(f'   MD = {mr} Hz ...', flush=True)
        seed(42)
        p = params.copy()
        for d in (plasticity_params, pv_params, som_params, vip_params, md_params):
            p.update(d)
        net, MD, mons, n = build_network(p)
        MD.rates = mr * Hz
        net.run(T * second)
        rec['pv'].append(len(mons['pv'].t)/T/n['n_pv'])
        rec['som'].append(len(mons['som'].t)/T/n['n_som'])
        rec['vip'].append(len(mons['vip'].t)/T/n['n_vip'])
        rec['pyr'].append(len(mons['pyr'].t)/T/n['n_pyr'])
    md_rates = np.array(md_rates)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(md_rates, rec['vip'], 'o-', color='#6A1B9A', lw=2, label='VIP (MD$^{DRD2}$ target)')
    ax.plot(md_rates, rec['som'], 's-', color='#00838F', lw=2, label='SOM (disinhibited by VIP)')
    ax.plot(md_rates, rec['pv'],  '^-', color='#C62828', lw=2, label='PV (MD$^{GRIK4}$ target)')
    ax.plot(md_rates, rec['pyr'], 'd-', color='#1565C0', lw=2, label='Pyramidal soma')
    ax.set_xlabel('MD thalamus drive (Hz)')
    ax.set_ylabel('Population firing rate (Hz)')
    ax.set_title('V4  MD control of the interneuron circuit  (Model A)\n'
                 'Qualitative check of Zhang 2025 wiring: MD$\\uparrow$ -> SOM$\\downarrow$ (disinhibition), PV$\\uparrow$ (gain)',
                 fontsize=9.5)
    ax.legend(fontsize=9); ax.grid(alpha=0.25)
    fig.tight_layout()
    p4 = os.path.join(OUTDIR, 'v4_md_interneuron_control.png')
    fig.savefig(p4, dpi=200); plt.close(fig)
    print('   saved', p4)
    results['V4'] = {'md_rates_Hz': md_rates.tolist(), **{k: rec[k] for k in rec}}
    print('   SOM:', [f'{x:.1f}' for x in rec['som']])
    print('   PV :', [f'{x:.1f}' for x in rec['pv']])

if __name__ == '__main__':
    print('=' * 70)
    print(' VALIDATION vs Yang 2016 & Zhang 2025 paper figures  (Model A)')
    print('=' * 70)
    v1_dendritic_io()
    v1_measured()
    v2_v3_plasticity_sweep()
    v4_md_sweep()
    with open(os.path.join(OUTDIR, 'results.json'), 'w') as f:
        json.dump(results, f, indent=2)
    print('\nAll validation figures written to', OUTDIR)
