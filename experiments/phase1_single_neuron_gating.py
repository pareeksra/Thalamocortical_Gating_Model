"""
phase1_single_neuron_gating.py
==============================
Phase 1 of the roadmap: make ONE pyramidal neuron with two branches gate correctly ---
the disinhibited branch potentiates (LTP), the SOM-inhibited branch does not.

This is a self-contained experiment (it does not modify parameters.py or validate_model.py).
It implements Yang et al. (2016)'s plasticity protocol faithfully:

  * dendrite-soma coupling at Yang's IN-VIVO value g_c = 0.8 nS (parameters.py already
    defines gEachCouple_pyr_vivo = 0.8 nS but the experiments used 4.0 nS, which drove
    the soma to ~201 Hz and produced a branch-UNIFORM bAP calcium transient that swamped
    the inhibition-selective NMDA calcium -- see ROADMAP.md / diagnosis);
  * post-synaptic (somatic) spiking fixed at ~10 Hz by an external source, exactly as
    Yang fixes the post rate at 10 Hz, so the bAP calcium is a small constant background
    rather than a swamp;
  * excitatory pathway drive at 80 Hz (see __main__), which with 0.8 nS coupling puts
    the free branch's NMDA calcium above theta_p while the inhibited branch stays below
    theta_d. (Historically 120 Hz was quoted here; the committed run uses 80 Hz and passes.)

Measured gating window (from the calcium-component diagnostic): with bAP background
B = post_rate * 36.4 ms, the free branch crosses theta_p once post_rate > 7.6 Hz and the
inhibited branch stays below theta_d while post_rate < 25 Hz. Yang's 10 Hz sits inside it.
"""
import sys, os
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
import numpy as np
from brian2 import *
from parameters import params, plasticity_params, som_params
from equations import (attach_rho_clipper, make_eqs_synapse_plasticity, eqs_soma, eqs_dend,
                       eqs_som, eqs_synapse_plasticity, on_pre_plasticity)


def run_gating(T=3.0, exc_rate=120.0, post_rate=10.0, gcouple_nS=0.8,
               som_bias_pA=25.0, seed_val=42):
    seed(seed_val)
    p = dict(params); p.update(plasticity_params); p.update(som_params)
    ndend = 2
    p['num_Soma'] = 1; p['num_DendEach'] = ndend; p['num_Dend'] = ndend
    p['gEachCouple_pyr'] = gcouple_nS * nS                 # Yang in-vivo coupling
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * ndend
    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']; p['norm_factor_Ca'] = t ** (1 / (t - 1))
    t = p['tauGABABRise'] / p['tauGABABDecay']; p['norm_factor_GABAB'] = t ** (1 / (t - 1))

    net = Network()

    # -- Pyramidal soma + 2 dendritic branches --------------------
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

    # -- Post-synaptic spike train FIXED at post_rate (Yang's protocol) --------
    # A Poisson "post" source drives the branch-uniform bAP calcium transient. This
    # replaces letting a runaway soma set the post rate. Both branches receive it equally
    # (bAP is branch-uniform in this model), exactly as before -- only the RATE is now
    # controlled and in-regime.
    post_src = PoissonGroup(1, rates=post_rate * Hz)
    bAP = Synapses(post_src, Dend, on_pre='V_post+=bAP_amp\nbAPCa_rise_post+=norm_factor_Ca',
                   delay=p['bAP_delay'], namespace=p)
    bAP.connect(j='k for k in range(2)')
    net.add([post_src, bAP])

    # -- SOM inhibition onto branch 0 only ------------------------
    SOM = NeuronGroup(10, eqs_som, threshold='V>vThres_som', reset='V=vReset_som',
                      refractory=p['refrac_som'], method='euler', namespace=p)
    SOM.V = p['vRest_som']; SOM.iBaseline_som = som_bias_pA * pA
    s2d = Synapses(SOM, Dend, on_pre='gTotGABA_post+=gGABA', namespace=p)
    s2d.connect(j='0')                                     # ALL SOM -> branch 0 only
    net.add([SOM, s2d])

    # -- Plastic excitatory pathway onto each branch --------------
    exc = PoissonGroup(20, rates=exc_rate * Hz)
    sb0 = Synapses(exc, Dend, model=eqs_synapse_plasticity, on_pre=on_pre_plasticity,
                   method='heun', namespace=p)
    sb0.connect(j='0'); sb0.rho = 0.5; attach_rho_clipper(sb0)
    sb1 = Synapses(exc, Dend, model=make_eqs_synapse_plasticity(2), on_pre=on_pre_plasticity,
                   method='heun', namespace=p)
    sb1.connect(j='1'); sb1.rho = 0.5; attach_rho_clipper(sb1)
    net.add([exc, sb0, sb1])

    net.run(T * second)

    w0 = float(np.mean(sb0.w[:])); w1 = float(np.mean(sb1.w[:]))
    r0 = float(np.mean(sb0.rho[:])); r1 = float(np.mean(sb1.rho[:]))
    ratio = w1 / w0 if w0 > 1e-6 else float('inf')
    print(f"  post_rate={post_rate} Hz  exc={exc_rate} Hz  coupling={gcouple_nS} nS")
    print(f"  Branch 0 (INHIBITED):   rho={r0:.3f}  w={w0:.3f}")
    print(f"  Branch 1 (FREE):        rho={r1:.3f}  w={w1:.3f}")
    print(f"  Ratio (free/inhibited): {ratio:.2f}   (LTP on free, no-change/LTD on inhibited)")
    gated = (r1 > 0.65) and (r0 < 0.55) and (ratio >= 1.5)
    print(f"  BRANCH-SPECIFIC GATING: {'PASS' if gated else 'FAIL'}")
    return dict(r0=r0, r1=r1, w0=w0, w1=w1, ratio=ratio, gated=gated)


if __name__ == '__main__':
    print("=== Phase 1: single-neuron branch-specific gating (Yang protocol) ===")
    print("=== integrated-NMDA-current calcium (Bug 2 fixed); Yang-realistic 80 Hz drive ===")
    for er, pr in [(80.0, 10.0), (80.0, 0.0)]:
        run_gating(exc_rate=er, post_rate=pr)
        print()
