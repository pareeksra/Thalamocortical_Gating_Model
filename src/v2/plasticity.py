"""
src/v2/plasticity.py
====================
Analytical calcium-based synaptic plasticity: Yang, Murray & Wang (2016),
*A dendritic disinhibitory circuit mechanism for pathway-specific gating*,
Nat. Commun. 7:12815, Methods p.12, Eqs. 32-35 (which restate Graupner & Brunel
2012, PNAS 109:3991, ref. 36, with slightly modified notation).

This replaces the continuous drho/dt double-well ODE (formerly
`model/equations.py:eqs_synapse_plasticity_template`, now commented out) with the
paper's closed-form epoch update: given the time the calcium trace spent above
each threshold during a stimulation epoch, return the post-epoch bistable state.

Equations, exactly as printed in the paper (verified against the PDF, not OCR).
Over an epoch the calcium trace spends time alpha_p above the potentiation
threshold theta_p and time alpha_d above the depression threshold theta_d
(alpha in seconds). With potentiation/depression strengths gamma_p, gamma_d
(units 1/s) the average potentiation and depression are

    Gp = gamma_p * alpha_p ,   Gd = gamma_d * alpha_d          (dimensionless)

and, writing E = exp(-(Gp + Gd) / tau),

    Eq. 32:  rho_bar    = Gp / (Gp + Gd)
    Eq. 33:  sigma_rho2 = sigma^2 * (alpha_p + alpha_d) / (Gp + Gd)
    Eq. 34:  U = 1/2 * ( 1 + erf( -(0.5 - rho_bar + rho_bar*E)
                                   / sqrt( sigma_rho2 * (1 - E^2) ) ) )
    Eq. 35:  D = 1/2 * ( 1 - erf( -(0.5 - rho_bar + (rho_bar - 1)*E)
                                   / sqrt( sigma_rho2 * (1 - E^2) ) ) )

where U is the long-term DOWN->UP switching probability and D the UP->DOWN
switching probability, sigma is the noise amplitude and tau the weight-change
time constant. The post-epoch weight (same page) is

    w_pre  = w0 + (w1 - w0) * rho_init
    w_post = w_pre * (1 - D) + (w1 - w_pre) * U

with, for convenience, w0 = 0 (DOWN) and w1 = 3 (UP) -- Yang's published values.
The bistable state is recovered as rho_new = (w_post - w0) / (w1 - w0), which is
the exact inverse of Model A's rho -> w map (equations.py:207
`w = w0 + (w1-w0)*rho`), so rho_new can be written straight back into the Brian 2
synapse.

Published Yang (2016) parameters (Methods p.12), used as the module defaults:
    sigma = 3.35,  tau = 346.36 s,  gamma_d = 39.949,  gamma_p = 177.552,
    theta_d = 1.0,  theta_p = 2.78,  w0 = 0,  w1 = 3,  rho* = 0.5.
"""
from __future__ import annotations
import numpy as np
from scipy.special import erf

# ---- Yang 2016 published constants (Methods p.12) ---------------------------
SIGMA    = 3.35        # noise amplitude
TAU      = 346.36      # s, synaptic-weight-change time constant
GAMMA_D  = 39.949      # depression strength gamma_d (1/s)
GAMMA_P  = 177.552     # potentiation strength gamma_p (1/s)
THETA_D  = 1.0         # depression (LTD) calcium threshold
THETA_P  = 2.78        # potentiation (LTP) calcium threshold
W0       = 0.0         # DOWN-state weight
W1       = 3.0         # UP-state weight (Yang's value; see docs/gamma_tau_analysis.md 2b.1)
RHO_STAR = 0.5         # unstable fixed point / decision barrier

_TINY = 1e-12


