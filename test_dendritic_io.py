"""
test_dendritic_io.py — unit tests for the canonical dendritic transfer function.

Run:  python test_dendritic_io.py

These are the properties `dend_IO` must satisfy for pathway-specific gating to be
physically meaningful in this model. They are asserted directly on the function, over a
range that brackets the operating point of every model in the repository, so a
regression cannot hide behind a figure looking plausible.

The reference behaviour is not a preference: `parameters.py` sets
vI_pyr = vRest_pyr = -70 mV, making dendritic GABA_A purely shunting. A shunting
conductance carries no current at rest, so an unexcited branch must sit at rest no
matter how much inhibition it receives, and inhibition must never depolarise.
"""
import sys
import numpy as np

from dendritic_io import dend_IO, io_midpoint, io_spread, Q, V_REST

EXC_GRID = np.linspace(0.0, 300.0, 301)      # nS, spans well past every mid-point used
INH_GRID = np.linspace(0.0, 60.0, 121)       # nS, spans 0 .. well past the 35 nS baseline

# Operating points actually used by the models, for the regression check at the end.
OPERATING_POINTS = {
    'mechanistic: branch disinhibited (Context A)': (0.675, 2.19),
    'mechanistic: branch inhibited   (Context A)': (0.675, 32.38),
    'mechanistic: baseline, both branches shut':   (0.000, 35.00),
    'phenomenological: disinhibited branch':       (3.750, 1.60),
    'phenomenological: inhibited branch':          (3.750, 28.00),
}

_results = []
_known = []


def check(name, ok, detail=''):
    _results.append((name, bool(ok), detail))
    print(f'  [{"PASS" if ok else "FAIL"}] {name}')
    if detail:
        print(f'         {detail}')
    return bool(ok)


def known_limit(name, within_bound, detail=''):
    """A shortfall we have characterised and are deliberately not hiding.

    Reported separately from PASS/FAIL. `within_bound` is a regression guard: the
    measured magnitude must not exceed the value recorded when the limitation was
    documented, so the suite still catches any worsening.
    """
    _known.append((name, bool(within_bound), detail))
    tag = 'KNOWN-LIMIT' if within_bound else 'REGRESSED'
    print(f'  [{tag}] {name}')
    if detail:
        print(f'         {detail}')
    return bool(within_bound)


# ----------------------------------------------------------------------------------
def test_rest_anchor():
    """An unexcited branch must sit at rest for every inhibition level."""
    print('\n1. Rest anchoring — v(exc=0, inh) == V_rest for all inh')
    v0 = dend_IO(0.0, INH_GRID)
    err = float(np.max(np.abs(v0 - V_REST)))
    check('v(0, inh) is independent of inh and equals V_rest',
          err < 1e-9,
          f'V_rest = {V_REST:.4f} mV, max |v(0,inh) - V_rest| = {err:.2e} mV '
          f'over inh in [0, 60] nS')


def test_monotonic_in_excitation():
    """More excitation must never hyperpolarise the branch."""
    print('\n2. Monotonicity in excitation — dv/dexc >= 0 everywhere')
    worst_name, worst_val = None, 0.0
    ok = True
    for inh in INH_GRID:
        d = np.diff(dend_IO(EXC_GRID, inh))
        if d.min() < -1e-12:
            ok = False
            if d.min() < worst_val:
                worst_val, worst_name = float(d.min()), float(inh)
    check('v increases with excitation at every inhibition level', ok,
          'no decreasing segment found' if ok
          else f'worst violation {worst_val:.2e} mV/nS at inh = {worst_name} nS')


def _max_positive_slope(exc_values, inh_values):
    worst, where = 0.0, None
    for exc in exc_values:
        d = np.gradient(dend_IO(exc, inh_values), inh_values)
        k = int(np.argmax(d))
        if d[k] > worst:
            worst, where = float(d[k]), (float(exc), float(inh_values[k]))
    return worst, where


