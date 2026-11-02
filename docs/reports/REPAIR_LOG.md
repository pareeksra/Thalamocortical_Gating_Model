# Model Repair Log — Audit and Correction Phase

**Status as of 2026-08-22.** This file is the working record of the audit-and-repair
pass on the Thalamocortical Gating model. It captures what was found, what was
changed, what was deliberately *not* changed, and which decisions are blocked on
scientific input. Read this before touching the model.

Nothing here has been committed. All changes sit in the working tree on `main`.

---

## 1. Where the model stands

| | Before | Now |
|---|---|---|
| Validation suite | 5/6 (partly fictitious) | **4/6** |
| Standalone unit tests | none | **69 assertions across 5 files** |
| Branch-selective NMDA calcium | none | **21×** (0.076 shut vs 1.613 open) |
| Dendritic voltage separation | 2.3× gate ratio | **52 mV** (−62.4 vs −11.1 mV) |
| MD → PV arm | 0.00 Hz, inert | **7.7 → 123 Hz** over MD 0–40 |
| E/I balance | Pyr 253.8 Hz unopposed | **PV 50.1 / Pyr 36.9 Hz** |
| Silent-synapse drift | 0.500 → 0.784 | **holds at 0.500000** |
| rho confinement | escaped to −0.011 and +1.562 | **[0.0006, 0.8469]** |

Suite detail: Test 1 PASS · Test 2 PASS · **Test 3 FAIL** · Test 4 PASS · **Test 5 FAIL** · Test 6 PASS.

The plasticity machinery now demonstrably works in isolation. The full circuit does
not yet show branch selectivity, for one well-characterised structural reason
(section 6).

---

## 2. Files touched

**Added**

```
dendritic_io.py                  canonical dendritic transfer function (was 4 copies)
test_dendritic_io.py             9 assertions  + 2 characterised limitations
test_numpy_plasticity.py        17 assertions
test_postsynaptic_calcium.py    16 assertions
test_pv_arm.py                  10 assertions
test_dendritic_nmda.py          17 assertions
project_documentation.tex        rewritten (was untracked already)
REPAIR_LOG.md                    this file
```

**Modified**

```
README.md                        rewritten against the implementation
src/v2/equations.py              postsynaptic calcium, Mg gate, NMDA, noise gating
src/v2/parameters.py             + rate_bg_pv, weight_bg_pv
src/v2/MultiCompartmentalModel.py  duplicate dend_IO removed; bAP calcium wired
src/v2/InterneuronalCircuit.py   stale dend_IO copy marked dead
experiments/validate_model.py    Tests 2/3/4/5 instrumentation; NMDA + PV wiring
experiments/print_network_summary.py  rewritten to introspect live objects
experiments/demo_v2_zhang2025.py      bAP calcium + PV background wiring
experiments/sweep_phase_diagram.py    same
main_gating_figures.py           canonical dend_IO; bAP normalisation fix
emergent_gating_mechanistic_model.py  canonical dend_IO; bAP normalisation + exact integration
```

---

## 3. Repairs made, in order

### Instrumentation first
Three tests were defective and are now honest.

- **Test 4** rate check was one-sided (`< 200 Hz`), so total silence scored PASS. Added:
  ρ bounds, "PV responds to MD drive", "E/I opposition present".
- **Test 5** was named "Random Seed Reproducibility" but ran three *different* seeds, and
  `cv = std/mean if mean > 0 else 0` scored silence as PASS. Now runs seeds `[0,0,42,84]`:
  5a same-seed identity, 5b non-vacuity, 5c cross-seed CV.
- **Test 3** asserted only `w_b1 > w_b0` with no effect size — a **coin flip** (Monte Carlo:
  50.7% false-positive rate). It spuriously PASSED at ratio 1.02 during this session. Now
  requires ratio ≥ 1.10 **and** ≥ 2 SEM paired separation (3.1% false positive).

`print_network_summary.py` constructed no Brian 2 objects and printed seven wrong numbers;
it now reads `len(group)` / `len(synapses)` / `group.equations` from live objects and reports
realised connection probabilities alongside requested ones.

