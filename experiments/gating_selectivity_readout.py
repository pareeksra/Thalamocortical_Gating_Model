"""
gating_selectivity_readout.py
=============================
2026-09-03 (Raghav): produce a number DIRECTLY comparable to Yang 2016's own
"gating selectivity" metric, Eq. 1:

    S = (r_on - r_off) / (r_on + r_off)   in [0, 1]

which is defined on the pyramidal neuron's OUTPUT FIRING RATE (r_on when a pathway's
gate is open, r_off when closed), NOT on synaptic weights. Everything the project has
called "gating selectivity" or "ratio" up to now is rho_free/rho_inhibited -- a ratio of
learned synaptic WEIGHTS, a learning outcome, not a firing-rate readout. The two are
different quantities and are not inter-convertible by any algebraic rescale (in
particular applying (r-1)/(r+1) to the weight ratio is NOT Yang's S -- see
docs/reports/PROJECT_STORY.md and this session's discussion).

To get a Yang-comparable number we must actually MEASURE the soma's free output rate.
That requires un-pinning the soma: Phase-1's learning protocol fixes the post rate at
10 Hz via an external Poisson source (experiments/phase1_single_neuron_gating.py, the
Bug-1 fix), so during learning the soma rate is clamped and cannot be used as r_on/r_off.
Here, in a SEPARATE readout phase, we remove that pin and let the soma fire freely from
dendritic coupling (eqs_soma's iCoupleDend), which is the only regime in which its output
rate means anything.

Design (stated explicitly because it defines what the number means):
- Reduced Phase-1 circuit: 1 soma, 2 dendritic branches, 10 SOM -> branch 0 only.
- Weights are FROZEN at their post-learning values (rho is a bare parameter here, not
  evolved) -- so this isolates the readout from the learning dynamics. Learned values are
  taken from the committed analytical Phase-1 result (docs/reports/gamma_tau_analysis.md 2c /
  memory): free branch rho ~ 0.92, inhibited branch rho ~ 0.33. Both are swept for
  sensitivity below.
- The plastic pathway (20 Poisson inputs at exc_rate) drives ONE branch at a time; we
  read the soma's free output rate.

Two selectivity definitions are reported, because they answer different questions:

  (1) WEIGHT-ONLY selectivity -- both branches disinhibited at readout (SOM off).
      r_on  = soma rate driving the FREE (potentiated, high-w) branch.
      r_off = soma rate driving the INHIBITED-during-learning (depressed, low-w) branch.
      Isolates what branch-specific LEARNING alone bought, with no active shunt.

  (2) FULL gating selectivity -- matches the trained state: SOM inhibits branch 0.
      r_on  = soma rate driving the free branch (gate open: not shunted, high w).
      r_off = soma rate driving the inhibited branch (gate closed: shunted AND low w).
      Combines learning + active disinhibition -- the closer analog of Yang Fig. 7d,e.

Honest expectation: the soma may fire weakly or not at all from a single branch's drive
once un-pinned (the whole model was calibrated with the soma pinned at 10 Hz). If
r_on ~ r_off ~ 0, that is a real null result about output-level gating and is reported
as such, not massaged.

Output: results/pre_audit/gating_selectivity_readout_results.json and a printed table.
"""
import os, sys, json
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
sys.path.insert(0, PROOT)

import numpy as np
from brian2 import *

from parameters import params, plasticity_params, som_params, pv_params, vip_params, md_params
from equations import (attach_rho_clipper, make_eqs_synapse_plasticity, eqs_soma, eqs_dend,
                       eqs_som, eqs_synapse_plasticity, on_pre_plasticity)

T_READOUT = 5.0          # s per condition -- long enough for a stable rate estimate
EXC_RATE = 80.0          # Hz, Yang's operating point (same as learning)
GCOUPLE_NS = 0.8         # Yang in-vivo coupling (Bug-1 fixed value)
SOM_BIAS_PA = 21.32      # current 30 Hz baseline

# Learned weights to freeze in (post-learning, analytical Phase-1 result).
RHO_FREE_DEFAULT = 0.92
RHO_INHIB_DEFAULT = 0.33