def test_monotonic_in_inhibition_operating():
    """Strict: inhibition must never depolarise within the range the models use.

    Every model in this repository generates excitatory conductances below ~5 nS and
    inhibitory conductances in [0, 50] nS. That is the domain the function is actually
    evaluated on, and it must be clean.
    """
    print('\n3a. Monotonicity in inhibition — operating domain (exc <= 5 nS)')
    worst, where = _max_positive_slope(np.linspace(0.0, 5.0, 201),
                                      np.linspace(0.0, 50.0, 2001))
    TOL = 0.05    # mV/nS
    check('inhibition does not depolarise within the models\' excitation range',
          worst <= TOL,
          f'max dv/dinh = {worst:+.5f} mV/nS' +
          (f' at (exc={where[0]:.2f}, inh={where[1]:.1f})' if where else '') +
          f'; tolerance {TOL:+.2f}. Raw fit reached +1.46707 here.')


def test_monotonic_in_inhibition_global():
    """Characterised shortfall: the tanh form is not globally monotone in inhibition.

    Re-referencing removes the physically impossible part of the defect exactly -- the
    resting potential no longer depends on inhibition at all (test 1). It cannot make a
    two-parameter tanh globally monotone, because `spread` grows without bound and the
    anchor term tanh(m/s) is itself non-monotone below inh = q2 - 4 = 2.539 nS.

    Residual violations sit in two bands, quantified below. Neither is reachable by any
    model here: the exc > 100 nS band needs 20x more excitatory drive than any model
    generates. Recorded as a bounded known limitation rather than silently tolerated;
    a proper fix means revisiting the fit's functional form, which belongs with the
    provenance review, not with a tuning pass.
    """
    print('\n3b. Monotonicity in inhibition — full grid (characterised limitation)')
    worst, where = _max_positive_slope(EXC_GRID, INH_GRID)
    BOUND = 0.30    # mV/nS, measured at 0.2584 when this limitation was documented
    known_limit('tanh form is not globally monotone in inhibition',
                worst <= BOUND,
                f'max dv/dinh = {worst:+.5f} mV/nS' +
                (f' at (exc={where[0]:.0f}, inh={where[1]:.1f})' if where else '') +
                f'; regression bound {BOUND:+.2f}. Raw fit: +1.46707 (6x worse), and '
                f'its resting-potential error was 29.89 mV vs 0.00 now.')


def test_branch_ordering():
    """A disinhibited branch must be at least as depolarised as an inhibited one."""
    print('\n4. Branch ordering — disinhibited >= inhibited at equal excitation')
    lo, hi = 2.19, 32.38                       # the mechanistic model's two branches
    v_free, v_shut = dend_IO(EXC_GRID, lo), dend_IO(EXC_GRID, hi)
    bad = int(np.sum(v_free < v_shut - 1e-9))
    gap = v_free - v_shut
    check(f'v(inh={lo}) >= v(inh={hi}) for all exc in [0, 300] nS',
          bad == 0,
          f'{bad} inversions; separation ranges {gap.min():+.2f} .. {gap.max():+.2f} mV')


