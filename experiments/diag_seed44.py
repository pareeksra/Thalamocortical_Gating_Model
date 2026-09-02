"""Diagnostic (2026-09-01): confirm whether the Phase-2B seed-44 collapse at
noise_level=0 reproduces in the FULL circuit, and how marginal 25 Hz is.
Runs the exact Phase-2B baseline call for seeds 42-46.

Checkpoints per-seed to docs/diag_seed44_results.json (2026-09-01 revision: the first
run was killed by a system restart after finishing 3/5 seeds with nothing persisted,
since the original version only wrote the JSON once at the very end. Re-run is now
resumable -- safe to relaunch after a kill, already-done seeds are skipped)."""
import os, sys, json
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
from full_circuit import build_gating_circuit

SEEDS = [42, 43, 44, 45, 46]
RESULTS_PATH = os.path.join(PROOT, 'docs', 'diag_seed44_results.json')


def load_results():
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH) as f:
            return json.load(f)
    return []


def save_results(results):
    with open(RESULTS_PATH, 'w') as f:
        json.dump(results, f, indent=2)


out = load_results()
done_seeds = {r['seed'] for r in out}
todo = [s for s in SEEDS if s not in done_seeds]
if done_seeds:
    print(f"Resuming: {sorted(done_seeds)} already done, running {todo}", flush=True)

for s in todo:
    r = build_gating_circuit(T=3.0, md_signal_rate=0.0, noise_level=0.0,
                             n_epochs=10, seed_val=s)
    row = dict(seed=s, ratio=round(r['ratio'], 4), r0=round(r['r0'], 4),
               r1=round(r['r1'], 4), som_rate=round(r['som_rate'], 3))
    out.append(row)
    save_results(out)
    print(f"seed={s}: ratio={row['ratio']:.4f}  r0(inhib)={row['r0']:.4f}  "
          f"r1(free)={row['r1']:.4f}  SOM={row['som_rate']:.2f} Hz  "
          f"{'[PASS]' if row['ratio']>2.0 else '[FAIL]'}", flush=True)

passes = sum(1 for r in out if r['ratio'] > 2.0)
print(f"\n=== diag_seed44 complete: {passes}/{len(out)} passed (ratio>2.0) ===", flush=True)
