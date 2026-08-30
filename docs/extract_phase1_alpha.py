"""
extract_phase1_alpha.py  --  Step 2a helper (formula-comparison diagnostic)
===========================================================================
Runs Phase-1's EXACT reduced circuit (Soma + 2 dendritic branches + 10 SOM
cells inhibiting branch 0 only) and measures the calcium-threshold-crossing
times that the analytical Yang plasticity rule consumes:

    alpha_d = total time the synaptic calcium trace c_total spends above theta_d
    alpha_p = total time c_total spends above theta_p

per branch, per synapse, over the whole protocol.

This is deliberately a measurement-only script: it does NOT modify equations.py
and does NOT change plasticity. It reproduces phase1_single_neuron_gating.py's
circuit verbatim (same params, same seed, same wiring) and simply attaches
StateMonitors on ind_p / ind_d so we can read off the (alpha_d, alpha_p) that
Phase-1 actually produces. Those operating points anchor the formula sweep in
formula_comparison.py.

Output: prints a summary and writes docs/phase1_alpha_operating_points.json.
"""
import sys, os, json
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
import numpy as np
from brian2 import *
from parameters import params, plasticity_params, som_params
from equations import (attach_rho_clipper, make_eqs_synapse_plasticity, eqs_soma,
                       eqs_dend, eqs_som, eqs_synapse_plasticity, on_pre_plasticity)


