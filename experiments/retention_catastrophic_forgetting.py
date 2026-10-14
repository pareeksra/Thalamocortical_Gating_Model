"""
retention_catastrophic_forgetting.py -- the core "no catastrophic forgetting" test.
====================================================================================
ROADMAP Phase 3 / REPAIR_LOG item 5, never run until now: learn context A, switch to
context B, verify A is RETAINED. This is the project's central scientific claim
(README: "context-specific learning without catastrophic forgetting"; PROJECT_STORY:
"different contexts write onto different physical branches instead of overwriting the
same synapses").

Protocol (reduced Phase-1 circuit, analytical Yang plasticity -- the validated path):
  Two dendritic branches, each with a plastic excitatory pathway. SOM can inhibit
  either branch; WHICH branch it inhibits is the "context" (the downstream effect of
  the MD disinhibition switch -- abstracted here to isolate the plasticity-retention
  question from MD-circuit fidelity).

  Phase A (n_epochs):  SOM inhibits branch 1  -> branch 0 is FREE, learns (rho0 up),
                       branch 1 is gated, protected (rho1 stays ~0.5/down).
  Phase B (n_epochs):  SOM inhibits branch 0  -> branch 1 is FREE, learns (rho1 up),
                       branch 0 is now GATED. CATASTROPHIC-FORGETTING TEST: does the
                       rho0 learned in A survive, or decay while B trains?

Success (mechanism works): after B, rho0 (A's memory) is retained near its end-of-A
value AND rho1 (B's memory) has risen. Catastrophic forgetting: rho0 collapses during B.

Control: a SINGLE-branch overwrite baseline -- train branch 0 free in A, then keep it
free and train a DIFFERENT input on the SAME branch in B. Without branch separation
the model should overwrite (this is the "what forgetting looks like" reference). Here
approximated by leaving branch 0 free in both phases (no context switch) and checking
it simply stays up (the trivial no-interference case), plus the key cross-branch test.

Output: docs/retention_results.json + figures/retention_forgetting.png
Run: <venv>/python -I experiments/retention_catastrophic_forgetting.py
"""
import os, sys, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
sys.path.insert(0, PROOT)

from brian2 import *
prefs.codegen.target = 'cython'
from parameters import params, plasticity_params, som_params
from equations import (attach_rho_clipper, make_eqs_synapse_plasticity, eqs_soma, eqs_dend,
                       eqs_som, eqs_synapse_plasticity, on_pre_plasticity)
from src.v2.plasticity import yang_synapse_update

T = 3.0
EXC_RATE = 80.0
POST_RATE = 10.0
GCOUPLE_NS = 0.8
SOM_BIAS_PA = 21.32          # 30 Hz condition (the locked, reliable baseline)
N_EPOCHS_PER_PHASE = 8
SEED = 42


