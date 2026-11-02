"""
model_explorer.py -- vary ANY parameter of the full gating model and see how it changes
=========================================================================================
2026-09-15 (Raghav): a general flexibility harness for the WHOLE spiking gating model
(model/full_circuit.py build_gating_circuit), not just the analytical supplementary
reconstructions. Override any parameter, sweep one (or grid two), across seeds, in
parallel, and plot how the gating outcome (ratio, r0/r1, SOM rate) responds.

Two kinds of parameters can be varied:
  * FUNCTION ARGS of build_gating_circuit (the high-level knobs):
      T, post_rate, exc_rate, gcouple_nS, md_signal_rate, noise_level, md2vip_scale,
      n_epochs, som_bias_pA
  * ANY parameters.py CONSTANT (via the new param_overrides hook), e.g.:
      gGABA, gNMDA, kappa_Ca_NMDA, theta_p, theta_d, gamma_p, gamma_d, tau, sigma,
      p_som2dend_spike, gAMPA, ... (anything in params/plasticity/pv/som/vip/md dicts)
Names that are function args are routed there; everything else is sent to param_overrides.

Usage
-----
  # single run at the current defaults
  py experiments/model_explorer.py

  # override a few parameters for one run
  py experiments/model_explorer.py --set som_bias_pA=21.32 --set noise_level=0.1 --seeds 42,43

  # SWEEP one parameter across seeds, plot ratio/r0/r1/SOM-rate vs value
  py experiments/model_explorer.py --sweep som_bias_pA=20.9,21.2,21.32,21.6 --seeds 42,43,44 --workers 6
  py experiments/model_explorer.py --sweep noise_level=0,0.1,0.2,0.3,0.4 --seeds 42,43,44
  py experiments/model_explorer.py --sweep theta_p=2.4,2.78,3.2 --seeds 42,43
  py experiments/model_explorer.py --sweep gGABA=3,4,5 --seeds 42,43   # nS; auto *nS

  # 2-D grid -> heatmap of mean gating ratio
  py experiments/model_explorer.py --grid som_bias_pA=20.9,21.32 noise_level=0,0.2 --seeds 42,43

Each build_gating_circuit run is ~30-75 s (numpy target); cost = n_values * n_seeds runs
(grid: n1*n2*n_seeds). A cost estimate is printed before launching. Results are checkpointed
to docs/model_explore_<name>.json and safe to re-run.
"""
import os, sys, json, argparse
from concurrent.futures import ProcessPoolExecutor, as_completed

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
from brian2 import nS, pA, mV, ms, Hz, second   # for unit-carrying param overrides
from full_circuit import build_gating_circuit

# High-level function-arg knobs and their exploration defaults.
FUNC_DEFAULTS = dict(T=3.0, post_rate=10.0, exc_rate=80.0, gcouple_nS=0.8,
                     md_signal_rate=0.0, noise_level=0.0, md2vip_scale=1.0,
                     n_epochs=10, som_bias_pA=21.32)
FUNC_ARGS = set(FUNC_DEFAULTS)

# parameters.py keys that carry Brian2 units -> multiply a bare CLI float by the unit.
# (Only the ones a user is likely to sweep; extend as needed.)
UNIT_MAP = {
    'gGABA': nS, 'gGABA_pv': nS, 'gGABA_som': nS, 'gGABA_pv2soma': nS, 'gAMPA': nS,
    'gAMPA_pv': nS, 'gAMPA_vip': nS, 'gNMDA': nS, 'iBaseline_som': pA,
}


def _coerce_param(name, val):
    """Turn a CLI float into the right units for a parameters.py key when known."""
    if name in UNIT_MAP:
        return val * UNIT_MAP[name]
    return val


INT_FUNC_ARGS = {'n_epochs'}   # func args that must be int, not float (CLI parses floats)


