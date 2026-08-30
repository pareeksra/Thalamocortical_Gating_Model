"""
phase1_analytical.py  --  Step 2b/2c
====================================
Phase-1 single-neuron branch-specific gating, driven by the ANALYTICAL Yang 2016
epoch plasticity (Eqs. 32-35, src/v2/plasticity.py) instead of the superseded
continuous drho/dt ODE (now commented out in model/equations.py).

Pipeline (Model A's plasticity, refactored):
  Build the Phase-1 reduced circuit ONCE (Soma + 2 dendritic branches + 10 SOM
  cells inhibiting branch 0 only). rho is a held parameter. Then, per epoch:
    1. net.run(T)  -- calcium accumulates at the current (fixed) weights.
    2. Read the epoch's calcium trace c_total = c + bAPCa from StateMonitors.
    3. alpha_d = time c_total > theta_d, alpha_p = time c_total > theta_p, per synapse.
    4. rho_new = yang_synapse_update(alpha_d, alpha_p, rho_current)  (per synapse).
    5. Write rho_new back into the Brian 2 synapse; w = w0+(w1-w0)*rho updates.
  Repeat for N epochs so plasticity compounds across epochs.

Outputs the epoch-by-epoch rho trajectory (both branches) to
figures/analytical_plasticity_trajectory.png and prints final rho / ratio.
"""
import sys, os, json
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(PROOT, 'docs', 'phase1_analytical_state.json')
sys.path.insert(0, os.path.join(PROOT, 'model'))
sys.path.insert(0, PROOT)
import numpy as np
from brian2 import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from parameters import params, plasticity_params, som_params
from equations import (attach_rho_clipper, make_eqs_synapse_plasticity, eqs_soma,
                       eqs_dend, eqs_som, eqs_synapse_plasticity, on_pre_plasticity)
from src.v2.plasticity import yang_synapse_update, alpha_above_threshold


