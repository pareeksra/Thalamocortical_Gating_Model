"""
validate_model.py - Systematic validation suite for the thalamocortical gating model.

Runs 6 independent tests to verify model correctness, robustness, and
reproducibility BEFORE any parameter sweeps.

Usage:
    python validate_model.py
"""
import sys, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import time as timer

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'model'))

from brian2 import *
prefs.codegen.target = 'numpy'

from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
from equations import (attach_rho_clipper, make_eqs_synapse_plasticity, eqs_soma, eqs_dend, eqs_pv, eqs_som, eqs_vip,
                       eqs_synapse_plasticity, on_pre_plasticity)

# Output directory
VAL_DIR = os.path.join(PROJECT_ROOT, 'figures', 'validation')
os.makedirs(VAL_DIR, exist_ok=True)

results = {}

# ================================================================
# Utility: Analytical LIF firing rate
# ================================================================
def lif_rate_analytical(I_ext_val, C_val, gL_val, V_rest_val, V_thresh_val, V_reset_val, t_ref_val):
    """Analytical firing rate (Hz) of a LIF neuron with constant current I_ext."""
    V_inf = V_rest_val + I_ext_val / gL_val
    if V_inf <= V_thresh_val:
        return 0.0
    tau_m = C_val / gL_val
    isi = t_ref_val + tau_m * np.log((V_inf - V_reset_val) / (V_inf - V_thresh_val))
    return 1.0 / isi


# ================================================================
# TEST 1: Isolated Cell Type Sanity Checks
# ================================================================
def test1_isolated_cells():
    print('\n' + '=' * 60)
    print(' TEST 1: Isolated Cell Type Sanity Checks')
    print('=' * 60)

    eqs_test = '''
    dV/dt = (-gL_t*(V - V_rest_t) + I_ext_t) / C_t : volt
    '''

    test_cases = [
        # (label, C, gL, V_rest, V_thresh, V_reset, t_ref, I_ext, should_fire)
        ('PV  @ 30 pA',  10*pF, 1*nS, -70*mV, -50*mV, -55*mV, 1*ms, 30*pA, True),
        ('PV  @  0 pA',  10*pF, 1*nS, -70*mV, -50*mV, -55*mV, 1*ms,  0*pA, False),
        ('SOM @ 22 pA',  20*pF, 1*nS, -70*mV, -50*mV, -55*mV, 2*ms, 22*pA, True),
        ('SOM @ 18 pA',  20*pF, 1*nS, -70*mV, -50*mV, -55*mV, 2*ms, 18*pA, False),
        ('VIP @ 30 pA',  20*pF, 1*nS, -70*mV, -50*mV, -55*mV, 2*ms, 30*pA, True),
    ]

    all_pass = True
    sim_rates = []
    ana_rates = []
    labels = []

    for label, C, gL, V_rest, V_thresh, V_reset, t_ref, I_ext, should_fire in test_cases:
        start_scope()

        G = NeuronGroup(1, eqs_test,
                        threshold='V > V_thresh_t',
                        reset='V = V_reset_t',
                        refractory=t_ref,
                        method='euler',
                        namespace={
                            'C_t': C, 'gL_t': gL, 'V_rest_t': V_rest,
                            'V_thresh_t': V_thresh, 'V_reset_t': V_reset,
                            'I_ext_t': I_ext,
                        })
        G.V = V_rest
        mon = SpikeMonitor(G)
        run(2 * second)

        sim_rate = len(mon.t) / 2.0
        ana_rate = lif_rate_analytical(
            float(I_ext), float(C), float(gL),
            float(V_rest), float(V_thresh), float(V_reset), float(t_ref)
        )

        if should_fire:
            err = abs(sim_rate - ana_rate) / ana_rate if ana_rate > 0 else 0
            ok = err < 0.25  # 25% tolerance (Euler integration overshoot for fast-spiking cells)
            status = f'sim={sim_rate:.1f} Hz, ana={ana_rate:.1f} Hz, err={err*100:.1f}%'
        else:
            ok = sim_rate == 0
            status = f'{"0 Hz as expected" if ok else f"expected 0 Hz, got {sim_rate:.1f} Hz"}'

        tag = 'PASS' if ok else 'FAIL'
        print(f'  {label}:  {tag}  ({status})')
        if not ok:
            all_pass = False

        sim_rates.append(sim_rate)
        ana_rates.append(ana_rate)
        labels.append(label)

    # -- Diagnostic plot --
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(labels))
    ax.bar(x - 0.17, ana_rates, 0.32, label='Analytical', color='#1565C0', alpha=0.85)
    ax.bar(x + 0.17, sim_rates, 0.32, label='Simulated',  color='#D32F2F', alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha='right')
    ax.set_ylabel('Firing Rate (Hz)')
    ax.set_title('Test 1 - Isolated Cell Types: Analytical vs Simulated')
    ax.legend()
    ax.grid(True, alpha=0.2)
    plt.tight_layout()
    plt.savefig(os.path.join(VAL_DIR, 'test1_cell_types.png'), dpi=150)
    plt.close()

    results['Test 1: Isolated Cell Types'] = all_pass
    return all_pass