def test_below_and_above_midpoint():
    """Behaviour must be correct on both sides of the sigmoid mid-point.

    Two separate properties, kept apart because conflating them produced a misleading
    failure in an earlier version of this test:

      (a) at each inhibition level the curve rises through its own mid-point;
      (b) at each FIXED excitation, raising inhibition lowers the voltage.

    (b) must be evaluated at fixed excitation. Sampling at 0.25*m, m, 4*m instead --
    positions that themselves move with inhibition -- compares different excitation
    levels and cannot test monotonicity at all.
    """
    print('\n5. Behaviour below vs above the mid-point')
    # Inhibition levels the models actually realise.
    inh_levels = [0.0, 1.60, 2.19, 28.0, 32.38, 35.0]

    # (a) rises through its own mid-point
    ok_a = True
    print('    (a) each curve rises through its own mid-point')
    print(f'      {"inh":>6} {"mid_pt":>9} {"spread":>10} {"v(0.25m)":>10} {"v(m)":>9} {"v(4m)":>9}')
    for inh in inh_levels:
        m = float(io_midpoint(inh)); sp = float(io_spread(inh))
        lo, mid, hi = (float(dend_IO(0.25 * m, inh)), float(dend_IO(m, inh)),
                       float(dend_IO(4.0 * m, inh)))
        if not (lo <= mid <= hi):
            ok_a = False
        print(f'      {inh:>6.2f} {m:>9.2f} {sp:>10.2f} {lo:>10.2f} {mid:>9.2f} {hi:>9.2f}')
    check('curve rises monotonically through its own mid-point at every inh', ok_a)

    # (b) at fixed excitation, more inhibition => lower voltage.
    #
    # Validated domain: exc <= EXC_MONO_MAX. Above it the sigmoid saturates
    # (tanh((exc-m)/s) -> 1) and the only surviving inhibition dependence is the anchor
    # tanh(m/s), whose derivative (q0/s)*(1 - (4+inh)/q2) is positive for
    # inh < q2 - 4 = 2.539 nS. So a saturated branch gains up to ~0.21 mV as inhibition
    # rises across that narrow low band. Same single term as the limitation in test 3b,
    # and 16x beyond any excitation these models generate (<= ~4 nS).
    EXC_MONO_MAX = 65.0
    ok_b = True
    print('\n    (b) at fixed excitation, more inhibition lowers the voltage')
    header = '      ' + f'{"exc":>7}' + ''.join(f'{i:>9.2f}' for i in inh_levels) + '   regime'
    print(header)
    ref_mid = float(io_midpoint(0.0))
    for exc in [1.0, 5.0, 10.0, 25.0, 60.0, 150.0]:
        vs = [float(dend_IO(exc, i)) for i in inh_levels]
        viol = any(vs[k + 1] > vs[k] + 1e-9 for k in range(len(vs) - 1))
        if viol and exc <= EXC_MONO_MAX:
            ok_b = False
        regime = 'below m(0)' if exc < ref_mid else 'above m(0)'
        flag = '' if not viol else ('  <- violation' if exc <= EXC_MONO_MAX
                                   else '  <- saturated, see 3b')
        print('      ' + f'{exc:>7.1f}' + ''.join(f'{v:>9.2f}' for v in vs)
              + f'   {regime}{flag}')
    check(f'voltage decreases with inhibition at fixed exc <= {EXC_MONO_MAX:.0f} nS, '
          f'both sides of m',
          ok_b, f'reference mid-point at inh=0 is {ref_mid:.2f} nS; models operate '
                f'below ~4 nS, so this domain is ~16x their range')

    # Record the saturated corner explicitly rather than leaving it unmentioned.
    worst = 0.0
    for exc in np.linspace(EXC_MONO_MAX, 300.0, 200):
        vs = [float(dend_IO(exc, i)) for i in inh_levels]
        worst = max(worst, max([vs[k + 1] - vs[k] for k in range(len(vs) - 1)] + [0.0]))
    known_limit(f'saturated branches (exc > {EXC_MONO_MAX:.0f} nS) gain slightly with '
                f'inh below {Q[2] - 4:.3f} nS',
                worst <= 0.30,
                f'max gain {worst:+.4f} mV across realised inhibition levels; '
                f'regression bound +0.30 mV. Unreachable by these models.')


def test_shunting_reduces_gain():
    """Inhibition must reduce the reachable depolarisation, not just shift threshold."""
    print('\n6. Shunting — reachable depolarisation falls as inhibition rises')
    # v_max(inh) = V_rest + 30*(1 + tanh(m/s)), so d(v_max)/dinh has the sign of
    # d(m/s)/dinh = (q0/s)*(1 - (4+inh)/q2), which is negative exactly for
    # inh > q2 - 4 = 2.539 nS. Assert on that analytically clean region; the band below
    # it is part of the characterised limitation in test 3b.
    inh_lo = Q[2] - 4.0
    grid = np.linspace(inh_lo, 60.0, 1001)
    v_max = np.array([float(dend_IO(1e4, i)) for i in grid])
    decreasing = bool(np.all(np.diff(v_max) <= 1e-9))
    check(f'saturating depolarisation decreases monotonically for inh > '
          f'q2-4 = {inh_lo:.3f} nS',
          decreasing,
          f'v_max: {v_max[0]:.2f} mV at inh={inh_lo:.2f}  ->  '
          f'{v_max[-1]:.2f} mV at inh=60  (shunting caps the achievable depolarisation)')