`dend_IO` was consolidated from four copies into `dendritic_io.py`, **provably
behaviour-preserving** (bit-identical over a 61×61 grid; all 8 figure checksums unchanged).

### `dend_IO` sign defect
Derived analytically rather than pattern-matched:

```
du/dinh = -[ q0 + (exc - m)/q2 ] / s
=> dv/dinh < 0 only when exc > q0*(4 + inh - q2)
   at exc = 0 the sign flips once inh > q2 - 4 = 2.5387 nS
```

`parameters.py` sets `vI_pyr = vRest_pyr = -70 mV`, making dendritic GABA_A purely
shunting, so an unexcited branch **must** sit at rest for every inhibition level. The raw
fit violated that by up to **29.89 mV**. Fixed by re-referencing to rest —
`V_rest + [f(exc,inh) − f(0,inh)]` — which leaves `d/dexc` untouched and changes none of
`q0..q3`. Resting error now **0.00 mV exactly**; spurious depolarisation 1.467 → 0.042 mV/nS.

Two residual shortfalls are recorded as bounded `KNOWN-LIMIT`, not hidden: a two-parameter
tanh cannot be made globally monotone in inhibition by re-referencing. Validated monotone
domain is `exc ≤ 65 nS`, 16× the models' operating range.

### Postsynaptic calcium
`Dend` has **no threshold and no reset — it never spikes**, so `on_post_plasticity` could
never have fired. That is why it was unattached and why `C_post_eff` was never defined.
The only viable carrier is the bAP machinery, and `norm_factor_Ca` normalises that
transient to a peak of **exactly 1.000** — the same scale as `C_pre = 1.0`. Connected:
`eqs_dend` gained the bAPCa trace (from `eqs_dend_only`), the bAP synapse injects
`norm_factor_Ca`, and plasticity reads `c_total = c + bAPCa_post`.

### NumPy calcium kernels — two mathematical errors
- The mechanistic bAP kernel injected `C_BAP` straight into the *rise* variable of a double
  exponential, which attenuates by 18.2×; with forward Euler at `dt/τ_rise = 0.25` the
  realised transient was **24× too small**. Fixed with a measured normalisation and exact
  exponential integration (peak error now 2e-16).
- The phenomenological trace used `norm = τd/(τd−τr) = 1.0714`, not the peak factor,
  leaving the peak at **82.4%** of intended. Corrected to `1.3001`.

### Mg²⁺ gating
Used the project's **own** parameterisation — `1/(1+exp(-(V-vHalfNMDA)/vSpreadNMDA))`,
already in `eqs_soma` — rather than importing the NumPy models' Jahr-Stevens form. Verified
identical: max difference 0.064, half-activation −20.53 vs −19.9 mV. Gate rises **17.4×**
from −70 to −30 mV.

### PV arm
The expected `iBaseline_pv` **current cannot work**: PV's f-I is a near-step because
`vThres − vReset` is only 5 mV at τ_m = 10 ms — rheobase 20.0 pA, 10 Hz needs 20.0003 pA,
40 Hz needs 20.5 pA. Copying SOM's 22 pA gives 74 Hz, not a baseline.

Used a background Poisson **conductance** instead — the project's own declared-but-unused
`rate_bgE` mechanism. `rate_bg_pv = 500 Hz` (the declared value), `weight_bg_pv = 0.25 nS`
**derived** to sit just below the ~0.4 nS needed for `V_inf = vThres`, so firing is
fluctuation-driven and graded. `p`, `n`, `g` untouched — p·n·g remains 3.0 nS (PV) vs
7.5 nS (VIP).

### ρ noise gating and clipping
Noise is now gated on calcium activity (`sqrt(ind_p + ind_d)`), which required switching
the plastic synapses to `method='heun'` — Brian 2's `euler` rejects state-dependent
(multiplicative) noise. A silent synapse now holds at **0.500000 exactly**. `attach_rho_clipper`
clamps ρ itself; note the clipper turns out to be redundant once the noise is gated, since
un-gated noise was the root cause of *both* excursions.