# ================================================================
# TEST 2: Calcium Trace & Plasticity Direction
# ================================================================
def test2_calcium_plasticity():
    print('\n' + '=' * 60)
    print(' TEST 2: Calcium Trace & Plasticity Direction')
    print('=' * 60)

    p = params.copy()
    p.update(plasticity_params)
    all_pass = True

    # Minimal post neuron (non-spiking target to host synaptic variables).
    # It must also carry the bAP calcium trace, because eqs_synapse_plasticity reads
    # bAPCa_post as its postsynaptic calcium term. Nothing injects into it here, so it
    # stays at 0 and c_total == c -- which is exactly what this test wants to measure:
    # the presynaptic jump and decay in isolation.
    # The stub previously had `dV/dt = -V/(20*ms)` with V defaulting to 0, so it sat
    # near 0 mV -- an arbitrary voltage that was harmless while calcium was ungated but
    # became load-bearing once the Mg2+ gate was added (gate(0 mV) = 0.83 vs
    # gate(-70 mV) = 0.018). It now relaxes to an explicitly stated holding potential.
    post_eqs = '''
    dV/dt = (v_hold_post - V)/(20*ms) : volt
    dgTotAMPA/dt = -gTotAMPA/(2*ms) : siemens
    dbAPCa/dt = (-bAPCa+bAPCa_rise)/tau_Ca_bAP_decay : 1
    dbAPCa_rise/dt = -bAPCa_rise/tau_Ca_bAP_rise : 1
    iTotNMDA1 : amp
    iTotNMDA2 : amp
    '''

    def mg_gate_at(v_mV):
        return 1.0 / (1.0 + np.exp(-(v_mV - float(p['vHalfNMDA'] / mV))
                                   / float(p['vSpreadNMDA'] / mV)))

    # 2a probes a branch at rest; 2b-2d need a depolarised branch, because with the gate
    # in place a resting branch admits almost no NMDA calcium at any presynaptic rate.
    V_REST_POST = float(p['vRest_pyr'] / mV)
    V_ACTIVE_POST = -30.0
    p['v_hold_post'] = V_REST_POST * mV
    gate_rest, gate_active = mg_gate_at(V_REST_POST), mg_gate_at(V_ACTIVE_POST)

    # Rate thresholds implied by the gate: <c> = C_pre*gate*r*tau_Ca.
    tau_ca_s = float(p['tau_Ca_NMDA'] / second)
    r_thD = p['theta_d'] / (p['C_pre'] * gate_active * tau_ca_s)
    r_thP = p['theta_p'] / (p['C_pre'] * gate_active * tau_ca_s)
    print(f'      Mg gate: {gate_rest:.4f} at rest ({V_REST_POST:.0f} mV), '
          f'{gate_active:.4f} at {V_ACTIVE_POST:.0f} mV')
    print(f'      implied rate thresholds at {V_ACTIVE_POST:.0f} mV: '
          f'theta_D ~ {r_thD:.0f} Hz, theta_P ~ {r_thP:.0f} Hz')
    print(f'      (ungated these were 33 / 93 Hz -- the gate moves them by 1/gate, which')
    print(f'       is why the original 40/100 Hz rates no longer straddle the boundary)')
    R_LTD = round(0.6 * r_thP / 10) * 10
    R_LTP = round(1.6 * r_thP / 10) * 10

    # -- 2a: Single pre-spike - calcium jump & decay --------------
    print('  2a: Single pre-spike calcium dynamics ...')
    start_scope()

    pre = SpikeGeneratorGroup(1, [0], [100 * ms])
    post = NeuronGroup(1, post_eqs, method='euler', namespace=p)
    syn = Synapses(pre, post, model=eqs_synapse_plasticity,
                   on_pre=on_pre_plasticity, method='heun', namespace=p)
    syn.connect()
    syn.rho = 0.5
    attach_rho_clipper(syn)
    syn.c = 0.0

    mon_2a = StateMonitor(syn, ['c', 'rho', 'w'], record=True, dt=0.1 * ms)
    run(300 * ms)

    t_2a = mon_2a.t / ms
    c_2a = mon_2a.c[0]

    # Peak calcium in a window right after the spike
    idx_win = (t_2a > 100) & (t_2a < 105)
    c_peak = float(np.max(c_2a[idx_win]))
    expected_2a = p['C_pre'] * gate_rest
    jump_ok = abs(c_peak - expected_2a) < max(0.05 * expected_2a, 1e-4)
    print(f'      Calcium peak after spike: {c_peak:.4f}  '
          f'(expected C_pre*gate = {expected_2a:.4f})  '
          f'-> {"PASS" if jump_ok else "FAIL"}')
    if not jump_ok:
        all_pass = False

    # Decay check: at t_spike + tau_Ca_NMDA the calcium should be ~ C_pre * e^{-1}
    tau_ms = float(p['tau_Ca_NMDA'] / ms)
    idx_decay = np.argmin(np.abs(t_2a - (100.0 + tau_ms)))
    c_at_tau = float(c_2a[idx_decay])
    expected_decay = expected_2a * np.exp(-1)
    decay_ok = abs(c_at_tau - expected_decay) / expected_decay < 0.20
    print(f'      Calcium at t+tau ({tau_ms:.0f} ms): {c_at_tau:.3f}  (expected ~{expected_decay:.3f})  '
          f'-> {"PASS" if decay_ok else "FAIL"}')
    if not decay_ok:
        all_pass = False

    # -- 2b: threshold crossings at a depolarised branch ----------
    # Held at V_ACTIVE_POST: with the Mg gate a resting branch cannot cross theta_D at
    # any presynaptic rate, so the crossing test is only meaningful on an active branch.
    p['v_hold_post'] = V_ACTIVE_POST * mV
    R_CROSS = round(1.2 * r_thD / 10) * 10
    print(f'  2b: {R_CROSS:.0f} Hz spike train at {V_ACTIVE_POST:.0f} mV '
          f'- threshold crossings ...')
    start_scope()

    spike_times = np.arange(50, 550, 1000.0 / R_CROSS) * ms
    spike_idx = np.zeros(len(spike_times), dtype=int)
    pre2 = SpikeGeneratorGroup(1, spike_idx, spike_times)
    post2 = NeuronGroup(1, post_eqs, method='euler', namespace=p)
    syn2 = Synapses(pre2, post2, model=eqs_synapse_plasticity,
                    on_pre=on_pre_plasticity, method='heun', namespace=p)
    syn2.connect()
    syn2.rho = 0.5
    attach_rho_clipper(syn2)
    syn2.c = 0.0
    mon_2b = StateMonitor(syn2, ['c', 'rho'], record=True, dt=0.1 * ms)
    run(800 * ms)

    c_2b = mon_2b.c[0]
    t_2b = mon_2b.t / ms
    crossed_d = bool(np.any(c_2b > p['theta_d']))
    crossed_p = bool(np.any(c_2b > p['theta_p']))

    # Steady state ~ C_pre*gate*rate*tau; R_CROSS is set to 1.2x the theta_D rate, so
    # theta_D should be crossed and theta_P should not.
    print(f'      Crossed theta_d ({p["theta_d"]:.1f}): {crossed_d}  -> {"PASS" if crossed_d else "FAIL"}')
    if not crossed_d:
        all_pass = False
    print(f'      Crossed theta_p ({p["theta_p"]:.2f}): {crossed_p}  (informational)')

    # -- 2c: High-rate input - plasticity direction (LTP) ---------
    p['v_hold_post'] = V_ACTIVE_POST * mV
    print(f'  2c: {R_LTP:.0f} Hz input at {V_ACTIVE_POST:.0f} mV '
          f'- plasticity direction (LTP expected) ...')
    start_scope()

    spike_times_hi = np.arange(10, 3010, 1000.0 / R_LTP) * ms
    spike_idx_hi = np.zeros(len(spike_times_hi), dtype=int)
    pre3 = SpikeGeneratorGroup(1, spike_idx_hi, spike_times_hi)
    post3 = NeuronGroup(1, post_eqs, method='euler', namespace=p)
    syn3 = Synapses(pre3, post3, model=eqs_synapse_plasticity,
                    on_pre=on_pre_plasticity, method='heun', namespace=p)
    syn3.connect()
    syn3.rho = 0.5
    attach_rho_clipper(syn3)
    syn3.c = 0.0
    mon_2c = StateMonitor(syn3, ['c', 'rho', 'w'], record=True, dt=1 * ms)
    run(3 * second)

    rho_init = 0.5
    rho_final = float(mon_2c.rho[0][-1])
    # R_LTP is 1.6x the gate-implied theta_P rate -> gamma_p dominates -> LTP (rho ^)
    ltp_ok = rho_final > rho_init
    print(f'      rho: {rho_init:.2f} -> {rho_final:.3f}  '
          f'({"increase = LTP OK" if ltp_ok else "UNEXPECTED DIRECTION"})  '
          f'-> {"PASS" if ltp_ok else "FAIL"}')
    if not ltp_ok:
        all_pass = False

    # -- 2d: Low-rate input - plasticity direction (LTD) ----------
    print(f'  2d: {R_LTD:.0f} Hz input at {V_ACTIVE_POST:.0f} mV '
          f'- plasticity direction (LTD expected) ...')
    start_scope()

    spike_times_lo = np.arange(10, 5010, 1000.0 / R_LTD) * ms
    spike_idx_lo = np.zeros(len(spike_times_lo), dtype=int)
    pre4 = SpikeGeneratorGroup(1, spike_idx_lo, spike_times_lo)
    post4 = NeuronGroup(1, post_eqs, method='euler', namespace=p)
    syn4 = Synapses(pre4, post4, model=eqs_synapse_plasticity,
                    on_pre=on_pre_plasticity, method='heun', namespace=p)
    syn4.connect()
    syn4.rho = 0.5
    attach_rho_clipper(syn4)
    syn4.c = 0.0
    mon_2d = StateMonitor(syn4, ['c', 'rho', 'w'], record=True, dt=1 * ms)
    run(5 * second)

    rho_final_lo = float(mon_2d.rho[0][-1])
    # At 40 Hz, steady-state Ca ~ 1.0 * 40 * 0.03 = 1.2 -> above theta_d but below theta_p
    # -> gamma_d dominates -> LTD (rho v)
    ltd_ok = rho_final_lo < rho_init
    print(f'      rho: {rho_init:.2f} -> {rho_final_lo:.3f}  '
          f'({"decrease = LTD OK" if ltd_ok else "UNEXPECTED DIRECTION"})  '
          f'-> {"PASS" if ltd_ok else "FAIL"}')
    if not ltd_ok:
        all_pass = False

    # -- Diagnostic plot --
    fig, axes = plt.subplots(4, 1, figsize=(11, 12))

    axes[0].plot(t_2a, c_2a, color='#1565C0', lw=1.2)
    axes[0].axhline(p['theta_d'], color='orange', ls='--', label=f'theta_d = {p["theta_d"]}')
    axes[0].axhline(p['theta_p'], color='red', ls='--', label=f'theta_p = {p["theta_p"]}')
    axes[0].axvline(100, color='gray', ls=':', alpha=0.4, label='pre spike')
    axes[0].set_ylabel('Calcium')
    axes[0].set_title('2a - Single Pre-Spike Calcium')
    axes[0].legend(fontsize=9)
    axes[0].grid(True, alpha=0.2)

    axes[1].plot(t_2b, c_2b, color='#D32F2F', lw=1)
    axes[1].axhline(p['theta_d'], color='orange', ls='--')
    axes[1].axhline(p['theta_p'], color='red', ls='--')
    axes[1].set_ylabel('Calcium')
    axes[1].set_title('2b - 50 Hz Pre-Spike Train')
    axes[1].grid(True, alpha=0.2)

    axes[2].plot(mon_2c.t / ms, mon_2c.rho[0], color='#2E7D32', lw=2, label='100 Hz -> LTP')
    axes[2].axhline(0.5, color='gray', ls='--', alpha=0.5)
    axes[2].set_ylabel('rho')
    axes[2].set_title('2c - Weight State (100 Hz, LTP expected)')
    axes[2].legend(fontsize=9)
    axes[2].grid(True, alpha=0.2)

    axes[3].plot(mon_2d.t / ms, mon_2d.rho[0], color='#E65100', lw=2, label='40 Hz -> LTD')
    axes[3].axhline(0.5, color='gray', ls='--', alpha=0.5)
    axes[3].set_ylabel('rho')
    axes[3].set_xlabel('Time (ms)')
    axes[3].set_title('2d - Weight State (40 Hz, LTD expected)')
    axes[3].legend(fontsize=9)
    axes[3].grid(True, alpha=0.2)

    plt.tight_layout()
    plt.savefig(os.path.join(VAL_DIR, 'test2_calcium_plasticity.png'), dpi=150)
    plt.close()

    results['Test 2: Calcium & Plasticity'] = all_pass
    return all_pass


