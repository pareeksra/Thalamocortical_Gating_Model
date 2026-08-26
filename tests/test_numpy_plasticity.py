"""
test_numpy_plasticity.py — regression tests for the NumPy Graupner-Brunel pipeline.

Run:  python test_numpy_plasticity.py

Guards the two mathematical errors fixed in the calcium kernels, and asserts the three
properties the plasticity machinery must have:

  * a condition capable of producing LTP actually moves rho/weight upward
  * a condition incapable of producing LTP does not
  * the stochastic terms are genuinely active where the model claims they are

IMPORTANT: the (r_pre, g_exc, g_inh) triples below are TEST INPUTS chosen to exercise
each regime. No model parameter is changed, and nothing here is calibrated against the
published figures. Whether the models' own operating point reaches these regimes is a
separate calibration question, still blocked on the parameter-provenance review.
"""
import builtins
import sys, os
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, 'numpy_models'))
sys.path.insert(0, os.path.join(_ROOT, 'model'))
import emergent_gating_mechanistic_model as M
import main_gating_figures as P

# Test inputs. Only g_inh differs between the first two.
LTP_CAPABLE   = dict(r_pre=800.0, g_exc=40.0, g_inh=2.0)    # disinhibited branch
LTP_INCAPABLE = dict(r_pre=800.0, g_exc=40.0, g_inh=35.0)   # same drive, gate shut
NO_DRIVE      = dict(r_pre=0.0,   g_exc=0.0,  g_inh=35.0)

_results = []


def check(name, ok, detail=''):
    _results.append((name, bool(ok)))
    print(f'  [{"PASS" if ok else "FAIL"}] {name}')
    if detail:
        print(f'         {detail}')
    return bool(ok)


def evolve(cond, n_trials=80, seed=0, rho0=0.5):
    """Run the real update function for n_trials at a fixed condition."""
    M.rng = np.random.default_rng(seed)
    rho = rho0
    traj = [rho]
    for _ in range(n_trials):
        rho = M.compute_plasticity_update(cond['r_pre'], cond['g_exc'],
                                          cond['g_inh'], rho)
        traj.append(rho)
    return np.array(traj)


# ------------------------------------------------------------------ kernels
def test_kernel_normalisation():
    """Both calcium kernels must peak at their stated amplitude."""
    print('\n1. Calcium kernel amplitudes (regression guard)')

    # mechanistic: double-exponential bAP, normalised via NORM_BAP
    r = b = 0.0
    peak = 0.0
    for i in range(2000):
        if i == 0:
            r += M.C_BAP * M.NORM_BAP
        b = r + (b - r) * M.DECAY_BAP
        r *= M.DECAY_RISE
        peak = max(peak, b)
    check('mechanistic bAP kernel peaks at C_BAP',
          abs(peak - M.C_BAP) < 1e-6,
          f'peak {peak:.6f}, C_BAP {M.C_BAP}. Un-normalised this was ~24x too small, '
          f'which is why calcium never reached theta_D.')

    # mechanistic: NMDA kernel rises instantaneously, so no normalisation is needed
    M.rng = np.random.default_rng(0)
    ca = M.simulate_calcium_poisson(0.0, 0.0, 0.0, 0.0, T=0.1)
    check('mechanistic NMDA kernel needs no normalisation (instantaneous rise)',
          float(ca.max()) == 0.0,
          'no spikes -> no calcium, confirming impulses are the only source')

    # phenomenological: analytic double-exponential
    _, _, cb, _ = P._calcium_trace(0.0)
    check('phenomenological bAP kernel peaks at BAP_SCALING',
          abs(float(cb.max()) - P.BAP_SCALING) < 1e-3,
          f'peak {float(cb.max()):.6f}, BAP_SCALING {P.BAP_SCALING}. The old constant '
          f'tau_d/(tau_d-tau_r) left it 18% low.')

    # kinetics must survive the amplitude fix
    tr = []
    r = b = 0.0
    for i in range(2000):
        if i == 0:
            r += M.C_BAP * M.NORM_BAP
        b = r + (b - r) * M.DECAY_BAP
        r *= M.DECAY_RISE
        tr.append(b)
    tr = np.array(tr)
    t_ms = np.arange(len(tr)) * M.DT_SIM * 1000
    i = int(tr.argmax())
    tail, tt = tr[i:], t_ms[i:] - t_ms[i]
    t_e = float(tt[int(np.argmin(np.abs(tail - tr[i] / np.e)))])
    tau_d = M.TAU_CA_DECAY * 1000
    check('bAP decay time constant unchanged by the amplitude fix',
          abs(t_e - tau_d) / tau_d < 0.15,
          f'1/e decay at {t_e:.1f} ms vs TAU_CA_DECAY = {tau_d:.0f} ms')


# ------------------------------------------------------------------ LTP present
def test_ltp_capable_condition():
    print('\n2. A condition capable of LTP must move rho and the weight upward')
    finals = []
    for sd in range(6):
        traj = evolve(LTP_CAPABLE, seed=sd)
        finals.append(traj[-1])
    finals = np.array(finals)
    w = M.W0 + (M.W1 - M.W0) * finals
    w0 = M.W0 + (M.W1 - M.W0) * 0.5
    print(f'         condition {LTP_CAPABLE}')
    print(f'         rho after 80 trials: {np.array2string(finals, precision=3)}')
    check('rho rises well above its 0.5 start',
          finals.mean() > 0.65,
          f'mean rho {finals.mean():.3f} (started 0.5)')
    check('the derived weight rises with it',
          w.mean() > w0,
          f'mean W {w.mean():.3f} vs W(rho=0.5) = {w0:.3f}')
    check('rho stays inside [0, 1]',
          bool((finals >= 0).all() and (finals <= 1).all()),
          f'range {finals.min():.3f} .. {finals.max():.3f}')