def run_once(func_kwargs, param_overrides, seed_val):
    """One model evaluation -> summary dict. Runs in a worker process."""
    fk = dict(func_kwargs)
    for k in INT_FUNC_ARGS:
        if k in fk:
            fk[k] = int(fk[k])
    r = build_gating_circuit(seed_val=seed_val, param_overrides=param_overrides or None,
                             **fk)
    return dict(seed=seed_val, ratio=round(r['ratio'], 4), r0=round(r['r0'], 4),
                r1=round(r['r1'], 4), som_rate=round(r['som_rate'], 3),
                pyr_rate=round(r['pyr_rate'], 3))


def _split(name, value):
    """Route a name=value to (func_kwargs_update, param_overrides_update)."""
    if name in FUNC_ARGS:
        return {name: value}, {}
    return {}, {name: _coerce_param(name, value)}


def _eval_point(base_func, base_over, axes, seed_val):
    """axes: list of (name, value). Build the kwargs/overrides for this point and run."""
    fk = dict(base_func); po = dict(base_over)
    for name, value in axes:
        f, o = _split(name, value)
        fk.update(f); po.update(o)
    row = run_once(fk, po, seed_val)
    row['_axes'] = {n: v for n, v in axes}
    return row


def sweep(param_name, values, seeds, base_func, base_over, workers):
    tasks = [(param_name, v, s) for v in values for s in seeds]
    print(f"Sweep '{param_name}' over {values}  x  seeds {seeds}  = {len(tasks)} runs "
          f"(~{len(tasks)*45/60:.1f}-{len(tasks)*75/60:.1f} min, {workers} workers)", flush=True)
    results = []
    with ProcessPoolExecutor(max_workers=workers, max_tasks_per_child=1) as ex:  # fresh process per run (audit 2026-11-01)
        futs = {ex.submit(_eval_point, base_func, base_over, [(param_name, v)], s): (v, s)
                for (pn, v, s) in tasks}
        for fut in as_completed(futs):
            v, s = futs[fut]
            try:
                row = fut.result()
            except Exception as e:
                print(f"  {param_name}={v} seed={s}: ERROR {e}", flush=True); continue
            results.append(row)
            print(f"  {param_name}={v:<8} seed={s}: ratio={row['ratio']:.3f} "
                  f"r0={row['r0']:.3f} r1={row['r1']:.3f} SOM={row['som_rate']:.1f}Hz", flush=True)
    return results


def grid(p1, v1, p2, v2, seeds, base_func, base_over, workers):
    tasks = [(a, b, s) for a in v1 for b in v2 for s in seeds]
    print(f"Grid '{p1}'x'{p2}' = {len(v1)}x{len(v2)}x{len(seeds)} = {len(tasks)} runs "
          f"(~{len(tasks)*45/60:.1f}-{len(tasks)*75/60:.1f} min)", flush=True)
    results = []
    with ProcessPoolExecutor(max_workers=workers, max_tasks_per_child=1) as ex:  # fresh process per run (audit 2026-11-01)
        futs = {ex.submit(_eval_point, base_func, base_over, [(p1, a), (p2, b)], s): (a, b, s)
                for (a, b, s) in tasks}
        for fut in as_completed(futs):
            a, b, s = futs[fut]
            try:
                row = fut.result()
            except Exception as e:
                print(f"  {p1}={a} {p2}={b} seed={s}: ERROR {e}", flush=True); continue
            results.append(row)
    return results