def yang_synapse_update(alpha_d, alpha_p, rho_init=RHO_STAR,
                        sigma=SIGMA, tau=TAU, gamma_d=GAMMA_D, gamma_p=GAMMA_P,
                        w0=W0, w1=W1, rho_star=RHO_STAR):
    """One analytical epoch update per Yang 2016 Eqs. 32-35 (Methods p.12).

    Parameters
    ----------
    alpha_d, alpha_p : float
        Seconds the epoch's calcium trace spent above theta_d and theta_p.
    rho_init : float
        Bistable UP-occupancy state before this epoch, in [0, 1].
    sigma, tau, gamma_d, gamma_p, w0, w1, rho_star : float
        Yang's published parameters; overridable for sweeps. `rho_star` is the
        barrier location inside the erf arguments (0.5 in the paper).

    Returns
    -------
    dict with keys:
        U, D        : Eq. 34 / Eq. 35 switching probabilities
        rho_bar     : Eq. 32 fixed point (nan if no calcium activity)
        sigma_rho2  : Eq. 33 variance
        w_pre, w_post : weights before/after the epoch
        rho_new     : (w_post - w0) / (w1 - w0), ready to write back to Brian 2

    Notes
    -----
    If the calcium trace never crosses either threshold (Gp + Gd == 0, i.e. a
    silent/shunted synapse) there is no drift and no gated noise, so the state is
    held: U = D = 0, rho_new = rho_init. This matches the gated-noise behaviour
    of the superseded ODE (a silent synapse must not random-walk).
    """
    Gp = gamma_p * alpha_p
    Gd = gamma_d * alpha_d
    total = Gp + Gd
    w_pre = w0 + (w1 - w0) * rho_init

    if total < _TINY or (alpha_p + alpha_d) < _TINY:
        return dict(U=0.0, D=0.0, rho_bar=float('nan'), sigma_rho2=0.0,
                    w_pre=float(w_pre), w_post=float(w_pre), rho_new=float(rho_init))

    rho_bar    = Gp / total                                   # Eq. 32
    sigma_rho2 = sigma * sigma * (alpha_p + alpha_d) / total   # Eq. 33
    E   = np.exp(-total / tau)
    var = sigma_rho2 * (1.0 - E * E)                           # denominator variance
    denom = np.sqrt(var) if var > _TINY else _TINY

    argU = -(rho_star - rho_bar + rho_bar * E) / denom
    argD = -(rho_star - rho_bar + (rho_bar - 1.0) * E) / denom
    U = 0.5 * (1.0 + erf(argU))                               # Eq. 34
    D = 0.5 * (1.0 - erf(argD))                               # Eq. 35

    w_post  = w_pre * (1.0 - D) + (w1 - w_pre) * U
    rho_new = (w_post - w0) / (w1 - w0)
    # Numerical guard: U, D in [0,1] keep rho_new in [0,1] up to rounding.
    rho_new = float(np.clip(rho_new, 0.0, 1.0))
    return dict(U=float(U), D=float(D), rho_bar=float(rho_bar),
                sigma_rho2=float(sigma_rho2), w_pre=float(w_pre),
                w_post=float(w_post), rho_new=rho_new)


def alpha_above_threshold(ca_trace, dt, theta):
    """Seconds a calcium trace spends above `theta`.

    `ca_trace` is a 1-D array sampled every `dt` seconds (the c_total trace of a
    single synapse over one epoch). alpha = (# samples above theta) * dt. This is
    the discrete counterpart of Yang's "time the calcium trace spends above the
    threshold" and is what feeds `yang_synapse_update`.
    """
    ca = np.asarray(ca_trace)
    return float(np.count_nonzero(ca > theta) * dt)


def rho_new(alpha_d, alpha_p, rho_init=RHO_STAR, **kw):
    """Convenience wrapper returning only the post-epoch rho."""
    return yang_synapse_update(alpha_d, alpha_p, rho_init, **kw)['rho_new']


if __name__ == '__main__':
    # Smoke test at Phase-1's measured operating points (docs/formula_comparison.py).
    for name, (ad, ap) in [('inhibited', (0.9751, 0.0)), ('free', (2.9693, 2.8637))]:
        r = yang_synapse_update(ad, ap, 0.5)
        print(f"{name:10s} alpha_d={ad:.3f} alpha_p={ap:.3f} -> "
              f"U={r['U']:.4f} D={r['D']:.4f} rho_new={r['rho_new']:.4f} w_post={r['w_post']:.4f}")
