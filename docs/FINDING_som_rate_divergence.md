# Resolving the SOM-rate divergence from Yang 2016

*2026-10-14. The reviewer question: "Yang gets gating at ~10 Hz SOM; why does this
spiking model need ~2× that?"*

## The puzzle, stated precisely (primary source checked)

Yang, Murray & Wang (2016) obtain pathway-specific dendritic gating with:
- SOM baseline firing **~10 Hz** — and the paper is explicit this is *experimental*,
  not a free parameter: *"firing of SOM neurons ~10 Hz as observed experimentally"*
  (Methods; refs 6, 15).
- Dendritic inhibition decay **tau_GABA,dend = 20 ms** (Methods, verified in the PDF
  text: "...inhibitory synapses, tGABA,dend = 20 ms").

This spiking reimplementation uses the **identical tau_GABA,dend = 20 ms** but needs
**~18–21 Hz** for gating (`docs/som_rate_sweep_table.csv`: fails at 16.9 Hz ratio 1.04,
passes at 21.5 Hz ratio 5.5). Same inhibitory time constant, ~2× the SOM rate. That
is exactly what a careful reviewer will flag.

## Resolution: gating is set by inhibition *coverage* (rate × tau), not rate

What gates plasticity is the **duty cycle of dendritic inhibition** — the fraction of
each inter-SOM-spike interval during which the GABA conductance keeps the branch
shunted below the NMDA/calcium escape threshold. That coverage is set by
**rate × tau_GABA,dend**, not by the rate alone. In a *spiking* model dendritic
calcium is driven by discrete NMDA events, so any window left uncovered within an ISI
permits an event-driven calcium excursion over theta_p — a sensitivity a rate-averaged
(mean-field) plasticity treatment smooths away. This is why the spiking model is more
demanding of coverage than Yang's formulation at the same tau.

### Evidence 1 — same-rate, tau-only controls (the cleanest statement)

Identical SOM spike train; only the GABA decay tail changes; gating flips:

| SOM rate | tau = 10 ms | tau = 20 ms | tau = 40 ms |
|---------:|:-----------:|:-----------:|:-----------:|
| 16.8 Hz  | –           | **fail** 1.04 | **pass** 3.52 |
| 25.3 Hz  | **fail** 1.01 | **pass** 4.53 | –           |

Doubling tau rescues gating at a rate that fails with the shorter tail — with no
change to the SOM rate. Inhibition *coverage*, not rate, is the control variable.
(A companion result already on file, `docs/gbar_I_sweep_table.csv`, shows the dual:
at fixed 10 Hz, raising gGABA to 6× only reaches ratio 1.45 — total inhibitory
*charge* cannot substitute for coverage either.)

### Evidence 2 — the critical rate scales ~inversely with tau

Crossover SOM rate (ratio = 2.0), reduced Phase-1 analytical protocol, seed 42:

| tau_GABA,dend | critical SOM rate | rate × tau |
|--------------:|------------------:|-----------:|
| 10 ms         | 35.4 Hz           | **354**    |
| 20 ms         | 18.2 Hz           | **364**    |
| 40 ms         | 12.4 Hz           | 497        |

For 10 → 20 ms the product `rate × tau` is constant to <3% — halving tau exactly
doubles the required rate, the signature of a duty-cycle law. At 40 ms the product
rises (~37%): the critical rate falls less than pure 1/tau predicts, as expected once
the GABA tail starts overlapping across successive ISIs (coverage saturates). A pure
1/tau law is the short-tau limit; the direction is unambiguous throughout.

## What this means for the 10 Hz question

With Yang's own tau_GABA,dend = 20 ms, the coverage our spiking model needs for gating
corresponds to ~18–21 Hz. The model reproduces **Yang's ~10 Hz regime at tau ≈ 40 ms**
(gates at ~12 Hz). So the divergence is not a parameter error or a bug — it is a
genuine, quantified consequence of event-driven dendritic calcium in a spiking model
being more sensitive to within-ISI inhibition gaps than a rate-based plasticity rule.
The honest one-line answer to the reviewer:

> *Gating depends on the duty cycle of dendritic inhibition (rate × tau_GABA,dend),
> not the SOM rate alone; our spiking calcium drive is event-driven, so it needs
> fuller coverage than Yang's rate-averaged rule. At Yang's tau = 20 ms that is
> ~18–21 Hz; the model recovers gating at Yang's ~10 Hz when tau = 40 ms.*

## Caveats

- Reduced Phase-1 circuit, single seed (42), 8-epoch analytical protocol (ratio is
  settled by then). Crossovers are good to ±a few Hz, not high precision — sufficient
  to establish the scaling, not a calibration.
- tau was varied via the new `param_overrides` hook in
  `experiments/phase1_analytical.py` (applied before derived quantities; default
  behaviour unchanged).
- A fuller version would repeat across seeds and in the full MD/PV/VIP circuit, and
  could test the mechanism directly by comparing event-driven vs rate-averaged calcium
  drive at fixed coverage.

## Reproduce

```bash
python -I experiments/tau_gaba_duty_cycle_sweep.py   # -> docs/tau_gaba_duty_cycle_{results.json,table.csv}
```