def _plot_sweep(param_name, values, results, out_png):
    import numpy as np
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    metrics = ['ratio', 'r0', 'r1', 'som_rate']
    titles = ['gating ratio (r1/r0)', 'r0 (inhibited branch)', 'r1 (free branch)', 'SOM rate (Hz)']
    fig, axes = plt.subplots(1, 4, figsize=(17, 4))
    for ax, m, t in zip(axes, metrics, titles):
        means, sds = [], []
        for v in values:
            vals = [r[m] for r in results if abs(r['_axes'][param_name] - v) < 1e-9]
            means.append(np.mean(vals) if vals else np.nan)
            sds.append(np.std(vals) if vals else 0.0)
        ax.errorbar(values, means, yerr=sds, marker='o', capsize=3, color='#4c72b0')
        if m == 'ratio':
            ax.axhline(2.0, color='#c44e52', ls='--', lw=1, label='pass threshold')
            ax.legend(fontsize=8)
        ax.set_title(t); ax.set_xlabel(param_name); ax.grid(alpha=0.2)
    fig.suptitle(f'Model sensitivity to "{param_name}" (mean ± SD across seeds; '
                 'all else at defaults)', fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(out_png, dpi=150); plt.close(fig); print(f"Saved {out_png}")


def _plot_grid(p1, v1, p2, v2, results, out_png):
    import numpy as np
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    Z = np.full((len(v2), len(v1)), np.nan)
    for i, b in enumerate(v2):
        for j, a in enumerate(v1):
            vals = [r['ratio'] for r in results
                    if abs(r['_axes'][p1]-a) < 1e-9 and abs(r['_axes'][p2]-b) < 1e-9]
            if vals:
                Z[i, j] = np.mean(vals)
    fig, ax = plt.subplots(figsize=(7, 5.5))
    im = ax.imshow(Z, origin='lower', aspect='auto', cmap='viridis',
                   extent=[min(v1), max(v1), min(v2), max(v2)])
    fig.colorbar(im, ax=ax, label='mean gating ratio')
    ax.set_xlabel(p1); ax.set_ylabel(p2)
    ax.set_title(f'Mean gating ratio vs {p1} x {p2}')
    fig.tight_layout(); fig.savefig(out_png, dpi=150); plt.close(fig); print(f"Saved {out_png}")


def _parse_kv(s):
    name, vals = s.split('=')
    return name.strip(), [float(x) for x in vals.split(',')]


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="Explore the full gating model's parameter space.")
    ap.add_argument('--set', action='append', default=[], metavar='name=val',
                    help='override a parameter for ALL runs (repeatable)')
    ap.add_argument('--sweep', type=str, default=None, metavar='name=v1,v2,...')
    ap.add_argument('--grid', nargs=2, default=None, metavar='name=v1,v2,..',
                    help='two axes for a 2-D ratio heatmap')
    ap.add_argument('--seeds', type=str, default='42,43,44')
    ap.add_argument('--workers', type=int, default=6)
    args = ap.parse_args()

    seeds = [int(x) for x in args.seeds.split(',')]
    base_func = dict(FUNC_DEFAULTS); base_over = {}
    for item in args.set:
        name, vals = _parse_kv(item)
        f, o = _split(name, vals[0]); base_func.update(f); base_over.update(o)

    DOCS = os.path.join(PROOT, 'results', 'pre_audit'); FIG = os.path.join(PROOT, 'figures')

    if args.sweep:
        name, values = _parse_kv(args.sweep)
        res = sweep(name, values, seeds, base_func, base_over, args.workers)
        json.dump(res, open(os.path.join(DOCS, f'model_explore_{name}.json'), 'w'), indent=2)
        _plot_sweep(name, values, res, os.path.join(FIG, f'model_explore_{name}.png'))
    elif args.grid:
        p1, v1 = _parse_kv(args.grid[0]); p2, v2 = _parse_kv(args.grid[1])
        res = grid(p1, v1, p2, v2, seeds, base_func, base_over, args.workers)
        json.dump(res, open(os.path.join(DOCS, f'model_explore_{p1}_x_{p2}.json'), 'w'), indent=2)
        _plot_grid(p1, v1, p2, v2, res, os.path.join(FIG, f'model_explore_{p1}_x_{p2}.png'))
    else:
        for s in seeds:
            row = _eval_point(base_func, base_over, [], s)
            print(f"seed {s}: ratio={row['ratio']:.3f} r0={row['r0']:.3f} "
                  f"r1={row['r1']:.3f} SOM={row['som_rate']:.1f}Hz "
                  f"pyr={row['pyr_rate']:.2f}Hz", flush=True)
