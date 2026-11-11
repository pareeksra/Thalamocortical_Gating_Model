"""
network_circuit.py -- step 3 (2026-11-10): a small recurrent PFC network built from the
canonical single-cell model (context_circuit.py), adding Zhang 2025's excitatory
recurrence E -> {E, SOM, VIP, PV}.

    N_E pyramidal cells, each soma + 2 branches (the canonical cell; Dend index 2c + b)
    shared afferents (patterns A / B, 'patterns' mode of context_circuit) -> every branch
    of every cell, plastic (Yang NMDA synapse, rho0 = 1/3, closed-form update per epoch)
    shared interneurons, canonical wiring and calibration:
        MD_k -> VIP_k -> SOM_k -> branch k of EVERY cell;  MD -> PV;  SOM -> PV;  PV -> soma
    canonical model: noisy SOM baseline, bAP calcium x0.2, VIP->SOM x0.25
    each soma: balanced fluctuation-driven background (BALANCED_SOMA_KW, as PoissonInput:
        identical statistics to 100 independent Poisson sources), PV->soma 0.1 nS;
        bAPs from the cell's own soma spikes (recurrence needs real spikes)
    recurrence (new), each with probability p_rec, AMPA, weights x rec_gain:
        E -> E soma   w_ee_nS  (ref 2.0 nS: at 10 Hz ~10% of the soma's external drive)
        E -> SOM      w_es_nS  (ref 0.75 nS: ~25% of SOM's Poisson background)
        E -> VIP      w_ev_nS  (ref 1.2 nS: ~25% of the MD -> VIP drive at 25 Hz)
        E -> PV       w_ep_nS  (ref 0.9 nS: ~25% of PV's background)
    E -> SOM and E -> VIP are NOT channel-specific (Zhang gives no branch structure), so
    recurrence spreads activity across both channels -- the test of step 3.
At rec_gain = 0 each cell is the canonical single cell (up to the soma-driven bAPs and
the PoissonInput form of the soma background).

Step 3b (md_loop=dict(...)): MD rates come from the PFC <-> MD rate loop of md_loop.py,
integrated every 1 ms. Its context populations are cued by the schedule (held for the whole
epoch, or only for the first cue_s seconds). The plastic E cells' population rate (filtered,
tau 50 ms) feeds both MD channels with weight w_em. MD spikes stay Poisson at the loop's
rates; the downstream synapses are unchanged. md_loop=None (default): fixed Poisson MD
rates, as before.
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE)]
from brian2 import (Network, NeuronGroup, PoissonGroup, PoissonInput, Synapses, SpikeMonitor, seed,
                    second, ms, mV, pA, nS, Hz, network_operation)
from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
from equations import (attach_rho_clipper, make_eqs_synapse_plasticity, eqs_soma, eqs_dend,
                       eqs_pv, eqs_som, eqs_vip, eqs_synapse_plasticity, on_pre_plasticity)
from circuit_helpers import som_initial_voltages
from context_circuit import (_syn_model, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA, SOM_NOISY_KW,
                             VIP2SOM_SCALE_CANON)
from src.v2.plasticity import yang_synapse_update

REC_REF = dict(w_ee_nS=2.0, w_es_nS=0.75, w_ev_nS=1.2, w_ep_nS=0.9)


def run_network_protocol(schedule, T=3.0, N_E=20, exc_rate=50.0, overlap=0.0, n_pattern=20, stim=None,
                         plastic=True, rho_init_syn=None, md_on_rate=25.0, md_off_rate=0.0, gcouple_nS=0.8,
                         seed_val=42, rec_gain=1.0, rec_targets=('E', 'SOM', 'VIP', 'PV'), p_rec=0.2,
                         w_ee_nS=None, w_es_nS=None, w_ev_nS=None, w_ep_nS=None, soma_scale=1.0,
                         param_overrides=None, md_loop=None):
    """schedule: context per T-second epoch. stim: pattern per epoch (0 = A, 1 = B, None = no
    input; default = context). rho_init_syn: (rho_b0, rho_b1), each (N_E, n_aff).
    md_loop: None, or dict(regime='amp'|'persist'|..., loop_cross, w_em, cue_s, + md_loop.LOOP_PRESETS
    overrides); the loop object carries its state across epochs.
    Returns dict(traj=[per-epoch records], idx_A, idx_B, n_aff, N_E)."""
    seed(seed_val)
    wrng = np.random.default_rng(30000 + seed_val)
    p = dict(params)
    for d in (plasticity_params, pv_params, som_params, vip_params, md_params):
        p.update(d)
    for k, v in (param_overrides or {}).items():
        if k not in p:
            raise KeyError(f"param_overrides key '{k}' is not a known model parameter")
        p[k] = v
    # canonical model (context_circuit defaults with synapse='yang')
    if 'gAMPA' not in (param_overrides or {}):
        p['gAMPA'] = 0 * nS
    p['bAP_Ca_scale'] = p.get('bAP_Ca_scale', 1.0) if 'bAP_Ca_scale' in (param_overrides or {}) else 0.2
    if 'gGABA_som' not in (param_overrides or {}):
        p['gGABA_som'] = p['gGABA_som'] * VIP2SOM_SCALE_CANON
    if 'gGABA_pv2soma' not in (param_overrides or {}):
        p['gGABA_pv2soma'] = BALANCED_SOMA_G_PV2SOMA
    rho_init = 1 / 3
    ndend = 2
    p['num_Soma'] = 1; p['num_DendEach'] = ndend; p['num_Dend'] = ndend
    p['gEachCouple_pyr'] = gcouple_nS * nS; p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * ndend
    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']; p['norm_factor_Ca'] = t ** (1 / (t - 1)) * float(p['bAP_Ca_scale'])
    t = p['tauGABABRise'] / p['tauGABABDecay']; p['norm_factor_GABAB'] = t ** (1 / (t - 1))
    n_md, n_pv, n_som, n_vip = p['n_md'], p['n_pv'], p['n_som_spike'], p['n_vip_spike']
    p['n_som_ch'] = n_som; p['n_vip_ch'] = n_vip; p['n_md_ch'] = n_md; p['n_dend_cpl'] = float(ndend)
    W = {k: (REC_REF[k] if v is None else v) * rec_gain for k, v in
         dict(w_ee_nS=w_ee_nS, w_es_nS=w_es_nS, w_ev_nS=w_ev_nS, w_ep_nS=w_ep_nS).items()}

    net = Network()
    # --- pyramidal cells -------------------------------------------------------------
    Soma = NeuronGroup(N_E, eqs_soma, threshold='V>vThres_pyr', reset='V=vReset_pyr',
                       refractory=p['refracTime_pyr'], method='euler', namespace=p)
    Soma.V = p['vRest_pyr']; Soma.vShadow = p['vRest_pyr']; Soma.vAveDend = p['vRest_pyr']
    Dend = NeuronGroup(ndend * N_E, eqs_dend, method='euler', namespace=p)
    Dend.V = p['vRest_pyr']; Dend.vSoma = p['vRest_pyr']
    d_idx = np.arange(ndend * N_E)
    d2s = Synapses(Dend, Soma, model='vAveDend_post = V_pre / n_dend_cpl : volt (summed)', namespace=p)
    d2s.connect(i=d_idx, j=d_idx // ndend)
    s2d = Synapses(Soma, Dend, model='vSoma_post = vShadow_pre : volt (summed)', namespace=p)
    s2d.connect(i=d_idx // ndend, j=d_idx)
    bAP = Synapses(Soma, Dend, on_pre='V_post+=bAP_amp\nbAPCa_rise_post+=norm_factor_Ca',
                   delay=p['bAP_delay'], namespace=p)
    bAP.connect(i=d_idx // ndend, j=d_idx)
    sk = BALANCED_SOMA_KW
    pin_e = PoissonInput(Soma, 'gTotAMPA', sk['n_soma_drive'], sk['soma_drive_hz'] * soma_scale * Hz,
                         weight=f"{sk['soma_drive_nS']}*nS")
    pin_i = PoissonInput(Soma, 'gTotGABA', sk['n_soma_inh'], sk['soma_inh_hz'] * soma_scale * Hz,
                         weight=f"{sk['soma_inh_nS']}*nS")
    net.add([Soma, Dend, d2s, s2d, bAP, pin_e, pin_i])

    # --- interneurons (canonical) ----------------------------------------------------
    PV = NeuronGroup(n_pv, eqs_pv, threshold='V>vThres_pv', reset='V=vReset_pv',
                     refractory=p['refrac_pv'], method='euler', namespace=p)
    PV.V = p['vRest_pv']
    BG_pv = PoissonGroup(n_pv, rates=p['rate_bg_pv'])
    sbg_pv = Synapses(BG_pv, PV, on_pre='gTotAMPA_post+=weight_bg_pv', namespace=p)
    sbg_pv.connect(j='i')
    SOM = NeuronGroup(2 * n_som, eqs_som, threshold='V>vThres_som', reset='V=vReset_som',
                      refractory=p['refrac_som'], method='euler', namespace=p)
    SOM.V = som_initial_voltages(2 * n_som, p, SOM_NOISY_KW['som_bias_pA'], 'random', seed_val)
    SOM.iBaseline_som = SOM_NOISY_KW['som_bias_pA'] * pA
    p['som_bg_w'] = SOM_NOISY_KW['som_bg_nS'] * nS
    BG_som = PoissonGroup(2 * n_som, rates=SOM_NOISY_KW['som_bg_E_hz'] * Hz)
    s_bg_som = Synapses(BG_som, SOM, on_pre='gTotAMPA_post += som_bg_w', namespace=p)
    s_bg_som.connect(j='i')
    VIP = NeuronGroup(2 * n_vip, eqs_vip, threshold='V>vThres_vip', reset='V=vReset_vip',
                      refractory=p['refrac_vip'], method='euler', namespace=p)
    VIP.V = p['vRest_vip']
    MD = PoissonGroup(2 * n_md, rates=0 * Hz)
    net.add([PV, BG_pv, sbg_pv, SOM, BG_som, s_bg_som, VIP, MD])
    s_md2pv = Synapses(MD, PV, on_pre='gTotAMPA_post+=gAMPA_pv', namespace=p)
    s_md2pv.connect(p=p['p_md2pv'])
    s_md2vip = Synapses(MD, VIP, on_pre='gTotAMPA_post+=gAMPA_vip', namespace=p)
    s_md2vip.connect(condition='i // n_md_ch == j // n_vip_ch', p=p['p_md2vip'])
    s_vip2som = Synapses(VIP, SOM, on_pre='gTotGABA_post+=gGABA_som', namespace=p)
    s_vip2som.connect(condition='i // n_vip_ch == j // n_som_ch', p=p['p_vip2som_spike'])
    s_som2dend = Synapses(SOM, Dend, on_pre='gTotGABA_post+=gGABA', namespace=p)
    s_som2dend.connect(condition='i // n_som_ch == j % 2', p=p['p_som2dend_spike'])
    s_pv2soma = Synapses(PV, Soma, on_pre='gTotGABA_post+=gGABA_pv2soma', namespace=p)
    s_pv2soma.connect(p=p['p_pv2soma'])
    s_som2pv = Synapses(SOM, PV, on_pre='gTotGABA_post+=gGABA_pv', namespace=p)
    s_som2pv.connect(p=p['p_som2pv'])
    net.add([s_md2pv, s_md2vip, s_vip2som, s_som2dend, s_pv2soma, s_som2pv])

    # --- recurrence (Zhang 2025: E -> E, SOM, VIP, PV), not channel-specific -------------
    rec = {}
    for tag, grp, var, wk in (('E', Soma, 'gTotAMPA', 'w_ee_nS'), ('SOM', SOM, 'gTotAMPA', 'w_es_nS'),
                              ('VIP', VIP, 'gTotAMPA', 'w_ev_nS'), ('PV', PV, 'gTotAMPA', 'w_ep_nS')):
        if tag not in rec_targets or W[wk] <= 0:
            continue
        p[f'rec_w_{tag}'] = W[wk] * nS
        S_ = Synapses(Soma, grp, on_pre=f'{var}_post += rec_w_{tag}', delay=1 * ms, namespace=p)
        M = wrng.random((N_E, len(grp))) < p_rec
        if tag == 'E':
            np.fill_diagonal(M, False)
        ii, jj = np.nonzero(M)
        S_.connect(i=ii, j=jj)
        net.add(S_); rec[tag] = S_

    # --- plastic afferents ('patterns' mode) -------------------------------------------
    acc_eqs = '\nad_acc : second\nap_acc : second\n'
    accumulate = ('ad_acc = ad_acc + int(c_total > theta_d)*dt\n'
                  'ap_acc = ap_acc + int(c_total > theta_p)*dt')
    n_sh = int(round(overlap * n_pattern))
    n_aff = 2 * n_pattern - n_sh
    idx_A = np.arange(0, n_pattern)
    idx_B = np.arange(n_pattern - n_sh, 2 * n_pattern - n_sh)
    AFF = PoissonGroup(n_aff, rates=0 * Hz)
    SB = []
    for b, eqs in ((0, eqs_synapse_plasticity), (1, make_eqs_synapse_plasticity(2))):
        sb = Synapses(AFF, Dend, model=_syn_model(eqs, True) + acc_eqs, on_pre=on_pre_plasticity,
                      method='heun', namespace=p)
        ii = np.tile(np.arange(n_aff), N_E); jj = 2 * np.repeat(np.arange(N_E), n_aff) + b
        sb.connect(i=ii, j=jj)
        assert np.array_equal(np.asarray(sb.i[:]), ii) and np.array_equal(np.asarray(sb.j[:]), jj)
        sb.rho = rho_init if rho_init_syn is None else np.asarray(rho_init_syn[b], float).ravel()
        attach_rho_clipper(sb)
        sb.run_regularly(accumulate, when='end')
        SB.append(sb)
    net.add([AFF] + SB)

    m_som, m_vip, m_pv, m_pyr = SpikeMonitor(SOM), SpikeMonitor(VIP), SpikeMonitor(PV), SpikeMonitor(Soma)
    m_md = SpikeMonitor(MD)
    net.add([m_som, m_vip, m_pv, m_pyr, m_md])
    loop, cue_s = None, None
    if md_loop is not None:
        from md_loop import MDLoop
        lk = dict(md_loop); cue_s = lk.pop('cue_s', None)
        loop = MDLoop(lk.pop('regime', 'amp'), lk.pop('loop_cross', 0.0), lk.pop('w_em', 0.0), **lk)
        lst = dict(n=0, rE=0.0)
        md_ch_ = np.arange(2 * n_md) // n_md

        @network_operation(dt=1 * ms)
        def _loop_step():
            n = m_pyr.num_spikes
            inst = (n - lst['n']) / 1e-3 / N_E            # E population rate in the last ms (Hz)
            lst['n'] = n
            lst['rE'] += (inst - lst['rE']) * (1e-3 / 0.05)  # tau 50 ms
            M = loop.step(1e-3, lst['rE'])
            MD.rates = M[md_ch_] * Hz
        net.add(_loop_step)
    ykw = dict(sigma=float(p['sigma']), tau=float(p['tau'] / second),
               gamma_d=float(p['gamma_d']), gamma_p=float(p['gamma_p']),
               w0=float(p['w0']), w1=float(p['w1']), rho_star=float(p['rhoStar']))
    som_ch = np.arange(2 * n_som) // n_som
    vip_ch = np.arange(2 * n_vip) // n_vip
    md_ch = np.arange(2 * n_md) // n_md

    traj = []
    for e, ctx in enumerate(schedule):
        if loop is None:
            MD.rates = np.where(md_ch == ctx, md_on_rate, md_off_rate) * Hz
        on = ctx if stim is None else stim[e]
        active = idx_A if on == 0 else (idx_B if on == 1 else np.array([], int))
        AFF.rates = np.where(np.isin(np.arange(n_aff), active), exc_rate, 0.0) * Hz
        for sb in SB:
            sb.ad_acc = 0 * second; sb.ap_acc = 0 * second
        n_p0 = m_pv.num_spikes
        cnt0 = np.bincount(np.asarray(m_pyr.i), minlength=N_E)
        t_start = float(net.t / second)
        if loop is None:
            net.run(T * second)
        elif cue_s is None or cue_s >= T:
            loop.set_cue(ctx); net.run(T * second)
        else:
            loop.set_cue(ctx); net.run(cue_s * second)
            loop.set_cue(None); net.run((T - cue_s) * second)
        r_ep = dict(epoch=e + 1, context=int(ctx), stim=None if on is None else int(on))
        for b, sb in enumerate(SB):
            ad = np.asarray(sb.ad_acc[:] / second); ap = np.asarray(sb.ap_acc[:] / second)
            r = np.asarray(sb.rho[:])
            if plastic:
                r = np.array([yang_synapse_update(ad[k], ap[k], r[k], **ykw)['rho_new'] for k in range(len(r))])
                sb.rho[:] = r
            r_ep[f'rho{b}_syn'] = r.reshape(N_E, n_aff).tolist()
            r_ep[f'rho{b}'] = float(r.mean())
        st = np.asarray(m_som.t / second); si = np.asarray(m_som.i)
        vt = np.asarray(m_vip.t / second); vi = np.asarray(m_vip.i)
        for ch in (0, 1):
            r_ep[f'som{ch}_hz'] = float(np.sum((st >= t_start) & (som_ch[si] == ch)) / T / n_som)
            r_ep[f'vip{ch}_hz'] = float(np.sum((vt >= t_start) & (vip_ch[vi] == ch)) / T / n_vip)
        r_ep['pv_hz'] = (m_pv.num_spikes - n_p0) / T / n_pv
        mt = np.asarray(m_md.t / second); mi = np.asarray(m_md.i)
        for ch in (0, 1):
            r_ep[f'md{ch}_hz'] = float(np.sum((mt >= t_start) & (md_ch[mi] == ch)) / T / n_md)
        if loop is not None:
            r_ep['loop_C'] = loop.C.tolist(); r_ep['loop_M'] = loop.M.tolist()
        cnt = np.bincount(np.asarray(m_pyr.i), minlength=N_E) - cnt0
        r_ep['pyr_hz_cells'] = (cnt / T).tolist()
        r_ep['pyr_hz'] = float(cnt.mean() / T)
        traj.append(r_ep)
    return dict(traj=traj, idx_A=idx_A.tolist(), idx_B=idx_B.tolist(), n_aff=n_aff, N_E=N_E, seed=seed_val,
                weights=W, rec_targets=list(rec))