def run_gating_analytical(n_epochs=20, T=3.0, exc_rate=80.0, post_rate=10.0,
                          gcouple_nS=0.8, som_bias_pA=25.0, gGABA_nS=None, seed_val=42,
                          verbose=True, resume=True, run_tag=''):
    prefs.codegen.target = 'cython'   # cached compile; ~10x faster than numpy target here
    start_scope()
    seed(seed_val)
    p = dict(params); p.update(plasticity_params); p.update(som_params)
    ndend = 2
    p['num_Soma'] = 1; p['num_DendEach'] = ndend; p['num_Dend'] = ndend
    p['gEachCouple_pyr'] = gcouple_nS * nS
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * ndend
    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']; p['norm_factor_Ca'] = t ** (1 / (t - 1))
    t = p['tauGABABRise'] / p['tauGABABDecay']; p['norm_factor_GABAB'] = t ** (1 / (t - 1))

    if gGABA_nS is not None:
        p['gGABA'] = gGABA_nS * nS   # SOM->dendrite per-synapse GABA conductance override
    state_path = STATE_PATH if not run_tag else STATE_PATH.replace('.json', f'_{run_tag}.json')

    theta_d = float(p['theta_d']); theta_p = float(p['theta_p'])
    # Analytical-update parameters (Yang published values, from plasticity_params).
    ykw = dict(sigma=float(p['sigma']), tau=float(p['tau'] / second),
               gamma_d=float(p['gamma_d']), gamma_p=float(p['gamma_p']),
               w0=float(p['w0']), w1=float(p['w1']), rho_star=float(p['rhoStar']))

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
    som_spikes = SpikeMonitor(SOM)   # to confirm the actual SOM firing rate
    net.add([SOM, s2d, som_spikes])

    exc = PoissonGroup(20, rates=exc_rate * Hz)
    # rho is a parameter now; method can be 'euler' (no stochastic term remains) but
    # 'heun' is kept for parity -- both integrate the deterministic calcium ODEs fine.
    #
    # alpha_d / alpha_p (time c_total spends above each threshold) are accumulated per
    # synapse in COMPILED run_regularly counters, reset each epoch. This replaces a
    # StateMonitor: it is O(1) memory (no growing trace) and integrates at the full
    # sim_dt = 0.02 ms rather than the coarser record_dt, so the alpha estimate is if
    # anything more accurate. c_total = c + bAPCa_post is evaluated inline with correct
    # postsynaptic indexing inside the generated code.
    acc_eqs = '\nad_acc : second\nap_acc : second\n'
    accumulate = ('ad_acc = ad_acc + int(c_total > theta_d)*dt\n'
                  'ap_acc = ap_acc + int(c_total > theta_p)*dt')
    sb0 = Synapses(exc, Dend, model=eqs_synapse_plasticity + acc_eqs,
                   on_pre=on_pre_plasticity, method='heun', namespace=p)
    sb0.connect(j='0'); sb0.rho = 0.5; attach_rho_clipper(sb0)
    sb0.run_regularly(accumulate, when='end')
    sb1 = Synapses(exc, Dend, model=make_eqs_synapse_plasticity(2) + acc_eqs,
                   on_pre=on_pre_plasticity, method='heun', namespace=p)
    sb1.connect(j='1'); sb1.rho = 0.5; attach_rho_clipper(sb1)
    sb1.run_regularly(accumulate, when='end')
    net.add([exc, sb0, sb1])

    # trajectory records: rho mean/std per branch, per epoch (epoch 0 = initial 0.5).
    # Checkpoint/auto-resume: because each 3 s epoch is ~74 s of wall-clock (dominated by
    # the Python soma-dendrite Coupling network_operation) and a single process is capped
    # by the run harness, state is written to STATE_PATH after every epoch and reloaded on
    # the next invocation. This makes the multi-epoch run robust to being interrupted and
    # lets the trajectory advance across calls. Resume restarts calcium/voltage from rest
    # for the first epoch of each chunk -- a <5% transient on that one epoch's alpha
    # (tau_Ca=30 ms vs 3000 ms epoch), noted for honesty; rho itself carries over exactly.
    start_epoch = 1
    traj = {'epoch': [0], 'rho0_mean': [0.5], 'rho1_mean': [0.5],
            'rho0_std': [0.0], 'rho1_std': [0.0],
            'ad0': [np.nan], 'ap0': [np.nan], 'ad1': [np.nan], 'ap1': [np.nan]}
    if resume and os.path.exists(state_path):
        with open(state_path) as f:
            st = json.load(f)
        if int(st.get('target', -1)) == n_epochs and int(st['epochs_done']) < n_epochs:
            sb0.rho[:] = np.asarray(st['rho0_syn'])
            sb1.rho[:] = np.asarray(st['rho1_syn'])
            traj = st['traj']
            start_epoch = int(st['epochs_done']) + 1
            if verbose:
                print(f"[resume] {st['epochs_done']}/{n_epochs} epochs done; "
                      f"free rho={traj['rho1_mean'][-1]:.3f} inhib rho={traj['rho0_mean'][-1]:.3f}")

    for e in range(start_epoch, n_epochs + 1):
        sb0.ad_acc = 0 * second; sb0.ap_acc = 0 * second
        sb1.ad_acc = 0 * second; sb1.ap_acc = 0 * second
        net.run(T * second)

        # per-synapse alpha (seconds) accumulated over THIS epoch
        ad0 = np.asarray(sb0.ad_acc[:] / second); ap0 = np.asarray(sb0.ap_acc[:] / second)
        ad1 = np.asarray(sb1.ad_acc[:] / second); ap1 = np.asarray(sb1.ap_acc[:] / second)

        # analytical per-synapse update, writing rho back into Brian 2
        r0 = np.asarray(sb0.rho[:]); r1 = np.asarray(sb1.rho[:])
        r0_new = np.array([yang_synapse_update(ad0[k], ap0[k], r0[k], **ykw)['rho_new']
                           for k in range(len(r0))])
        r1_new = np.array([yang_synapse_update(ad1[k], ap1[k], r1[k], **ykw)['rho_new']
                           for k in range(len(r1))])
        sb0.rho[:] = r0_new
        sb1.rho[:] = r1_new

        traj['epoch'].append(e)
        traj['rho0_mean'].append(float(r0_new.mean())); traj['rho0_std'].append(float(r0_new.std()))
        traj['rho1_mean'].append(float(r1_new.mean())); traj['rho1_std'].append(float(r1_new.std()))
        traj['ad0'].append(float(ad0.mean())); traj['ap0'].append(float(ap0.mean()))
        traj['ad1'].append(float(ad1.mean())); traj['ap1'].append(float(ap1.mean()))
        # checkpoint after every epoch so an interrupted run can resume exactly
        with open(state_path, 'w') as f:
            json.dump({'epochs_done': e, 'target': n_epochs, 'T': T,
                       'rho0_syn': r0_new.tolist(), 'rho1_syn': r1_new.tolist(),
                       'traj': traj}, f)
        if verbose:
            print(f"epoch {e:2d}: INHIB rho={r0_new.mean():.3f} (ad={ad0.mean():.2f} ap={ap0.mean():.2f}) | "
                  f"FREE rho={r1_new.mean():.3f} (ad={ad1.mean():.2f} ap={ap1.mean():.2f})", flush=True)

    r0f = traj['rho0_mean'][-1]; r1f = traj['rho1_mean'][-1]
    w0f = ykw['w0'] + (ykw['w1'] - ykw['w0']) * r0f
    w1f = ykw['w0'] + (ykw['w1'] - ykw['w0']) * r1f
    ratio = r1f / r0f if r0f > 1e-6 else float('inf')
    epochs_run = max(0, n_epochs - start_epoch + 1)
    som_rate = (som_spikes.num_spikes / (len(SOM) * epochs_run * T)) if epochs_run > 0 else float('nan')
    return dict(traj=traj, rho0=r0f, rho1=r1f, w0=w0f, w1=w1f, ratio=ratio,
                n_epochs=n_epochs, T=T, som_rate_hz=som_rate,
                som_bias_pA=som_bias_pA, gGABA_nS=(gGABA_nS if gGABA_nS is not None else 4.0))


