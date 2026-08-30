"""
phase2_schizophrenia_sim.py
=============================
Phase 2C of the roadmap: NMDA-hypofunction (ketamine-model) protocol.

Ketamine and related NMDAR antagonists preferentially block NMDA receptors on fast-
spiking and VIP-type interneurons at sub-anesthetic doses (Krystal et al., 1994;
Homayoun & Moghaddam, 2007), producing a net disinhibition/inhibition imbalance widely
used as a circuit-level model of schizophrenia-like cortical dysfunction. Here this is
implemented at the synapse the model actually has for that pathway: the MD -> VIP
excitatory weight (gAMPA_vip), which carries the same class of NMDA/AMPA co-signaling
onto VIP as the rest of the circuit.

`model/full_circuit.py`'s `md2vip_scale` parameter linearly attenuates this synaptic
weight (1.0 = intact, 0.0 = fully blocked) independent of the noise_level channel.
Prediction under progressive MD -> VIP block: VIP can no longer be driven, so SOM's
tonic drive is no longer suppressed regardless of MD state; SOM remains at its
resting/baseline firing rate; branch 0 (the branch SOM inhibits) stays tonically
suppressed and fails to potentiate even at MD levels that would normally disinhibit it.
"""
import os
import sys

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
FIGROOT = os.path.join(PROOT, 'figures')

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from full_circuit import build_gating_circuit

MD2VIP_SCALES = [1.0, 0.66, 0.33, 0.0]
MD_SIGNAL_RATE = 25.0
N_SEEDS = 3
T_SIM = 3.0
# 2026-08-30 migration to analytical plasticity: see phase2_snr_breakdown.py for the
# same epochs=10 rationale (measured 90 s/epoch steady-state; 15 epochs x 3 seeds x 4
# scale points would run ~3 h at 15 epochs, ~2 h at 10).
N_EPOCHS = 10
RESULTS_PATH = os.path.join(PROOT, 'docs', 'phase2_ketamine_sweep_results.json')

import json


def load_records():
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH) as f:
            return json.load(f)
    return []


def save_records(records):
    with open(RESULTS_PATH, 'w') as f:
        json.dump(records, f, indent=2)


def sweep():
    records = load_records()
    done = {round(r['md2vip_scale'], 4) for r in records}
    todo = [s for s in MD2VIP_SCALES if round(s, 4) not in done]
    print(f"=== Phase 2C: {len(todo)} md2vip_scale point(s) to run (of {len(MD2VIP_SCALES)}, "
          f"{len(records)} already done) ===", flush=True)
    for scale in todo:
        ratios, r0s, r1s, som_rates, vip_rates = [], [], [], [], []
        for s in range(N_SEEDS):
            out = build_gating_circuit(T=T_SIM, md_signal_rate=MD_SIGNAL_RATE,
                                        noise_level=0.0, md2vip_scale=scale,
                                        n_epochs=N_EPOCHS, seed_val=42 + s)
            ratios.append(out['ratio']); r0s.append(out['r0']); r1s.append(out['r1'])
            som_rates.append(out['som_rate']); vip_rates.append(out['vip_rate'])
            print(f"  scale={scale:.2f} seed={42+s}: ratio={out['ratio']:.3f} "
                  f"r0={out['r0']:.3f} r1={out['r1']:.3f} SOM={out['som_rate']:.1f} Hz "
                  f"VIP={out['vip_rate']:.1f} Hz", flush=True)
        rec = dict(md2vip_scale=scale, ratio_mean=float(np.mean(ratios)),
                   r0_mean=float(np.mean(r0s)), r1_mean=float(np.mean(r1s)),
                   som_rate_mean=float(np.mean(som_rates)),
                   vip_rate_mean=float(np.mean(vip_rates)))
        records.append(rec)
        records.sort(key=lambda r: -r['md2vip_scale'])
        save_records(records)
        print(f"md2vip_scale={scale:.2f}  ratio={rec['ratio_mean']:.2f}  "
              f"rho0={rec['r0_mean']:.3f}  rho1={rec['r1_mean']:.3f}  "
              f"SOM={rec['som_rate_mean']:.1f} Hz  VIP={rec['vip_rate_mean']:.1f} Hz",
              flush=True)
    return records


def plot(records, out_path):
    scale = [r['md2vip_scale'] for r in records]
    block = [100 * (1 - s) for s in scale]
    r0 = [r['r0_mean'] for r in records]
    r1 = [r['r1_mean'] for r in records]
    som = [r['som_rate_mean'] for r in records]
    vip = [r['vip_rate_mean'] for r in records]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))

    ax = axes[0]
    ax.plot(block, r1, 'o-', color='#1565C0', lw=2, label=r'Branch 1 (free), $\rho$')
    ax.plot(block, r0, 's-', color='#C62828', lw=2, label=r'Branch 0 (SOM-targeted), $\rho$')
    ax.set_xlabel('MD -> VIP synaptic block (%)')
    ax.set_ylabel(r'Steady-state synaptic efficacy $\rho$')
    ax.set_title('Branch-specific plasticity vs. MD -> VIP block')
    ax.legend(fontsize=8)

    ax2 = axes[1]
    ax2.plot(block, som, 'o-', color='#00838F', lw=2, label='SOM rate (Hz)')
    ax2.plot(block, vip, 's-', color='#6A1B9A', lw=2, label='VIP rate (Hz)')
    ax2.set_xlabel('MD -> VIP synaptic block (%)')
    ax2.set_ylabel('Population firing rate (Hz)')
    ax2.set_title(f'Interneuron rates at MD = {MD_SIGNAL_RATE:.0f} Hz')
    ax2.legend(fontsize=8)

    fig.suptitle('NMDA-hypofunction (MD -> VIP block) disrupts branch-specific gating')
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Saved {out_path}")


if __name__ == '__main__':
    print("=== Phase 2C: NMDA-hypofunction (ketamine-model) protocol ===")
    records = sweep()
    fully_blocked = records[-1]
    print(f"\nAt full MD->VIP block: SOM={fully_blocked['som_rate_mean']:.1f} Hz "
          f"(baseline, VIP-independent), branch0 rho={fully_blocked['r0_mean']:.3f}, "
          f"branch1 rho={fully_blocked['r1_mean']:.3f}, ratio={fully_blocked['ratio_mean']:.2f}")
    os.makedirs(FIGROOT, exist_ok=True)
    plot(records, os.path.join(FIGROOT, 'phase2_ketamine_failure.png'))
    print("\n=== Phase 2C complete ===")
