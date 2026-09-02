"""
build_progress_report.py
=========================
Builds docs/Progress_Report.docx: a chronological, first-person-plural lab-notebook
narrative of the project, written for a PI. Every number in this script is copied from
a source file in the repo (README.md, docs/gamma_tau_analysis.md,
figures/paper_replications/measured_results.json, docs/phase1_alpha_operating_points.json,
docs/formula_comparison_table.csv, docs/gamma_tau_300s_checkpoints.json) or read directly
off a figure when no raw-data file exists for it (flagged inline where that happens).

This is a LIVING DOCUMENT: re-running this script regenerates the report from scratch.
To add a new dated entry, append a new `log_entry(...)` call and a new section at the
bottom (see the "CHANGE LOG" section) rather than editing history in place.

Saved to TWO locations on every run: the local repo copy (docs/Progress_Report.docx) and
Raghav's Google Drive sync folder (G:/My Drive/Progress_Report.docx), per his instruction
that both stay in sync after every append. If the Drive path is unreachable (drive not
mounted, sync client not running), the local copy still saves and the script reports the
Drive failure rather than silently skipping it.
"""
import os
import shutil
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GDRIVE_PATH = r'G:\My Drive\Progress_Report.docx'
FIG = os.path.join(PROOT, 'figures')
DOCS = os.path.join(PROOT, 'docs')

doc = Document()

# ---------------------------------------------------------------------------
def h1(text):
    doc.add_heading(text, level=1)

def h2(text):
    doc.add_heading(text, level=2)

def h3(text):
    doc.add_heading(text, level=3)

def p(text, italic=False, bold=False):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.italic = italic
    run.bold = bold
    return para

def flag(text):
    """A visually distinct callout for an honest flag/inconsistency."""
    para = doc.add_paragraph()
    run = para.add_run('Flag: ')
    run.bold = True
    run.font.color.rgb = RGBColor(0xB0, 0x00, 0x00)
    run2 = para.add_run(text)
    run2.italic = True
    return para

def figure(relpath, caption, width_in=6.0):
    full = os.path.join(PROOT, relpath)
    if not os.path.exists(full):
        flag(f"figure '{relpath}' was listed as a source but does not exist on disk; skipped.")
        return
    doc.add_picture(full, width=Inches(width_in))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cap.add_run(caption)
    run.italic = True
    run.font.size = Pt(9)

def table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Light Grid Accent 1'
    hdr = t.rows[0].cells
    for i, htext in enumerate(headers):
        hdr[i].text = str(htext)
        for run in hdr[i].paragraphs[0].runs:
            run.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
    doc.add_paragraph()
    return t

FIG_N = [0]
def fig_num():
    FIG_N[0] += 1
    return FIG_N[0]