def make_trajectory_figure(res, figpath):
    tj = res['traj']
    ep = np.array(tj['epoch'])
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))

    ax[0].errorbar(ep, tj['rho1_mean'], yerr=tj['rho1_std'], marker='o', lw=2,
                   capsize=2, label='free (branch 1)', color='C1')
    ax[0].errorbar(ep, tj['rho0_mean'], yerr=tj['rho0_std'], marker='s', lw=2,
                   capsize=2, label='inhibited (branch 0)', color='C0')
    ax[0].axhline(0.5, color='k', ls=':', lw=1, label='rho* = 0.5 (barrier)')
    ax[0].axhline(0.7, color='green', ls='--', lw=1, alpha=0.6, label='pass line (0.7)')
    ax[0].set_xlabel('epoch (3 s each)'); ax[0].set_ylabel('rho (mean +/- SD over 20 synapses)')
    ax[0].set_title('Analytical Yang plasticity: rho trajectory')
    ax[0].set_ylim(0, 1); ax[0].legend(fontsize=8)

    ax[1].plot(ep[1:], tj['ap1'][1:], marker='o', label='free alpha_p', color='C1')
    ax[1].plot(ep[1:], tj['ad1'][1:], marker='^', ls='--', label='free alpha_d', color='C1', alpha=0.6)
    ax[1].plot(ep[1:], tj['ap0'][1:], marker='s', label='inhib alpha_p', color='C0')
    ax[1].plot(ep[1:], tj['ad0'][1:], marker='v', ls='--', label='inhib alpha_d', color='C0', alpha=0.6)
    ax[1].set_xlabel('epoch'); ax[1].set_ylabel('alpha (s above threshold)')
    ax[1].set_title('Calcium threshold-crossing time per epoch')
    ax[1].legend(fontsize=8)

    fig.suptitle(f"Phase-1 analytical plasticity  |  final: free rho={res['rho1']:.3f}, "
                 f"inhib rho={res['rho0']:.3f}, ratio={res['ratio']:.2f}", fontsize=11)
    fig.tight_layout()
    fig.savefig(figpath, dpi=130)


if __name__ == '__main__':
    # usage: phase1_analytical.py [n_epochs] [som_bias_pA] [tag] [gGABA_nS]
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    som_bias = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0
    tag = sys.argv[3] if len(sys.argv) > 3 else ''
    gGABA = float(sys.argv[4]) if len(sys.argv) > 4 else None
    print(f"=== Phase 1 ANALYTICAL (Yang 2016 Eqs. 32-35): {N} epochs x 3 s "
          f"(exc=80 Hz, post=10 Hz, g_c=0.8 nS, SOM_bias={som_bias} pA, "
          f"gGABA={'default 4.0' if gGABA is None else gGABA} nS, seed 42) ===")
    res = run_gating_analytical(n_epochs=N, som_bias_pA=som_bias, gGABA_nS=gGABA, run_tag=tag)
    figdir = os.path.join(PROOT, 'figures')
    os.makedirs(figdir, exist_ok=True)
    figname = 'analytical_plasticity_trajectory' + (f'_{tag}' if tag else '') + '.png'
    figpath = os.path.join(figdir, figname)
    make_trajectory_figure(res, figpath)

    print("\n--- Final ---")
    print(f"  SOM firing rate:      {res['som_rate_hz']:.2f} Hz  (bias {res['som_bias_pA']} pA, "
          f"gGABA {res['gGABA_nS']} nS)")
    print(f"  Free branch (1):      rho={res['rho1']:.3f}  w={res['w1']:.3f}  "
          f"(final alpha_p={res['traj']['ap1'][-1]:.2f} alpha_d={res['traj']['ad1'][-1]:.2f})")
    print(f"  Inhibited branch (0): rho={res['rho0']:.3f}  w={res['w0']:.3f}  "
          f"(final alpha_p={res['traj']['ap0'][-1]:.2f} alpha_d={res['traj']['ad0'][-1]:.2f})")
    print(f"  Ratio (free/inhib):   {res['ratio']:.2f}")
    free_pass = res['rho1'] > 0.7
    inhib_pass = res['rho0'] <= 0.5
    print(f"  PASS criteria: free rho>0.7 -> {free_pass} ; inhibited rho<=0.5 -> {inhib_pass}")
    print(f"  STEP 2d: {'PASS' if (free_pass and inhib_pass) else 'FAIL'}")
    print(f"  Wrote {figpath}")
    print(f"  Wrote {figpath}")