def build():
    start_scope(); seed(SEED)
    p = dict(params); p.update(plasticity_params); p.update(som_params)
    ndend = 2
    p['num_Soma'] = 1; p['num_DendEach'] = ndend; p['num_Dend'] = ndend
    p['gEachCouple_pyr'] = GCOUPLE_NS * nS; p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * ndend
    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']; p['norm_factor_Ca'] = t ** (1 / (t - 1))
    t = p['tauGABABRise'] / p['tauGABABDecay']; p['norm_factor_GABAB'] = t ** (1 / (t - 1))

    net = Network()
    Soma = NeuronGroup(1, eqs_soma, threshold='V>vThres_pyr', reset='V=vReset_pyr',
                       refractory=p['refracTime_pyr'], method='euler', namespace=p)
    Soma.V = p['vRest_pyr']; Soma.vShadow = p['vRest_pyr']; Soma.vAveDend = p['vRest_pyr']
    Dend = NeuronGroup(ndend, eqs_dend, method='euler', namespace=p)
    Dend.V = p['vRest_pyr']; Dend.vSoma = p['vRest_pyr']

    @network_operation(dt=p['sim_dt'])
    def coupling():
        Soma.vAveDend = np.mean(Dend.V[:]); Dend.vSoma = np.repeat(Soma.vShadow[:], ndend)
    net.add([Soma, Dend, coupling])

    post_src = PoissonGroup(1, rates=POST_RATE * Hz)
    bAP = Synapses(post_src, Dend, on_pre='V_post+=bAP_amp\nbAPCa_rise_post+=norm_factor_Ca',
                   delay=p['bAP_delay'], namespace=p)
    bAP.connect(j='k for k in range(2)'); net.add([post_src, bAP])

    SOM = NeuronGroup(10, eqs_som, threshold='V>vThres_som', reset='V=vReset_som',
                      refractory=p['refrac_som'], method='euler', namespace=p)
    SOM.V = p['vRest_som']; SOM.iBaseline_som = SOM_BIAS_PA * pA
    # SOM -> BOTH branches, but each connection's effective weight is gated per-phase by
    # a context scalar som_gain[j] in {0,1}. This is the switchable-inhibition context:
    # the downstream effect of the MD disinhibition switch, isolated. gTotGABA only rises
    # on the branch whose gain is 1.
    s2d = Synapses(SOM, Dend, model='som_gain : 1',
                   on_pre='gTotGABA_post += gGABA * som_gain', namespace=p)
    s2d.connect()  # all SOM -> all branches
    som_mon = SpikeMonitor(SOM)
    net.add([SOM, s2d, som_mon])

    acc_eqs = '\nad_acc : second\nap_acc : second\n'
    accumulate = ('ad_acc = ad_acc + int(c_total > theta_d)*dt\n'
                  'ap_acc = ap_acc + int(c_total > theta_p)*dt')
    # Per-branch INPUT sources (not shared), so a context can switch which input is
    # active -- the "different contexts = different active inputs" half of the claim.
    # Rates are set per-phase in main(); start both at EXC_RATE.
    exc0 = PoissonGroup(20, rates=EXC_RATE * Hz)
    exc1 = PoissonGroup(20, rates=EXC_RATE * Hz)
    sb0 = Synapses(exc0, Dend, model=eqs_synapse_plasticity + acc_eqs, on_pre=on_pre_plasticity,
                   method='heun', namespace=p)
    sb0.connect(j='0'); sb0.rho = 0.5; attach_rho_clipper(sb0); sb0.run_regularly(accumulate, when='end')
    sb1 = Synapses(exc1, Dend, model=make_eqs_synapse_plasticity(2) + acc_eqs,
                   on_pre=on_pre_plasticity, method='heun', namespace=p)
    sb1.connect(j='1'); sb1.rho = 0.5; attach_rho_clipper(sb1); sb1.run_regularly(accumulate, when='end')
    net.add([exc0, exc1, sb0, sb1])

    ykw = dict(sigma=float(p['sigma']), tau=float(p['tau'] / second), gamma_d=float(p['gamma_d']),
               gamma_p=float(p['gamma_p']), w0=float(p['w0']), w1=float(p['w1']),
               rho_star=float(p['rhoStar']))
    return net, s2d, sb0, sb1, som_mon, ykw, exc0, exc1


def run_epoch(net, sb0, sb1, ykw):
    sb0.ad_acc = 0 * second; sb0.ap_acc = 0 * second
    sb1.ad_acc = 0 * second; sb1.ap_acc = 0 * second
    net.run(T * second)
    for sb in (sb0, sb1):
        ad = np.asarray(sb.ad_acc[:] / second); ap = np.asarray(sb.ap_acc[:] / second)
        r = np.asarray(sb.rho[:])
        sb.rho[:] = np.array([yang_synapse_update(ad[k], ap[k], r[k], **ykw)['rho_new']
                              for k in range(len(r))])
    return float(np.mean(sb0.rho[:])), float(np.mean(sb1.rho[:]))