# ================================================================
# TEST 3: Branch-Specific Gating
# ================================================================
def test3_branch_gating():
    print('\n' + '=' * 60)
    print(' TEST 3: Branch-Specific Gating')
    print('=' * 60)

    start_scope()

    p = params.copy()
    p.update(plasticity_params)
    p.update(som_params)

    num_pyr = 1
    num_dend_each = 2
    p['num_Soma'] = num_pyr
    p['num_DendEach'] = num_dend_each
    p['num_Dend'] = num_pyr * num_dend_each
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * num_dend_each

    temp = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']
    p['norm_factor_Ca'] = temp ** (1 / (temp - 1))
    temp = p['tauGABABRise'] / p['tauGABABDecay']
    p['norm_factor_GABAB'] = temp ** (1 / (temp - 1))

    net = Network()

    # -- Pyramidal Neuron -----------------------------------------
    reset_eqs = 'V = vReset_pyr'
    Soma = NeuronGroup(num_pyr, eqs_soma, threshold='V > vThres_pyr',
                       reset=reset_eqs, refractory=p['refracTime_pyr'],
                       method='euler', namespace=p)
    Soma.V = p['vRest_pyr']
    Soma.vShadow = p['vRest_pyr']
    Soma.vAveDend = p['vRest_pyr']

    Dend = NeuronGroup(p['num_Dend'], eqs_dend, method='euler', namespace=p)
    Dend.V = p['vRest_pyr']
    Dend.vSoma = p['vRest_pyr']

    @network_operation(dt=p['sim_dt'])
    def Coupling():
        temp_v = Dend.V[:].reshape((num_pyr, num_dend_each))
        Soma.vAveDend = np.mean(temp_v, axis=1)
        Dend.vSoma = np.repeat(Soma.vShadow[:], num_dend_each)

    bAP_syn = Synapses(Soma, Dend, on_pre='V_post += bAP_amp\nbAPCa_rise_post += norm_factor_Ca',
                       delay=p['bAP_delay'], namespace=p)
    bAP_syn.connect(j='i*num_DendEach + k for k in range(num_DendEach)')

    net.add([Soma, Dend, Coupling, bAP_syn])

    # -- SOM interneurons -> inhibit ONLY Branch 0 ----------------
    SOM_cells = NeuronGroup(10, eqs_som, threshold='V > vThres_som',
                            reset='V = vReset_som', refractory=p['refrac_som'],
                            method='euler', namespace=p)
    SOM_cells.V = p['vRest_som']
    SOM_cells.iBaseline_som = 25.0 * pA  # ~30-40 Hz baseline

    syn_som2dend = Synapses(SOM_cells, Dend,
                            on_pre='gTotGABA_post += gGABA', namespace=p)
    syn_som2dend.connect(j='0')  # ALL SOM -> only dendrite index 0
    net.add([SOM_cells, syn_som2dend])

    # -- Excitatory input - separate Synapses per branch ----------
    exc_input = PoissonGroup(20, rates=80 * Hz)

    syn_exc_b0 = Synapses(exc_input, Dend, model=eqs_synapse_plasticity,
                          on_pre=on_pre_plasticity, method='heun', namespace=p)
    syn_exc_b0.connect(j='0')   # all 20 inputs -> dendrite 0
    syn_exc_b0.rho = 0.5
    attach_rho_clipper(syn_exc_b0)

    # Second pathway population -> NMDA slot 2 (Brian 2 permits one writer per summed
    # variable per target group; the dendrite declares two slots for exactly this).
    syn_exc_b1 = Synapses(exc_input, Dend, model=make_eqs_synapse_plasticity(2),
                          on_pre=on_pre_plasticity, method='heun', namespace=p)
    syn_exc_b1.connect(j='1')   # all 20 inputs -> dendrite 1
    syn_exc_b1.rho = 0.5
    attach_rho_clipper(syn_exc_b1)

    net.add([exc_input, syn_exc_b0, syn_exc_b1])

    # -- Monitors -------------------------------------------------
    mon_w_b0 = StateMonitor(syn_exc_b0, ['w', 'c', 'rho'], record=True, dt=50 * ms)
    mon_w_b1 = StateMonitor(syn_exc_b1, ['w', 'c', 'rho'], record=True, dt=50 * ms)
    mon_dend = StateMonitor(Dend, 'V', record=True, dt=1 * ms)
    mon_spike = SpikeMonitor(Soma)
    net.add([mon_w_b0, mon_w_b1, mon_dend, mon_spike])

    # -- Run ------------------------------------------------------
    print('  Running 3-second simulation (Branch 0 inhibited, Branch 1 free) ...')
    net.run(3 * second, report='text')

    # -- Analyze --------------------------------------------------
    w_b0_all = np.array([mon_w_b0.w[i][-1] for i in range(len(syn_exc_b0))])
    w_b1_all = np.array([mon_w_b1.w[i][-1] for i in range(len(syn_exc_b1))])
    w_b0_final, w_b1_final = float(np.mean(w_b0_all)), float(np.mean(w_b1_all))
    n0, n1 = len(w_b0_all), len(w_b1_all)

    print(f'  Branch 0 (inhibited):    mean={w_b0_final:.3f}  sd={np.std(w_b0_all):.3f}  n={n0}')
    print(f'  Branch 1 (disinhibited): mean={w_b1_final:.3f}  sd={np.std(w_b1_all):.3f}  n={n1}')

    if w_b0_final > 0.01:
        ratio = w_b1_final / w_b0_final
    else:
        ratio = float('inf') if w_b1_final > 0.01 else 1.0

    # Two criteria, both required. The old test asserted only `w_b1 > w_b0`, which on
    # two statistically identical branches is a coin flip -- observed passing at ratio
    # 1.02 and failing at 0.99 with no change to the model. A gating test has to demand
    # an effect that noise cannot supply.
    MIN_RATIO = 1.10          # disinhibited branch at least 10% stronger

    # PAIRED comparison. Both Synapses objects were built from the same 20-cell
    # `exc_input` group (all-to-one onto each dendrite), so synapse i on branch 0 and
    # synapse i on branch 1 are driven by the *same* presynaptic spike train. Pairing
    # on i cancels that shared drive, which is by far the largest variance component --
    # the unpaired spread is ~0.9 per synapse because individual bistable synapses sit
    # near the 0 / w1 rails. Unpaired power at n=20 is only ~13% for a +20% effect;
    # paired power is far higher, which matters for detecting a genuine fix rather than
    # just rejecting the broken state.
    paired = (len(w_b1_all) == len(w_b0_all))
    if paired:
        d = w_b1_all - w_b0_all
        sem_d = float(np.std(d, ddof=1) / np.sqrt(len(d))) if len(d) > 1 else 0.0
        separation = float(np.mean(d)) / sem_d if sem_d > 1e-12 else 0.0
        sep_label = 'paired'
    else:
        sem = float(np.sqrt(np.var(w_b0_all) / max(n0, 1) + np.var(w_b1_all) / max(n1, 1)))
        separation = (w_b1_final - w_b0_final) / sem if sem > 1e-12 else 0.0
        sep_label = 'unpaired'

    ratio_ok = ratio >= MIN_RATIO
    sep_ok = separation >= 2.0    # difference exceeds ~2 standard errors
    passed = bool(ratio_ok and sep_ok)

    print(f'  Ratio (free / inhibited): {ratio:.3f}  (need >= {MIN_RATIO:.2f})'
          f'  -> {"ok" if ratio_ok else "insufficient effect size"}')
    print(f'  Separation ({sep_label}):    {separation:.2f} SEM  (need >= 2.00)'
          f'  -> {"ok" if sep_ok else "within noise"}')
    print(f'  Branch-specific gating:   {"PASS" if passed else "FAIL"}')

    # -- Diagnostic plot ------------------------------------------
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)

    axes[0].plot(mon_dend.t / ms, mon_dend.V[0] / mV, color='#D32F2F', alpha=0.8,
                 label='Branch 0 (SOM-inhibited)', lw=0.5)
    axes[0].plot(mon_dend.t / ms, mon_dend.V[1] / mV, color='#2E7D32', alpha=0.8,
                 label='Branch 1 (free)', lw=0.5)
    axes[0].set_ylabel('Dendrite V (mV)')
    axes[0].set_title('Test 3 - Branch-Specific Gating: Dendritic Voltages')
    axes[0].legend(fontsize=9)
    axes[0].grid(True, alpha=0.2)

    # Mean weight over time per branch
    w_b0_t = np.mean([mon_w_b0.w[i] for i in range(len(syn_exc_b0))], axis=0)
    w_b1_t = np.mean([mon_w_b1.w[i] for i in range(len(syn_exc_b1))], axis=0)
    axes[1].plot(mon_w_b0.t / ms, w_b0_t, color='#D32F2F', lw=2.5, label='Branch 0 (inhibited)')
    axes[1].plot(mon_w_b1.t / ms, w_b1_t, color='#2E7D32', lw=2.5, label='Branch 1 (free)')
    axes[1].set_ylabel('Mean Weight (w)')
    axes[1].set_title('Synaptic Weight Evolution')
    axes[1].legend(fontsize=9)
    axes[1].grid(True, alpha=0.2)

    # Mean calcium per branch
    c_b0_t = np.mean([mon_w_b0.c[i] for i in range(len(syn_exc_b0))], axis=0)
    c_b1_t = np.mean([mon_w_b1.c[i] for i in range(len(syn_exc_b1))], axis=0)
    axes[2].plot(mon_w_b0.t / ms, c_b0_t, color='#D32F2F', lw=1, label='Branch 0')
    axes[2].plot(mon_w_b1.t / ms, c_b1_t, color='#2E7D32', lw=1, label='Branch 1')
    axes[2].axhline(p['theta_d'], color='orange', ls='--', alpha=0.6, label=f'theta_d = {p["theta_d"]}')
    axes[2].axhline(p['theta_p'], color='red', ls='--', alpha=0.6, label=f'theta_p = {p["theta_p"]}')
    axes[2].set_ylabel('Mean Calcium')
    axes[2].set_xlabel('Time (ms)')
    axes[2].set_title('Calcium Concentration per Branch')
    axes[2].legend(fontsize=9)
    axes[2].grid(True, alpha=0.2)

    plt.tight_layout()
    plt.savefig(os.path.join(VAL_DIR, 'test3_branch_gating.png'), dpi=150)
    plt.close()

    results['Test 3: Branch-Specific Gating'] = passed
    return passed