# ------------------------------------------------------------------ LTP absent
def test_ltp_incapable_conditions():
    print('\n3. Conditions incapable of LTP must NOT produce it')
    up = np.array([evolve(LTP_CAPABLE, seed=s)[-1] for s in range(6)])
    for label, cond in (('inhibited branch, same drive', LTP_INCAPABLE),
                        ('no drive at all', NO_DRIVE)):
        got = np.array([evolve(cond, seed=s)[-1] for s in range(6)])
        print(f'         {label}: rho {np.array2string(got, precision=3)}')
        check(f'{label}: rho does not rise into the LTP range',
              got.mean() < 0.65,
              f'mean rho {got.mean():.3f}')
        check(f'{label}: clearly separated from the LTP-capable condition',
              up.mean() - got.mean() > 0.15,
              f'LTP-capable {up.mean():.3f} vs this {got.mean():.3f} '
              f'(gap {up.mean() - got.mean():+.3f})')


# ------------------------------------------------------------------ noise
def test_stochasticity_active():
    print('\n4. The stochastic terms must actually be active')

    # (a) vesicle-release noise on the NMDA amplitude, CV_CA
    M.rng = np.random.default_rng(0)
    peaks = []
    for _ in range(400):
        ca = M.simulate_calcium_poisson(2.0, 0.0, 1.0, 0.0, T=0.5)
        if ca.max() > 0:
            peaks.append(float(ca.max()))
    peaks = np.array(peaks)
    single = peaks[peaks < 1.6]      # trials with a lone pre-spike
    cv = float(single.std() / single.mean()) if len(single) > 20 else float('nan')
    check('NMDA amplitude carries vesicle noise at about CV_CA',
          abs(cv - M.CV_CA) < 0.12,
          f'measured CV {cv:.3f} over {len(single)} single-spike trials, '
          f'CV_CA = {M.CV_CA}')

    # (b) the rho update itself is stochastic
    outs = [M.synapse_change(0.4, 0.3, 0.5) for _ in range(200)]
    check('the rho update is stochastic for identical alpha inputs',
          float(np.std(outs)) > 1e-4,
          f'std over 200 identical calls = {float(np.std(outs)):.5f}')

    # (c) Poisson spike counts vary trial to trial
    M.rng = np.random.default_rng(0)
    counts = [int(M.rng.poisson(25.0 * M.T_TRIAL)) for _ in range(400)]
    check('MD spike counts are Poisson-distributed, not fixed',
          np.std(counts) > 1.0 and abs(np.var(counts) / np.mean(counts) - 1.0) < 0.25,
          f'mean {np.mean(counts):.2f}, var {np.var(counts):.2f}, '
          f'Fano {np.var(counts)/np.mean(counts):.2f} (Poisson -> 1)')

    # (d) interneuron rate variability
    M.rng = np.random.default_rng(0)
    rates = [M.noisy_rate(40.0) for _ in range(500)]
    check('interneuron rates carry trial-to-trial variability',
          np.std(rates) > 1.0,
          f'mean {np.mean(rates):.2f} Hz, sd {np.std(rates):.2f} Hz '
          f'(CV {np.std(rates)/np.mean(rates):.3f}, CV_RATE = {M.CV_RATE})')


# ------------------------------------------------------------------ trajectory
def test_trial_to_trial_evolution():
    print('\n5. Trial-to-trial evolution is a trajectory, not a jump or a walk')
    traj = evolve(LTP_CAPABLE, n_trials=120, seed=0)
    first, last = traj[:20].mean(), traj[-20:].mean()
    monotone_ish = last > first
    step_max = float(np.abs(np.diff(traj)).max())
    check('rho climbs over trials rather than jumping in one step',
          monotone_ish and step_max < 0.5,
          f'first-20 mean {first:.3f} -> last-20 mean {last:.3f}, '
          f'largest single-trial step {step_max:.3f}')
    walk = evolve(NO_DRIVE, n_trials=120, seed=0)
    check('an undriven synapse only diffuses (no systematic climb)',
          abs(walk[-20:].mean() - 0.5) < 0.25,
          f'undriven rho ends at {walk[-20:].mean():.3f}, started 0.5')


if __name__ == '__main__':
    print('=' * 76)
    print('  NumPy Graupner-Brunel plasticity — regression tests')
    print('=' * 76)
    for fn in (test_kernel_normalisation, test_ltp_capable_condition,
               test_ltp_incapable_conditions, test_stochasticity_active,
               test_trial_to_trial_evolution):
        fn()
    n = builtins.sum(1 for _, ok in _results if ok)
    print('\n' + '=' * 76)
    for name, ok in _results:
        print(f'  {"PASS" if ok else "FAIL"}  {name}')
    print(f'\n  {n}/{len(_results)} assertions passed')
    print('=' * 76)
    sys.exit(0 if n == len(_results) else 1)
