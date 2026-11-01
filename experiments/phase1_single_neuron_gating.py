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

2026-11-01 (audit Problem 5): this script used to build the circuit, do ONE net.run()
and read rho back. Since the continuous drho/dt ODE was retired (rho is now a held
parameter updated per epoch by src/v2/plasticity.py), that path always returned
rho = 0.5 on both branches -> ratio 1.0 -> FAIL, i.e. the "headline result" script was
silently broken. run_gating() is now a thin wrapper around the canonical analytical
epoch runner (experiments/phase1_analytical.run_gating_analytical) with the same
protocol, so it measures real plasticity again.
"""

import sys, os
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'experiments'))
from phase1_analytical import run_gating_analytical


def run_gating(T=3.0, exc_rate=80.0, post_rate=10.0, gcouple_nS=0.8,
               som_bias_pA=21.32, seed_val=42, n_epochs=15, som_phase='random', verbose=True):
    """Branch-specific gating under the analytical Yang plasticity (n_epochs x T s)."""
    r = run_gating_analytical(n_epochs=n_epochs, T=T, exc_rate=exc_rate, post_rate=post_rate,
                              gcouple_nS=gcouple_nS, som_bias_pA=som_bias_pA, seed_val=seed_val,
                              verbose=False, resume=False,
                              run_tag=f'p1gating_{exc_rate:g}_{post_rate:g}_{seed_val}',
                              som_phase=som_phase)
    try:
        os.remove(os.path.join(PROOT, 'docs',
                               f'phase1_analytical_state_p1gating_{exc_rate:g}_{post_rate:g}_{seed_val}.json'))
    except OSError:
        pass
    r0, r1, ratio = r['rho0'], r['rho1'], r['ratio']
    gated = (r1 > 0.65) and (r0 < 0.5) and (ratio >= 2.0)
    if verbose:
        print(f"  post_rate={post_rate} Hz  exc={exc_rate} Hz  coupling={gcouple_nS} nS  "
              f"SOM {r['som_rate_hz']:.1f} Hz ({som_phase})  {n_epochs} epochs")
        print(f"  Branch 0 (INHIBITED):   rho={r0:.3f}  w={r['w0']:.3f}  (d_rho={r0-0.5:+.3f})")
        print(f"  Branch 1 (FREE):        rho={r1:.3f}  w={r['w1']:.3f}  (d_rho={r1-0.5:+.3f})")
        print(f"  Ratio (free/inhibited): {ratio:.2f}")
        print(f"  BRANCH-SPECIFIC GATING: {'PASS' if gated else 'FAIL'}")
    return dict(r0=r0, r1=r1, w0=r['w0'], w1=r['w1'], ratio=ratio, gated=gated,
                som_rate=r['som_rate_hz'])


if __name__ == '__main__':
    print("=== Phase 1: single-neuron branch-specific gating (Yang protocol, analytical plasticity) ===")
    for er, pr in [(80.0, 10.0), (80.0, 0.0)]:
        run_gating(exc_rate=er, post_rate=pr)
        print()