# ================================================================
# TEST 4: Long-Run Stability (10 seconds)
# ================================================================
def test4_stability():
    print('\n' + '=' * 60)
    print(' TEST 4: Long-Run Stability (10 s)')
    print('=' * 60)

    start_scope()

    p = params.copy()
    p.update(plasticity_params)
    p.update(pv_params)
    p.update(som_params)
    p.update(vip_params)
    p.update(md_params)

    num_pyr = 1
    num_dend_each = 2
    num_pv = p['n_pv']
    num_som = p['n_som_spike']
    num_vip = p['n_vip_spike']
    num_md = p['n_md']

    p['num_Soma'] = num_pyr
    p['num_DendEach'] = num_dend_each
    p['num_Dend'] = num_pyr * num_dend_each
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * num_dend_each

    temp = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']
    p['norm_factor_Ca'] = temp ** (1 / (temp - 1))
    temp = p['tauGABABRise'] / p['tauGABABDecay']
    p['norm_factor_GABAB'] = temp ** (1 / (temp - 1))

    net = Network()

    # Build full circuit (same as demo_v2_zhang2025.py)
    reset_eqs = 'V = vReset_pyr'
    Soma = NeuronGroup(num_pyr, eqs_soma, threshold='V > vThres_pyr',
                       reset=reset_eqs, refractory=p['refracTime_pyr'],
                       method='euler', namespace=p)
    Soma.V = p['vRest_pyr']
    Soma.vShadow = p['vRest_pyr']
    Soma.vAveDend = p['vRest_pyr']

    Dend = NeuronGroup(p['num_Dend'], eqs_dend, method='euler', namespace=p)
    Dend.V = p['vRest_pyr']
    Dend.vSoma = p['vRest_pyr']

    @network_operation(dt=p['sim_dt'])
    def Coupling():
        temp_v = Dend.V[:].reshape((num_pyr, num_dend_each))
        Soma.vAveDend = np.mean(temp_v, axis=1)
        Dend.vSoma = np.repeat(Soma.vShadow[:], num_dend_each)

    bAP_syn = Synapses(Soma, Dend, on_pre='V_post += bAP_amp\nbAPCa_rise_post += norm_factor_Ca',
                       delay=p['bAP_delay'], namespace=p)
    bAP_syn.connect(j='i*num_DendEach + k for k in range(num_DendEach)')

    PV_cells = NeuronGroup(num_pv, eqs_pv, threshold='V > vThres_pv',
                           reset='V = vReset_pv', refractory=p['refrac_pv'],
                           method='euler', namespace=p)
    PV_cells.V = p['vRest_pv']
    # Tonic background drive giving PV a baseline it can be modulated around.
    BG_pv = PoissonGroup(num_pv, rates=p['rate_bg_pv'])
    syn_bg_pv = Synapses(BG_pv, PV_cells, on_pre='gTotAMPA_post += weight_bg_pv',
                         namespace=p)
    syn_bg_pv.connect(j='i')


    SOM_cells = NeuronGroup(num_som, eqs_som, threshold='V > vThres_som',
                            reset='V = vReset_som', refractory=p['refrac_som'],
                            method='euler', namespace=p)
    SOM_cells.V = p['vRest_som']
    SOM_cells.iBaseline_som = 22.0 * pA

    VIP_cells = NeuronGroup(num_vip, eqs_vip, threshold='V > vThres_vip',
                            reset='V = vReset_vip', refractory=p['refrac_vip'],
                            method='euler', namespace=p)
    VIP_cells.V = p['vRest_vip']

    md_rate_hz = 20.0
    MD = PoissonGroup(num_md, rates=md_rate_hz * Hz)  # Constant moderate rate

    syn_md2pv = Synapses(MD, PV_cells, on_pre='gTotAMPA_post += gAMPA_pv', namespace=p)
    syn_md2pv.connect(p=p['p_md2pv'])
    syn_md2vip = Synapses(MD, VIP_cells, on_pre='gTotAMPA_post += gAMPA_vip', namespace=p)
    syn_md2vip.connect(p=p['p_md2vip'])
    syn_vip2som = Synapses(VIP_cells, SOM_cells, on_pre='gTotGABA_post += gGABA_som', namespace=p)
    syn_vip2som.connect(p=p['p_vip2som_spike'])
    syn_som2dend = Synapses(SOM_cells, Dend, on_pre='gTotGABA_post += gGABA', namespace=p)
    syn_som2dend.connect(p=p['p_som2dend_spike'])
    syn_pv2soma = Synapses(PV_cells, Soma, on_pre='gTotGABA_post += gGABA_pv2soma', namespace=p)
    syn_pv2soma.connect(p=p['p_pv2soma'])

    pathway_input = PoissonGroup(30, rates=80 * Hz)
    syn_input = Synapses(pathway_input, Dend, model=eqs_synapse_plasticity,
                         on_pre=on_pre_plasticity, method='heun', namespace=p)
    syn_input.connect()
    syn_input.rho = 0.5
    attach_rho_clipper(syn_input)

    mon_soma_v = StateMonitor(Soma, 'V', record=True, dt=1 * ms)
    mon_w = StateMonitor(syn_input, ['w', 'rho'], record=[0], dt=100 * ms)
    mon_pv_sp = SpikeMonitor(PV_cells)
    mon_som_sp = SpikeMonitor(SOM_cells)
    mon_pyr_sp = SpikeMonitor(Soma)

    net.add([Soma, Dend, Coupling, bAP_syn,
             PV_cells, SOM_cells, VIP_cells, MD, BG_pv, syn_bg_pv,
             syn_md2pv, syn_md2vip, syn_vip2som, syn_som2dend, syn_pv2soma,
             pathway_input, syn_input,
             mon_soma_v, mon_w, mon_pv_sp, mon_som_sp, mon_pyr_sp])

    print('  Running 10-second full circuit simulation ...')
    net.run(10 * second, report='text')

    # -- Check for numerical stability ----------------------------
    all_pass = True

    v_trace = mon_soma_v.V[0] / mV
    has_nan = bool(np.any(np.isnan(v_trace)))
    has_inf = bool(np.any(np.isinf(v_trace)))
    print(f'  NaN in voltage:     {has_nan}  -> {"FAIL" if has_nan else "PASS"}')
    print(f'  Inf in voltage:     {has_inf}  -> {"FAIL" if has_inf else "PASS"}')
    if has_nan or has_inf:
        all_pass = False

    # -- 4c: derived weight must stay inside [w0, w1] -------------
    # This is guaranteed by clip(rho) in the w assignment, so on its own it is a weak
    # check. The informative version is 4b below, on the *state* variable rho.
    w_trace = mon_w.w[0]
    w_bounded = bool(np.all((w_trace >= p['w0'] - 1e-9) & (w_trace <= p['w1'] + 1e-9)))
    print(f'  Weight w within [{p["w0"]:.1f}, {p["w1"]:.1f}]: {w_bounded}  '
          f'(min={np.min(w_trace):.3f}, max={np.max(w_trace):.3f})  '
          f'-> {"PASS" if w_bounded else "FAIL"}')
    if not w_bounded:
        all_pass = False

    # -- 4b: rho itself must remain inside its double well --------
    # rho is the integrated state variable. Only `w` is clipped, so if the noise term
    # or the drift pushes rho outside [0, 1] the escape is invisible in `w`. Assert on
    # rho directly: leaving [0, 1] means the bistable potential is not confining it.
    rho_trace = mon_w.rho[0]
    rho_bounded = bool(np.all((rho_trace >= -1e-9) & (rho_trace <= 1.0 + 1e-9)))
    print(f'  rho within [0, 1]:      {rho_bounded}  '
          f'(min={np.min(rho_trace):.4f}, max={np.max(rho_trace):.4f})  '
          f'-> {"PASS" if rho_bounded else "FAIL (rho escaped the double well)"}')
    if not rho_bounded:
        all_pass = False

    # -- 4d: firing rates below a physiological ceiling -----------
    duration = 10.0
    pv_rate = len(mon_pv_sp.t) / duration / num_pv
    som_rate = len(mon_som_sp.t) / duration / num_som
    pyr_rate = len(mon_pyr_sp.t) / duration / num_pyr
    rates_ok = (pv_rate < 200) and (som_rate < 200) and (pyr_rate < 200)
    print(f'  Firing rates (Hz): PV={pv_rate:.1f}, SOM={som_rate:.1f}, Pyr={pyr_rate:.1f}  '
          f'-> {"PASS" if rates_ok else "FAIL (>200 Hz)"}')
    if not rates_ok:
        all_pass = False

    # -- 4e: the MD->PV arm must actually drive PV ----------------
    # MD runs at 20 Hz into 20 PV cells at p_md2pv=0.5 for the whole 10 s. The spec
    # gives PV the role of broad somatic inhibition; a projection that leaves its
    # target at exactly 0 Hz cannot inhibit anything. Previously this check had only
    # an upper bound, so total silence scored PASS.
    pv_driven = pv_rate > 0.0
    print(f'  PV responds to MD drive: {pv_driven}  (PV={pv_rate:.2f} Hz under '
          f'{md_rate_hz:.0f} Hz MD)  -> {"PASS" if pv_driven else "FAIL (MD->PV arm inert)"}')
    if not pv_driven:
        all_pass = False

    # -- 4f: E/I opposition ---------------------------------------
    # An actively firing pyramidal cell with a completely silent PV population is the
    # unopposed-excitation pathology the E/I-balance hypothesis is about.
    ei_ok = not (pyr_rate > 10.0 and pv_rate <= 0.0)
    print(f'  E/I opposition present: {ei_ok}  (Pyr={pyr_rate:.1f} Hz vs PV={pv_rate:.2f} Hz)'
          f'  -> {"PASS" if ei_ok else "FAIL (pyramidal firing is unopposed)"}')
    if not ei_ok:
        all_pass = False

    # -- Diagnostic plot ------------------------------------------
    fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    axes[0].plot(mon_soma_v.t / ms, v_trace, color='#1565C0', lw=0.3)
    axes[0].set_ylabel('Soma V (mV)')
    axes[0].set_title('Test 4 - 10 s Stability: Soma Voltage')
    axes[0].grid(True, alpha=0.2)

    axes[1].plot(mon_w.t / ms, w_trace, color='#2E7D32', lw=2)
    axes[1].axhline(0, color='gray', ls='--', alpha=0.3)
    axes[1].axhline(3, color='gray', ls='--', alpha=0.3)
    axes[1].set_ylabel('Weight')
    axes[1].set_xlabel('Time (ms)')
    axes[1].set_title('Synaptic Weight Stability')
    axes[1].grid(True, alpha=0.2)

    plt.tight_layout()
    plt.savefig(os.path.join(VAL_DIR, 'test4_stability.png'), dpi=150)
    plt.close()

    results['Test 4: Long-Run Stability'] = all_pass
    return all_pass