def measure_soma_rate_v2(drive_branch, rho_free, rho_inhib, som_on, seed_val=42):
    """Build the reduced circuit with FROZEN learned weights and NO post-pinning (soma
    fires freely from dendritic coupling), drive exactly one branch's plastic pathway at
    EXC_RATE via an INDEPENDENT Poisson source per branch (the undriven branch's source is
    0 Hz), and return the soma's free output firing rate (Hz) over T_READOUT.

    drive_branch : 0 (inhibited-during-learning) or 1 (free)
    som_on       : whether SOM tonically inhibits branch 0 during this readout"""
    seed(seed_val)
    p = dict(params); p.update(plasticity_params); p.update(som_params)
    ndend = 2
    p['num_Soma'] = 1; p['num_DendEach'] = ndend; p['num_Dend'] = ndend
    p['gEachCouple_pyr'] = GCOUPLE_NS * nS
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * ndend
    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']; p['norm_factor_Ca'] = t ** (1 / (t - 1))
    t = p['tauGABABRise'] / p['tauGABABDecay']; p['norm_factor_GABAB'] = t ** (1 / (t - 1))

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

    SOM = NeuronGroup(10, eqs_som, threshold='V>vThres_som', reset='V=vReset_som',
                      refractory=p['refrac_som'], method='euler', namespace=p)
    SOM.V = p['vRest_som']
    SOM.iBaseline_som = (SOM_BIAS_PA if som_on else 0.0) * pA
    s2d = Synapses(SOM, Dend, on_pre='gTotGABA_post+=gGABA', namespace=p)
    s2d.connect(j='0')
    net.add([SOM, s2d])

    rate0 = EXC_RATE if drive_branch == 0 else 0.0
    rate1 = EXC_RATE if drive_branch == 1 else 0.0
    exc0 = PoissonGroup(20, rates=rate0 * Hz)
    sb0 = Synapses(exc0, Dend, model=eqs_synapse_plasticity, on_pre=on_pre_plasticity,
                   method='heun', namespace=p)
    sb0.connect(j='0'); sb0.rho = rho_inhib; attach_rho_clipper(sb0)
    exc1 = PoissonGroup(20, rates=rate1 * Hz)
    sb1 = Synapses(exc1, Dend, model=make_eqs_synapse_plasticity(2), on_pre=on_pre_plasticity,
                   method='heun', namespace=p)
    sb1.connect(j='1'); sb1.rho = rho_free; attach_rho_clipper(sb1)
    net.add([exc0, sb0, exc1, sb1])

    mon = SpikeMonitor(Soma)
    net.add(mon)
    net.run(T_READOUT * second)
    return len(mon.t) / T_READOUT


def selectivity(r_on, r_off):
    denom = r_on + r_off
    return (r_on - r_off) / denom if denom > 1e-9 else 0.0


if __name__ == '__main__':
    rho_free, rho_inhib = RHO_FREE_DEFAULT, RHO_INHIB_DEFAULT
    print(f"=== Yang-comparable gating selectivity readout ===")
    print(f"Frozen learned weights: rho_free={rho_free}, rho_inhib={rho_inhib}")
    print(f"Readout: soma UNPINNED, exc={EXC_RATE}Hz, coupling={GCOUPLE_NS}nS, "
          f"T={T_READOUT}s/condition\n")

    results = {'params': dict(rho_free=rho_free, rho_inhib=rho_inhib, exc_rate=EXC_RATE,
                              gcouple_nS=GCOUPLE_NS, som_bias_pA=SOM_BIAS_PA,
                              T_readout=T_READOUT)}

    # (1) weight-only: SOM off, drive each branch
    r_on_w = measure_soma_rate_v2(drive_branch=1, rho_free=rho_free, rho_inhib=rho_inhib, som_on=False)
    r_off_w = measure_soma_rate_v2(drive_branch=0, rho_free=rho_free, rho_inhib=rho_inhib, som_on=False)
    S_w = selectivity(r_on_w, r_off_w)
    print(f"(1) WEIGHT-ONLY (SOM off):")
    print(f"    r_on  (free branch)      = {r_on_w:.2f} Hz")
    print(f"    r_off (depressed branch) = {r_off_w:.2f} Hz")
    print(f"    Yang selectivity S       = {S_w:.3f}\n")
    results['weight_only'] = dict(r_on=r_on_w, r_off=r_off_w, S=S_w)

    # (2) full gating: SOM on branch 0, drive each branch
    r_on_f = measure_soma_rate_v2(drive_branch=1, rho_free=rho_free, rho_inhib=rho_inhib, som_on=True)
    r_off_f = measure_soma_rate_v2(drive_branch=0, rho_free=rho_free, rho_inhib=rho_inhib, som_on=True)
    S_f = selectivity(r_on_f, r_off_f)
    print(f"(2) FULL GATING (SOM on branch 0 -- learning + active shunt):")
    print(f"    r_on  (free branch, gate open)   = {r_on_f:.2f} Hz")
    print(f"    r_off (inhib branch, gate closed) = {r_off_f:.2f} Hz")
    print(f"    Yang selectivity S               = {S_f:.3f}\n")
    results['full_gating'] = dict(r_on=r_on_f, r_off=r_off_f, S=S_f)

    print(f"Yang's own reported S: ~0.5 (network scale, random wiring), "
          f"~0.7 (task-trained subset).")
    print(f"Reminder: different setup (single neuron vs. network/task), so treat as a "
          f"unit-matched sanity check, not a controlled replication.")

    out = os.path.join(PROOT, 'results', 'pre_audit', 'gating_selectivity_readout_results.json')
    with open(out, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {out}")