### Dendritic NMDA conductance
`iTotNMDA1`/`iTotNMDA2` were declared and never assigned; `gNMDA`, `alphaNMDA`,
`tauNMDARise`, `tauNMDADecay` were all unused. No formulation existed anywhere — checked
the whole repo, `InterneuronalCircuit.py` (no NMDA at all), and the `.pyc` files committed
in all 7 commits (identical bare declarations throughout, nothing ever deleted).

The formulation was nevertheless **identifiable from the parameters**:

- A linear (GABA_B-style) kernel gives `2.5 × 30 × 80 × 0.1 = 600 nS`, **150× the leak** —
  absurd. The saturating form bounds `s ∈ [0,1]` → 62 nS against a 75 nS ceiling.
- `alphaNMDA` exists *only* in the saturating form and is unused anywhere else.
- `iTotNMDA1 : amp` as a bare parameter is Brian 2's signature for a **summed-variable
  target**. Brian 2 confirmed this itself: *"Multiple 'summed variables' target the variable
  'iTotNMDA1'. Use multiple variables in the target group instead."* Two slots = two
  afferent pathways.

Implemented in `equations.py` only:

```
dx_nmda/dt = -x_nmda/tauNMDARise                              x_nmda += 1 on_pre
ds_nmda/dt = -s_nmda/tauNMDADecay + alphaNMDA*x_nmda*(1-s_nmda)
iTotNMDA{1,2}_post = -gNMDA*s_nmda*(V_post - vE_pyr)*mg_gate : amp (summed)
```

`eqs_synapse_plasticity` still resolves to slot 1 (API preserved);
`make_eqs_synapse_plasticity(2)` serves a second pathway. **NMDA is deliberately not scaled
by `w`** — in GB, `w` is AMPA efficacy, and making NMDA plastic would close a runaway loop.

---

## 4. Verified working

| Mechanism | Evidence |
|---|---|
| MD → VIP → SOM disinhibition | SOM 36.5 → 0.0 Hz as MD rises; VIP 35.2 Hz at MD 25 |
| Somatic-output gating | Pyr silent at MD 5 (gate shut), active at MD 20 (gate open) |
| Calcium kinetics | single-spike peak and 1/e decay exact; bAP peak error 2e-16 |
| NMDA current | matches `-gNMDA·Σs·(V−vE)·mg` to **≤0.02%** at 5 voltages; reverses to 0.0000 pA at `vE` |
| NMDA saturation | `s` bounded [0,1]; ratios 2.00/1.17/1.07 against rate ratios 2.50 |
| Mg gate | exact to 1e-9 over a 120× range |
| Branch-selective calcium | 21× (NMDA component) |
| PV arm | baseline 7.65 Hz, graded to 123 Hz, suppresses pyramidal 51.7% |
| LTP and LTD | NumPy 0.5 → 0.816 vs 0.527 (differing *only* in `g_inh`); Brian 2 480 Hz → LTP, 180 Hz → LTD |
| Stability | no NaN/Inf; ρ ∈ [0.0006, 0.8469]; w ∈ [0.002, 2.541] |

---

## 5. Open defects

**Test 3 fails — branch-uniform bAP calcium swamps the selective signal.** Fully
characterised (section 6). Not a parameter problem.

**Test 5 fails — the model is not bitwise reproducible under a fixed seed.** Same seed
gives PV 14.425 vs 14.275 Hz and Pyr 4.5 vs 5.5 Hz. Discovered by the Test 5 rewrite
(the old test could never have caught it, since it never ran a seed twice). **Undiagnosed.**

**Shared RNG stream couples plasticity to circuit noise** in the mechanistic model:
`dend_IO` feeds `simulate_calcium_poisson`, whose draw *counts* depend on `v_dend`, so any
change to the plasticity path reshuffles the interneuron noise. Reproducibility hazard.

**NumPy models remain sub-threshold at their own operating point** — `g_exc = 0.625 nS`
against a `dend_IO` mid-point of 34.4 nS (55× below). Calibration, deliberately untouched.

---

## 6. The bAP calcium problem — characterised, verdict reached, not yet acted on