# ================================================================
# TEST 5: Random Seed Reproducibility
# ================================================================
def test5_reproducibility():
    """Seed reproducibility and cross-seed consistency.

    The previous version of this test ran three *different* seeds (0, 42, 84) and
    checked only that the across-seed CV was below 0.50 -- so it never tested
    reproducibility at all. Worse, it computed `cv = std/mean if mean > 0 else 0`,
    which scored a completely silent population as CV = 0 and therefore PASS. Two of
    its three populations were passing on exactly that basis.

    This version runs seeds [0, 0, 42, 84] and makes three separate assertions:
      5a  same seed twice  -> bit-identical spike counts (actual reproducibility)
      5b  every population is non-silent (otherwise 5c is vacuous)
      5c  across distinct seeds, rate CV < 0.50
    """
    print('\n' + '=' * 60)
    print(' TEST 5: Seed Reproducibility & Cross-Seed Consistency (4 runs)')
    print('=' * 60)

    p = params.copy()
    p.update(plasticity_params)
    p.update(pv_params)
    p.update(som_params)
    p.update(vip_params)
    p.update(md_params)

    num_pyr = 1
    num_dend_each = 2
    num_pv = p['n_pv']
    num_som = p['n_som_spike']
    num_vip = p['n_vip_spike']
    num_md = p['n_md']

    p['num_Soma'] = num_pyr
    p['num_DendEach'] = num_dend_each
    p['num_Dend'] = num_pyr * num_dend_each
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * num_dend_each

    temp = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']
    p['norm_factor_Ca'] = temp ** (1 / (temp - 1))
    temp = p['tauGABABRise'] / p['tauGABABDecay']
    p['norm_factor_GABAB'] = temp ** (1 / (temp - 1))

    pv_rates = []
    som_rates = []
    pyr_rates = []

    # Runs 0 and 1 share a seed -> they must agree exactly (5a).
    # Runs 0, 2, 3 have distinct seeds -> used for the variability check (5c).
    seeds = [0, 0, 42, 84]

    for run_i, this_seed in enumerate(seeds):
        start_scope()
        seed(this_seed)
        np.random.seed(this_seed)

        net = Network()

        reset_eqs = 'V = vReset_pyr'
        Soma = NeuronGroup(num_pyr, eqs_soma, threshold='V > vThres_pyr',
                           reset=reset_eqs, refractory=p['refracTime_pyr'],
                           method='euler', namespace=p)
        Soma.V = p['vRest_pyr']
        Soma.vShadow = p['vRest_pyr']
        Soma.vAveDend = p['vRest_pyr']

        Dend = NeuronGroup(p['num_Dend'], eqs_dend, method='euler', namespace=p)
        Dend.V = p['vRest_pyr']
        Dend.vSoma = p['vRest_pyr']

        @network_operation(dt=p['sim_dt'])
        def Coupling():
            temp_v = Dend.V[:].reshape((num_pyr, num_dend_each))
            Soma.vAveDend = np.mean(temp_v, axis=1)
            Dend.vSoma = np.repeat(Soma.vShadow[:], num_dend_each)

        bAP_syn = Synapses(Soma, Dend, on_pre='V_post += bAP_amp\nbAPCa_rise_post += norm_factor_Ca',
                           delay=p['bAP_delay'], namespace=p)
        bAP_syn.connect(j='i*num_DendEach + k for k in range(num_DendEach)')

        PV_cells = NeuronGroup(num_pv, eqs_pv, threshold='V > vThres_pv',
                               reset='V = vReset_pv', refractory=p['refrac_pv'],
                               method='euler', namespace=p)
        PV_cells.V = p['vRest_pv']

        # Tonic background drive giving PV a baseline it can be modulated around.
        BG_pv = PoissonGroup(num_pv, rates=p['rate_bg_pv'])
        syn_bg_pv = Synapses(BG_pv, PV_cells, on_pre='gTotAMPA_post += weight_bg_pv',
                             namespace=p)
        syn_bg_pv.connect(j='i')


        SOM_cells = NeuronGroup(num_som, eqs_som, threshold='V > vThres_som',
                                reset='V = vReset_som', refractory=p['refrac_som'],
                                method='euler', namespace=p)
        SOM_cells.V = p['vRest_som']
        SOM_cells.iBaseline_som = 22.0 * pA

        VIP_cells = NeuronGroup(num_vip, eqs_vip, threshold='V > vThres_vip',
                                reset='V = vReset_vip', refractory=p['refrac_vip'],
                                method='euler', namespace=p)
        VIP_cells.V = p['vRest_vip']

        MD = PoissonGroup(num_md, rates=5 * Hz)

        syn_md2pv = Synapses(MD, PV_cells, on_pre='gTotAMPA_post += gAMPA_pv', namespace=p)
        syn_md2pv.connect(p=p['p_md2pv'])
        syn_md2vip = Synapses(MD, VIP_cells, on_pre='gTotAMPA_post += gAMPA_vip', namespace=p)
        syn_md2vip.connect(p=p['p_md2vip'])
        syn_vip2som = Synapses(VIP_cells, SOM_cells, on_pre='gTotGABA_post += gGABA_som', namespace=p)
        syn_vip2som.connect(p=p['p_vip2som_spike'])
        syn_som2dend = Synapses(SOM_cells, Dend, on_pre='gTotGABA_post += gGABA', namespace=p)
        syn_som2dend.connect(p=p['p_som2dend_spike'])
        syn_pv2soma = Synapses(PV_cells, Soma, on_pre='gTotGABA_post += gGABA_pv2soma', namespace=p)
        syn_pv2soma.connect(p=p['p_pv2soma'])

        pathway_input = PoissonGroup(30, rates=80 * Hz)
        syn_input = Synapses(pathway_input, Dend, model=eqs_synapse_plasticity,
                             on_pre=on_pre_plasticity, method='heun', namespace=p)
        syn_input.connect()
        syn_input.rho = 0.5
        attach_rho_clipper(syn_input)

        mon_pv = SpikeMonitor(PV_cells)
        mon_som = SpikeMonitor(SOM_cells)
        mon_pyr = SpikeMonitor(Soma)

        net.add([Soma, Dend, Coupling, bAP_syn,
                 PV_cells, SOM_cells, VIP_cells, MD, BG_pv, syn_bg_pv,
                 syn_md2pv, syn_md2vip, syn_vip2som, syn_som2dend, syn_pv2soma,
                 pathway_input, syn_input,
                 mon_pv, mon_som, mon_pyr])

        print(f'  Run {run_i + 1}/{len(seeds)} (seed={this_seed}) ...')
        net.run(2 * second, report='text')

        dur = 2.0
        pv_rates.append(len(mon_pv.t) / dur / num_pv)
        som_rates.append(len(mon_som.t) / dur / num_som)
        pyr_rates.append(len(mon_pyr.t) / dur / num_pyr)

    # -- 5a: same seed must reproduce exactly ---------------------
    all_pass = True
    print()
    repro_ok = True
    for label, rates in [('PV', pv_rates), ('SOM', som_rates), ('Pyr', pyr_rates)]:
        same = abs(rates[0] - rates[1]) < 1e-12
        print(f'  5a {label:3s} seed 0 twice: {rates[0]:.3f} vs {rates[1]:.3f} Hz'
              f'  -> {"PASS" if same else "FAIL (not reproducible)"}')
        if not same:
            repro_ok = False
    if not repro_ok:
        all_pass = False

    # -- 5b/5c: non-vacuity, then cross-seed consistency ----------
    print()
    distinct = [0, 2, 3]   # indices of the runs with distinct seeds
    n_uncovered = 0
    for label, rates in [('PV', pv_rates), ('SOM', som_rates), ('Pyr', pyr_rates)]:
        arr = np.array([rates[i] for i in distinct])
        mean_r = float(np.mean(arr))
        std_r = float(np.std(arr))

        # 5b: a silent population makes the CV check meaningless -- CV would be 0 and
        # score PASS, which is what previously hid the inert MD->PV arm. Such a
        # population is reported as NOT COVERED rather than PASS.
        #
        # Note it is not failed either. At this test's 5 Hz MD drive the pyramidal cell
        # is *correctly* silent: VIP is unrecruited, SOM runs at ~36 Hz, and the
        # dendritic gate is shut. Failing on that would be a false positive. The PV arm
        # is asserted in Test 4 (check 4e) instead, under a 20 Hz drive where PV is
        # genuinely required to respond.
        if mean_r <= 0.0:
            print(f'  5b {label:3s}: rates = {[f"{r:.1f}" for r in arr]}  mean=0.00  '
                  f'-> NOT COVERED (silent; CV undefined, so not asserted here)')
            n_uncovered += 1
            continue

        cv = std_r / mean_r
        ok = cv < 0.50   # Allow up to 50% CV for small stochastic networks
        print(f'  5c {label:3s}: rates = {[f"{r:.1f}" for r in arr]}  '
              f'mean={mean_r:.1f}  CV={cv:.2f}  -> {"PASS" if ok else "FAIL"}')
        if not ok:
            all_pass = False

    # The consistency check must cover at least one population, otherwise the whole
    # test is vacuous no matter how it is scored.
    if n_uncovered >= 3:
        print('  5b: no population was active -- consistency check covered nothing '
              '-> FAIL')
        all_pass = False
    elif n_uncovered:
        print(f'  ({n_uncovered} of 3 populations silent and therefore not covered)')

    results['Test 5: Reproducibility'] = all_pass
    return all_pass


