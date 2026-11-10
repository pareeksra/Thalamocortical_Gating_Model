"""
brian2_rng_mechanism2.py -- follow-up: is the trigger MULTIPLE stochastic RNG consumers
running together (PoissonGroups + a noise/xi group integrated with heun), all sharing the
global numpy RNG? 2026-10-11.

T1 established: bare PoissonGroup (+ fixed connects) reproduces in-process. The real
circuit additionally has (a) several PoissonGroups and (b) plastic synapses with a noise
term xi integrated by 'heun', all consuming the same global RNG each timestep. These tests
add those, built twice in-process, to see which combination breaks same-seed reproducibility.
"""
import numpy as np
from brian2 import *
prefs.codegen.target = 'numpy'
BrianLogger.suppress_name('resolution_conflict', 'base')

NOISE_EQS = 'dv/dt = -v/(10*ms) + xi*(ms**-0.5) : 1'   # xi -> draws randn() each step


def build(n_poisson, noise_groups, method='heun'):
    start_scope()
    seed(0); np.random.seed(0)
    net = Network()
    pgs = [PoissonGroup(10, rates=500 * Hz) for _ in range(n_poisson)]
    net.add(*pgs)
    for _ in range(noise_groups):
        ng = NeuronGroup(10, NOISE_EQS, method=method)
        net.add(ng)
    mon = SpikeMonitor(pgs[0])
    net.add(mon)
    net.run(0.5 * second)
    return len(mon.t)


def test(label, **kw):
    a = build(**kw); b = build(**kw)
    v = 'REPRODUCIBLE' if a == b else 'NON-REPRODUCIBLE  <-- trigger'
    print(f"{label:60s} {a:5d} vs {b:5d}  -> {v}", flush=True)
    return a == b


if __name__ == '__main__':
    print("=== Multiple stochastic RNG consumers, in-process, same seed ===\n", flush=True)
    t_multi_p = test("3 PoissonGroups, no noise group", n_poisson=3, noise_groups=0)
    t_1p_1n = test("1 PoissonGroup + 1 noise(xi,heun) group", n_poisson=1, noise_groups=1)
    t_3p_1n = test("3 PoissonGroups + 1 noise(xi,heun) group", n_poisson=3, noise_groups=1)
    t_3p_2n = test("3 PoissonGroups + 2 noise(xi,heun) groups", n_poisson=3, noise_groups=2)

    print("\n--- interpretation ---", flush=True)
    if t_multi_p and not (t_1p_1n and t_3p_1n and t_3p_2n):
        print("Multiple PoissonGroups alone reproduce, but adding a noise(xi) group integrated by "
              "heun breaks same-seed reproducibility in-process. CONFIRMED MECHANISM: when a noise "
              "term (randn via heun) and PoissonGroups (rand) both draw from the ONE global numpy "
              "RNG every timestep, their interleaving/scheduling across a rebuilt network is not "
              "pinned by seed() alone, so the shared RNG state diverges -> different Poisson draws. "
              "Fresh-process isolation (our fix) sidesteps it entirely.", flush=True)
    elif all([t_multi_p, t_1p_1n, t_3p_1n, t_3p_2n]):
        print("All combinations reproduced -> the trigger is more specific than 'noise + Poisson'; "
              "needs the actual plasticity-synapse path. Would bisect further.", flush=True)
    else:
        print("Mixed result -- see rows above for which exact combination is the trigger.", flush=True)
