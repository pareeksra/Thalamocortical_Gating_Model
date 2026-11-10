"""cross_session_check.py -- (b) cross-session/cross-invocation bit-identity.
Re-run seed 42 NOW (fresh process, different session/day) and compare full precision to the
baseline stored by docs/determinism_check.py in a PREVIOUS session."""
import os, sys, json
PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))
from full_circuit import build_gating_circuit
CFG = dict(T=3.0, md_signal_rate=0.0, noise_level=0.0, n_epochs=3, som_bias_pA=21.32)
KEYS = ['r0','r1','w0','w1','ratio','pv_rate','som_rate','vip_rate','pyr_rate']
base = json.load(open(os.path.join(PROOT,'results', 'pre_audit','determinism_check_results.json')))['A_seed42']
now = build_gating_circuit(seed_val=42, **CFG)
print("=== cross-session seed-42 bit-identity (now vs stored earlier session) ===", flush=True)
allmatch = True
for k in KEYS:
    same = (now[k] == base[k])
    if not same: allmatch = False
    print(f"  {k:9s} stored={base[k]!r}  now={now[k]!r}  -> {'MATCH' if same else 'DIFFER'}", flush=True)
print(f"\n  VERDICT: {'BIT-IDENTICAL across sessions' if allmatch else 'DIFFERS across sessions'}", flush=True)
