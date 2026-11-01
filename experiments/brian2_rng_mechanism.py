"""
brian2_rng_mechanism.py -- pin the EXACT mechanism of the in-process same-seed
non-determinism (step A, source-grounded + empirical).
2026-10-11.

Source facts (brian2 2.10.1):
  - numpy target: rand() = numpy.random.rand, poisson() = np.random.poisson
    (core/functions.py:7, 877-890) -> they draw from numpy's GLOBAL RNG.
  - seed(n): RuntimeDevice.seed -> np.random.seed(n) (+ resets cython-only buffer
    indices) (devices/device.py:587-599).
  So seed(n) resets the global numpy RNG; the cython rand_buffer is irrelevant here.

Question: given that, why did two in-process same-seed builds give DIFFERENT PoissonGroup
spikes? These minimal tests isolate it. No assumptions -- the script reports what happens.
"""
import numpy as np
from brian2 import *
prefs.codegen.target = 'numpy'
BrianLogger.suppress_name('resolution_conflict', 'base')


def bare_poisson(seed_before_run=False, extra_connects=0):
    """One bare PoissonGroup build+run in-process. Returns spike count.
    extra_connects: build this many probabilistic Synapses (connect(p=0.5)) BEFORE the
    run, to consume a variable/large amount of RNG and shift global state."""
    start_scope()
    seed(0)
    np.random.seed(0)
    net = Network()
    G = PoissonGroup(10, rates=500 * Hz)
    net.add(G)
    for k in range(extra_connects):
        a = NeuronGroup(20, 'v:1', threshold='v>2', reset='v=0')
        b = NeuronGroup(20, 'v:1')
        s = Synapses(a, b); s.connect(p=0.5)
        net.add(a, b, s)
    if seed_before_run:
        seed(0); np.random.seed(0)
    mon = SpikeMonitor(G)
    net.add(mon)
    net.run(0.5 * second)
    return len(mon.t)


def test(label, **kw):
    a = bare_poisson(**kw)
    b = bare_poisson(**kw)
    verdict = 'REPRODUCIBLE' if a == b else 'NON-REPRODUCIBLE'
    print(f"{label:55s} run1={a:5d} run2={b:5d}  -> {verdict}", flush=True)
    return a == b


if __name__ == '__main__':
    print("=== Brian2 in-process same-seed RNG mechanism (numpy target) ===\n", flush=True)
    print("T1: bare PoissonGroup only (seed at build start)", flush=True)
    t1 = test("   PoissonGroup, nothing else", extra_connects=0)

    print("\nT2: same, but build 3 probabilistic Synapses BEFORE the run", flush=True)
    t2 = test("   PoissonGroup + 3 connect(p=0.5) before run", extra_connects=3)

    print("\nT3: with extra connects, but RE-SEED right before net.run()", flush=True)
    t3 = test("   PoissonGroup + 3 connects + reseed before run", extra_connects=3,
              seed_before_run=True)

    print("\n--- interpretation ---", flush=True)
    if t1 and not t2:
        print("A bare PoissonGroup reproduces, but adding probabilistic connects before the run "
              "breaks it -> the culprit is VARIABLE RNG CONSUMPTION during build: connect(p=...) "
              "draws a build-dependent number of randoms from the SAME global RNG the PoissonGroup "
              "then draws from, so the RNG state entering net.run differs between builds.", flush=True)
    if t3 and not t2:
        print("Re-seeding right before net.run() restores reproducibility -> confirms it: the "
              "fix is to reseed immediately before the run, OR (what we do) isolate each build in "
              "its own process so build-time RNG consumption can't carry over.", flush=True)
    if t1 and t2:
        print("Even bare + connects reproduce here -> the in-process non-determinism needs the "
              "fuller circuit; would require further bisection.", flush=True)
    if not t1:
        print("Even a bare PoissonGroup is non-reproducible in-process -> the issue is at the "
              "PoissonGroup/device level, not build-time consumption.", flush=True)
