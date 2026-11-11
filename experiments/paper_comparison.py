"""
paper_comparison.py -- R4 of docs/reports/PLAN_robustness.md: the canonical model's numbers
next to the published ones (2026-11-10). Canonical model = model/context_circuit.py
defaults (Yang NMDA-plastic synapse, fluctuation-driven SOM baseline).

Runs the two checks that need new simulations; the table pulls the rest from the result
files named in it.
  V2  Yang Fig. 7b: weight change vs presynaptic rate after a 300-s protocol, post 10 Hz
      (Poisson bAPs), at three inhibition levels. Branch 0 is disinhibited by MD (SOM_0
      silenced), branch 1 is inhibited by SOM_1 at its baseline; the SOM drive is scaled to
      give a medium and a strong inhibition level. Time above theta_d / theta_p is measured
      over 30 s (plasticity frozen) and the closed-form update (Yang Eqs. 32-35) is applied
      for 300 s, from rho = 1/3 (w = 1).
      Yang: three regimes for weak inhibition (no change at low rates, LTD at medium,
      LTP at high); medium inhibition moves the LTP threshold up; strong inhibition
      prevents LTP over a reasonable rate range.
  V4  Zhang 2025 wiring check: interneuron rates vs MD rate (sign and monotonicity of the
      MD -> VIP -| SOM and MD -> PV arms). Zhang's model is a trained rate RNN that gives
      wiring, not rates, so this is qualitative.
Run:  <py> -I experiments/paper_comparison.py run [n_workers] [vip1]
      <py> -I experiments/paper_comparison.py table [vip1]
      (vip1: VIP->SOM x1, reproduces the table committed before 2026-11-11)
Out:  results/current/paper_comparison.json, figures/paper_comparison_v2.png,
      docs/reports/PAPER_COMPARISON.md (table)
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
VIP1 = 'vip1' in sys.argv[2:]   # argument 'vip1': VIP->SOM x1, the table committed before 2026-11-11
VSCALE = 1.0 if VIP1 else None
OUT = os.path.join(PROOT, 'results', 'current', 'paper_comparison' + ('_vip1' if VIP1 else '') + '.json')
RATES = [2, 5, 10, 15, 20, 30, 40, 60, 80, 100, 150]
SOM_SCALES = [0.6, 1.0, 1.6]       # scale of the SOM drive (inhibited branch): low / default / high
SEEDS = [42, 43, 44]
MD_RATES = [0, 5, 10, 15, 20, 30, 40]
T_MEAS, T_PROTO = 30.0, 300.0


def som_kw(scale):
    from context_circuit import SOM_NOISY_KW
    kw = dict(SOM_NOISY_KW)
    kw['som_bg_E_hz'] *= scale
    return kw


def _v2(rate, scale, seed, vip2som_scale=None):
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol
    from parameters import plasticity_params as pp
    from context_circuit import yang_synapse_update
    t0 = time.time()
    tr = run_context_protocol([0], T=T_MEAS, input_mode='always', exc_rate=float(rate), plastic=False,
                              vip2som_scale=vip2som_scale, seed_val=seed, **som_kw(scale))['traj'][0]
    ykw = dict(sigma=float(pp['sigma']), tau=float(pp['tau']), gamma_d=float(pp['gamma_d']),
               gamma_p=float(pp['gamma_p']), w0=float(pp['w0']), w1=float(pp['w1']), rho_star=float(pp['rhoStar']))
    f = T_PROTO / T_MEAS
    out = dict(kind='v2', rate=rate, scale=scale, seed=seed, som=[tr['som0_hz'], tr['som1_hz']])
    for b in (0, 1):
        u = yang_synapse_update(tr[f'ad{b}'] * f, tr[f'ap{b}'] * f, 1 / 3, **ykw)
        out[f'dw{b}'] = float(u['w_post'] - u['w_pre'])
        out[f'ad{b}'], out[f'ap{b}'] = tr[f'ad{b}'] / T_MEAS, tr[f'ap{b}'] / T_MEAS
    out['wall_s'] = round(time.time() - t0, 1)
    return out


def _v4(md, seed, vip2som_scale=None):
    """vip2som_scale None = canonical (x0.25); 1.0 = the pre-2026-11-11 table."""
    from brian2 import prefs
    prefs.codegen.target = 'cython'
    from context_circuit import run_context_protocol
    tr = run_context_protocol([0], T=3.0, input_mode='always', md_on_rate=float(md), plastic=False, vip2som_scale=vip2som_scale,
                              seed_val=seed, **som_kw(1.0))['traj'][0]
    return dict(kind='v4', md=md, seed=seed, som_on=tr['som0_hz'], som_off=tr['som1_hz'],
                vip_on=tr['vip0_hz'], vip_off=tr['vip1_hz'], pv=tr['pv_hz'])


def run(nw):
    sys.path.insert(0, os.path.join(PROOT, 'src', 'v2'))
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    J = [('v2', r, s, sd) for r in RATES for s in SOM_SCALES for sd in SEEDS]
    J += [('v4', m, sd) for m in MD_RATES for sd in SEEDS]
    J = [j for j in J if '_'.join(map(str, j)) not in done]
    print(f'{len(J)} jobs, {nw} workers', flush=True)
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {(ex.submit(_v2, *j[1:], vip2som_scale=VSCALE) if j[0] == 'v2' else ex.submit(_v4, *j[1:], vip2som_scale=VSCALE)): j for j in J}
        for fu in as_completed(futs):
            j = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                print(j, 'ERROR', repr(e), flush=True); continue
            done['_'.join(map(str, j))] = r
            json.dump(done, open(OUT, 'w'))
            print(j, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()
                      if k not in ('kind', 'seed')}, flush=True)
    print('done', flush=True)


def _crossings(x, y):
    """Rates where dw changes sign (linear interpolation): list of (rate, 'LTD->LTP' etc.)."""
    out = []
    for k in range(len(x) - 1):
        if y[k] * y[k + 1] < 0:
            xc = x[k] + (0 - y[k]) * (x[k + 1] - x[k]) / (y[k + 1] - y[k])
            out.append((round(float(xc), 1), 'LTD->LTP' if y[k + 1] > 0 else 'LTP->LTD'))
    return out


def analyse_v2(d):
    rows = [r for r in d.values() if r['kind'] == 'v2']
    curves = {}
    free = []
    for rate in RATES:
        rs = [r for r in rows if r['rate'] == rate]
        if rs:
            free.append((rate, np.mean([r['dw0'] for r in rs]), np.mean([r['som'][0] for r in rs])))
    curves['disinhibited (MD on)'] = dict(rates=[f[0] for f in free], dw=[f[1] for f in free],
                                          som_hz=float(np.mean([f[2] for f in free])))
    for s in SOM_SCALES:
        pts = []
        for rate in RATES:
            rs = [r for r in rows if r['rate'] == rate and r['scale'] == s]
            if rs:
                pts.append((rate, np.mean([r['dw1'] for r in rs]), np.mean([r['som'][1] for r in rs])))
        curves[f'SOM drive x{s}'] = dict(rates=[p[0] for p in pts], dw=[p[1] for p in pts],
                                         som_hz=float(np.mean([p[2] for p in pts])))
    for c in curves.values():
        x, y = np.array(c['rates'], float), np.array(c['dw'])
        y = np.where(np.abs(y) < 0.02, 0.0, y)          # |dw| < 0.02: "no change"
        c['crossings'] = _crossings(x, np.where(y == 0, 1e-9 * np.sign(np.gradient(y) + 1e-12), y))
        ltp = x[y > 0]
        c['ltp_onset_hz'] = float(ltp.min()) if len(ltp) else None
        ltd = x[y < 0]
        c['ltd_range_hz'] = [float(ltd.min()), float(ltd.max())] if len(ltd) else None
    return curves


def analyse_v4(d):
    rows = [r for r in d.values() if r['kind'] == 'v4']
    out = {}
    for k in ('som_on', 'som_off', 'vip_on', 'vip_off', 'pv'):
        out[k] = [float(np.mean([r[k] for r in rows if r['md'] == m])) for m in MD_RATES]
    out['md'] = MD_RATES
    return out


def plot(curves):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.5, 4.3))
    cols = ['#9ecae1', '#3182bd', '#08519c', '#000000']
    for c, (name, cv) in zip(cols, curves.items()):
        ax.plot(cv['rates'], cv['dw'], 'o-', color=c, lw=2, ms=4, label=f"{name}: SOM {cv['som_hz']:.0f} Hz")
    ax.axhline(0, color='0.6', lw=1)
    ax.set_xscale('log')
    ax.set(xlabel='presynaptic rate (Hz)', ylabel='weight change Δw (300 s, post 10 Hz)',
           title='Yang Fig. 7b analogue, canonical model (3 seeds)')
    ax.title.set_fontsize(10)
    ax.legend(fontsize=8, frameon=False)
    ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    fp = os.path.join(PROOT, 'figures', 'paper_comparison_v2' + ('_vip1' if VIP1 else '') + '.png')
    fig.savefig(fp, dpi=150, facecolor='white')
    print('saved', fp)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 11)
    else:
        d = json.load(open(OUT))
        cv = analyse_v2(d)
        for k, c in cv.items():
            print(k, f"SOM {c['som_hz']:.1f} Hz", 'dw', np.round(c['dw'], 3).tolist(), 'LTP from', c['ltp_onset_hz'],
                  'LTD', c['ltd_range_hz'])
        v4 = analyse_v4(d)
        for k in ('som_on', 'som_off', 'vip_on', 'pv'):
            print(k, np.round(v4[k], 1).tolist())
        plot(cv)
        json.dump(dict(v2=cv, v4=v4), open(OUT.replace('.json', '_summary.json'), 'w'), indent=1)
