# Does the forgetting mechanism work in miniature? Yes — but only with the complete definition of "context"

*2026-10-15. First run of the project's central claim (ROADMAP Phase 3 / REPAIR_LOG
item 5 / README: "context-specific learning without catastrophic forgetting").*
*Figure: `figures/retention_forgetting.png`.*

## The test

Learn context A, switch to context B, check that A is retained. Reduced Phase-1
circuit, analytical Yang plasticity, 30 Hz SOM (the locked reliable baseline), seed 42,
8 epochs/phase. Two dendritic branches, each with its own plastic excitatory input. A
"context" sets which branch SOM disinhibits (routes learning) — the abstracted
downstream effect of the MD disinhibition switch.

- **Phase A:** branch 0 free (learns), branch 1 gated.
- **Phase B:** branch 1 free (learns), branch 0 gated → **does A's memory on branch 0
  survive?**

## Result: branch separation alone is NOT enough

| Context switch | branch-0 input during B | branch-0 (A) retention | verdict |
|---|---|---|---|
| **Inhibition only** | stays ON (80 Hz) | **30%** | catastrophic forgetting |
| **Inhibition + input gated** | OFF (context-specific) | **100%** | retained |

With inhibition-only context switching — the naive reading of "different contexts
write to different branches" — **branch 0's memory is ~70% erased** while branch 1
learns. The mechanism, as often stated, fails.

## Why: gating is not protection — it drives active LTD

Diagnosed directly: when branch 0 is gated in Phase B, its plasticity drive is
`alpha_d = 3.0 s` (calcium above the LTD threshold theta_d = 1.0 for essentially the
entire epoch) but `alpha_p = 0.26 s` (almost no LTP). The Yang/Graupner–Brunel update
then has `rho_bar = 0.28`, depression dominating (D = 0.19 ≫ U = 0.07), so rho0 falls
~0.17 per epoch and decays smoothly toward the DOWN state.

The key point: **this calcium plasticity rule has no frozen/protected state.** SOM
shunting suppresses the branch's calcium below the LTP threshold (theta_p = 2.78, so
potentiation stops) but *not* below the LTD threshold (theta_d = 1.0) — because the
branch is still receiving its excitatory input plus the backpropagating-AP calcium.
It therefore sits in the LTD band and is *actively depressed*. Shunting a branch does
not protect its memory; it erases it, just more slowly. (Raising the gating strength to
8× only brings alpha_d from 3.0 s to 1.1 s — inhibition alone cannot drive it to the
hold regime, because the bAP calcium persists.)

## What actually prevents forgetting

The memory is protected only when context A's **input** is silent during context B.
With branch-0's excitatory drive off, its calcium falls below theta_d, so
`alpha_p + alpha_d ≈ 0`, and the Yang update holds rho unchanged (the
`Gp + Gd → 0 ⇒ rho_new = rho_init` branch of the rule). Result: **100% retention**,
while branch 1 learns its own memory — the two coexist (figure, panel B).

So the correct, sharper claim is:

> **No catastrophic forgetting requires context-specific gating of both the
> disinhibition AND the input.** The MD-set disinhibition routes *learning* to the
> active branch; the context-sparsity of the *input* protects the idle branch. Branch
> separation is necessary but not sufficient — it must be paired with input that is
> actually silent for the inactive context.

This is faithful to the Zhang framing (a context = a specific active input pattern
together with its MD-set disinhibitory configuration), and it is a stronger, more
honest statement than "separate branches ⇒ no forgetting."

## Consequence for scaling

A ~3000-neuron network build must preserve input context-sparsity, not just
branch-specific gating. If contexts share persistently-active inputs, the model will
forget at scale for the mechanistic reason above. This is exactly the failure the
"verify in miniature before scaling" step was meant to surface.

## Caveats

- Reduced Phase-1 circuit, single seed (42), 8 epochs/phase, the "context" abstracted
  to a per-phase SOM gain + per-branch input on/off switch (not the full MD→VIP→SOM
  reconfiguration). A fuller version drives the switch through MD and repeats across
  seeds and in the full circuit.
- Retention here is tested over 8 epochs of interference; longer B-training or many
  A/B alternations would further stress it.

## Reproduce

```bash
python -I experiments/retention_catastrophic_forgetting.py inputgated   # retains
python -I experiments/retention_catastrophic_forgetting.py inhibonly     # forgets
python -I plotting/retention_figure.py                                   # figure
```