def measure_alpha(T=3.0, exc_rate=80.0, post_rate=10.0, gcouple_nS=0.8,
                  som_bias_pA=25.0, seed_val=42):
    """Run Phase-1's circuit and return per-branch (alpha_d, alpha_p) in seconds.

    alpha is measured by integrating the ind_d / ind_p indicators (which are
    exactly int(c_total > theta_d) / int(c_total > theta_p) inside the plastic
    synapse equations) over time, at record_dt resolution.
    """
    start_scope()
    seed(seed_val)
    p = dict(params); p.update(plasticity_params); p.update(som_params)
    ndend = 2
    p['num_Soma'] = 1; p['num_DendEach'] = ndend; p['num_Dend'] = ndend
    p['gEachCouple_pyr'] = gcouple_nS * nS
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * ndend
    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']; p['norm_factor_Ca'] = t ** (1 / (t - 1))
    t = p['tauGABABRise'] / p['tauGABABDecay']; p['norm_factor_GABAB'] = t ** (1 / (t - 1))

    net = Network()

    Soma = NeuronGroup(1, eqs_soma, threshold='V>vThres_pyr', reset='V=vReset_pyr',
                       refractory=p['refracTime_pyr'], method='euler', namespace=p)
    Soma.V = p['vRest_pyr']; Soma.vShadow = p['vRest_pyr']; Soma.vAveDend = p['vRest_pyr']
    Dend = NeuronGroup(ndend, eqs_dend, method='euler', namespace=p)
    Dend.V = p['vRest_pyr']; Dend.vSoma = p['vRest_pyr']

    @network_operation(dt=p['sim_dt'])
    def Coupling():
        Soma.vAveDend = np.mean(Dend.V[:])
        Dend.vSoma = np.repeat(Soma.vShadow[:], ndend)
    net.add([Soma, Dend, Coupling])

    post_src = PoissonGroup(1, rates=post_rate * Hz)
    bAP = Synapses(post_src, Dend, on_pre='V_post+=bAP_amp\nbAPCa_rise_post+=norm_factor_Ca',
                   delay=p['bAP_delay'], namespace=p)
    bAP.connect(j='k for k in range(2)')
    net.add([post_src, bAP])

    SOM = NeuronGroup(10, eqs_som, threshold='V>vThres_som', reset='V=vReset_som',
                      refractory=p['refrac_som'], method='euler', namespace=p)
    SOM.V = p['vRest_som']; SOM.iBaseline_som = som_bias_pA * pA
    s2d = Synapses(SOM, Dend, on_pre='gTotGABA_post+=gGABA', namespace=p)
    s2d.connect(j='0')
    net.add([SOM, s2d])

    exc = PoissonGroup(20, rates=exc_rate * Hz)
    sb0 = Synapses(exc, Dend, model=eqs_synapse_plasticity, on_pre=on_pre_plasticity,
                   method='heun', namespace=p)
    sb0.connect(j='0'); sb0.rho = 0.5; attach_rho_clipper(sb0)
    sb1 = Synapses(exc, Dend, model=make_eqs_synapse_plasticity(2), on_pre=on_pre_plasticity,
                   method='heun', namespace=p)
    sb1.connect(j='1'); sb1.rho = 0.5; attach_rho_clipper(sb1)
    net.add([exc, sb0, sb1])

    # StateMonitor cannot record the c_total subexpression directly: it references
    # the postsynaptic bAPCa through an index that Brian2 refuses to link on a
    # Synapses monitor. Instead record the local synaptic calcium `c` (a clock-driven
    # state variable) per synapse, and the branch bAPCa on the Dend group, then
    # reconstruct c_total = c + bAPCa_branch in post-processing. This is exact:
    # eqs_synapse_plasticity defines c_total = c + bAPCa_post, and bAP is branch-uniform.
    rec_dt = p['record_dt']
    mon0 = StateMonitor(sb0, ['c'], record=True, dt=rec_dt)
    mon1 = StateMonitor(sb1, ['c'], record=True, dt=rec_dt)
    mon_bap = StateMonitor(Dend, ['bAPCa'], record=True, dt=rec_dt)
    net.add([mon0, mon1, mon_bap])

    net.run(T * second)

    dt_s = float(rec_dt / second)
    theta_p = float(p['theta_p']); theta_d = float(p['theta_d'])
    bap = np.asarray(mon_bap.bAPCa)  # shape (2, n_t): postsynaptic bAP calcium per branch

    def summarize(mon, branch_idx, label):
        c_syn = np.asarray(mon.c)             # shape (n_syn, n_t)
        c_tot = c_syn + bap[branch_idx][None, :]  # add branch bAPCa, broadcast over synapses
        ind_p = (c_tot > theta_p).astype(float)
        ind_d = (c_tot > theta_d).astype(float)
        alpha_p = ind_p.sum(axis=1) * dt_s   # per-synapse seconds above theta_p
        alpha_d = ind_d.sum(axis=1) * dt_s
        return {
            'branch': label,
            'n_syn': int(ind_p.shape[0]),
            'alpha_p_mean': float(alpha_p.mean()),
            'alpha_p_std': float(alpha_p.std()),
            'alpha_p_min': float(alpha_p.min()),
            'alpha_p_max': float(alpha_p.max()),
            'alpha_d_mean': float(alpha_d.mean()),
            'alpha_d_std': float(alpha_d.std()),
            'alpha_d_min': float(alpha_d.min()),
            'alpha_d_max': float(alpha_d.max()),
            'c_total_mean': float(c_tot.mean()),
            'c_total_max': float(c_tot.max()),
        }

    return {
        'protocol': dict(T=T, exc_rate=exc_rate, post_rate=post_rate,
                         gcouple_nS=gcouple_nS, som_bias_pA=som_bias_pA, seed=seed_val),
        'theta_d': float(p['theta_d']), 'theta_p': float(p['theta_p']),
        'inhibited_branch0': summarize(mon0, 0, 'inhibited (branch 0)'),
        'free_branch1': summarize(mon1, 1, 'free (branch 1)'),
    }


if __name__ == '__main__':
    prefs.codegen.target = 'numpy'   # avoid C++ compile dependency; slower but portable
    res = measure_alpha()
    b0 = res['inhibited_branch0']; b1 = res['free_branch1']
    print("=== Phase-1 alpha operating points (exc=80 Hz, post=10 Hz, g_c=0.8 nS, seed 42) ===")
    print(f"theta_d={res['theta_d']}  theta_p={res['theta_p']}  T={res['protocol']['T']} s")
    for b in (b0, b1):
        print(f"\n{b['branch']}  (n_syn={b['n_syn']})")
        print(f"  alpha_p = {b['alpha_p_mean']:.4f} +/- {b['alpha_p_std']:.4f} s "
              f"(min {b['alpha_p_min']:.4f}, max {b['alpha_p_max']:.4f})")
        print(f"  alpha_d = {b['alpha_d_mean']:.4f} +/- {b['alpha_d_std']:.4f} s "
              f"(min {b['alpha_d_min']:.4f}, max {b['alpha_d_max']:.4f})")
        print(f"  c_total: mean {b['c_total_mean']:.3f}, max {b['c_total_max']:.3f}")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'phase1_alpha_operating_points.json')
    with open(out, 'w') as f:
        json.dump(res, f, indent=2)
    print(f"\nWrote {out}")
