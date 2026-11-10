"""
test5_pv_diag.py -- root-cause the Test-5 PV same-seed non-determinism (step A).
2026-10-11 (Raghav). Rebuilds the EXACT Test-5 circuit (validate_model.py) for seed 0,
TWICE in one process, mirroring the real loop (start_scope + seed + np.random.seed each
time), and instruments every stochastic element that drives PV, to localize what differs:

  - BG_pv  : the 500 Hz background Poisson onto PV (SpikeMonitor -> count + exact times)
  - MD     : the 5 Hz MD Poisson (SpikeMonitor -> count + exact times)
  - syn_md2pv connectivity : probabilistic connect(p=...) -> exact (i,j) pairs
  - PV     : output spike count (the quantity that was non-reproducible)

If seeding truly fixed everything, all four must match between the two seed-0 runs. The
one that differs is the culprit. No assumptions -- the script reports which differ.
"""
import sys, os
import numpy as np
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'model'))
from brian2 import *
prefs.codegen.target = 'numpy'
from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
from equations import (attach_rho_clipper, eqs_soma, eqs_dend, eqs_pv, eqs_som, eqs_vip,
                       eqs_synapse_plasticity, on_pre_plasticity)
BrianLogger.suppress_name('resolution_conflict', 'base')


def build_and_run(seed_val, include_pyramidal=True):
    start_scope()
    seed(seed_val)
    np.random.seed(seed_val)

    p = params.copy()
    for d in (plasticity_params, pv_params, som_params, vip_params, md_params):
        p.update(d)
    num_pyr, num_dend_each = 1, 2
    num_pv, num_som, num_vip, num_md = p['n_pv'], p['n_som_spike'], p['n_vip_spike'], p['n_md']
    p['num_Soma'] = num_pyr; p['num_DendEach'] = num_dend_each; p['num_Dend'] = num_pyr*num_dend_each
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * num_dend_each
    t = p['tau_Ca_bAP_rise']/p['tau_Ca_bAP_decay']; p['norm_factor_Ca'] = t**(1/(t-1))
    t = p['tauGABABRise']/p['tauGABABDecay']; p['norm_factor_GABAB'] = t**(1/(t-1))

    net = Network()
    pyr_objs = []
    if include_pyramidal:
        Soma = NeuronGroup(num_pyr, eqs_soma, threshold='V > vThres_pyr', reset='V = vReset_pyr',
                           refractory=p['refracTime_pyr'], method='euler', namespace=p)
        Soma.V = p['vRest_pyr']; Soma.vShadow = p['vRest_pyr']; Soma.vAveDend = p['vRest_pyr']
        Dend = NeuronGroup(p['num_Dend'], eqs_dend, method='euler', namespace=p)
        Dend.V = p['vRest_pyr']; Dend.vSoma = p['vRest_pyr']

        @network_operation(dt=p['sim_dt'])
        def Coupling():
            temp_v = Dend.V[:].reshape((num_pyr, num_dend_each))
            Soma.vAveDend = np.mean(temp_v, axis=1)
            Dend.vSoma = np.repeat(Soma.vShadow[:], num_dend_each)

        bAP_syn = Synapses(Soma, Dend, on_pre='V_post += bAP_amp\nbAPCa_rise_post += norm_factor_Ca',
                           delay=p['bAP_delay'], namespace=p)
        bAP_syn.connect(j='i*num_DendEach + k for k in range(num_DendEach)')
        pyr_objs += [Soma, Dend, Coupling, bAP_syn]

    PV_cells = NeuronGroup(num_pv, eqs_pv, threshold='V > vThres_pv', reset='V = vReset_pv',
                           refractory=p['refrac_pv'], method='euler', namespace=p)
    PV_cells.V = p['vRest_pv']
    BG_pv = PoissonGroup(num_pv, rates=p['rate_bg_pv'])
    syn_bg_pv = Synapses(BG_pv, PV_cells, on_pre='gTotAMPA_post += weight_bg_pv', namespace=p)
    syn_bg_pv.connect(j='i')

    SOM_cells = NeuronGroup(num_som, eqs_som, threshold='V > vThres_som', reset='V = vReset_som',
                            refractory=p['refrac_som'], method='euler', namespace=p)
    SOM_cells.V = p['vRest_som']; SOM_cells.iBaseline_som = 22.0 * pA
    VIP_cells = NeuronGroup(num_vip, eqs_vip, threshold='V > vThres_vip', reset='V = vReset_vip',
                            refractory=p['refrac_vip'], method='euler', namespace=p)
    VIP_cells.V = p['vRest_vip']
    MD = PoissonGroup(num_md, rates=5 * Hz)

    syn_md2pv = Synapses(MD, PV_cells, on_pre='gTotAMPA_post += gAMPA_pv', namespace=p)
    syn_md2pv.connect(p=p['p_md2pv'])
    syn_md2vip = Synapses(MD, VIP_cells, on_pre='gTotAMPA_post += gAMPA_vip', namespace=p)
    syn_md2vip.connect(p=p['p_md2vip'])
    syn_vip2som = Synapses(VIP_cells, SOM_cells, on_pre='gTotGABA_post += gGABA_som', namespace=p)
    syn_vip2som.connect(p=p['p_vip2som_spike'])

    if include_pyramidal:
        syn_som2dend = Synapses(SOM_cells, Dend, on_pre='gTotGABA_post += gGABA', namespace=p)
        syn_som2dend.connect(p=p['p_som2dend_spike'])
        syn_pv2soma = Synapses(PV_cells, Soma, on_pre='gTotGABA_post += gGABA_pv2soma', namespace=p)
        syn_pv2soma.connect(p=p['p_pv2soma'])
        pathway_input = PoissonGroup(30, rates=80 * Hz)
        syn_input = Synapses(pathway_input, Dend, model=eqs_synapse_plasticity,
                             on_pre=on_pre_plasticity, method='heun', namespace=p)
        syn_input.connect(); syn_input.rho = 0.5; attach_rho_clipper(syn_input)
        pyr_objs += [syn_som2dend, syn_pv2soma, pathway_input, syn_input]

    mon_pv = SpikeMonitor(PV_cells)
    mon_bg = SpikeMonitor(BG_pv)
    mon_md = SpikeMonitor(MD)
    # capture connectivity BEFORE running
    md2pv_ij = (np.array(syn_md2pv.i[:]), np.array(syn_md2pv.j[:]))

    net.add([PV_cells, SOM_cells, VIP_cells, MD, BG_pv, syn_bg_pv, syn_md2pv,
             syn_md2vip, syn_vip2som, mon_pv, mon_bg, mon_md] + pyr_objs)
    net.run(2 * second)

    return dict(
        pv_count=len(mon_pv.t), pv_times=np.array(mon_pv.t/ms),
        bg_count=len(mon_bg.t), bg_times=np.array(mon_bg.t/ms),
        md_count=len(mon_md.t), md_times=np.array(mon_md.t/ms),
        md2pv_n=len(md2pv_ij[0]), md2pv_ij=md2pv_ij,
    )