### Measured

```
                NMDA Ca    bAP Ca    total
inhibited branch  0.076     7.343    7.419
free branch       1.613     7.343    8.956      selective ratio 21x -> 1.21x
```

`⟨bAPCa⟩ = rate × 36.40 ms` (analytic kernel area) predicts 7.32 at 201 Hz vs **measured
7.343**. The bAP term is branch-uniform, has no location dependence, no voltage dependence
and no saturation — while NMDA *does* saturate. So bAP wins at high rates by construction.

### Selectivity budget

```
 soma Hz   bAPCa  tot open  tot shut   ratio   outcome
       0   0.000     1.613     0.076   21.22   selective (LTD regime)
      37   1.347     2.960     1.423    2.08   SELECTIVE LTP     <- Test 4 sits here
      74   2.704     4.317     2.780    1.55   boundary
     201   7.316     8.929     7.392    1.21   selectivity LOST  <- Test 3 sits here
```

Selectivity is **abolished** above `r_lost = (θ_P − Ca_shut)/area ≈ 74.3 Hz`, and the ratio
decays as `1/r` because numerator and denominator share the additive uniform term.

### Audit verdict: **B — keep as an abstraction, explicitly qualified**

The decisive measurement: the project's double-exponential kernel and GB's
single-exponential jump differ by only **21% in area (36.40 vs 30.00 ms)**. The linear
unbounded accumulation is a property of **GB's own calcium model**, faithfully inherited —
so reformulating the kernel would *not* fix it. The problem is **regime**, not formulation.

Not verdict A, because unqualified the model silently produces non-selective LTP above
74 Hz, contradicting two documented requirements. Not verdict C, because every candidate
replacement (location-dependent attenuation, saturation, voltage dependence) needs either an
architectural feature the model lacks — there is **no location variable** — or a departure
from GB requiring provenance input that is unavailable.

### Qualifications B requires (not yet implemented)

1. Declare the validity envelope: postsynaptic rate below ~74 Hz.
2. Enforce it with the model's own mechanism (PV somatic gain control), which converts the
   limitation into a **testable prediction**: *PV-mediated gain control is a precondition
   for branch-specific plasticity.*
3. Record that `C_post = C_pre = 1.0` is a by-product of `norm_factor_Ca`, not a fitted choice.
4. Record that `tau_Ca_bAP_decay = tau_Ca_NMDA = 30 ms` — one value, two processes.
5. Record that the bAP term is branch-uniform and GB supplies no distribution rule.

### Test 3 audit

Test 3 builds Soma, Dend, SOM only — **no PV, VIP or MD** — driving SOM with a direct 25 pA
bias and `connect(j='0')`. That is *intentional unit isolation* (category A: intrinsic
dendritic gating) that the repairs made **obsolete**: it was sound while calcium was
presynaptic-only and the soma was irrelevant, but the soma is now part of the calcium
pathway, so the test isolates the input side and leaves the output side unconstrained.

PV **should** be included — because somatic rate is now a *control variable* of dendritic
calcium, not because it makes the test pass. **Guard against self-deception:** adding PV
moves Test 3 from fail to pass, so the fix must be validated across a range of somatic
rates inside the window, not at the single value where it passes.

---

## 7. Blocked on scientific decision

**The Graupner-Brunel provenance gate (unresolved, blocks all calibration).** Both files the
code cites — `data/parameters.txt`, `data/equations.txt` — **never existed** (not in any
commit). All seven constants arrived in one squashed "Initial commit". The only citations
anywhere are one docstring reference to "Graupner & Brunel 2012 Eq. 7" and
"Bhatt et al. 2009; Bhatt & Jahr 2012" for `CV_CA`. **Ten constants have no traceable
source:** `theta_d`, `theta_p`, `gamma_d`, `gamma_p`, `tau_rho`, `sigma`, `C_pre`,
`C_NMDA`, `C_bAP`, and Yang's `q[0..3]`.

Needs external verification:
1. Do θ_d=1.0, θ_p=2.78, γ_d=39.949, γ_p=177.552, τ=346.36 s, σ=3.35 **co-occur in one
   published parameter set**?