# ===========================================================================
# TITLE
# ===========================================================================
title = doc.add_heading('Progress Report', level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run('Thalamocortical Gating & Cognitive Flexibility Model — a running lab notebook')
r.italic = True
r.font.size = Pt(13)

note = doc.add_paragraph()
note.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = note.add_run('This is a living document. Sections are dated and appended chronologically; '
                 'nothing above is rewritten once written. Compiled 2026-08-31.')
r.italic = True
r.font.size = Pt(9)
doc.add_paragraph()

p("This report tells the story of the thalamocortical gating project in the order things "
  "actually happened, in plain language, with the numbers we actually measured. It is meant "
  "to be read like a lab notebook: what we set out to do, what we built, what worked, what "
  "didn't, and what we're still unsure about. Where we found a number in one file that "
  "disagreed with a number in another, we say so rather than picking the one that looks "
  "better.")

# ===========================================================================
# 1. WHAT WE SET OUT TO DO
# ===========================================================================
h1('1. What we set out to do')

p("The question behind this project is whether a single biological mechanism can explain "
  "how the mediodorsal (MD) thalamus helps the prefrontal cortex switch between contexts "
  "without needing to erase what it already learned. Concretely: can MD thalamic drive "
  "control which dendritic branch of a pyramidal neuron is allowed to undergo synaptic "
  "plasticity, so that different contexts write their learning onto different physical "
  "branches instead of overwriting the same synapses?")

p("We built this by grafting together two published models that, on their own, don't "
  "talk to each other. Yang, Murray & Wang (2016) describe a spiking, reduced-compartment "
  "pyramidal neuron with a dendritic disinhibitory circuit (VIP inhibits SOM, SOM inhibits "
  "the dendrite, PV inhibits the soma) and a calcium-based Graupner-Brunel plasticity rule "
  "on the dendrite. That model has no thalamus in it at all — just an abstract \"control "
  "input.\" Zhang et al. (2025) describe a trained rate RNN with an actual MD thalamus that "
  "projects to interneurons in a cell-type-specific way (MD's GRIK4-expressing cells to PV, "
  "its DRD2-expressing cells to VIP) and improves the network's behavioral performance under "
  "uncertainty. Zhang's model has no dendrites and no synaptic plasticity — it's a trained "
  "network, not a mechanistic one.")

p("The project's plan, stated in the README, is: replicate Yang's single-neuron gating "
  "mechanism, graft on Zhang's MD→interneuron wiring, and see whether MD activity can "
  "control which branch gates. We want to be precise about how far that arc has actually "
  "gone, because it's easy to overstate: as of the last full verification pass "
  "(2026-08-26), the project reproduces Yang's gating mechanism at the single-neuron level, "
  "borrows only Zhang's wiring labels (not its trained task, its psychometric behavior, or "
  "its PFC↔MD feedback loop), and has not yet been scaled to anything like Yang's ~3,000-"
  "neuron network (this project runs 1 pyramidal soma, 2 dendrites, and 20 of each "
  "interneuron type). We inherit Yang's reduced multi-compartment cell, its VIP→SOM→dendrite "
  "disinhibition motif, its NMDA plateau nonlinearity, and its Graupner-Brunel calcium "
  "plasticity rule with its published constants; we inherit Zhang's MD→PV and MD→VIP "
  "connections and nothing else of Zhang's model.")

p("There are three independent implementations of this idea living in the repository, and "
  "they matter a lot for reading any given figure correctly:")

table(
    ['Model', 'What it is', 'Plasticity status'],
    [
        ['A — Brian 2 spiking network (model/, experiments/)',
         'The full spiking circuit: multi-compartment pyramidal cell, PV/SOM/VIP LIF '
         'interneurons, MD as a Poisson input, native Brian 2 Graupner-Brunel synapses.',
         'Working — the only model whose single-synapse LTP/LTD actually functions.'],
        ['B — Phenomenological NumPy (numpy_models/main_gating_figures.py)',
         'A proof-of-concept with hardcoded dendritic inhibition instead of simulated '
         'interneurons.',
         'Inert — falls back to a random walk (see Section 4).'],
        ['C — Emergent mechanistic NumPy (numpy_models/emergent_gating_mechanistic_model.py)',
         'Inhibition emerges from noisy interneuron rates driven by Poisson MD spike counts.',
         'Inert, same reason as B.'],
    ]
)

p("Everything from here on is about Model A, because it's the only one where plasticity "
  "does anything. Models B and C are frozen illustrative sketches; their status hasn't "
  "changed since the last verification pass and we don't revisit them below.")

# ===========================================================================
# 2. PHASE 1
# ===========================================================================
h1('2. Phase 1 — building and validating the single-neuron gating mechanism')

p("Model A's connectivity, as built, looks like this:")
figure('figures/network_architecture.png',
       f'Figure {fig_num()}. Model A network connectivity: MD thalamus and cortical '
       'pathway as Poisson inputs, VIP/SOM/PV interneurons, and the plastic pathway onto '
       'the two dendritic branches. Weights and connection probabilities read from '
       'model/parameters.py.')

p("Phase 1's job was to get one pyramidal neuron with two dendritic branches to show "
  "branch-specific gating: a disinhibited branch should potentiate under a plateau-driving "
  "input, while a branch under SOM inhibition should not, using Yang's own calcium and "
  "plasticity equations. Two things had to be fixed before that would happen at all.")

h2('2.1 Two calibration bugs, found and fixed')

p("Bug 1 was that the excitatory drive onto the dendrite was too weak to reach Yang's NMDA "
  "plateau. Yang's dendritic half-activation is g₁/₂ = 5.56·(4 + g_inh) nS (his Eq. 22); "
  "with a disinhibited branch (g_inh ≈ 2 nS) that's about 33 nS, and with a SOM-inhibited "
  "branch (g_inh ≈ 35 nS) it's about 217 nS. The fix was driving the pathway at 80 Hz with "
  "Yang's own in-vivo dendrite-soma coupling (g_c = 0.8 nS, `gEachCouple_pyr_vivo` in "
  "parameters.py) instead of the 4.0 nS the experiments had been using — that's enough to "
  "put the free branch on the plateau while the shunted branch stays near rest.")

p("Bug 2 was that the calcium model wasn't actually Yang's. Yang's dendritic calcium has "
  "two components: an NMDA component that's a leaky integral of the NMDA current (his "
  "Eq. 13, scaled by κ_NMDA = 0.371 /pA), and a VGCC component from back-propagating action "
  "potentials, modeled as per-spike bumps (his Eq. 14, peak κ_VGCC = 0.957). The two NumPy "
  "models (B and C) instead treat both as fixed per-spike jumps, which caps a single "
  "pairing's calcium at 0.371 + 0.957 = 1.328 — below θ_p = 2.78, so LTP is structurally "
  "impossible in B and C no matter what else changes. Model A now integrates the NMDA "
  "current properly as a leaky integral, so calcium can accumulate past θ_p under a "
  "sustained plateau.")

p("Once both were fixed, `experiments/phase1_single_neuron_gating.py` (exc = 80 Hz, "
  "post = 10 Hz, coupling = 0.8 nS, seed 42) measured a free branch that potentiates "
  "(ρ ≈ 0.78) against an inhibited branch that does not (ρ ≈ 0.02) — the free/inhibited "
  "ratio quoted in the project README is about 43.")

h2('2.2 Quantitative replication against both papers')

p("`experiments/validate_vs_papers.py` reruns four specific comparisons against the source "
  "papers and saves the raw numbers to "
  "`figures/paper_replications/measured_results.json`. We pulled them directly from that "
  "file rather than from any narrative description of it.")

h3('V1 — dendritic input-output function (Yang Fig. 2c)')
p("Yang's closed-form half-activation is g₁/₂ = 5.56·(4 + g_inh). We measured it directly "
  "in the model at five inhibition levels:")
table(
    ['g_inh (nS)', '0.0', '2.0', '10.0', '20.0', '35.0'],
    [['measured g₁/₂ (nS)', '22.24', '33.36', '77.83', '133.42', '216.81']],
)
p("This matches Yang's formula to the digit at every level — the paper_replications README "
  "calls this an exact match, and the arithmetic checks out (5.56·4 = 22.24, 5.56·6 = 33.36, "
  "and so on).")
figure('figures/paper_replications/replicated_YANG2016_fig2c_dendritic_IO.png',
       f'Figure {fig_num()}. Dendritic depolarization vs. excitatory conductance at five '
       'inhibition levels, replicating Yang Fig. 2c. Half-activation shifts with inhibition '
       'exactly as predicted by Eq. 22 (table above).')

h3('V2 — rate-dependent plasticity and the LTP-threshold shift (Yang Fig. 7b)')
table(
    ['presynaptic rate (Hz)', '20', '40', '60', '80', '100', '120'],
    [
        ['ρ, free branch', '0.580', '0.770', '0.780', '0.792', '0.811', '0.811'],
        ['ρ, SOM-inhibited branch', '0.0184', '0.0181', '0.0180', '0.0122', '0.0196', '0.0162'],
    ],
)
p("The free branch crosses ρ = 0.5 (into the LTP regime) somewhere around 20 Hz and "
  "saturates near ρ ≈ 0.79–0.81. The inhibited branch stays pinned near ρ ≈ 0.01–0.02 at "
  "every single rate we tried, 20 through 120 Hz — inhibition doesn't just weaken "
  "potentiation, it removes the branch from the game entirely across the whole range. That's "
  "the qualitative effect Yang reports (a directional match, not an exact numeric one, since "
  "Yang's Fig. 7b is itself qualitative).")
figure('figures/paper_replications/replicated_YANG2016_fig7b_LTP_vs_rate.png',
       f'Figure {fig_num()}. Steady-state ρ vs. presynaptic pathway rate for the free and '
       'SOM-inhibited branches, replicating Yang Fig. 7b.')

h3('V3 — branch-specific gating at Yang\'s operating point (Yang Fig. 7d-e)')
p("At exc = 80 Hz / post = 10 Hz — Yang's own operating point — validate_vs_papers.py "
  "measured ρ_free = 0.7917, ρ_inhibited = 0.01221, a free/inhibited ratio of 64.83.")
figure('figures/paper_replications/replicated_YANG2016_fig7de_branch_gating.png',
       f'Figure {fig_num()}. Branch-specific gating at Yang\'s operating point (exc 80 Hz, '
       'post 10 Hz): free branch ρ=0.792, inhibited branch ρ=0.012, ratio 64.8.')

h3('V4 — Zhang wiring: does MD control the interneurons the way Zhang says it should?')
table(
    ['MD drive (Hz)', '0', '5', '10', '20', '30', '40'],
    [
        ['PV rate (Hz)', '7.1', '13.4', '22.2', '52.3', '83.7', '126.7'],
        ['SOM rate (Hz)', '36.0', '36.0', '29.9', '0.0', '0.0', '0.0'],
        ['VIP rate (Hz)', '0.0', '0.0', '0.2', '16.4', '49.0', '92.9'],
        ['Pyramidal rate (Hz)', '8.7', '4.7', '3.3', '0.7', '0.7', '0.0'],
    ],
)
p("As MD drive rises, VIP rises (0 → 93 Hz), which suppresses SOM (36 → 0 Hz) — the "
  "disinhibition pathway working as Zhang's wiring predicts. PV rises in parallel (7 → 127 "
  "Hz), the separate gain-control arm. This is a qualitative check only: Zhang's model is a "
  "trained rate RNN doing a cognitive task, and we're only borrowing its connectivity "
  "labels, not reproducing any of its behavioral results.")
figure('figures/paper_replications/replicated_ZHANG2025_MD_interneuron_control.png',
       f'Figure {fig_num()}. Population firing rates of VIP, SOM, PV, and the pyramidal '
       'soma as a function of MD drive, replicating the qualitative direction of Zhang\'s '
       'MD→PV / MD→VIP wiring.')

flag("Three different measurements of what is nominally the same headline number (the "
     "Phase-1 free/inhibited ratio) disagree with each other by close to 50%. The README's "
     "top-line banner reports ratio ~43 (ρ_free ≈ 0.78, ρ_inhibited ≈ 0.02), from "
     "`phase1_single_neuron_gating.py`. `validate_vs_papers.py`'s V3 measurement (above, and "
     "also quoted in Validation_Report.docx) gives ratio 64.83 (ρ_free = 0.7917, "
     "ρ_inhibited = 0.01221) at the same nominal operating point. And our own re-measurement "
     "of the pre-refactor equations in the γ/τ audit (Section 4 below) gives yet a third "
     "value, ratio 42.76 (ρ_free = 0.779, ρ_inhibited = 0.018) — close to the README's number "
     "but not identical to it, and both are far from validate_vs_papers.py's 64.83. All "
     "three runs use seed 42 and the same nominal parameters, so this is consistent with "
     "the reproducibility problem the README already documents elsewhere (its Test 5 flag: "
     "same seed, PV rate 14.425 vs 14.275 Hz across runs) rather than three unrelated bugs. "
     "We are not picking one of these numbers as \"the real one\" — we are flagging that the "
     "inhibited branch's ρ, in particular, seems to land anywhere from 0.012 to 0.020 "
     "depending on exactly which script and which moment measured it.")

# ===========================================================================
# 3. PHASE 2
# ===========================================================================
h1('3. Phase 2 — noise robustness and a schizophrenia-like disruption model')

p("Phase 2 asks two practical questions about the full spiking circuit "
  "(`model/full_circuit.py`, which adds PV/VIP/SOM/MD to the reduced Phase-1 pair of "
  "branches): how much biological noise can the gating mechanism tolerate before it stops "
  "working, and what happens to gating if we simulate a specific, literature-grounded "
  "circuit disruption (NMDA hypofunction, the standard ketamine model of schizophrenia-like "
  "cortical dysfunction)?")

h2('3.1 Noise parameterization')

p("`experiments/phase2_snr_breakdown.py` scales three biologically distinct noise sources "
  "together under one `noise_level` parameter: an MD noise Poisson input (separate from the "
  "signal channel, which is held at 0 Hz throughout this sweep so we're looking at the "
  "network's resting disinhibition state), vesicle-release variance on the plastic NMDA "
  "pathway (coefficient of variation up to 0.30), and background membrane-potential "
  "fluctuation on SOM and VIP. Gating selectivity is defined the same way as Section 2, "
  "ρ_free / ρ_inhibited, averaged over 3 seeds per noise level, each a 3-second run.")

flag("Neither this sweep nor the ketamine sweep below has a saved raw-data file (no JSON, "
     "CSV, or log) — only the rendered PNG. The numbers we report in this section were read "
     "directly off the plotted points and error bars, not from stored values, so treat them "
     "as approximate to the nearest unit rather than exact.")

p("Reading the curve: gating selectivity starts around 62 at noise = 0, drifts down through "
  "the high 30s and 20s as noise increases to 0.25–0.40 (with wide, overlapping error bars "
  "in that range — the script itself flags noise = 0.30–0.40 as an \"unstable transition "
  "zone\" where individual seeds disagree about whether gating held), and then collapses "
  "sharply: by noise = 0.45 the mean ratio has dropped below 1.5 (the script's own breaking-"
  "point threshold) and stays essentially at 1 — no gating — all the way out to noise = 2.0.")

figure('figures/phase2_snr_curve.png',
       f'Figure {fig_num()}. Branch-specific gating selectivity vs. noise level (n=3 seeds '
       'per point). Selectivity falls from ~62 at zero noise through an unstable transition '
       'zone (noise 0.30-0.40) to full collapse (ratio < 1.5) at noise = 0.45 and beyond.')

h2('3.2 The ketamine / NMDA-hypofunction simulation')

p("`experiments/phase2_schizophrenia_sim.py` implements a specific, targeted disruption "
  "rather than generic noise. Ketamine and related NMDA-receptor antagonists preferentially "
  "block NMDA receptors on fast-spiking and VIP-type interneurons at sub-anesthetic doses "
  "(the script cites Krystal et al. 1994 and Homayoun & Moghaddam 2007 for this), which is a "
  "standard circuit-level model of schizophrenia-like cortical dysfunction. The script "
  "implements this at the one synapse the model actually has for that pathway — the MD→VIP "
  "excitatory weight — and linearly attenuates it from fully intact (scale 1.0) to fully "
  "blocked (scale 0.0), holding MD drive fixed at 25 Hz throughout.")

p("The stated prediction, before running anything, was: block MD→VIP, and VIP can no "
  "longer be recruited by MD, so SOM is no longer suppressed regardless of what MD is "
  "doing; SOM sits at its own resting baseline and tonically inhibits the branch it targets, "
  "which then can't potentiate even under an MD signal that would normally have opened the "
  "gate for it.")

p("That is what we see. At 0% and 34% block, both branches potentiate to about the same "
  "level (ρ ≈ 0.80–0.81) — MD at 25 Hz successfully drives VIP (≈29 Hz), VIP suppresses SOM "
  "down near 0 Hz, and with SOM quiet, neither branch is under any dendritic shunt, so both "
  "learn. At 67% and 100% block, the SOM-targeted branch's ρ collapses to about 0.015–0.02 "
  "while the free branch stays at ρ ≈ 0.80 — SOM has risen back to its baseline rate of "
  "about 36.5 Hz because VIP can no longer be driven (VIP rate falls to about 0 Hz at these "
  "block levels), and that baseline SOM firing is now enough to permanently shunt its "
  "target branch regardless of the ongoing 25 Hz MD signal.")

p("The interesting thing here is not that the circuit's output gets weaker under this "
  "disruption — it's that MD's control over which branch gets to learn is what breaks. Below "
  "about 50% block, MD can still open the gate for its target branch; above that, the branch "
  "is stuck closed no matter what MD says. That's the schizophrenia-relevant reading: a loss "
  "of context-dependent flexibility, not a global silencing of learning.")

figure('figures/phase2_ketamine_failure.png',
       f'Figure {fig_num()}. Left: steady-state ρ for the free and SOM-targeted branches vs. '
       'MD→VIP synaptic block. Right: SOM and VIP population rates over the same sweep, at '
       'MD = 25 Hz. Branch-specific gating is intact below ~50% block and collapses above it, '
       'tracking SOM\'s return to its un-suppressed baseline rate.')

# ===========================================================================
# 4. THE AUDIT — three divergences from Yang 2016
# ===========================================================================
h1('4. The audit — three divergences from Yang 2016')

p("Separately from building the model forward, we went back and checked the model against "
  "Yang's own Methods section line by line, looking specifically for places where the "
  "implementation quietly departs from the paper it's supposed to be faithful to. We found "
  "three, of very different character: one was an honest omission that we could just wire "
  "in, one was a calibration choice that turned out to have a real cost once we tested it "
  "properly, and one was a straightforward units bug that took real work to run down and "
  "ended up reshaping the whole plasticity implementation (Section 5).")

h2('4.1 Divergence 1 — the SOM→PV synapse was declared but never wired')

p("Yang 2016 includes a SOM→PV inhibitory connection at P_SOM→PV = 0.8 (used in his Fig. "
  "6). The project already had a parameter for its weight (`gGABA_pv`) and the receiving "
  "side of the equations (`eqs_pv`'s `gTotGABA` channel) sitting there unused — the "
  "connection probability itself hadn't been declared, and no Synapses object was ever "
  "built to use it, so `iGABA` on the PV cells was always exactly zero. This was a genuinely "
  "unfinished piece of Yang's circuit, not a deliberate simplification.")

p("We fixed this by adding `p_som2pv = 0.8` to `md_params` in `model/parameters.py` and "
  "wiring the actual Synapses object in `model/full_circuit.py` "
  "(`s_som2pv = Synapses(SOM, PV, on_pre='gTotGABA_post+=gGABA_pv', ...)`, connected at "
  "that probability). This divergence is now closed.")

h2('4.2 Divergence 2 — the SOM baseline firing rate was roughly 4x too high')

p("Yang 2016 sets SOM neurons' baseline firing rate at about 10 Hz via a 150 pA input "
  "current (Methods p. 11). The project's SOM cells were running at roughly 36–40 Hz under "
  "a 22 pA bias current — about four times too fast. This mattered for more than just "
  "accuracy: a too-fast interneuron baseline was part of what drove the older bAP-swamping "
  "problem documented in `docs/REPAIR_LOG.md`.")

p("We recalibrated the bias current analytically and then swept it empirically: SOM's "
  "f-I curve is a near-step function (C_som = 20 pF, g_L,som = 1 nS gives τ_m = 20 ms, and "
  "the 5 mV gap between threshold and reset means the whole useful range sits within a "
  "fraction of a pA of rheobase). A 0.01 pA sweep landed on iBaseline_som = 20.04 pA, which "
  "gives 10.00 Hz in isolation, matching the analytic LIF inter-spike-interval formula to "
  "rounding. `model/parameters.py`'s `som_params` was updated to this value.")

flag("Recalibrating the SOM rate to match Yang's 10 Hz turned out not to be a clean win. "
     "When we tested it inside the actual Phase-1 gating protocol under the newly-"
     "implemented analytical plasticity (Step 2d, Section 5.4 below), branch-specific gating "
     "broke down almost completely — both branches potentiated to nearly the same degree "
     "(ratio 1.02, versus 2.81 at the project's working 25 pA / ~63 Hz setting). So this "
     "divergence is fixed in the sense that the SOM cell now fires at the rate Yang reports, "
     "but that fix is currently in tension with the model's own headline gating result, which "
     "was calibrated — and, we discovered, depends — on the faster rate. Section 5.4 works "
     "through why, and it turns out to implicate a different part of the model (calcium "
     "sensitivity, not the SOM rate itself) than we expected going in.")

flag("The same nominal bias current produces very different firing rates depending on which "
     "circuit it sits in. The README reports 22–25 pA giving ~36–40 Hz, measured in the full "
     "circuit and in `demo_v2_zhang2025.py`. Our own measurement of Phase-1's own reduced "
     "two-branch circuit at 25 pA (`docs/gamma_tau_analysis.md`, Section 3) gives 63.3 Hz — "
     "not 36-40 Hz — for what is nominally the same current. A SOM bias current is therefore "
     "not a portable number; it has to be recalibrated for whatever surrounding network it's "
     "embedded in, which is worth keeping in mind before quoting any interneuron rate out of "
     "context.")

h2('4.3 Divergence 3 — the γ/τ units bug (the one that reshaped Section 5)')

p("This one took the most digging. Graupner & Brunel (2012) — the source of the project's "
  "continuous dρ/dt equation — divide the entire right-hand side of their plasticity ODE "
  "by the time constant τ, including the potentiation and depression terms. "
  "`model/equations.py`, as committed, divided only the double-well restoring term by τ; "
  "the γ_p/γ_d terms were instead multiplied by the calcium-threshold indicator times a "
  "bare `1/second`. The ratio between what was written and the canonical form is exactly "
  "(1/second)/(1/τ) = τ = 346.36 — the γ terms were running about 346 times stronger than "
  "Graupner-Brunel's own equation calls for. (The line already carried a code comment "
  "flagging this as \"346x stronger\"; we independently re-derived the same number from the "
  "paper before trusting the comment.)")

p("This matters for more than amplitude. With τ = 346.36 s, canonical Graupner-Brunel "
  "dynamics are slow — multi-minute — and the project's Phase-1 protocol runs for 3 "
  "simulated seconds. The 346x term is what let a 3-second run show any ρ separation at all; "
  "dividing correctly by τ, as the paper actually specifies, should need run durations "
  "comparable to τ itself (hundreds of seconds) to see a comparable effect, if the effect "
  "is even there with these particular γ/θ/τ values.")

h3('What we tried: does canonical Graupner-Brunel gate if we just give it enough time?')

p("We swapped in the canonical form (both γ terms and the double-well term divided by τ) "
  "in an isolated test — `equations.py` itself was left untouched — and ran it through "
  "Phase-1's exact circuit at two timescales.")

table(
    ['Form', 'ρ₀ (inhibited)', 'ρ₁ (free)', 'ratio', 'duration'],
    [
        ['As-committed (346x term)', '0.018', '0.779', '42.76', 'T = 3 s'],
        ['Canonical (γ/τ)', '0.424', '0.638', '1.51', 'T = 3 s'],
    ],
)

p("Over 300 simulated seconds (checkpointed every 30 s; full precision in "
  "`docs/gamma_tau_300s_checkpoints.json`), the canonical form's ratio oscillated rather "
  "than converging:")

table(
    ['t (s)', '30', '60', '90', '120', '150', '180', '210', '240', '270', '300'],
    [['ratio', '1.82', '2.16', '2.06', '2.83', '2.42', '2.49', '1.79', '1.49', '2.24', '2.34']],
)

p("Mean ratio across the ten checkpoints: 2.16 ± 0.37 (SD). This was directionally real — "
  "the free branch was above the inhibited branch at every single checkpoint, 10 out of 10 "
  "— but weak and clearly not converging by t = 300 s (0.87τ): it peaked at t = 120 s (2.83) "
  "and dropped to 1.49 by t = 240 s before partially recovering. ρ₀ never approached the "
  "~0.01–0.02 the 346x-boosted version reaches in 3 seconds; it wandered between 0.26 and "
  "0.46, much closer to the shared 0.5 starting point than to either stable well minimum. "
  "The best-case ratio over 300 seconds (2.83) was an order of magnitude short of the "
  "as-committed model's 42.76, and this single 300-second run cost about 1.7 hours of "
  "wall-clock time — so \"just run it longer\" was not a cheap thing to keep testing.")

p("We did not conclude from this that canonical Graupner-Brunel definitely fails — only "
  "that patching the units bug in place and hoping it settles out over more time was not "
  "obviously going to reproduce anything like the project's headline numbers, and confirming "
  "that one way or the other would cost many more hours of wall-clock per data point. That's "
  "what motivated the decision, described next, to stop patching the continuous ODE and "
  "implement Yang's actual analytical plasticity equations instead of the Graupner-Brunel "
  "ODE the project had been using as a stand-in.")

# ===========================================================================
# 5. THE PLASTICITY REFACTOR
# ===========================================================================
h1('5. The plasticity refactor — switching to Yang\'s real Eqs. 32-35')

p("The γ/τ investigation above left us with a continuous ODE that was hard to run "
  "correctly and possibly didn't reproduce the target result even patched. Yang's own paper "
  "doesn't actually integrate a continuous dρ/dt during a trial — it uses a closed-form, "
  "per-epoch analytical update (his Eqs. 32-35) derived from the same Graupner-Brunel "
  "formalism, restated for a bistable UP/DOWN synapse. We decided to implement that formula "
  "directly rather than continue debugging the ODE.")

h2('5.1 Step 2a — is a simpler approximation already good enough?')

p("Before committing to the full implementation, we ran a cheap diagnostic. One of the "
  "NumPy figure models (Model C) already contains a simpler, deterministic relaxation "
  "formula — ρ_new = ρ̄ + (ρ_init − ρ̄)·exp(−(Γ_p+Γ_d)/τ), with no variance term — and we "
  "wanted to know whether it was secretly equivalent to Yang's real formula at the "
  "operating points this project actually uses.")

p("We first measured, rather than assumed, the calcium-threshold-crossing times "
  "(α_d, α_p) that Phase-1's actual circuit produces over its 3-second protocol "
  "(`docs/phase1_alpha_operating_points.json`):")

table(
    ['branch', 'α_d (s)', 'α_p (s)'],
    [
        ['inhibited (branch 0)', '0.975 ± 0.039', '0.000 (never crosses θ_p)'],
        ['free (branch 1)', '2.969 ± 0.011', '2.864 ± 0.071'],
    ],
)

p("Then we evaluated both formulas — Model C's linear relaxation and Yang's real Eqs. "
  "32-35 — using Yang's own published constants for both, so the only thing that differed "
  "was the formula, not the numbers (w₀=0, w₁=3, ρ*=0.5, σ=3.35, τ=346.36 s, "
  "γ_d=39.949, γ_p=177.552):")

table(
    ['branch', 'ρ_linear', 'ρ_Yang', 'U (switch to UP)', 'D (switch to DOWN)'],
    [
        ['inhibited', '0.4468', '0.4959', '0.0015', '0.0096'],
        ['free', '0.7600', '0.8604', '0.7854', '0.0647'],
    ],
)

p("For the coarse free/inhibited ratio, the two formulas were nearly interchangeable at "
  "these specific points (linear 1.70 vs. Yang 1.74). But per-branch, they disagreed by up "
  "to about 0.10 in ρ, in a way that flips sign across the (α_d, α_p) plane rather than "
  "being a constant offset, and the variance term the linear form drops (Eq. 33) turned out "
  "to be large — σ_ρ ranges 0.25 to 0.53 across the operating range we tested, which is "
  "comparable to the entire [0,1] span of ρ. Concretely: the linear form under-potentiates "
  "the free branch (0.76 vs. Yang's 0.86) and manufactures a spurious ~10% depression on the "
  "inhibited branch (0.5 → 0.447) that Yang's formula says shouldn't happen in one 3-second "
  "epoch (0.5 → 0.496, essentially no change) because the epoch is far too short relative to "
  "τ for the synapse to actually flip DOWN.")

figure('figures/formula_comparison.png',
       f'Figure {fig_num()}. Left/middle: ρ_new vs. calcium-threshold time for the '
       'potentiation and depression arms, linear relaxation vs. Yang Eqs. 32-35. Right: '
       'the signed difference (ρ_Yang − ρ_linear) across the full (α_d, α_p) plane, with '
       'Phase-1\'s measured inhibited and free operating points marked.')

p("Conclusion: the simpler formula was coincidentally close enough for the single-epoch "
  "ratio at these specific points, but it is a genuinely different function of the calcium "
  "trace, not a valid stand-in, and the differences compound across repeated epochs (the "
  "linear form relaxes deterministically every epoch; Yang's formula makes probabilistic, "
  "closer-to-all-or-none jumps). This confirmed it was worth implementing the real "
  "equations rather than leaning on the approximation.")

h2('5.2 The w₁ finding')

p("While tracing through the formula we hit a real discrepancy worth resolving before "
  "writing any code: Model C defines its UP-state weight as W1 = 1.0, while "
  "`model/parameters.py` (Model A) and Model B both use w1 = 3.0. Yang's paper is explicit "
  "about which is his own value: \"For convenience, we set the weight of DOWN state to "
  "w0 = 0 and the weight of UP state w1 = 3.\" He also fixes the physical scale a paragraph "
  "later — the naive synapse sits at w_pre = 1, corresponding to a real conductance of "
  "2.5 nS, and after learning the actual conductance is w_post × 2.5 nS. So w is a "
  "dimensionless multiplier on a real conductance, running 0 to 3, not something normalized "
  "to [0,1].")

p("Tracing the code path confirmed both conventions are internally self-consistent, just "
  "answering different questions. In Model A, w = w0 + (w1−w0)·clip(ρ, 0, 1) is consumed "
  "directly as `gTotAMPA_post += w*gAMPA` — with w1 = 3.0, this genuinely scales a physical "
  "AMPA conductance, and it already matches Yang's convention. In Model C, "
  "W = W0 + (W1−W0)·ρ with W1 = 1.0 makes W identical to ρ itself — it's used only for "
  "plotting and selectivity indices, never multiplied against a conductance, so within "
  "Model C's own code the 1.0 is a legitimate [0,1] display normalization, not a bug.")

p("It is, however, the wrong constant to plug into Yang's actual update formula: "
  "w_post = w_pre(1−D) + (w1−w_pre)U requires w1 = 3, because with w1 = 1 and a starting "
  "w_pre = 1.5 (ρ = 0.5), the potentiation term (w1 − w_pre) becomes −0.5 and potentiation "
  "would flip sign into depression. Decision: `src/v2/plasticity.py` hard-defaults to "
  "w1 = 3 everywhere in the analytical path, matching Model A and Yang; Model C's own W1 = "
  "1.0 is left untouched in its own file, where it's correct for what it's used for.")

flag("This report was asked to read parameters from `src/v2/parameters.py`, but no such "
     "file exists — `src/v2/` currently contains only `plasticity.py` (and its `__init__.py`). "
     "All plasticity constants quoted in this report (θ_d, θ_p, γ_d, γ_p, τ, σ, w0, w1) come "
     "from `model/parameters.py`'s `plasticity_params` dict, which is what `plasticity.py` "
     "and the experiment scripts actually import from.")

h2('5.3 Implementation')

p("Three pieces of code came out of this. `src/v2/plasticity.py` implements "
  "`yang_synapse_update(alpha_d, alpha_p, rho_init, ...)`, Yang's Eqs. 32-35 exactly — the "
  "erf-based UP/DOWN switching probabilities with the σ_ρ² variance term — with a docstring "
  "citing Yang 2016, Methods p. 12, Eqs. 32-35 by equation number. A silent or fully-shunted "
  "synapse (no calcium above either threshold) returns U = D = 0 and holds ρ at its current "
  "value, matching the old gated-noise behavior where a silent synapse shouldn't drift.")

p("`model/equations.py`'s old continuous dρ/dt double-well ODE is commented out, not "
  "deleted, under the label \"Legacy continuous ODE — superseded by analytical epoch update "
  "per Yang 2016 Eqs. 32-35.\" ρ is now a plain settable parameter rather than an integrated "
  "state variable. We flagged, rather than silently broke, the consequence: six other "
  "scripts that relied on the ODE to evolve ρ over time — `validate_vs_papers.py`, "
  "`validate_model.py`, `demo_v2_zhang2025.py`, `sweep_phase_diagram.py`, "
  "`print_network_summary.py`, and `model/full_circuit.py` (which is what Phase 2's SNR and "
  "ketamine sweeps in Section 3 run on) — will now hold ρ static at its initial value unless "
  "they're migrated to call the new epoch update themselves. That migration hasn't happened "
  "yet.")

flag("Because of the point above, the Phase 2 figures in Section 3 (the SNR sweep and the "
     "ketamine simulation) were generated under the old continuous-ODE plasticity, before "
     "this refactor. Now that the ODE has been superseded by the analytical update, those "
     "two sweeps will need to be rerun under the new plasticity before their specific "
     "numbers (the noise-level breaking point at 0.45, the ~50% MD→VIP block threshold) "
     "can be treated as still current. The qualitative story they tell is probably still "
     "right, but the numbers are not guaranteed to carry over.")

p("`experiments/phase1_analytical.py` is the refactored Phase-1 pipeline: it builds the "
  "same circuit once, holds ρ fixed as a parameter, and per 3-second epoch reads each "
  "synapse's α_d/α_p from a compiled Brian 2 counter (integrated at the full 0.02 ms "
  "simulation timestep, reset every epoch), calls `yang_synapse_update` per synapse, and "
  "writes the new ρ back in. Each epoch costs about 74 seconds of wall-clock, dominated by "
  "a Python-level soma-dendrite coupling operation, so the script checkpoints its state to "
  "disk after every epoch and resumes automatically — this is what let us run 15-epoch "
  "trajectories across more than one process invocation without losing progress.")

h2('5.4 Step 2c — does it actually gate over multiple epochs?')

p("We ran 15 consecutive 3-second epochs at Phase-1's working settings (exc = 80 Hz, "
  "post = 10 Hz, coupling = 0.8 nS, SOM bias = 25 pA, seed 42):")

table(
    ['epoch', '0', '1', '2', '3', '5', '8', '11', '13', '15'],
    [
        ['free ρ (branch 1)', '0.500', '0.863', '0.916', '0.924', '0.924', '0.925', '0.924', '0.926', '0.924'],
        ['inhibited ρ (branch 0)', '0.500', '0.476', '0.471', '0.460', '0.419', '0.392', '0.367', '0.341', '0.329'],
    ],
)

p("Final: free ρ = 0.924 (w = 2.771), inhibited ρ = 0.329 (w = 0.986), ratio = 2.81. The "
  "free branch compounds up to the UP state and plateaus by epoch 2–3 — consistent with its "
  "own calcium drive (α_p ≈ 2.9 s of 3 s, giving ρ̄ ≈ 0.81 and a per-epoch switching "
  "probability U ≈ 0.79). The inhibited branch never crosses θ_p in any epoch and drifts "
  "monotonically down under a weak but persistent depression pull, still declining at epoch "
  "15. The pass criteria we set (free ρ > 0.7, inhibited ρ ≤ 0.5) were both met, and — "
  "importantly — this is not a repeat of the old 346x bug: the ratio here grows honestly "
  "from an actual difference in how much calcium each branch accumulates.")

figure('figures/analytical_plasticity_trajectory.png',
       f'Figure {fig_num()}. Epoch-by-epoch ρ trajectory (mean ± SD over 20 synapses per '
       'branch) under the analytical Yang plasticity, SOM bias = 25 pA. Free branch '
       'saturates near 0.92 by epoch 3; inhibited branch declines monotonically toward '
       '0.33 by epoch 15. Final ratio 2.81.')

h2('5.5 Step 2d — does it still gate at Yang\'s own SOM baseline?')

p("With the analytical plasticity validated at the project's working SOM setting, we "
  "went back to Divergence 2 (Section 4.2) and re-tested it: does gating survive if we "
  "actually use the corrected, Yang-matched SOM bias (20.04 pA, measured at 10.14 Hz by a "
  "spike monitor) instead of the 25 pA / ~63 Hz the working protocol has been using?")

p("It does not. Same 15-epoch protocol, only the SOM bias changed:")

table(
    ['quantity', '25 pA (working setting)', '20.04 pA (Yang\'s ~10 Hz)'],
    [
        ['measured SOM rate', '~63 Hz', '10.14 Hz'],
        ['inhibited branch α_p (final epoch)', '~0.02 s', '2.59 s'],
        ['inhibited branch ρ (final)', '0.329', '0.910'],
        ['free branch ρ (final)', '0.924', '0.924'],
        ['ratio', '2.81', '1.02'],
    ],
)

p("At 10.14 Hz, the inhibited branch's α_p jumps from essentially zero to 2.59 seconds out "
  "of the 3-second epoch — the SOM shunt is no longer enough to keep the branch off the "
  "NMDA plateau, its calcium crosses θ_p for most of the epoch, and it potentiates almost "
  "identically to the free branch. This is the same failure mode described to us from an "
  "earlier attempt under the old continuous-ODE plasticity (both branches potentiating "
  "together, reported at the time as ratio ≈ 1.04) — but we want to be careful here: that "
  "earlier number was relayed to us as project history rather than found in any committed "
  "script output or log, so we can't independently verify it from the files in the "
  "repository. What we can say with a saved log and a spike-monitor-confirmed SOM rate is "
  "that the same qualitative failure reappears under the new analytical plasticity, for a "
  "reason we could pin down precisely (below).")

figure('figures/analytical_plasticity_trajectory_som10hz.png',
       f'Figure {fig_num()}. Same protocol as Figure {FIG_N[0]-1}, SOM bias lowered to 20.04 '
       'pA (measured 10.14 Hz). The two branches\' trajectories overlap almost completely — '
       'gating is abolished (ratio 1.02).')

p("Yang's Methods (p. 12) state his SOM→dendrite inhibition explicitly: total conductance "
  "G_SOM→dend = 40 nS, each SOM cell at ~10 Hz before disinhibition, τ_GABA,dend = 20 ms, "
  "giving a time-averaged conductance ḡ_I = 10 Hz × 0.02 s × 40 nS = 8.0 nS, with a "
  "disinhibition threshold g_I,th = 4.0 nS. Checking the model's own wiring: 10 SOM cells "
  "at gGABA = 4.0 nS each is exactly 40 nS total, with τ_GABA = 20 ms — the model already "
  "matches Yang's spec exactly. At the measured 10.14 Hz, that gives ḡ_I ≈ 10.14 × 0.02 × "
  "40 ≈ 8.1 nS, matching Yang's own 8.0 nS default almost precisely.")

p("So the model reproduces Yang's specified inhibition at 10 Hz and still fails to gate. "
  "That rules out the naive explanation (\"gGABA is too weak\"). Working backward, the "
  "project's working 25 pA / 63 Hz setting corresponds to ḡ_I ≈ 63 × 0.02 × 40 ≈ 50 nS — "
  "roughly six times Yang's own specified inhibition. In other words, gating in this "
  "spiking implementation currently requires about six times more dendritic shunting than "
  "Yang's rate-model math says should be necessary, which means the mismatch is most likely "
  "in the branch's calcium/NMDA sensitivity (how readily it reaches the plateau under a "
  "given amount of shunting), not in the GABA conductance itself. This also means the Step "
  "2c result above (ratio 2.81) was obtained at roughly six times Yang's specified "
  "inhibition — worth keeping in mind as a caveat on that number.")

p("We have not changed any parameter in response to this. Three options are on the table: "
  "strengthen gGABA so 10 Hz delivers the ~50 nS the model currently needs (departs from "
  "Yang's stated 40 nS by ~6x, but keeps SOM at its correct rate); reduce the branch's "
  "calcium sensitivity (lower κ_NMDA/gNMDA, or raise θ_p) so Yang's 8 nS is sufficient "
  "(keeps SOM→dendrite conductance faithful to Yang, but reopens the whole Phase-1 calcium "
  "calibration and requires re-validating the free branch still gates); or document this as "
  "a known calibration gap between the rate-model math and the spiking implementation "
  "without forcing a fit. We proposed running one more cheap diagnostic first — sweeping "
  "the effective inhibitory conductance from ~8 to ~55 nS to find exactly where the "
  "inhibited branch's α_p collapses to zero — before picking one of the three, so we'd know "
  "whether the model's real requirement is a modest 2x over Yang (making option two "
  "feasible) or the full 6x (favoring option one with an explicit caveat, or option three).")

# ===========================================================================
# 6. WHAT'S NEXT AND WHAT'S STILL UNCERTAIN
# ===========================================================================
h1('6. What\'s next, and what we\'re still unsure about')

p("Immediately open: which of the three Step 2d recalibration options to pursue (or "
  "whether to run the suggested inhibitory-conductance sweep first) is an open decision, "
  "not yet made.")

p("Once that's settled, several pieces of cleanup follow directly from the plasticity "
  "refactor: the six scripts listed in Section 5.3 that still assume the old continuous ODE "
  "need to be migrated to the epoch-update pattern before their outputs can be trusted "
  "again, and that specifically includes rerunning the Phase 2 SNR and ketamine sweeps "
  "(Section 3) under the new plasticity, since their current numbers were generated before "
  "this refactor.")

p("Some older, unresolved items from the last full verification pass are still open and "
  "unaffected by anything in this report: `validate_model.py`'s Test 3 (branch-specific "
  "gating) still uses an old, unpinned-post-rate configuration that Phase-1's dedicated "
  "script was written to supersede, and needs to be rewritten to Yang's 10 Hz protocol and "
  "rerun; Test 5 (reproducibility under a fixed seed) is still failing and undiagnosed, and "
  "is very plausibly the same underlying looseness we flagged in Section 2.2's three-way "
  "ratio discrepancy; and the network-scale stage (Yang's ~3,000-neuron network vs. this "
  "project's 1-soma/2-dendrite/20-interneuron circuit) hasn't been started.")

p("Models B and C (the two NumPy figure models) remain plasticity-inert for the same "
  "structural reason documented in Section 2.1 (Bug 2) and haven't been touched in this "
  "phase of work; whether they're worth repairing or should simply be retired in favor of "
  "Model A is an open question we haven't addressed.")

p("Underneath all of this is the honest uncertainty this report tried not to smooth over: "
  "we don't yet have a single, reproducible number for Phase-1's headline gating ratio "
  "(Section 2.2's flag), and Step 2d just showed that the model's gating mechanism, as "
  "currently calibrated, depends on dendritic inhibition several times stronger than Yang's "
  "own math says it should need. Both of those are worth resolving before treating any "
  "specific ratio in this project as a stable, citable result.")

# ===========================================================================
# 7. 2026-08-30 UPDATE
# ===========================================================================
h1('7. 2026-08-30 update — git safety, confirming the Phase 2 migration gap, '
   'and inhibition sweeps')

p("Three follow-ups from Section 6's open items, done in order.")

h2('7.1 A week of uncommitted work is now in git')

p("Everything documented in Sections 3-6 above — the analytical plasticity "
  "implementation, the formula-comparison diagnostic, both Phase 2 sweeps, and this "
  "report itself — had been sitting as untracked or modified files since 2026-08-26/27, "
  "never committed. It is now: commit 212505b, 36 files changed (3247 insertions).")

h2('7.2 Confirming the Phase 2 migration gap directly')

p("Section 5.3 already flagged, by inference, that `full_circuit.py` and the two Phase 2 "
  "scripts were not migrated to the analytical plasticity update and that Section 3's "
  "figures might therefore be stale. We checked this directly rather than leaving it as "
  "an inference.")

flag("Confirmed. File timestamps establish the order of events precisely: both Phase 2 "
     "figures (phase2_snr_curve.png, phase2_ketamine_failure.png) were generated on "
     "2026-08-27 (00:54 and 00:33), and full_circuit.py was itself last edited 2026-08-27 "
     "03:05 — all before model/equations.py was edited on 2026-08-29 16:35 to comment out "
     "dρ/dt and declare `rho : 1` as a bare parameter (Section 5.3). Reading "
     "full_circuit.py's build_gating_circuit() directly confirms it does a single "
     "net.run(T) and reads sb0.rho/sb1.rho straight afterward, with no epoch loop and no "
     "call into src/v2/plasticity.py — the exact pattern that needs the epoch-update "
     "machinery experiments/phase1_analytical.py added. Consequence: rerunning "
     "phase2_snr_breakdown.py or phase2_schizophrenia_sim.py today, unmodified, would "
     "hold rho frozen at its initialized 0.5 on both branches for the entire run, at "
     "every noise_level / md2vip_scale / seed combination — ratio identically 1.0, not "
     "just numerically close to it. The existing figures (ratio ~62 at zero noise, "
     "branch-0 rho falling to ~0.01-0.02 under full MD->VIP block) sit in the same range "
     "as the old 346x-bugged ODE's dynamics (Section 4.3), not the new analytical "
     "update's honest ~2.81 ceiling (Section 5.4) — consistent with having been generated "
     "before the bug was even fixed, let alone before the switch to the analytical "
     "update. Both Phase 2 figures must be treated as retired until full_circuit.py is "
     "migrated to the same epoch-loop + yang_synapse_update pattern as "
     "experiments/phase1_analytical.py and both sweeps are rerun.")

p("docs/gamma_tau_analysis.md was also updated with one sentence confirming that its "
  "opening question (Section 4.3's gamma/tau timescale question — does canonical "
  "Graupner-Brunel gate given enough time?) is superseded by the switch to the "
  "analytical epoch-based update, which does not depend on simulation duration for "
  "convergence.")

h2('7.3 SOM-rate and gGABA inhibition sweeps')

p("Step 2d (Section 5.5) left three options on the table for reconciling Yang's ~10 Hz SOM "
  "rate with this model's need for far more dendritic shunting to gate. Rather than pick "
  "one blind, we ran two sweeps, each the full 15-epoch analytical protocol per point "
  "(three points reused from prior runs, described inline).")

h3('Sweep 1 — SOM rate, gGABA held at Yang-matched 40 nS total')

table(
    ['measured SOM rate (Hz)', '10.14', '16.87', '21.49', '25.29', '28.80', '33.09',
     '39.04', '46.49', '55.22', '63.30'],
    [['ratio (free/inhib)', '1.02', '1.04', '5.51', '5.58', '4.95', '4.29', '3.63',
      '3.12', '2.91', '2.81']],
)

figure('figures/som_rate_sweep.png',
       f'Figure {fig_num()}. Sweep 1: gating ratio and final rho vs. measured SOM rate, '
       'gGABA held at the Yang-matched 40 nS total. The transition from fail to pass is a '
       'near step-function between 16.87 and 21.49 Hz, not a gradual climb.')

p("The crossover is sharp, not gradual: ratio sits at ~1.0-1.04 for 10.14-16.87 Hz, then "
  "jumps to 5.51 at 21.49 Hz — a step, not a slope, consistent with the same near-threshold "
  "steepness noted in Section 4.2's SOM f-I curve. The minimum functional SOM rate for "
  "ratio > 2 is therefore roughly 2x Yang's own ~10 Hz, not the far larger multiple the "
  "original 63 Hz-vs-10 Hz comparison (Section 5.5) implied. Past the crossover, ratio "
  "*declines* monotonically from a peak of 5.58 at 25.29 Hz back down to 2.81 at 63.3 Hz "
  "(the project's original working point) — more SOM drive past the crossover does not mean "
  "more gating; it means less, though still comfortably above threshold.")

h3('Sweep 2 — gGABA, SOM held at Yang\'s ~10.15 Hz')

table(
    ['gGABA per synapse (nS)', '4.0', '6.0', '8.0', '10.0', '12.0', '14.0', '16.0', '18.0',
     '20.0', '22.0', '24.0'],
    [['ratio (free/inhib)', '1.02', '1.04', '1.06', '1.11', '1.12', '1.15', '1.19', '1.23',
      '1.29', '1.35', '1.45']],
)

figure('figures/gbar_I_sweep.png',
       f'Figure {fig_num()}. Sweep 2: gating ratio and final rho vs. gGABA per synapse, SOM '
       'held at Yang\'s measured ~10.15 Hz. Ratio climbs slowly and smoothly, never '
       'approaching the ratio=2 criterion even at 6x Yang\'s conductance.')

p("No gGABA value in the tested range — up to 24.0 nS/synapse (240 nS total, 6x Yang's own "
  "40 nS spec) — recovers gating at Yang's SOM rate. The climb from 1.02 to 1.45 is smooth "
  "and decelerating, not a step; extrapolating the same trend would need on the order of "
  "50 nS/synapse (roughly 12x Yang's value) to reach ratio=2, which is well outside any "
  "range defensible as \"the same synapse, just recalibrated.\"")

h3('The two sweeps together point to a temporal-patterning effect, not a conductance-amount effect')

p("Comparing the two sweeps by time-averaged inhibitory conductance (ḡ_I = rate x "
  "tau_GABA,dend x gGABA_total) rather than by rate or conductance alone is revealing. "
  "Sweep 1's crossover sits between 16.87 Hz (ḡ_I ≈ 13.5 nS, fails) and 21.49 Hz "
  "(ḡ_I ≈ 17.2 nS, ratio 5.51) — only about 1.7-2.1x Yang's own 8.0 nS default, not the 6x "
  "the Section 5.5 diagnosis estimated from comparing only the 10 Hz and 63 Hz endpoints. "
  "Sweep 2's best point (24 nS/synapse at 10.16 Hz) reaches ḡ_I ≈ 48.8 nS — nearly 3x "
  "*higher* than Sweep 1's crossover ḡ_I — and still only manages ratio 1.45.")

flag("Two conditions with comparable, or even reversed, time-averaged inhibitory "
     "conductance produce opposite gating outcomes depending on whether that conductance "
     "arrives as frequent small GABA events (high SOM rate) or infrequent large ones (low "
     "rate, boosted per-synapse gGABA). This points to the dendrite's NMDA plateau being "
     "sensitive to the temporal duty cycle of inhibition, not just its time-average: with "
     "tau_GABA,dend = 20 ms and a 10 Hz SOM rate (100 ms mean ISI), the GABA conductance "
     "fully decays for most of the inter-spike interval, leaving gaps long enough for the "
     "branch to reach the NMDA plateau and accumulate calcium regardless of how large each "
     "individual GABA event is. At >=20 Hz (<=50 ms ISI, closer to a few tau_GABA), "
     "consecutive events overlap enough to hold the branch below plateau continuously. This "
     "is a genuine mechanistic finding, not just a negative result, and it directly answers "
     "why Sweep 2 could not compensate for Sweep 1's rate deficit by raising conductance "
     "alone.")

p("Reading this against the three Step 2d options: option A (raise gGABA at Yang's rate) "
  "is empirically ruled out within any defensible range — Sweep 2 tops out at ratio 1.45 "
  "even at 6x conductance, and the trend says reaching ratio=2 this way would need "
  "roughly 12x. Option B (reduce calcium/NMDA sensitivity so Yang's 8 nS suffices) was not "
  "directly tested by either sweep, but the temporal-patterning finding gives it a "
  "concrete mechanistic target: it would need to make the plateau's activation slow or "
  "inertial enough to bridge a ~100 ms gap between SOM spikes, which is a specific, "
  "testable hypothesis rather than a blind parameter search. Option C (document the gap) "
  "is now much better supported than a bare admission of mismatch — the gap has a specific, "
  "explicable mechanism (duty cycle vs. NMDA plateau kinetics) rather than being an "
  "unexplained ~6x scaling problem. Sweep 1 also surfaces a fourth possibility the original "
  "framing didn't consider: the minimum SOM rate for reliable gating is only about 2x "
  "Yang's, not 6x — a substantially smaller, more defensible departure from the paper than "
  "the number this project had been working with. This decision is Raghav's to make; we "
  "have not changed any parameter in response to these results.")

# ===========================================================================
# 8. 2026-08-31 UPDATE
# ===========================================================================
h1('8. 2026-08-31 update — 25 Hz SOM baseline adopted, and Phase 2 rerun honestly '
   'under the analytical plasticity update')

p("Section 7 ended with a decision left open (which of the Step 2d options to take on the "
  "SOM-rate gap) and a debt outstanding (both Phase 2 figures retired as stale, generated "
  "before the plasticity migration and the bug fix — Section 7.2). This entry closes both. "
  "It records the calibration choice we actually committed to the code, then reports the "
  "Phase 1 re-confirmation and the first honest rerun of both Phase 2 sweeps under the "
  "epoch-based analytical update. Every number below is copied from a JSON written by the "
  "rerun itself (docs/phase2_snr_sweep_results.json, docs/phase2_ketamine_sweep_results.json, "
  "figures/validation_vs_papers/results.json) or from the parameters.py comment that records "
  "the calibration.")

h2('8.1 The SOM baseline is now set to ~25 Hz, on a duty-cycle argument')

p("Section 7.3's two sweeps did the deciding. The clean finding there was that gating is "
  "governed by the temporal duty cycle of dendritic inhibition — whether GABA covers the gap "
  "between SOM spikes relative to tau_GABA,dend = 20 ms — and not by the time-averaged "
  "inhibitory charge (cross-referenced: Section 7.3, \"the two sweeps together\"). Yang's own "
  "~10 Hz rate leaves ~100 ms inter-spike gaps, far longer than the 20 ms GABA decay, so the "
  "branch reaches its NMDA plateau between spikes no matter how large each GABA event is "
  "(Sweep 2 topped out at ratio 1.45 even at 6x Yang's conductance). Sweep 1 located the "
  "fail->pass step between 16.87 Hz (ratio 1.04) and 21.49 Hz (ratio 5.51), with the peak at "
  "25.29 Hz (ratio 5.58).")

flag("We set the SOM bias current to 20.9 pA, calibrated to 25.29 Hz in Phase-1's reduced "
     "circuit — the sweep's peak point — rather than to Yang's 10 Hz (model/parameters.py, "
     "iBaseline_som). This is a ~2.5x departure from Yang's reported rate, but it is now a "
     "*justified* one: >= ~20 Hz is the rate at which 20 ms of GABA coverage stops being "
     "outrun by the inter-spike interval, which is a specific biophysical criterion rather "
     "than an unexplained recalibration. Two honest caveats are recorded in the code and "
     "kept here: (i) the value is NOT portable across circuits — the same 20.9 pA produces a "
     "different rate depending on what else is wired to SOM, so full_circuit.py must measure "
     "its own SOM rate and be checked against the same >= ~20 Hz target rather than "
     "inheriting the number; and (ii) this is still a departure from the paper we are "
     "modelling, so the gap is documented, not hidden (Step 2d option C), now with a "
     "mechanism attached.")

h2('8.2 Phase 1 gating re-confirmed under the 25 Hz default')

p("With the 25 Hz baseline in place, we re-ran the Phase-1 single-neuron analytical "
  "protocol to confirm the headline branch-specific gating result still holds — this is the "
  "number Section 2.2 flagged as not yet stable across implementations, so re-pinning it "
  "under the committed calibration matters.")

table(
    ['quantity', 'value'],
    [['free-branch rho (uninhibited)', '0.9249'],
     ['inhibited-branch rho', '0.1658'],
     ['gating ratio (free / inhibited)', '5.5786']],
)

figure('figures/analytical_plasticity_trajectory_som25hz_default.png',
       f'Figure {fig_num()}. Phase-1 analytical plasticity trajectory under the committed '
       '25 Hz SOM default: the free branch potentiates to rho ~0.92 while the SOM-inhibited '
       'branch is held down to rho ~0.17, a gating ratio of 5.58.')

p("This sits essentially on top of the sweep's own peak (ratio 5.58 at 25.29 Hz, Section "
  "7.3) and is reproduced independently by the paper-replication battery below (V3: ratio "
  "5.50). For the first time in this project the Phase-1 headline ratio agrees to within "
  "~1.5% across three separate code paths, which is the stability Section 2.2 said was "
  "missing. It is an honest ~5.6, not the ~43-62 the earlier bugged/ODE runs reported.")

h2('8.3 Phase 2 rerun — the first honest sweeps under analytical plasticity')

p("Section 7.2 retired both Phase 2 figures because they were generated before the "
  "plasticity migration (frozen rho, ratios in the old bugged ~62 range). Both scripts were "
  "migrated to the epoch-loop + analytical-update pattern and rerun from scratch. The point "
  "of comparison is therefore qualitative: does the *phenomenon* survive an honest "
  "plasticity model, and where does it now break — not a like-for-like delta against the "
  "retired numbers.")

h3('8.3a Noise robustness (Phase 2B) — gating collapses as noise starves the SOM rate')

table(
    ['noise level', '0.0', '0.25', '0.30', '0.35', '0.40', '0.45', '0.50', '>=0.75'],
    [['gating ratio', '3.30', '2.77', '2.30', '1.73', '1.10', '1.02', '1.00', '~1.00'],
     ['measured SOM rate (Hz)', '25.3', '42.2', '38.6', '29.7', '16.7', '6.7', '1.8', '~0']],
)

figure('figures/phase2_snr_curve.png',
       f'Figure {fig_num()}. Phase 2B: gating ratio vs. injected noise level under the '
       'analytical update and 25 Hz SOM baseline. Selectivity falls and stays below 1.5 from '
       'noise level 0.40 onward; the collapse tracks the SOM rate dropping through the '
       '~20 Hz duty-cycle threshold identified in Section 7.3.')

p("The breaking point is a noise level of ~0.35-0.40: ratio holds above 2 through 0.30 "
  "(2.30), is marginal at 0.35 (1.73), and has collapsed to 1.10 by 0.40, staying below 1.5 "
  "thereafter. The mechanism ties directly back to Section 7.3: noise degrades the measured "
  "SOM rate, and gating fails almost exactly where that rate crosses below the ~20 Hz "
  "duty-cycle threshold — at noise 0.40 the SOM rate has fallen to 16.7 Hz (below "
  "threshold, ratio 1.10), while at 0.30 it is still 38.6 Hz (above, ratio 2.30). So Phase "
  "2B is not an independent robustness result; it is the Section 7.3 duty-cycle finding seen "
  "again through a different knob. The high ratio_sem at noise 0.0 (1.16 on a mean of 3.30) "
  "is worth noting — the zero-noise point is the noisiest across seeds, which we have not "
  "yet diagnosed.")

flag("Breaking point did shift meaningfully vs. the retired figures, but the shift is in "
     "magnitude, not existence. The phenomenon (noise abolishes branch-specific gating) "
     "survives the honest plasticity model, but the peak ratio is ~3.3, not the retired "
     "~62 — the collapse now happens from a realistic ceiling, and it has an explicit cause "
     "(SOM rate falling through the duty-cycle threshold) rather than being an unexplained "
     "fall from an inflated number.")

h3('8.3b MD->VIP disinhibition (Phase 2C) — the schizophrenia/ketamine failure mode')

table(
    ['MD->VIP scale', '1.0 (intact)', '0.66', '0.33', '0.0 (full block)'],
    [['gating ratio', '1.00', '1.00', '3.29', '3.42'],
     ['SOM rate (Hz)', '0.0', '1.3', '25.3', '25.3'],
     ['VIP rate (Hz)', '28.4', '4.0', '0.0', '0.0']],
)

figure('figures/phase2_ketamine_failure.png',
       f'Figure {fig_num()}. Phase 2C: gating ratio vs. MD->VIP drive scale. Intact MD->VIP '
       'drive (scale 1.0) fires VIP at 28 Hz, which silences SOM (0 Hz) and abolishes gating '
       '(ratio 1.0); attenuating MD->VIP restores SOM to its 25 Hz baseline and recovers '
       'gating (ratio ~3.4).')

p("The circuit logic reads cleanly: strong MD->VIP drive fires VIP (28 Hz at intact scale), "
  "VIP inhibits SOM to silence (0 Hz), and with SOM below the duty-cycle threshold gating is "
  "abolished (ratio 1.00). Attenuating MD->VIP releases SOM back to its 25 Hz baseline and "
  "gating returns — ratio 3.29 at scale 0.33 and 3.42 at full block. The transition is a "
  "step between scale 0.66 (ratio 1.00, SOM 1.3 Hz) and 0.33 (ratio 3.29, SOM 25.3 Hz), the "
  "same near-threshold sharpness seen in Section 7.3's rate sweep. Once again the pass/fail "
  "line coincides with SOM crossing ~20 Hz — the three Phase-2 knobs (noise, MD->VIP drive, "
  "and the Section 7.3 direct rate sweep) all break at the same underlying place.")

flag("This is the same qualitative failure mode the retired figure showed (excess MD->VIP "
     "disinhibition breaks gating — the model's proposed schizophrenia/ketamine analogue), "
     "so the breaking point did not move in kind: gating is lost once MD->VIP scale exceeds "
     "~0.33-0.5. What changed is the honest ceiling it falls from (~3.4, not the retired "
     "~62) and that the failure now has an explicit intermediary — VIP silencing SOM below "
     "the duty-cycle threshold — rather than an unexplained collapse.")

h2('8.4 Paper-replication battery still sane under the new calibration')

p("Finally, the four-panel validation-against-papers battery was rerun end-to-end under the "
  "analytical update and 25 Hz baseline (figures/validation_vs_papers/, results.json). The "
  "question is whether recalibrating SOM broke any of the qualitative behaviours the model "
  "is supposed to reproduce. It did not — all four remain directionally correct.")

table(
    ['panel', 'what it checks', 'result — still sane?'],
    [['V1', 'dendritic input-output vs. dendritic inhibition',
      'Yes. Half-activation conductance rises monotonically with inhibition '
      '(22 -> 217 nS as inh goes 0 -> 35 nS); V at a fixed 25 nS drive drops from '
      '-31 mV (no inh) to -69 mV (35 nS) — inhibition shifts the dendritic threshold '
      'rightward, as expected.'],
     ['V2', 'LTP (final rho) vs. presynaptic rate, free vs. inhibited branch',
      'Yes. Free-branch rho rises with rate (0.88 -> 0.93 over 20-120 Hz) while the '
      'inhibited branch stays suppressed (0.46 -> ~0.16); the free/inhibited gap widens '
      'with rate.'],
     ['V3', 'branch-specific gating ratio at 80 Hz exc / 10 Hz post',
      'Yes. free 0.925, inhibited 0.168, ratio 5.50 — independently reproduces the '
      'Phase-1 headline (5.58, Section 8.2) to ~1.5%.'],
     ['V4', 'MD-driven interneuron recruitment',
      'Yes. As MD rate goes 0 -> 40 Hz, PV climbs (6.5 -> 119 Hz) and VIP climbs '
      '(0 -> 86 Hz) while VIP-driven SOM is suppressed (24.7 -> 0 Hz) and pyramidal '
      'output falls (18 -> 0 Hz) — the disinhibitory motif behaves as designed.']],
)

figure('figures/validation_vs_papers/v3_branch_gating.png',
       f'Figure {fig_num()}. Validation panel V3: branch-specific gating under the committed '
       'calibration reproduces the Phase-1 headline ratio (5.50) via an independent code path.')

p("Nothing in the battery contradicts the 25 Hz recalibration; the recalibration changed the "
  "operating point, not the qualitative physiology. The one honest reservation carried "
  "forward from Section 7 is unchanged: these are all self-consistency and directional "
  "checks against the paper's *reported behaviours*, not a fit to the paper's raw data, and "
  "the network-scale replication (Yang's ~3,000-neuron network) still hasn't been started "
  "(Section 6 open item).")

h2('8.5 Where this leaves things')

p("The Section 7.3 decision is now committed in code (25 Hz SOM, with the caveats above), "
  "the Phase-1 headline ratio is stable at ~5.6 across three code paths for the first time, "
  "and both Phase 2 sweeps plus the paper battery have been rerun honestly under the "
  "analytical update — clearing the debt Section 7.2 opened. The recurring structural "
  "result across every Phase-2 knob is that gating passes or fails at a single place: "
  "whether SOM stays above the ~20 Hz duty-cycle threshold. The open items that remain are "
  "the ones this entry did not touch: the non-portability of iBaseline_som into "
  "full_circuit.py (needs its own rate measurement), the undiagnosed zero-noise variance in "
  "Phase 2B, Test 5's seed-reproducibility failure (Section 7), and the un-started "
  "network-scale stage.")

h1('9. 2026-09-02 update — SOM baseline relocked to 30 Hz via a full-circuit '
   'reliability sweep')

h2('9.1 The reduced-vs-full circuit mismatch, and a new evidence rule')

p("Section 8's reliability claims — Test 5's seed-44 failure and the ~1.5% cross-code-path "
  "stability figure — were both measured in the reduced Phase-1 circuit "
  "(phase1_single_neuron_gating.py / phase1_reliability_sweep.py), not in "
  "model/full_circuit.py, which is the circuit every Phase 2 result and every number in "
  "this report actually comes from. Section 4.2 had already flagged that the same iBaseline_"
  "som pA value produces a different SOM rate in the two circuits (25 pA measured 63.3 Hz "
  "reduced vs. ~36-40 Hz full); the reliability story inherited the same disjunction without "
  "it being named as a problem. Going forward, the rule is: any reliability or validation "
  "number cited in this report or to the PI must come from the full circuit. The reduced "
  "circuit remains useful for fast dev iteration but is retired as evidence (a note to that "
  "effect is now in phase1_reliability_sweep.py's docstring); "
  "experiments/full_circuit_reliability_sweep.py is the new script for anything citable.")

h2('9.2 Reproducing the seed-44 failure in the full circuit')

p("Before trusting any new full-circuit sweep, the specific failure that started this — "
  "Test 5's seed 44 collapsing to ratio ~1.015 — needed to reproduce in the circuit that "
  "matters. diag_seed44.py reran seeds 42-46 in model/full_circuit.py at noise_level=0, 10 "
  "analytical-plasticity epochs each, same protocol as the sweeps below.")

table(
    ['seed', '42', '43', '44', '45', '46'],
    [['gating ratio', '4.068', '4.808', '1.015', '4.816', '4.381'],
     ['result', 'PASS', 'PASS', 'FAIL', 'PASS', 'PASS']],
)

p("Seed 44 failed again, at 1.0153 — essentially identical to the original 1.015 — "
  "confirming this is a real, reproducible failure rather than a one-off fluke or a Test-5 "
  "harness artifact. The failure signature is informative: the inhibited branch's rate "
  "(r0) climbed to 0.9105, matching the free branch (r1=0.9245) almost exactly — SOM lost "
  "control of the inhibited branch entirely rather than the ratio merely softening. This is "
  "the same qualitative picture as the noise-driven and MD->VIP-driven collapses in Section "
  "8.3: once SOM's effective rate falls through the duty-cycle threshold, the branch it was "
  "gating escapes rather than partially leaking.")

h2('9.3 A 20-seed full-circuit reliability sweep, and the rate decision')

p("With the failure confirmed in the right circuit, the actual reliability question — does "
  "25 Hz hold up broadly, and if not what does — was answered with a 20-seed sweep (seeds "
  "40-59, noise_level=0, full circuit) at each candidate rate, parallelized across 8 worker "
  "processes (experiments/full_circuit_reliability_sweep.py; Brian2's numpy codegen target "
  "has no shared compile cache, so this parallelizes safely). 30 Hz (21.32 pA) passed cleanly:")

table(
    ['rate', 'seeds tested', 'passed (ratio>2.0)', 'ratio range'],
    [['25 Hz (20.90 pA)', '1 (seed 44, historical)', '0/1 — reproduced above', '1.015'],
     ['30 Hz (21.32 pA)', '40-59 (20 seeds)', '20/20', '3.25 - 5.07']],
)

p("All 20 seeds passed at 30 Hz, so the 33 Hz fallback was never needed. The margin above "
  "the ~21 Hz duty-cycle cliff identified in Section 7.3/8.1 is now ~9 Hz, versus the ~4 Hz "
  "margin 25 Hz carried — seed 44's failure is exactly the kind of near-cliff outlier a 4 Hz "
  "margin should be expected to produce occasionally. iBaseline_som is now 21.32 pA in "
  "model/parameters.py (with the reasoning above appended as a comment), synchronized across "
  "the three other hardcoded defaults (model/full_circuit.py, experiments/"
  "phase1_analytical.py, experiments/validate_vs_papers.py) that don't read parameters.py.")

flag("This changes the calibration but not the underlying mechanism: 30 Hz is still "
     "motivated by the same duty-cycle argument as 25 Hz (tau_GABA,dend=20 ms coverage of "
     "the inter-spike interval), just with a wider safety margin — 3x Yang's 10 Hz baseline "
     "rather than 2.5x, defensible on the same biophysical grounds.")

h2('9.4 Phase 2 re-validated at the new baseline — breaking points held, baseline got tighter')

p("Both Phase 2 sweeps were rerun in full at 30 Hz. The 25 Hz-era results were archived "
  "(docs/*_at25hz.json, figures/*_at25hz.png) before rerunning so the comparison below is "
  "against the actual prior numbers, not a description of them.")

table(
    ['noise level', '0.0', '0.25', '0.30', '0.35', '0.40', '0.45', '>=0.50'],
    [['ratio @ 25 Hz (archived)', '3.30', '2.77', '2.30', '1.73', '1.10', '1.02', '~1.00'],
     ['ratio @ 30 Hz (new)', '4.18', '2.76', '2.31', '1.82', '1.12', '1.02', '~1.00']],
)

p("The Phase 2B collapse point is unchanged: ratio holds above 2 through noise 0.30, is "
  "marginal at 0.35, and has collapsed by 0.40 in both datasets. The one real difference is "
  "the noise=0 baseline itself, which is both higher and far tighter across seeds "
  "(3.30 +/- 1.16 -> 4.18 +/- 0.52 SEM) — a direct, welcome side effect of moving away from "
  "25 Hz's thin margin. That zero-noise variance was flagged as undiagnosed in Section 8.3a; "
  "it has not been root-caused, but it has shrunk substantially now that the baseline sits "
  "further from the cliff.")

p("Phase 2C (the MD->VIP / schizophrenia-analogue sweep) shows the same pattern: intact "
  "MD->VIP drive (scale 1.0) and scale 0.66 are both fully collapsed (ratio ~1.00, SOM "
  "silenced) at either baseline — the transition still sits between scale 0.66 and 0.33. "
  "The healthy end is again higher at 30 Hz (scale 0.33: 3.29 -> 4.18; full block: 3.42 -> "
  "4.16), consistent with the same baseline shift seen in Phase 2B.")

flag("Both breaking points held their qualitative shape and approximate location — this was "
     "a recalibration of the SOM baseline's safety margin, not a change to the gating "
     "mechanism or its failure modes. The regenerated figures (figures/phase2_snr_curve.png, "
     "figures/phase2_ketamine_failure.png) now show the 30 Hz data; the 25 Hz-era versions "
     "are preserved as figures/phase2_snr_curve_at25hz.png and "
     "figures/phase2_ketamine_failure_at25hz.png for reference.")

h2('9.5 Where this leaves things')

p("30 Hz / 21.32 pA is locked as the SOM baseline, backed by a 20/20 full-circuit reliability "
  "sweep rather than a single seed's sweep peak. The open items carried forward are largely "
  "unchanged from Section 8.5: the network-scale stage is still un-started, and the Phase 2B "
  "zero-noise variance — while smaller now — is still not root-caused. One item from Section "
  "8.5 is effectively closed: Test 5's seed-reproducibility failure (Section 7) is the same "
  "phenomenon as seed 44 here, and is now understood (near-cliff SOM margin) and resolved "
  "(wider margin at 30 Hz) rather than an open question.")

# ===========================================================================
# SAVE
# ===========================================================================
out_path = os.path.join(DOCS, 'Progress_Report.docx')
doc.save(out_path)
print(f"Wrote {out_path}")

# Mirror to Google Drive. Copy rather than a second doc.save() so both files are
# byte-identical, not two independent renders.
try:
    os.makedirs(os.path.dirname(GDRIVE_PATH), exist_ok=True)
    shutil.copyfile(out_path, GDRIVE_PATH)
    print(f"Wrote {GDRIVE_PATH}")
except OSError as e:
    print(f"WARNING: could not write Google Drive copy at {GDRIVE_PATH}: {e}")