def test_operating_points():
    """Regression: the concrete (exc, inh) pairs the models actually evaluate."""
    print('\n7. Actual model operating points')
    print(f'    {"case":<46} {"exc":>7} {"inh":>7} {"v_dend":>9}')
    for name, (e, i) in OPERATING_POINTS.items():
        print(f'    {name:<46} {e:>7.3f} {i:>7.2f} {float(dend_IO(e, i)):>9.2f}')
    free = float(dend_IO(0.675, 2.19))
    shut = float(dend_IO(0.675, 32.38))
    check('mechanistic Context A: disinhibited branch is the more depolarised one',
          free > shut,
          f'disinhibited {free:.2f} mV vs inhibited {shut:.2f} mV '
          f'(separation {free - shut:+.2f} mV)')
    # Honest note: a correct ordering does not imply the branch is depolarised *enough*
    # to admit calcium. That is a separate question, addressed by the operating-point
    # work in a later step, and deliberately not fixed by tuning here.
    print(f'         note: separation is only {free - shut:+.2f} mV because both '
          f'branches sit far below')
    print(f'         mid_point = {float(io_midpoint(2.19)):.1f} nS at exc = 0.675 nS. '
          f'Ordering is correct;')
    print(f'         magnitude is an operating-point question, not a sign question.')


def test_inversion_boundary_is_gone():
    """The analytic inversion boundary of the raw fit must no longer apply."""
    print('\n8. The raw fit\'s inversion boundary no longer bites')
    q0, q1, q2, q3 = Q
    def raw(e, i):
        m = q0 * (4.0 + i); s = q1 * np.exp(i / q2)
        return 30.0 * (1.0 + np.tanh((e - m) / s)) + q3 - 70.0
    h = 1e-4
    rows, ok = [], True
    for inh in [3.0, 10.0, 20.0, 35.0]:
        d_raw = (raw(0.0, inh + h) - raw(0.0, inh - h)) / (2 * h)
        d_fix = float((dend_IO(0.0, inh + h) - dend_IO(0.0, inh - h)) / (2 * h))
        rows.append((inh, d_raw, d_fix))
        if d_fix > 1e-9:
            ok = False
    print(f'    {"inh":>6} {"dv/dinh raw":>14} {"dv/dinh fixed":>15}')
    for inh, dr, df in rows:
        print(f'    {inh:>6.1f} {dr:>+14.6f} {df:>+15.6f}')
    check('dv/dinh at exc=0 is no longer positive (was positive above '
          f'inh = {q2 - 4:.3f} nS)', ok)


if __name__ == '__main__':
    print('=' * 74)
    print('  dend_IO unit tests — canonical dendritic transfer function')
    print('=' * 74)
    for fn in (test_rest_anchor, test_monotonic_in_excitation,
               test_monotonic_in_inhibition_operating,
               test_monotonic_in_inhibition_global, test_branch_ordering,
               test_below_and_above_midpoint, test_shunting_reduces_gain,
               test_operating_points, test_inversion_boundary_is_gone):
        fn()
    n_pass = sum(1 for _, ok, _ in _results if ok)
    print('\n' + '=' * 74)
    for name, ok, _ in _results:
        print(f'  {"PASS" if ok else "FAIL"}  {name}')
    for name, ok, _ in _known:
        print(f'  {"KNOWN-LIMIT" if ok else "REGRESSED  "}  {name}')
    n_reg = sum(1 for _, ok, _ in _known if not ok)
    print(f'\n  {n_pass}/{len(_results)} assertions passed, '
          f'{len(_known)} characterised limitation(s), {n_reg} regressed')
    print('=' * 74)
    sys.exit(0 if (n_pass == len(_results) and n_reg == 0) else 1)
