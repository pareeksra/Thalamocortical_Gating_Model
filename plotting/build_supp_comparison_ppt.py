"""
build_supp_comparison_ppt.py
============================
A plain (white background, no theme/art) side-by-side comparison deck: Yang (2016)
supplementary panels (left) vs. our model's replication (right). Ordered so the panels
RELEVANT TO OUR MODEL come first, then the ones generated only to VALIDATE Yang's
modelling choices (which our model doesn't itself use).

Panels: figures/pre_audit/supp_panels/{pap_,our_}*.png (built by the crop step).
Output: docs/meetings/Yang_Supp_Comparison.pptx (+ Google Drive mirror if reachable).
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from PIL import Image

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAN = os.path.join(PROOT, 'figures', 'pre_audit', 'supp_panels')
GDRIVE = r'G:\My Drive\Yang_Supp_Comparison.pptx'

WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x11, 0x11, 0x11)
GREY = RGBColor(0x55, 0x55, 0x55)
BLUE = RGBColor(0x1f, 0x3a, 0x8a)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def _slide():
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = WHITE
    return s


def _textbox(s, text, left, top, w, h, size, bold=False, color=BLACK, align=PP_ALIGN.CENTER, italic=False):
    tb = s.shapes.add_textbox(Inches(left), Inches(top), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = color; r.font.italic = italic
    return tb


def _fit_picture(s, path, box_left, box_top, box_w, box_h):
    """Place an image scaled to fit within a box (inches), centered."""
    im = Image.open(path); iw, ih = im.size
    scale = min(box_w / iw, box_h / ih)
    w = iw * scale; h = ih * scale
    left = box_left + (box_w - w) / 2
    top = box_top + (box_h - h) / 2
    s.shapes.add_picture(path, Inches(left), Inches(top), Inches(w), Inches(h))


def title_slide():
    s = _slide()
    _textbox(s, "Replicating Yang (2016) Supplementary Figures 1 & 2",
             0.6, 2.5, 12.1, 1.2, 34, bold=True, align=PP_ALIGN.LEFT)
    _textbox(s, "Paper panels (left) vs. our model's replication (right). "
                "Panels relevant to our gating model first, then panels generated only to "
                "validate Yang's modelling choices.",
             0.6, 3.9, 12.1, 1.2, 17, color=GREY, align=PP_ALIGN.LEFT, italic=True)
    return s


def section_slide(text):
    s = _slide()
    _textbox(s, text, 0.6, 3.0, 12.1, 1.5, 30, bold=True, color=BLUE, align=PP_ALIGN.LEFT)
    return s


def compare_slide(heading, pap, our, caption):
    s = _slide()
    _textbox(s, heading, 0.4, 0.25, 12.5, 0.8, 24, bold=True, align=PP_ALIGN.LEFT)
    # column labels
    _textbox(s, "Yang 2016 (paper)", 0.4, 1.05, 6.0, 0.4, 15, bold=True, color=GREY)
    _textbox(s, "Our model", 6.9, 1.05, 6.0, 0.4, 15, bold=True, color=BLUE)
    # images
    _fit_picture(s, os.path.join(PAN, pap), 0.4, 1.5, 6.0, 4.6)
    _fit_picture(s, os.path.join(PAN, our), 6.9, 1.5, 6.0, 4.6)
    # caption
    _textbox(s, caption, 0.5, 6.35, 12.3, 0.9, 14, color=BLACK, align=PP_ALIGN.LEFT, italic=True)
    return s


# ---------------------------------------------------------------------------
title_slide()

section_slide("Part 1 — Panels relevant to our gating model\n"
              "(the dendritic NMDA-plateau mechanism our model is built on)")

compare_slide(
    "NMDA plateau potential (Supp Fig. 1f)",
    "pap_1f.png", "our_1f.png",
    "The dendrite jumps sharply to a plateau (~-10 mV) once enough NMDA synapses activate "
    "(here ≥15). This regenerative nonlinearity is exactly what our model's dendritic branches rely on.")

compare_slide(
    "NMDA input gated by inhibition (Supp Fig. 1g)",
    "pap_1g.png", "our_1g.png",
    "Mean dendritic voltage vs input rate: a sharp threshold at ~25-30 Hz that 30 Hz inhibition "
    "completely suppresses. This IS our gating mechanism — SOM inhibition shutting a dendritic branch.")

compare_slide(
    "Saturating NMDA enables strong inhibitory control (Supp Fig. 2a)",
    "pap_2a.png", "our_2a.png",
    "With saturating NMDA, modest inhibition holds the branch down across all input rates (the "
    "inhibited curve never reaches the disinhibited one) — why gating is robust in our model.")

section_slide("Part 2 — Panels generated only to validate Yang's modelling choices\n"
              "(our model does not use AMPA or non-saturating NMDA; shown for completeness)")

compare_slide(
    "AMPA input is barely gated (Supp Fig. 1h)",
    "pap_1h.png", "our_1h.png",
    "AMPAR-driven input is roughly linear and only weakly affected by inhibition — validating "
    "Yang's (and our) choice to use NMDA-only excitation for gateable dendrites.")

compare_slide(
    "Non-saturating NMDA loses inhibitory control (Supp Fig. 2b)",
    "pap_2b.png", "our_2b.png",
    "A control: without NMDA saturation the inhibited curve climbs back up at high rates, so "
    "inhibition can no longer gate. Confirms saturation is essential.")

compare_slide(
    "Steady-state bistability (Supp Fig. 2c)",
    "pap_2c.png", "our_2c.png",
    "Steady-state voltage jumps sharply at a threshold θ_NMDA in the effective input "
    "g_NMDA/(g_L+g_GABA) — the theoretical basis of the plateau switch.")

compare_slide(
    "NMDA conductance saturation (Supp Fig. 2d)",
    "pap_2d.png", "our_2d.png",
    "The effective NMDA input saturates with rate; adding inhibition (g_GABA/g_L = 0.6) lowers "
    "the saturated value toward the plateau threshold. Theory panel underpinning gating.")

# ---------------------------------------------------------------------------
out = os.path.join(PROOT, 'docs', 'meetings', 'Yang_Supp_Comparison.pptx')
prs.save(out)
print(f"Saved {out}")
try:
    prs.save(GDRIVE)
    print(f"Saved {GDRIVE}")
except Exception as e:
    print(f"Could not save to Google Drive ({GDRIVE}): {e}")
