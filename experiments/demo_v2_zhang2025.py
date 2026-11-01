"""
demo_v2_zhang2025.py -- MD context switch selects WHICH branch learns (Zhang 2025 wiring).

2026-11-01 rewrite (audit Problems 2 & 5). The previous version switched a single global
MD population 5 -> 40 Hz, did two plain net.run() calls and plotted the plastic weight w.
Since rho became a held parameter updated per epoch (src/v2/plasticity.py), w could no
longer change inside net.run(), so its "plasticity" panel was two flat lines; and with one
global MD channel, MD could not select a branch in any case.

This version uses model/context_circuit.py: one MD -> VIP -> SOM channel per branch.
Context A (MD_0 on) disinhibits branch 0; context B (MD_1 on) disinhibits branch 1. Inputs
are context-sparse (the idle branch's input is silent), the condition under which learning
is retained (docs/audit/retention_md_context.json).

Run:  <venv>/python experiments/demo_v2_zhang2025.py [seed]
Out:  figures/demo_zhang2025_context_switch.png
"""
import sys, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT]
from brian2 import prefs
prefs.codegen.target = 'cython'
from context_circuit import run_context_protocol

N_EP = 6


def main(seed_val=42):
    sched = [0] * N_EP + [1] * N_EP
    r = run_context_protocol(sched, T=3.0, seed_val=seed_val)
    tr = r['traj']
    ep = np.array([0] + [t['epoch'] for t in tr])
    g = lambda k, init: np.array([init] + [t[k] for t in tr])

    fig, ax = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    for a in ax:
        a.axvspan(0.5, N_EP + 0.5, color='#0072B2', alpha=0.06)
        a.axvspan(N_EP + 0.5, 2 * N_EP + 0.5, color='#D55E00', alpha=0.06)
        a.spines[['top', 'right']].set_visible(False)
    ax[0].step(ep[1:], g('vip0_hz', 0)[1:], where='mid', color='#0072B2', label='VIP channel 0')
    ax[0].step(ep[1:], g('vip1_hz', 0)[1:], where='mid', color='#D55E00', label='VIP channel 1')
    ax[0].step(ep[1:], g('pv_hz', 0)[1:], where='mid', color='0.4', ls=':', label='PV')
    ax[0].set_ylabel('rate (Hz)'); ax[0].legend(frameon=False, fontsize=8)
    ax[0].set_title('MD context A (MD$_0$ on) then B (MD$_1$ on)')
    ax[1].step(ep[1:], g('som0_hz', 0)[1:], where='mid', color='#0072B2', label='SOM -> branch 0')
    ax[1].step(ep[1:], g('som1_hz', 0)[1:], where='mid', color='#D55E00', label='SOM -> branch 1')
    ax[1].set_ylabel('SOM rate (Hz)'); ax[1].legend(frameon=False, fontsize=8)
    ax[2].plot(ep, g('rho0', 0.5), '-o', color='#0072B2', label='branch 0 (learns in A)')
    ax[2].plot(ep, g('rho1', 0.5), '-o', color='#D55E00', label='branch 1 (learns in B)')
    ax[2].axhline(0.5, color='0.8', lw=1, zorder=0)
    ax[2].set_ylim(0, 1.05); ax[2].set_ylabel(r'$\rho$ (branch mean)'); ax[2].set_xlabel('epoch (3 s)')
    ax[2].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    out = os.path.join(PROOT, 'figures', 'demo_zhang2025_context_switch.png')
    fig.savefig(out, dpi=150, facecolor='white')
    a, b = tr[N_EP - 1], tr[-1]
    print(f"seed {seed_val}: end A rho0={a['rho0']:.3f} rho1={a['rho1']:.3f} | "
          f"end B rho0={b['rho0']:.3f} rho1={b['rho1']:.3f}")
    print(f"context A: SOM0 {a['som0_hz']:.1f} Hz, SOM1 {a['som1_hz']:.1f} Hz | "
          f"context B: SOM0 {b['som0_hz']:.1f} Hz, SOM1 {b['som1_hz']:.1f} Hz")
    print('saved', out)
    return r


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 42)
