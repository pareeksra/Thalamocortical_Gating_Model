"""
dendritic_io.py
===============
Canonical dendritic input/output transfer function, shared by every model in this
project.

Provenance
----------
The four fitted constants `Q` and the surrounding functional form come from the
analytical reduction of the Yang et al. (2016) two-layer pyramidal model. Before this
module existed, the same expression was copy-pasted into four separate files:

    main_gating_figures.py              (vectorised, live)
    emergent_gating_mechanistic_model.py (scalar via `math`, live)
    src/v2/MultiCompartmentalModel.py    (vectorised, unused helper)
    src/v2/InterneuronalCircuit.py       (vectorised, whole file unused)

All four were mathematically identical; they differed only in whether they used
`numpy` or `math`. This module is the single canonical definition. `dend_IO` is
implemented with numpy so it accepts either scalars or arrays: array in, array out
(so existing `dend_IO(np.atleast_1d(x), inh)[0]` call sites keep working), scalar in,
numpy scalar out (usable in arithmetic and by `math.*` exactly as a float).

The rest-referencing correction
-------------------------------
The raw fit is  f(exc, inh) = 30*(1 + tanh((exc - m)/s)) + q3 - 70  with
m = q0*(4 + inh) and s = q1*exp(inh/q2). Used directly it inverts the gating at low
excitation. The condition is analytic, not numerical:

    du/dinh = -[ q0 + (exc - m)/q2 ] / s        (s > 0 always)
    => dv/dinh < 0  (inhibition hyperpolarises, as it must)
       only when   exc > m - q0*q2 = q0*(4 + inh - q2)

With q0*q2 = 36.35 nS, at exc = 0 the sign flips once inh > q2 - 4 = 2.539 nS. Above
that, *more* inhibition yields a *more* depolarised branch. At inh = 35 nS the raw fit
puts a branch with zero excitatory drive at -42.4 mV instead of rest.

That is impossible in this model on its own terms. `parameters.py` sets
vI_pyr = vRest_pyr = -70 mV, so dendritic GABA_A is purely *shunting*: it carries no
current at rest and can only divide an excitatory drive. The passive steady state,

    v = (gL*V_rest + g_exc*V_E + g_inh*V_I) / (gL + g_exc + g_inh),

therefore returns exactly V_rest at g_exc = 0 for every g_inh. The fit must inherit
that. So the sigmoid is re-referenced to rest:

    dend_IO(exc, inh) = V_rest + [ f(exc, inh) - f(0, inh) ]

Because the subtracted term does not depend on `exc`, this
  * leaves d/dexc untouched            -> monotonicity in excitation is preserved,
  * forces v(0, inh) = V_rest exactly  -> the shunting constraint holds by construction,
  * changes none of q0..q3             -> the Yang fit is re-referenced, not refitted.

What it does change is the asymptote: the reachable depolarisation now falls as
inhibition rises (at inh = 35 nS, saturating excitation reaches about -36 mV rather
than -9 mV). That is the intended shunting behaviour and is why the correction is a
fix rather than an offset.

Remaining caveat for provenance review (Step 3): `spread` reaches ~700 nS at inh = 28
and ~2000 nS at inh = 35, far wider than any excitation this project generates. The
original fit was almost certainly not constrained at such inhibition levels, so the
*shape* in that regime is extrapolation even after re-referencing. Flagged, not tuned.

See `test_dendritic_io.py` for the executable characterisation.
"""

import numpy as np

# Fitted constants of the Yang et al. (2016) dendritic I/O reduction.
#   Q[0] : mid-point slope w.r.t. inhibitory conductance   (mV / nS)
#   Q[1] : spread prefactor                                (nS)
#   Q[2] : spread exponential scale w.r.t. inhibition      (nS)
#   Q[3] : voltage offset                                  (mV)
Q = [5.5592051, 9.64361681, 6.5386557, 0.7779744]

V_REST_DEND = -70.0          # mV -- resting potential of the dendritic compartment
V_SWING     = 30.0           # mV -- half the total swing of the raw sigmoid

# The fit carries a constant offset q3 on top of V_REST_DEND; together they are the
# voltage an unexcited branch sits at. `vRest_pyr` in parameters.py is -70 mV and the
# fit's own zero-excitation asymptote is -70 + q3, so V_REST is the fit's rest.
V_REST = V_REST_DEND + Q[3]


def dend_IO(exc, inh):
    """Steady-state dendritic branch voltage (mV) from conductances (nS).

    Parameters
    ----------
    exc : float or array_like
        Total excitatory conductance on the branch (nS).
    inh : float or array_like
        Total inhibitory conductance on the branch (nS).

    Returns
    -------
    Dendritic membrane voltage (mV), same shape as the broadcast of the inputs.
    """
    exc = np.asarray(exc, dtype=float)
    inh = np.asarray(inh, dtype=float)
    mid_point = Q[0] * (4.0 + inh)
    spread    = Q[1] * np.exp(inh / Q[2])
    # Re-referenced to rest: subtract the exc = 0 value of the raw fit so that an
    # unexcited branch sits at V_rest for every level of inhibition. See module
    # docstring for the derivation.
    return V_REST + V_SWING * (np.tanh((exc - mid_point) / spread)
                               - np.tanh((0.0 - mid_point) / spread))


def io_midpoint(inh):
    """Excitatory conductance (nS) at which the branch is half-activated."""
    return Q[0] * (4.0 + np.asarray(inh, dtype=float))


def io_spread(inh):
    """Width (nS) of the sigmoid's transition region."""
    return Q[1] * np.exp(np.asarray(inh, dtype=float) / Q[2])
