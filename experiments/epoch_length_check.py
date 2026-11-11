"""
epoch_length_check.py -- is the canonical model robust to the plasticity epoch length T?
(2026-11-10, found while building tests/test_replication.py S3.)

Yang 2016 Eqs. 32-35 (src/v2/plasticity.yang_synapse_update) give the UP/DOWN switching
probabilities of a bistable synapse for ONE continuous protocol, starting from a pure
DOWN (U) or UP (D) state. run_context_protocol re-applies them every T-second epoch from
the current occupancy rho, i.e. it lets the bistable dynamics consolidate between epochs.
For strong drive (LTP at 60 Hz) this is harmless: 300 s in one update or in 3-s epochs
gives 0.914 vs 0.925. For slow drift it is not: an idle synapse with only bAP calcium
(9.4% of the time above theta_d) keeps rho exactly in 3-s epochs but falls from 0.928 to
0.111 in one 300-s update (0.188 in 30-s epochs). So results involving slow LTD --
retention with silent inputs, the inhibited branch -- may depend on T, a numerical choice
that R2 did not vary.

Test (prediction written before running: gating survives every T; retention with silent
inputs falls as T grows):
  per T in {1.5, 3, 6, 12, 24} s, fixed 24 s per phase (A then B), seeds 42-44:
    always   -> rho_free, rho_inh after A; ret_always after B
    context  -> ret_ctx (A silent during B)
  long idle ('patterns' mode, overlap 0): learn A x 8 x 3 s, then a 300-s B phase in
    3-s / 30-s / 300-s epochs with A silent -> ret_ctx_long.
Result with bAP calcium x1.0 (2026-11-10, 'bap1'): gating holds for every T, but retention
with silent inputs falls with T (1.00 at 1.5 s -> 0.80 at 24 s) and after a 300-s idle phase
is 0.998 / 0.18 / 0.12 in 3 / 30 / 300-s epochs -> bAP calcium recalibrated to Yang's x0.2.
Run:  <py> -I experiments/epoch_length_check.py [n_workers] [bap1]
Out:  results/current/epoch_length_check.json
"""
import os, sys, json, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(PROOT, 'model'), PROOT, os.path.join(PROOT, 'experiments')]
BAP1 = 'bap1' in sys.argv[1:]   # 'bap1': the pre-2026-11-10 bAP calcium x1.0 (first run); default: canonical x0.2
KW = dict(bap_ca_scale=1.0) if BAP1 else {}
KW['vip2som_scale'] = 1.0   # results produced before VIP->SOM x0.25 became canonical (2026-11-10)
OUT = os.path.join(PROOT, 'results', 'current', 'epoch_length_check' + ('_bap1' if BAP1 else '') + '.json')
TS = [1.5, 3.0, 6.0, 12.0, 24.0]
SEEDS = [42, 43, 44]
LONG_T = [3.0, 30.0, 300.0]


def _cy():
    from brian2 import prefs
    prefs.codegen.target = 'cython'


def _phase_job(T, seed):
    _cy()
    from context_circuit import run_context_protocol
    n = int(round(24.0 / T))
    out = dict(kind='phase', T=T, seed=seed)
    for mode in ('always', 'context'):
        tr = run_context_protocol([0] * n + [1] * n, T=T, input_mode=mode, seed_val=seed, **KW)['traj']
        out[mode] = dict(rho0=[t['rho0'] for t in tr], rho1=[t['rho1'] for t in tr])
    a, c = out['always'], out['context']
    out['rho_free'], out['rho_inh'] = a['rho0'][n - 1], a['rho1'][n - 1]
    out['ret_always'] = a['rho0'][-1] / a['rho0'][n - 1]
    out['ret_ctx'] = c['rho0'][-1] / c['rho0'][n - 1]
    return out


def _long_job(TB, seed):
    """Patterns mode (overlap 0): learn A for 8 x 3 s (context A), then context B with
    pattern B on for 300 s in TB-second epochs, carrying the per-synapse rho across.
    Retention = mean rho of A's synapses on branch 0 after B / after learning."""
    _cy()
    from context_circuit import run_context_protocol
    tA = run_context_protocol([0] * 8, T=3.0, input_mode='patterns', overlap=0.0, seed_val=seed, **KW)['traj'][-1]
    n = int(round(300.0 / TB))
    tB = run_context_protocol([1] * n, T=TB, input_mode='patterns', overlap=0.0, seed_val=seed + 1000,
                              rho_init_syn=(tA['rho0_syn'], tA['rho1_syn']), **KW)['traj'][-1]
    a0, a1 = np.mean(tA['rho0_syn'][:20]), np.mean(tB['rho0_syn'][:20])
    return dict(kind='long', TB=TB, seed=seed, rho_A_learned=float(a0), rho_A_after=float(a1),
                ret_ctx_long=float(a1 / a0))


def main(nw):
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    J = [('phase', T, s) for T in TS for s in SEEDS] + [('long', T, s) for T in LONG_T for s in SEEDS]
    J = [j for j in J if '_'.join(map(str, j)) not in done]
    with ProcessPoolExecutor(max_workers=nw, max_tasks_per_child=1) as ex:
        futs = {ex.submit(_phase_job if j[0] == 'phase' else _long_job, j[1], j[2]): j for j in J}
        for fu in as_completed(futs):
            j = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                print(j, 'ERROR', repr(e), flush=True); continue
            done['_'.join(map(str, j))] = r
            json.dump(done, open(OUT, 'w'))
            print(j, {k: round(v, 3) for k, v in r.items() if isinstance(v, float)}, flush=True)
    print(f"\n{'T (s)':>6} | {'free':>5} {'inh':>5} | {'ret_ctx':>7} {'ret_alw':>7}")
    summ = {}
    for T in TS:
        rs = [r for r in done.values() if r['kind'] == 'phase' and r['T'] == T]
        m = {k: float(np.mean([r[k] for r in rs])) for k in ('rho_free', 'rho_inh', 'ret_ctx', 'ret_always')}
        summ[f'T={T}'] = m
        print(f"{T:6.1f} | {m['rho_free']:.3f} {m['rho_inh']:.3f} | {m['ret_ctx']:7.3f} {m['ret_always']:7.3f}")
    print('\n300-s idle phase (A silent), epoch length of the idle phase:')
    for T in LONG_T:
        rs = [r for r in done.values() if r['kind'] == 'long' and r['TB'] == T]
        m = float(np.mean([r['ret_ctx_long'] for r in rs]))
        summ[f'long_TB={T}'] = dict(ret_ctx_long=m)
        print(f'  {T:5.0f}-s epochs: retention of A = {m:.3f}')
    json.dump(dict(summary=summ, runs=done), open(OUT, 'w'), indent=1)


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 11)