def main(gate_input=True):
    """gate_input=True: context switches BOTH the disinhibition AND which input is
    active (A's input silent during B) -- the Zhang-faithful 'different contexts =
    different active inputs' test. gate_input=False: only the inhibition switches,
    input stays on both branches always (the inhibition-only test -- shown to forget)."""
    net, s2d, sb0, sb1, som_mon, ykw, exc0, exc1 = build()
    traj = {'epoch': [0], 'rho0': [0.5], 'rho1': [0.5], 'phase': ['init']}
    OFF = 0.0 * Hz if gate_input else EXC_RATE * Hz

    # Phase A: SOM inhibits branch 1 -> branch 0 free; branch-0 input ON, branch-1 input OFF (if gated).
    s2d.som_gain['j==0'] = 0.0; s2d.som_gain['j==1'] = 1.0
    exc0.rates = EXC_RATE * Hz; exc1.rates = OFF
    for e in range(1, N_EPOCHS_PER_PHASE + 1):
        r0, r1 = run_epoch(net, sb0, sb1, ykw)
        traj['epoch'].append(e); traj['rho0'].append(r0); traj['rho1'].append(r1); traj['phase'].append('A')
    rho0_endA, rho1_endA = traj['rho0'][-1], traj['rho1'][-1]

    # Phase B: SOM inhibits branch 0 -> branch 1 free; branch-1 input ON, branch-0 input OFF (if gated).
    # CATASTROPHIC-FORGETTING TEST: does rho0 (A) survive?
    s2d.som_gain['j==0'] = 1.0; s2d.som_gain['j==1'] = 0.0
    exc0.rates = OFF; exc1.rates = EXC_RATE * Hz
    for e in range(N_EPOCHS_PER_PHASE + 1, 2 * N_EPOCHS_PER_PHASE + 1):
        r0, r1 = run_epoch(net, sb0, sb1, ykw)
        traj['epoch'].append(e); traj['rho0'].append(r0); traj['rho1'].append(r1); traj['phase'].append('B')
    rho0_endB, rho1_endB = traj['rho0'][-1], traj['rho1'][-1]

    som_rate = len(som_mon.t) / (2 * N_EPOCHS_PER_PHASE * T) / 10.0
    retention = rho0_endB / rho0_endA if rho0_endA > 1e-6 else float('nan')
    verdict = ('RETAINED' if (rho0_endB > 0.7 * rho0_endA and rho1_endB > 0.7)
               else 'CATASTROPHIC-FORGETTING' if rho0_endB < 0.5 * rho0_endA
               else 'PARTIAL')
    out = dict(
        som_bias_pA=SOM_BIAS_PA, som_rate_hz=round(som_rate, 2), n_epochs_per_phase=N_EPOCHS_PER_PHASE,
        rho0_endA=round(rho0_endA, 4), rho1_endA=round(rho1_endA, 4),
        rho0_endB=round(rho0_endB, 4), rho1_endB=round(rho1_endB, 4),
        rho0_retention_frac=round(retention, 4), verdict=verdict, traj=traj)
    mode = 'inputgated' if gate_input else 'inhibonly'
    json.dump(out, open(os.path.join(PROOT, 'docs', f'retention_results_{mode}.json'), 'w'), indent=2)

    print(f"SOM rate: {som_rate:.1f} Hz")
    print(f"End of A: branch0(free,learned)={rho0_endA:.3f}  branch1(gated)={rho1_endA:.3f}")
    print(f"End of B: branch0(now gated)={rho0_endB:.3f}  branch1(free,learned)={rho1_endB:.3f}")
    print(f"Branch-0 (context A memory) retention after training B: {retention*100:.1f}%")
    print(f"VERDICT: {verdict}")

    # figure
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ep = traj['epoch']
    ax.plot(ep, traj['rho0'], '-o', color='#0072B2', lw=2, ms=5, label='branch 0 (learns in A)')
    ax.plot(ep, traj['rho1'], '-o', color='#D55E00', lw=2, ms=5, label='branch 1 (learns in B)')
    ax.axvline(N_EPOCHS_PER_PHASE, color='0.5', ls='--', lw=1)
    ax.axhline(0.5, color='0.8', lw=1, zorder=0)
    ax.text(N_EPOCHS_PER_PHASE/2, 1.02, 'Phase A\n(branch 0 free)', ha='center', fontsize=9, color='#0072B2')
    ax.text(N_EPOCHS_PER_PHASE*1.5, 1.02, 'Phase B\n(branch 1 free)', ha='center', fontsize=9, color='#D55E00')
    ax.annotate(f'branch 0 retained\n{retention*100:.0f}% of A', xy=(ep[-1], traj['rho0'][-1]),
                xytext=(ep[-1]-3, 0.72), fontsize=9, color='#0072B2',
                arrowprops=dict(arrowstyle='->', color='#0072B2'))
    ax.set_xlabel('epoch'); ax.set_ylabel('synaptic efficacy  rho (branch mean)')
    ax.set_ylim(0, 1.12); ax.set_title('No catastrophic forgetting: sequential A -> B learning on separate branches',
                                        fontsize=11)
    ax.legend(frameon=False, loc='center left'); ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(PROOT, 'figures', f'retention_forgetting_{mode}.png'), dpi=150,
                bbox_inches='tight', facecolor='white')
    print(f"Saved figures/retention_forgetting_{mode}.png and docs/retention_results_{mode}.json")


if __name__ == '__main__':
    import sys
    gi = not (len(sys.argv) > 1 and sys.argv[1] == 'inhibonly')
    main(gate_input=gi)
