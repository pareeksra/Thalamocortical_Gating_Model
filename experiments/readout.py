"""
readout.py -- functional recall readout for 'patterns'-mode experiments (2026-11-10).

After learning, plasticity is frozen and each pattern is presented with each gate open
(the R4 protocol, experiments/robustness_r4_learning.READ). Soma: balanced drive, bAPs
from the soma. Readout drive 10 Hz per synapse -- inside the window where learned
weights decide the output (robustness_r4_readout.py: S 0.86-0.89 at 5-10 Hz, ~0 at 50 Hz).
Returns S for pattern A (gate A vs gate B open) and pattern B, and the soma rates.
"""
import numpy as np

READ_HZ = 10.0


def readout_S(rho0_syn, rho1_syn, overlap, seed, rate=READ_HZ, run=None):
    from context_circuit import run_context_protocol, BALANCED_SOMA_KW, BALANCED_SOMA_G_PV2SOMA
    from robustness_r4_learning import READ, S_from
    run = run or run_context_protocol
    r = run([c for c, _ in READ], T=5.0, input_mode='patterns', overlap=overlap,
            stim=[s for _, s in READ], plastic=False, rho_init_syn=(rho0_syn, rho1_syn), exc_rate=rate,
            bap_source='soma', seed_val=seed, param_overrides={'gGABA_pv2soma': BALANCED_SOMA_G_PV2SOMA},
            **BALANCED_SOMA_KW)
    rates = [t['pyr_hz'] for t in r['traj']]
    S, (SA, SB) = S_from(rates)
    return dict(S=S, S_A=SA, S_B=SB, rates=rates)
