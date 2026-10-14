"""
build_pi_meeting_ppt.py -- PI meeting deck for the 2026-10-14/15 session.
=========================================================================
Plain-background background slides (the question + the model), then the three new
results each as text-left / figure-right. Matches the house style of
plotting/build_results_ppt.py (16:9, blank layout, black/grey on white).

Run: <venv>/python -I plotting/build_pi_meeting_ppt.py
Out: docs/PI_Meeting_2026-10-15.pptx
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(PROOT, 'figures')
OUT = os.path.join(PROOT, 'docs', 'PI_Meeting_2026-10-15.pptx')

WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x11, 0x11, 0x11)
GREY = RGBColor(0x55, 0x55, 0x55)
BLUE = RGBColor(0x00, 0x72, 0xB2)
GREEN = RGBColor(0x00, 0x9E, 0x73)
ORANGE = RGBColor(0xD5, 0x5E, 0x00)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def _tb(slide, l, t, w, h):
    return slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h)).text_frame


def title_slide(title, subtitle=None, foot=None):
    s = prs.slides.add_slide(BLANK)
    tf = _tb(s, 0.8, 2.6, 11.7, 1.5); tf.word_wrap = True
    p = tf.paragraphs[0]; r = p.add_run(); r.text = title
    r.font.size = Pt(38); r.font.bold = True; r.font.color.rgb = BLACK
    if subtitle:
        tf2 = _tb(s, 0.8, 4.0, 11.7, 1.2); tf2.word_wrap = True
        r2 = tf2.paragraphs[0].add_run(); r2.text = subtitle
        r2.font.size = Pt(18); r2.font.color.rgb = GREY
    if foot:
        tf3 = _tb(s, 0.8, 6.6, 11.7, 0.6)
        r3 = tf3.paragraphs[0].add_run(); r3.text = foot
        r3.font.size = Pt(13); r3.font.color.rgb = GREY
    return s


def header(s, text):
    tf = _tb(s, 0.6, 0.35, 12.1, 0.9); tf.word_wrap = True
    r = tf.paragraphs[0].add_run(); r.text = text
    r.font.size = Pt(26); r.font.bold = True; r.font.color.rgb = BLACK


def bullets(s, items, left=0.8, top=1.5, width=11.7, height=5.5, size=20):
    tf = _tb(s, left, top, width, height); tf.word_wrap = True
    first = True
    for it in items:
        lvl = 0; txt = it; color = BLACK; bold = False
        if isinstance(it, tuple):
            txt, lvl = it[0], it[1]
            if len(it) > 2: color = it[2]
            if len(it) > 3: bold = it[3]
        p = tf.paragraphs[0] if first else tf.add_paragraph(); first = False
        p.level = lvl
        r = p.add_run(); r.text = txt
        r.font.size = Pt(size - 3 * lvl); r.font.color.rgb = color; r.font.bold = bold
        p.space_after = Pt(9)
    return tf


def text_and_figure(head, items, fig, fig_left=6.9, fig_top=1.4, fig_w=6.1):
    s = prs.slides.add_slide(BLANK)
    header(s, head)
    bullets(s, items, left=0.6, top=1.5, width=6.1, height=5.6, size=17)
    p = os.path.join(FIG, fig)
    if os.path.exists(p):
        s.shapes.add_picture(p, Inches(fig_left), Inches(fig_top), width=Inches(fig_w))
    return s


def full_figure(head, fig, note=None):
    s = prs.slides.add_slide(BLANK)
    header(s, head)
    p = os.path.join(FIG, fig)
    if os.path.exists(p):
        s.shapes.add_picture(p, Inches(0.7), Inches(1.4), width=Inches(12.0))
    if note:
        tf = _tb(s, 0.7, 6.9, 12.0, 0.5)
        r = tf.paragraphs[0].add_run(); r.text = note
        r.font.size = Pt(13); r.font.color.rgb = GREY
    return s


# ---------------------------------------------------------------- slides
title_slide(
    "MD-gated dendritic plasticity: progress update",
    "Does the mediodorsal thalamus gate which dendritic branch learns — enabling "
    "context-specific learning without catastrophic forgetting?",
    "Raghav · PI meeting 2026-10-15 · Thalamocortical Gating Model (spiking, Brian 2)")

# --- Background 1: the question (plain) ---
s = prs.slides.add_slide(BLANK)
header(s, "Background — the question")
bullets(s, [
    "While reading in a noisy café, the brain routes attention without erasing what it knows.",
    ("Hypothesis: the mediodorsal (MD) thalamus acts as a meta-controller that selects "
     "WHICH dendritic branch of a prefrontal pyramidal neuron is allowed to undergo plasticity.", 0),
    ("→ Different contexts write onto different physical branches instead of overwriting "
     "the same synapses — context-specific learning without catastrophic forgetting.", 0, BLUE, True),
    "",
    ("Two papers grafted together (neither answers it alone):", 0),
    ("Yang, Murray & Wang 2016 — the mechanism: spiking reduced-compartment pyramidal "
     "neuron, dendritic disinhibitory circuit (VIP→SOM→dendrite, PV→soma), "
     "calcium-based Graupner–Brunel plasticity.", 1),
    ("Zhang et al. 2025 — the MD wiring: MD→PV (gain) + MD→VIP (disinhibition) as "
     "the context/meta-control signal.", 1),
], top=1.4, size=18)

# --- Background 2: the model (plain + diagram) ---
text_and_figure(
    "Background — the model (Model A, spiking, Brian 2)",
    [
        ("One pyramidal neuron: soma + 2 dendritic branches.", 0),
        ("Each branch has an independent plastic cortical input "
         "(Graupner–Brunel calcium rule, Yang Eqs. 32–35).", 0),
        ("SOM inhibits a branch → shunts its calcium → gates its plasticity.", 0),
        ("MD sets the context via PV (somatic gain) and VIP→SOM (branch disinhibition).", 0),
        ("", 0),
        ("Readout: gating ratio = rho(free branch) / rho(inhibited branch). "
         "Ratio > 2 = gating works.", 0, BLUE, True),
    ],
    "network_architecture.png", fig_left=6.6, fig_top=1.3, fig_w=6.4)

# --- Since last meeting ---
s = prs.slides.add_slide(BLANK)
header(s, "Since the last meeting")
bullets(s, [
    ("Environment moved from Windows to Linux; rebuilt the Brian 2 stack and verified "
     "bit-exact reproduction of all committed results.", 0),
    ("Then closed the three open questions that were blocking confidence in the model:", 0),
    ("1.  Gating reliability — why did a few random seeds fail?", 1, ORANGE, True),
    ("2.  SOM-rate divergence — why does the model need ~2× Yang's firing rate?", 1, ORANGE, True),
    ("3.  No catastrophic forgetting — does the core claim actually hold?", 1, ORANGE, True),
    ("", 0),
    ("All three resolved, committed, and pushed to GitHub. Details follow.", 0, GREEN, True),
], top=1.5, size=19)

# --- Result 1 ---
text_and_figure(
    "Result 1 — Gating reliability: a small-N variance artifact",
    [
        ("Problem: at the 25 Hz baseline, 2/20 random seeds failed (gating ratio ~1).", 0, ORANGE, True),
        ("Diagnosed: the inhibited branch draws a small, random integer number of "
         "SOM synapses (p=0.5 over only 20 SOM cells). Too few → weak shunt → branch "
         "depolarizes → NMDA opens → calcium escapes → gating lost.", 0),
        ("Not a firing-rate or timing problem; a population-size variance effect.", 0),
        ("Fix (controlled): hold mean inhibition constant, enlarge the SOM pool so the "
         "variance self-averages.", 0),
        ("Result: N=100 → 20/20 seeds gate (full 10-epoch protocol).", 0, GREEN, True),
    ],
    "n_som_disinhibition_variance.png")

# --- Result 2 ---
text_and_figure(
    "Result 2 — SOM-rate divergence from Yang, resolved",
    [
        ("Reviewer question: Yang gets gating at ~10 Hz SOM; our model needs ~18–21 Hz "
         "at the SAME τ_GABA = 20 ms. Why 2×?", 0, ORANGE, True),
        ("Answer: gating tracks the DUTY CYCLE of inhibition (rate × τ), not the rate "
         "alone. Our spiking calcium is event-driven, so it needs fuller coverage than "
         "a rate-averaged rule.", 0),
        ("Proof: critical rate scales ~1/τ (rate×τ constant to <3%, 10→20 ms). "
         "Same spike train + longer GABA tail rescues gating.", 0),
        ("The model recovers Yang's ~10 Hz regime at τ = 40 ms — a quantified "
         "consequence of spiking calcium, not a bug.", 0, GREEN, True),
    ],
    "som_rate_divergence.png")

# --- Result 3 ---
text_and_figure(
    "Result 3 — No catastrophic forgetting (the core claim)",
    [
        ("First direct test: learn context A → switch to B → is A retained?", 0),
        ("Branch separation ALONE is not enough: inhibition-only switch → "
         "A's memory 70% erased (30% retained).", 0, ORANGE, True),
        ("Why: gating is not protection. A shunted branch still gets input + bAP calcium, "
         "sits in the LTD band, and is actively depressed (Yang plasticity has no frozen "
         "state).", 0),
        ("Memory is protected only when context A's INPUT is silent during B → "
         "100% retained, while B learns on its own branch.", 0, GREEN, True),
        ("Sharper claim: no forgetting needs context-specific gating of BOTH the "
         "disinhibition AND the input.", 0, BLUE, True),
    ],
    "retention_forgetting.png")

# --- Summary: before -> after ---
full_figure(
    "Summary — before → after (this session)",
    "before_after_proof.png",
    "All panels from committed simulation data. Orange = baseline/broken; green = resolved.")

# --- Next steps ---
s = prs.slides.add_slide(BLANK)
header(s, "Where this leaves us / next steps")
bullets(s, [
    ("Settled: gating reliability, SOM-rate calibration, and the no-forgetting mechanism "
     "— all verified in the reduced circuit and documented.", 0, GREEN, True),
    ("", 0),
    ("Next — scale to a ~3000-neuron network (Yang scale):", 0, BLACK, True),
    ("Now unblocked in principle, but it MUST preserve input context-sparsity — not "
     "just branch-specific gating — or it will forget at scale.", 1),
    ("Repeat the key tests across seeds and in the full MD→VIP→SOM circuit.", 1),
    ("", 0),
    ("Open decisions for discussion: ambition (faithful replication + modest extension "
     "vs. full novel network for publication); MD fidelity (Poisson vs. full PFC↔MD loop).", 0, GREY),
], top=1.4, size=18)

prs.save(OUT)
print(f"Saved {OUT}  ({len(prs.slides.__iter__.__self__._sldIdLst)} slides)")
