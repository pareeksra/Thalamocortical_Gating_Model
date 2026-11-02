"""
sweep_phase_diagram.py -- 2D sweep over MD->PV and MD->VIP synaptic weights.

2026-11-01 rewrite (audit Problem 5). The previous version built its own stale circuit
(4 nS soma-dendrite coupling, 22 pA SOM bias, every input on BOTH branches), did one
1.5 s net.run() and reported Delta-w. Since rho became a held parameter updated per epoch
(src/v2/plasticity.py), w could not change inside net.run(), so the Delta-w panel was
identically 0 for every grid point.

This version calls the canonical full-circuit builder (model/full_circuit.py,
build_gating_circuit: SOM -> branch 0 only, analytical Yang plasticity, desynchronised
SOM) at a fixed MD drive, overriding gAMPA_pv / gAMPA_vip, and reports interneuron rates
plus the plasticity on the SOM-targeted branch (d_rho_inh) and the free branch.
Each grid point runs in a fresh process.

Run:  <venv>/python -I experiments/sweep_phase_diagram.py [--grid 5] [--cores 10] [--epochs 8]
Out:  figures/phase_diagram.png, results/current/phase_diagram.json
"""
import sys, os, argparse, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT]

BASE_PV, BASE_VIP = 0.12, 0.5        # nS, parameters.py gAMPA_pv / gAMPA_vip
MD_RATE = 25.0                       # Hz, full_circuit default md_signal_rate


def run_point(args):
    i, g_pv, j, g_vip, n_epochs = args
    from brian2 import prefs, nS
    prefs.codegen.target = 'cython'
    from full_circuit import build_gating_circuit
    r = build_gating_circuit(T=3.0, md_signal_rate=MD_RATE, noise_level=0.0, n_epochs=n_epochs,
                             seed_val=42, param_overrides={'gAMPA_pv': g_pv * nS,
                                                           'gAMPA_vip': g_vip * nS})
    return dict(i=i, j=j, g_pv=g_pv, g_vip=g_vip, pv=r['pv_rate'], som=r['som_rate'],
                vip=r['vip_rate'], pyr=r['pyr_rate'], r0=r['r0'], r1=r['r1'],
                d_rho_inh=r['d_rho_inh'], d_rho_free=r['d_rho_free'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--grid', type=int, default=5)
    ap.add_argument('--cores', type=int, default=10)
    ap.add_argument('--epochs', type=int, default=8)
    a = ap.parse_args()
    N = a.grid
    pv_vals = np.linspace(0.0, BASE_PV * 2.5, N)
    vip_vals = np.linspace(0.0, BASE_VIP * 2.5, N)
    tasks = [(i, float(pv_vals[i]), j, float(vip_vals[j]), a.epochs) for i in range(N) for j in range(N)]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.cores, max_tasks_per_child=1) as ex:
        res = list(ex.map(run_point, tasks))
    print(f'{N}x{N} sweep in {time.time() - t0:.0f} s')
    os.makedirs(os.path.join(PROOT, 'results', 'current'), exist_ok=True)
    json.dump(res, open(os.path.join(PROOT, 'results', 'current', 'phase_diagram.json'), 'w'), indent=1)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    M = {k: np.zeros((N, N)) for k in ('pv', 'som', 'vip', 'd_rho_inh')}
    for r in res:
        for k in M:
            M[k][r['i'], r['j']] = r[k]
    fig, axes = plt.subplots(2, 2, figsize=(11, 9))
    ext = [pv_vals[0], pv_vals[-1], vip_vals[0], vip_vals[-1]]
    for ax, (k, title, cmap) in zip(axes.flat, [('pv', 'PV rate (Hz)', 'Reds'),
                                                  ('som', 'SOM rate (Hz)', 'Blues'),
                                                  ('vip', 'VIP rate (Hz)', 'Purples'),
                                                  ('d_rho_inh', r'SOM-targeted branch $\Delta\rho$', 'coolwarm')]):
        kw = dict(vmin=-0.5, vmax=0.5) if k == 'd_rho_inh' else {}
        im = ax.imshow(M[k].T, origin='lower', cmap=cmap, aspect='auto', extent=ext, **kw)
        ax.plot(BASE_PV, BASE_VIP, 'k*', ms=12, label='parameters.py values')
        ax.set_title(title); ax.set_xlabel('MD->PV weight (nS)'); ax.set_ylabel('MD->VIP weight (nS)')
        fig.colorbar(im, ax=ax)
    axes.flat[0].legend(loc='upper right', fontsize=8)
    fig.suptitle(f'MD->PV vs MD->VIP weights at MD = {MD_RATE:g} Hz ({a.epochs} epochs, seed 42)')
    fig.tight_layout()
    out = os.path.join(PROOT, 'figures', 'phase_diagram.png')
    fig.savefig(out, dpi=150, facecolor='white')
    print('saved', out)


if __name__ == '__main__':
    main()