def arr_equal(a, b):
    return a.shape == b.shape and np.array_equal(a, b)


if __name__ == '__main__':
    # 'single <seed>' mode: one build in THIS (fresh) process, print PV count only.
    # Used to test whether same-seed reproduces across SEPARATE processes.
    if len(sys.argv) >= 2 and sys.argv[1] == 'single':
        s = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        R = build_and_run(s)
        print(f"PV_COUNT seed={s}: {R['pv_count']}", flush=True)
        sys.exit(0)

    if len(sys.argv) >= 2 and sys.argv[1] == 'minimal':
        # Subtractive bisection: strip the pyramidal+plasticity block, keep only the
        # interneuron+Poisson block. If BG_pv/PV now reproduce in-process, the pyramidal/
        # plasticity block is the trigger.
        print("=== Subtractive: interneuron+Poisson block ONLY (no pyramidal/plasticity) ===", flush=True)
        M1 = build_and_run(0, include_pyramidal=False)
        M2 = build_and_run(0, include_pyramidal=False)
        bg = (M1['bg_count'] == M2['bg_count']) and arr_equal(M1['bg_times'], M2['bg_times'])
        pv = (M1['pv_count'] == M2['pv_count']) and arr_equal(M1['pv_times'], M2['pv_times'])
        print(f"  BG_pv: {M1['bg_count']} vs {M2['bg_count']}  -> {'MATCH' if bg else 'DIFFER'}", flush=True)
        print(f"  PV   : {M1['pv_count']} vs {M2['pv_count']}  -> {'MATCH' if pv else 'DIFFER'}", flush=True)
        if bg and pv:
            print("  => stripped circuit REPRODUCES in-process -> the pyramidal/plasticity block "
                  "is the trigger (its presence makes the shared-RNG draws diverge across builds).", flush=True)
        else:
            print("  => still DIFFERS without the pyramidal block -> trigger is in the "
                  "interneuron+Poisson block itself; bisect further.", flush=True)
        sys.exit(0)

    print("=== Test-5 PV non-determinism: seed 0 run TWICE, localize what differs ===", flush=True)
    R1 = build_and_run(0)
    R2 = build_and_run(0)

    print(f"\nPV output spikes:   run1={R1['pv_count']}   run2={R2['pv_count']}   "
          f"{'IDENTICAL' if R1['pv_count']==R2['pv_count'] else 'DIFFER <-- the symptom'}", flush=True)

    print("\n-- Localizing (which stochastic driver differs between the two seed-0 runs) --", flush=True)
    bg_same = (R1['bg_count']==R2['bg_count']) and arr_equal(R1['bg_times'], R2['bg_times'])
    md_same = (R1['md_count']==R2['md_count']) and arr_equal(R1['md_times'], R2['md_times'])
    conn_same = arr_equal(R1['md2pv_ij'][0], R2['md2pv_ij'][0]) and arr_equal(R1['md2pv_ij'][1], R2['md2pv_ij'][1])
    pv_same = (R1['pv_count']==R2['pv_count']) and arr_equal(R1['pv_times'], R2['pv_times'])

    print(f"  BG_pv Poisson (500 Hz): count {R1['bg_count']} vs {R2['bg_count']}, "
          f"times {'MATCH' if bg_same else 'DIFFER <-- culprit'}", flush=True)
    print(f"  MD Poisson (5 Hz):      count {R1['md_count']} vs {R2['md_count']}, "
          f"times {'MATCH' if md_same else 'DIFFER <-- culprit'}", flush=True)
    print(f"  MD->PV connectivity:    {R1['md2pv_n']} vs {R2['md2pv_n']} conns, "
          f"pairs {'MATCH' if conn_same else 'DIFFER <-- culprit'}", flush=True)
    print(f"  PV spike train:         {'MATCH' if pv_same else 'DIFFER (symptom)'}", flush=True)

    print("\nConclusion:", flush=True)
    for name, same in [('BG_pv Poisson', bg_same), ('MD Poisson', md_same),
                       ('MD->PV connectivity', conn_same)]:
        if not same:
            print(f"  -> {name} is NOT reproducible across same-seed builds. Root cause located here.", flush=True)
    if bg_same and md_same and conn_same and not pv_same:
        print("  -> All inputs reproduce but PV spikes differ: points to PV internal state / "
              "numerical path, not the stochastic inputs. Needs deeper look.", flush=True)
    if pv_same:
        print("  -> PV also reproduced here: the non-determinism did NOT reproduce in this "
              "isolated two-build test; difference may need the full 4-seed loop context.", flush=True)