2. Does that set specify `C_pre`/`C_post` — and are they 0.371/0.957, 1.0/something, or neither?
3. Was it fitted to a **pairing** or a **rate/Poisson** protocol? This decides whether
   θ_p being unreachable by a single pair is expected or a defect.
4. Assumed `τ_Ca` and pre→post delay `D`?
5. For Yang et al. — do `q = [5.5592051, 9.64361681, 6.5386557, 0.7779744]` appear there, and
   **over what inhibitory range was the fit constrained**? `spread` reaches 2037 nS at
   inh = 35 nS, so that whole regime is extrapolation.
6. Does `CV_CA = 0.30` match Bhatt et al.?

**θ and the Mg gate are jointly inconsistent.** θ_D/θ_P were self-consistent with *ungated*
calcium at 33/93 Hz. The gate moves them to 108/301 Hz at −30 mV and 1880/5226 Hz at rest.
Not retuned; Test 2 derives its rates from the gate and prints the shifted boundary so the
inconsistency stays visible.

**The two model families are not on the same postsynaptic calcium scale.** Brian 2 has *no*
`C_post` constant at all; the NumPy models have `C_BAP = 0.957`. Unifying either way breaks
the other: adopting the NumPy amplitudes in Brian 2 drops ⟨c⟩ at 80 Hz from 2.400 to 0.890,
below θ_D.

**The repository contains two competing postsynaptic calcium designs** —
`on_post_plasticity` (`c += C_post_eff`, GB's form, structurally unusable) and the bAPCa
double exponential (in-house idiom, now connected). Which was authoritative is unknown.

**Other unresolved:** the `/tau` units inconsistency in Brian 2's `drho/dt` (γ terms 346×
stronger than the double well while noise sits at canonical amplitude); the NumPy models'
missing double well (monostable relaxation, so "bistable" figure titles are unsupported);
GB Eq. 7 variance overridden by a constant noise floor; `w1` = 3.0 vs 1.0 across models.

---

## 8. Do not change

θ_D, θ_P, all GB constants, calcium amplitudes (`C_pre`, `C_BAP`, `norm_factor_Ca`), any
firing or background rate, the 2 Hz MD floor, dendritic branch count, the PV/VIP p·n·g
architecture, the NMDA repair, the noise gating, the ρ clipper, `dend_IO`, and the calcium
kernel time constants.

---

## 9. Running things

There is no `python` on PATH and the system `python3` has no Brian 2.

```bash
export PY=/home/raghav/miniconda3/envs/myenv/bin/python   # 3.14.2, brian2 2.10.1

# unit tests -- fast
$PY test_dendritic_io.py            # 9  assertions, ~5 s
$PY test_numpy_plasticity.py        # 17 assertions, ~60 s
$PY test_dendritic_nmda.py          # 17 assertions, ~3 min
$PY test_postsynaptic_calcium.py    # 16 assertions, ~5 min
$PY test_pv_arm.py                  # 10 assertions, ~4 min

# full suite -- ~17 min, run detached
nohup $PY experiments/validate_model.py > /tmp/v.txt 2>&1 &

# figures
$PY main_gating_figures.py                        # ~3 s
$PY emergent_gating_mechanistic_model.py          # ~4 s
$PY experiments/print_network_summary.py          # instant, now genuinely introspects
```

Long runs exceed the 2-minute foreground limit — background them.

---

## 10. Recommended next step

Implement the verdict-B qualifications (section 6), starting with including PV in Test 3
and adding these tests **before** the change:

1. Selectivity-vs-rate curve asserting the `1/r` decay and `⟨bAPCa⟩ = rate × 36.40 ms`.
2. Selective-window boundary test asserting `r_lost ≈ 74 Hz`.
3. Branch-uniformity test documenting the present state (flips legitimately if the calcium
   model is ever reformulated).
4. Somatic-rate precondition in Test 3, so it fails loudly if the soma escapes the window.
5. Retention test for the documented no-catastrophic-forgetting claim.

Then resolve the provenance gate (section 7) before any calibration.
