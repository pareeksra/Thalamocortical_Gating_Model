"""
retention_figure.py -- the no-catastrophic-forgetting result (two mechanisms compared).
========================================================================================
Left  (inhibition-only): context switches only the SOM disinhibition; branch-0's input
       stays ON during context B -> branch 0 sits in the LTD band and is actively
       depressed -> catastrophic forgetting (A retained ~29%).
Right (input-gated): context switches BOTH disinhibition AND which input is active
       (A's input silent during B) -> branch 0's calcium drops below theta_d, the Yang
       update holds rho -> A retained ~100% while B learns on branch 1.

Reads docs/retention_results_{inhibonly,inputgated}.json.
Run: <venv>/python -I plotting/retention_figure.py  -> figures/retention_forgetting.png
"""
import os, sys, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C0, C1 = '#0072B2', '#D55E00'   # branch 0 / branch 1


def panel(ax, d, title):
    t = d['traj']; ep = t['epoch']
    nA = d['n_epochs_per_phase']
    ax.plot(ep, t['rho0'], '-o', color=C0, lw=2, ms=4, label='branch 0 (learns in A)')
    ax.plot(ep, t['rho1'], '-o', color=C1, lw=2, ms=4, label='branch 1 (learns in B)')
    ax.axvline(nA, color='0.5', ls='--', lw=1)
    ax.axhline(0.5, color='0.85', lw=1, zorder=0)
    ax.text(nA/2, 1.04, 'Phase A', ha='center', fontsize=9, color=C0)
    ax.text(nA*1.5, 1.04, 'Phase B', ha='center', fontsize=9, color=C1)
    ret = d['rho0_retention_frac'] * 100
    ax.annotate(f'{ret:.0f}% retained', xy=(ep[-1], t['rho0'][-1]),
                xytext=(ep[-1]-5, t['rho0'][-1]+ (0.18 if ret>60 else -0.22)), fontsize=9.5,
                color=C0, fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=C0))
    ax.set_xlabel('epoch'); ax.set_ylim(0, 1.15)
    ax.set_title(title, fontsize=10.5, loc='left')
    ax.spines[['top', 'right']].set_visible(False)


def main():
    di = json.load(open(os.path.join(PROOT, 'docs', 'retention_results_inhibonly.json')))
    dg = json.load(open(os.path.join(PROOT, 'docs', 'retention_results_inputgated.json')))
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    panel(axL, di, f"A  Inhibition-only context switch\n"
                   f"   (A's input stays on) -> FORGETS ({di['rho0_retention_frac']*100:.0f}%)")
    panel(axR, dg, f"B  Input-gated context switch\n"
                   f"   (A's input silent in B) -> RETAINS ({dg['rho0_retention_frac']*100:.0f}%)")
    axL.set_ylabel('synaptic efficacy  rho (branch mean)')
    axR.legend(frameon=False, loc='center right', fontsize=9)
    fig.suptitle('No catastrophic forgetting requires context-specific INPUT, not just '
                 'branch-specific gating', fontsize=12.5, fontweight='bold', y=1.03)
    fig.tight_layout()
    out = os.path.join(PROOT, 'figures', 'retention_forgetting.png')
    fig.savefig(out, dpi=150, bbox_inches='tight', facecolor='white')
    print(f'Saved {out}')
    print(f"  inhibition-only: {di['rho0_retention_frac']*100:.1f}% retained ({di['verdict']})")
    print(f"  input-gated    : {dg['rho0_retention_frac']*100:.1f}% retained ({dg['verdict']})")


if __name__ == '__main__':
    main()
