"""
circuit_helpers.py
==================
Shared building blocks for the Model A (Brian 2) circuit builders, added in the
2026-11-01 audit-repair pass (see docs/reports/AUDIT_2026-11-01.md).

1. add_compiled_coupling -- soma<->dendrite voltage coupling as compiled summed
   variables, replacing the per-script Python `@network_operation(dt=sim_dt)`.
   The old operation ran on its own 0.02 ms clock while every NeuronGroup ran on
   Brian 2's DEFAULT 0.1 ms clock (`defaultclock.dt` was never set anywhere), so 4 of
   every 5 Python calls re-wrote identical values; it was also the wall-clock
   bottleneck. Semantics are unchanged: the soma sees the mean dendritic voltage and
   every dendrite sees the soma's shadow voltage, both read at the start of each step.

2. som_initial_voltages -- initial membrane voltages for a bias-driven SOM population.
   Every builder used to start all SOM cells at vRest with an identical constant bias and
   (at md=0 / noise=0) no other input, so the whole population fired in PERFECT LOCKSTEP
   (verified: 20 cells -> 1 unique spike time per cycle). The "20-cell SOM population"
   was therefore a single oscillator delivering one big GABA volley per cycle, which is
   what made gating depend on rate x tau_GABA (gap between volleys) -- see the audit doc.
   mode='random' (new default) draws each cell's phase in its firing cycle uniformly,
   from a DEDICATED numpy Generator seeded by seed_val, so Brian 2's global RNG stream
   (connectivity, Poisson inputs) is NOT perturbed. mode='sync' reproduces the legacy
   behaviour exactly; mode='even' spaces phases evenly (idealised asynchrony).
"""
import numpy as np
from brian2 import Synapses, mV, pA, nS, ms, second


def add_compiled_coupling(net, Soma, Dend, ndend, namespace=None):
    """Wire Soma.vAveDend = mean(Dend.V) and Dend.vSoma = Soma.vShadow as compiled
    summed variables (Soma must have 1 neuron). Returns the two Synapses objects."""
    ns = dict(namespace or {}); ns['n_dend_cpl'] = float(ndend)
    # Explicit names: auto-named 'synapses_N' objects would shift the auto-numbering
    # (and hence the scheduling order / RNG consumption order) of every Synapses object
    # created afterwards, breaking bit-identity with the legacy build.
    d2s = Synapses(Dend, Soma, model='vAveDend_post = V_pre / n_dend_cpl : volt (summed)',
                   namespace=ns, name='cpl_dend2soma*')
    d2s.connect()                      # every dendrite -> the soma
    s2d = Synapses(Soma, Dend, model='vSoma_post = vShadow_pre : volt (summed)', namespace=ns,
                   name='cpl_soma2dend*')
    s2d.connect()                      # the soma -> every dendrite
    net.add([d2s, s2d])
    return d2s, s2d


def som_period_and_vinf(p, bias_pA):
    """Free-running LIF period (s) and asymptotic voltage (V) of a SOM cell under a
    constant bias current and no synaptic input. period = inf if sub-rheobase."""
    tau_m = float(p['C_som'] / p['gL_som'])                       # s
    v_inf = float(p['vRest_som'] + bias_pA * pA / p['gL_som'])    # V
    v_r, v_th = float(p['vReset_som']), float(p['vThres_som'])
    if v_inf <= v_th:
        return np.inf, v_inf
    t_charge = tau_m * np.log((v_inf - v_r) / (v_inf - v_th))
    return t_charge + float(p['refrac_som']), v_inf


def som_initial_voltages(n, p, bias_pA, mode='random', seed_val=0):
    """Initial voltages (volt, as a Brian quantity array) placing each SOM cell at a
    phase of its free-running cycle. See module docstring for the modes."""
    v_rest = float(p['vRest_som'])
    if mode == 'sync':
        return np.full(n, v_rest) * 1000 * mV
    period, v_inf = som_period_and_vinf(p, bias_pA)
    v_r, v_th = float(p['vReset_som']), float(p['vThres_som'])
    if not np.isfinite(period):
        # sub-rheobase: no intrinsic cycle -- spread uniformly between rest and v_inf
        rng = np.random.default_rng(10_000 + seed_val)
        lo, hi = min(v_rest, v_inf), max(v_rest, v_inf)
        return rng.uniform(lo, hi, n) * 1000 * mV
    tau_m = float(p['C_som'] / p['gL_som'])
    t_charge = period - float(p['refrac_som'])
    if mode == 'even':
        phase = (np.arange(n) + 0.5) / n
    elif mode == 'random':
        phase = np.random.default_rng(10_000 + seed_val).uniform(0.0, 1.0, n)
    else:
        raise ValueError(f"som phase mode must be 'sync', 'even' or 'random', got {mode!r}")
    # map phase onto the charging trajectory (refractory sliver folded into the start)
    t = phase * t_charge
    v = v_inf + (v_r - v_inf) * np.exp(-t / tau_m)
    v = np.minimum(v, v_th - 1e-6)
    return v * 1000 * mV