# ================================================================
# TEST 6: dt Warning Fix Verification
# ================================================================
def test6_dt_warning():
    print('\n' + '=' * 60)
    print(' TEST 6: dt Namespace Warning Fix')
    print('=' * 60)

    p = params.copy()
    p.update(plasticity_params)

    has_dt_key = 'dt' in p
    has_sim_dt_key = 'sim_dt' in p

    print(f'  "dt" in params:     {has_dt_key}  -> {"FAIL (should be removed)" if has_dt_key else "PASS"}')
    print(f'  "sim_dt" in params: {has_sim_dt_key}  -> {"PASS" if has_sim_dt_key else "FAIL (should exist)"}')

    passed = (not has_dt_key) and has_sim_dt_key
    results['Test 6: dt Warning Fix'] = passed
    return passed


# ================================================================
# MAIN
# ================================================================
if __name__ == '__main__':
    t_start = timer.time()

    print('+' + '=' * 58 + '+')
    print('|       MODEL VALIDATION SUITE                              |')
    print('|       Thalamocortical Gating Model - Robustness Check     |')
    print('+' + '=' * 58 + '+')

    test1_isolated_cells()
    test2_calcium_plasticity()
    test3_branch_gating()
    test4_stability()
    test5_reproducibility()
    test6_dt_warning()

    elapsed = timer.time() - t_start

    # -- Final Summary --------------------------------------------
    print('\n')
    print('+' + '=' * 58 + '+')
    print('|                    RESULTS SUMMARY                        |')
    print('+' + '=' * 58 + '+')

    n_pass = 0
    n_total = len(results)
    for name, passed in results.items():
        tag = 'PASS' if passed else 'FAIL'
        line = f'  {name:40s} {tag}'
        print(f'| {line:56s} |')
        if passed:
            n_pass += 1

    print('+' + '=' * 58 + '+')
    summary = f'  {n_pass}/{n_total} PASSED   ({elapsed:.0f} s elapsed)'
    print(f'| {summary:56s} |')
    print('+' + '=' * 58 + '+')

    if n_pass == n_total:
        print('\n  All tests passed. Model is ready for parameter sweeps.')
    else:
        print('\n  Some tests failed. Review figures/validation/ for diagnostics.')

    print(f'\n  Diagnostic plots saved to: {os.path.abspath(VAL_DIR)}/')
