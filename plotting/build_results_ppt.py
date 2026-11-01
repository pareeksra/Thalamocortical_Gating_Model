"""
build_results_ppt.py
=====================
Plain results deck, per Raghav's spec: no theme, no background art, no AI-generated
images -- just the real result figures already in figures/, one per slide, with a short
numeric caption. Follows the same episode order as docs/PROJECT_STORY.md.

Saved to docs/Results_Summary.pptx (and G:/My Drive if reachable, matching
build_progress_report.py's convention).
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(PROOT, 'figures')
DOCS = os.path.join(PROOT, 'docs')
OUT_NAME = 'Results_Summary_PI.pptx'
GDRIVE_PATH = os.path.join(r'G:\My Drive', OUT_NAME)

WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x11, 0x11, 0x11)
GREY = RGBColor(0x55, 0x55, 0x55)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]  # fully blank layout -- no template placeholders/art


def new_slide():
    s = prs.slides.add_slide(BLANK)
    bg = s.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = WHITE
    return s


def title_slide(title, subtitle=None):
    s = new_slide()
    tb = s.shapes.add_textbox(Inches(0.7), Inches(2.7), Inches(12), Inches(1.5))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run(); r.text = title
    r.font.size = Pt(40); r.font.bold = True; r.font.color.rgb = BLACK
    if subtitle:
        tb2 = s.shapes.add_textbox(Inches(0.7), Inches(4.1), Inches(12), Inches(1.0))
        tf2 = tb2.text_frame; tf2.word_wrap = True
        p2 = tf2.paragraphs[0]
        r2 = p2.add_run(); r2.text = subtitle
        r2.font.size = Pt(18); r2.font.color.rgb = GREY
    return s


def text_slide(heading, bullets):
    """Plain heading + bullet list, no image."""
    s = new_slide()
    hb = s.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(12.1), Inches(0.8))
    hp = hb.text_frame.paragraphs[0]
    hr = hp.add_run(); hr.text = heading
    hr.font.size = Pt(28); hr.font.bold = True; hr.font.color.rgb = BLACK

    bb = s.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(11.7), Inches(5.5))
    tf = bb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = f"\u2022  {line}"
        p.font.size = Pt(20)
        p.font.color.rgb = BLACK
        p.space_after = Pt(14)
    return s


def figure_slide(heading, relpath, caption_lines):
    """Heading + one real figure, centered, + small caption text below/beside it."""
    s = new_slide()
    hb = s.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.3), Inches(0.7))
    hp = hb.text_frame.paragraphs[0]
    hr = hp.add_run(); hr.text = heading
    hr.font.size = Pt(24); hr.font.bold = True; hr.font.color.rgb = BLACK

    full = os.path.join(PROOT, relpath)
    if not os.path.exists(full):
        wb = s.shapes.add_textbox(Inches(1), Inches(2), Inches(10), Inches(1))
        wp = wb.text_frame.paragraphs[0]
        wr = wp.add_run(); wr.text = f"[missing figure: {relpath}]"
        wr.font.size = Pt(16); wr.font.color.rgb = RGBColor(0xB0, 0x00, 0x00)
    else:
        # picture on the left ~65% of the slide, caption text on the right
        pic = s.shapes.add_picture(full, Inches(0.4), Inches(1.15), height=Inches(5.9))
        # cap picture width if it overflows the left zone
        max_w = Inches(8.2)
        if pic.width > max_w:
            ratio = max_w / pic.width
            pic.width = int(pic.width * ratio)
            pic.height = int(pic.height * ratio)

    cb = s.shapes.add_textbox(Inches(8.9), Inches(1.3), Inches(4.1), Inches(5.7))
    tf = cb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(caption_lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.font.size = Pt(14)
        p.font.color.rgb = BLACK if line and not line.startswith('  ') else GREY
        p.space_after = Pt(8)
    return s


def comparison_table_slide(heading, subheading, col_headers, rows, note_lines=None):
    """Heading + a plain 3-column table (Check | Paper | Our model), + optional small
    note text underneath (e.g. a caveat row is handled inline via *-prefixed cell text,
    but a general footnote goes here)."""
    s = new_slide()
    hb = s.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.3), Inches(0.6))
    hp = hb.text_frame.paragraphs[0]
    hr = hp.add_run(); hr.text = heading
    hr.font.size = Pt(24); hr.font.bold = True; hr.font.color.rgb = BLACK

    if subheading:
        sb = s.shapes.add_textbox(Inches(0.5), Inches(0.85), Inches(12.3), Inches(0.4))
        sp = sb.text_frame.paragraphs[0]
        sr = sp.add_run(); sr.text = subheading
        sr.font.size = Pt(13); sr.font.italic = True; sr.font.color.rgb = GREY

    n_rows = len(rows) + 1
    n_cols = len(col_headers)
    top = Inches(1.45)
    height = Inches(5.6)
    tbl_shape = s.shapes.add_table(n_rows, n_cols, Inches(0.5), top, Inches(12.3), height)
    tbl = tbl_shape.table
    col_widths = [Inches(2.6), Inches(5.0), Inches(4.7)]
    for i, w in enumerate(col_widths[:n_cols]):
        tbl.columns[i].width = w

    for c, htext in enumerate(col_headers):
        cell = tbl.cell(0, c)
        cell.text = htext
        cell.fill.solid(); cell.fill.fore_color.rgb = RGBColor(0xEE, 0xEE, 0xEE)
        for p in cell.text_frame.paragraphs:
            for r in p.runs:
                r.font.bold = True; r.font.size = Pt(13); r.font.color.rgb = BLACK

    for ri, row in enumerate(rows, start=1):
        for c, val in enumerate(row):
            cell = tbl.cell(ri, c)
            cell.text = val
            cell.fill.solid(); cell.fill.fore_color.rgb = WHITE
            caveat = val.startswith('*')
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(12)
                for r in p.runs:
                    r.font.size = Pt(12)
                    r.font.color.rgb = RGBColor(0xB0, 0x00, 0x00) if caveat else BLACK
                    r.font.italic = caveat

    if note_lines:
        nb = s.shapes.add_textbox(Inches(0.5), Inches(7.05), Inches(12.3), Inches(0.4))
        ntf = nb.text_frame
        ntf.word_wrap = True
        for i, line in enumerate(note_lines):
            p = ntf.paragraphs[0] if i == 0 else ntf.add_paragraph()
            p.text = line
            p.font.size = Pt(11); p.font.italic = True; p.font.color.rgb = GREY
    return s


# ===========================================================================
title_slide("Thalamocortical Gating Model",
            "Progress meeting - what we replicated, what broke, what we fixed, "
            "and what needs a decision. All figures below are real simulation output.")

text_slide("The question and the approach", [
    "Question: can MD thalamus control WHICH dendritic branch of a pyramidal neuron",
    "is allowed to learn - so different contexts write onto different branches",
    "instead of overwriting the same synapses?",
    "",
    "Approach: combine two papers that don't talk to each other.",
    "Yang, Murray & Wang 2016 - the gating mechanism itself (dendrite + calcium +",
    "plasticity). No thalamus - just an abstract control input.",
    "Zhang et al. 2025 - the MD thalamus wiring (MD -> PV, MD -> VIP). No dendrites,",
    "no plasticity - a trained network, not a mechanistic one.",
    "",
    "Canonical model (\"Model A\"): 1 soma, 2 dendritic branches, 20 of each",
    "interneuron type (PV / SOM / VIP), Brian 2 spiking simulation.",
    "Scope check: we borrow Zhang's wiring labels only, not his trained task or",
    "behavior; not yet at Yang's ~3000-neuron network scale.",
])

figure_slide("Model architecture", "figures/network_architecture.png", [
    "Model A connectivity.",
    "",
    "MD thalamus (Poisson input) drives PV and VIP.",
    "VIP inhibits SOM (disinhibition).",
    "SOM inhibits one dendritic branch only.",
    "PV inhibits the soma.",
    "",
    "Weights / probabilities read directly",
    "from model/parameters.py.",
])

# --- Bug 1 / Bug 2 ---------------------------------------------------------
figure_slide("Bug 1 + Bug 2 fix - validation",
             "figures/paper_replications/replicated_YANG2016_fig2c_dendritic_IO.png", [
    "Bug 1: coupling constant was 4.0 nS,",
    "should have been Yang's 0.8 nS.",
    "-> soma fired at 201 Hz instead of ~10 Hz.",
    "",
    "Bug 2: calcium model wasn't Yang's leaky",
    "integral - old version capped at 1.328,",
    "below LTP threshold (2.78). LTP impossible.",
    "",
    "After both fixes, measured dendritic",
    "half-activation vs. Yang's own formula",
    "g(1/2) = 5.56 x (4 + g_inh):",
    "",
    "  22.24 / 33.36 / 77.83 / 133.42 / 216.81 nS",
    "  matches Yang's formula to the digit",
    "  at all 5 inhibition levels.",
])

text_slide("Bug 1 + Bug 2 - sanity check number", [
    "Free branch rho = 0.78",
    "Inhibited branch rho = 0.02",
    "(seed 42, exc = 80 Hz, post = 10 Hz, coupling = 0.8 nS)",
    "",
    "First working separation between the two branches after both fixes.",
    "",
    "Caveat found later: this specific ratio was inflated by a separate,",
    "then-undiscovered bug (the 346x plasticity-timescale bug - next section).",
    "The dendritic I/O match on the previous slide is the cleaner check,",
    "since it does not depend on the plasticity equation at all.",
])

# --- Paper replication battery ---------------------------------------------
figure_slide("V2 - LTP threshold shifts with rate (Yang Fig. 7b)",
             "figures/paper_replications/replicated_YANG2016_fig7b_LTP_vs_rate.png", [
    "Presynaptic rate (Hz):",
    "  20    40    60    80   100   120",
    "",
    "Free branch rho:",
    "  0.58  0.77  0.78  0.79  0.81  0.81",
    "",
    "Inhibited branch rho:",
    "  stays ~0.012-0.020 across the whole range",
    "",
    "Free branch potentiates more as rate rises;",
    "inhibited branch never does, at any rate.",
])

figure_slide("V3 - gating at Yang's own operating point",
             "figures/paper_replications/replicated_YANG2016_fig7de_branch_gating.png", [
    "exc = 80 Hz, post = 10 Hz",
    "(Yang's own stated operating point)",
    "",
    "Free branch rho = 0.792",
    "Inhibited branch rho = 0.012",
    "",
    "Ratio = 64.83",
    "",
    "(One of 3 different measurements of the",
    "same nominal number that didn't agree with",
    "each other - flagged, not hidden - see",
    "Progress_Report.docx Section 2.2.)",
])

figure_slide("V4 - does MD control the interneurons the way Zhang says?",
             "figures/paper_replications/replicated_ZHANG2025_MD_interneuron_control.png", [
    "MD drive (Hz):    0    5   10   20   30   40",
    "",
    "PV rate (Hz):    7.1 13.4 22.2 52.3 83.7 126.7",
    "SOM rate (Hz):  36.0 36.0 29.9  0.0  0.0  0.0",
    "VIP rate (Hz):   0.0  0.0  0.2 16.4 49.0 92.9",
    "",
    "As MD rises, VIP rises and suppresses SOM",
    "(36 -> 0 Hz) - disinhibition works as Zhang's",
    "wiring predicts. PV rises in parallel",
    "(separate gain-control arm).",
    "",
    "Qualitative check only - we borrow Zhang's",
    "wiring labels, not his trained behavior.",
])

# --- gamma/tau bug + plasticity refactor -----------------------------------
figure_slide("The 346x plasticity-timescale bug",
             "figures/formula_comparison.png", [
    "tau = 346.36 s (Yang's own published time",
    "constant) - but the project's ODE only",
    "divided part of the equation by tau.",
    "",
    "Ratio of what was written vs. correct: 346.",
    "",
    "Form            rho_inhib  rho_free  ratio",
    "As-committed      0.018     0.779    42.76",
    "Canonical(fixed)  0.424     0.638     1.51",
    "  (both at T = 3 seconds)",
    "",
    "Canonical form run for 300 s (~1.7 hrs",
    "wall-clock): oscillated 1.49-2.83,",
    "never converged. Motivated switching to",
    "Yang's actual closed-form equation instead",
    "of patching this ODE further.",
])

figure_slide("Multi-epoch result with Yang's real equation",
             "figures/analytical_plasticity_trajectory.png", [
    "Yang's closed-form epoch update",
    "(his Eqs. 32-35), not a continuous ODE.",
    "",
    "epoch:     0    1    2    3    5    8   15",
    "free rho: .50  .86  .92  .92  .92  .93  .92",
    "inhib rho:.50  .48  .47  .46  .42  .39  .33",
    "",
    "Final ratio = 2.81",
    "",
    "Much lower than the old 42.76 headline -",
    "because 42.76 was never real (previous slide).",
    "This number is honest.",
])

# --- SOM rate sweeps ---------------------------------------------------------
figure_slide("Sweep 1 - SOM firing rate (this is where 25 Hz comes from)",
             "figures/som_rate_sweep.png", [
    "gGABA held fixed at Yang-matched 40 nS.",
    "",
    "SOM rate (Hz): 10  17  21  25  29  33  39  46  55  63",
    "ratio:        1.0 1.0 5.5 5.6 5.0 4.3 3.6 3.1 2.9 2.8",
    "",
    "Sharp STEP between 17 and 21 Hz, not gradual.",
    "Peak ratio 5.58 at 25.3 Hz.",
    "Ratio then DECLINES past the peak -",
    "more SOM drive is not always better.",
])

figure_slide("Sweep 2 - GABA conductance amount (this one failed)",
             "figures/gbar_I_sweep.png", [
    "SOM held at Yang's own ~10.15 Hz.",
    "gGABA per synapse swept 4 -> 24 nS.",
    "",
    "Ratio only climbs from 1.02 to 1.45,",
    "even at 6x Yang's own conductance spec.",
    "Never reaches the ratio = 2 pass line.",
    "",
    "Conclusion: it's SOM's RATE / TIMING that",
    "matters for gating, not the total amount",
    "of inhibitory conductance.",
])

# --- Paper vs. our model, side by side --------------------------------------
comparison_table_slide(
    "Validation summary: paper result vs. our model",
    "Everything above this slide, side by side. Only checks done under matched "
    "conditions (same formula / same operating point) are marked as a real match.",
    ["Check", "Paper (Yang 2016 / Zhang 2025)", "Our model"],
    [
        ["Dendritic I/O curve\n(Yang Fig. 2c)",
         "g(1/2) = 5.56 x (4 + g_inh)\n(closed-form formula)",
         "Matches to the digit at all 5\ntested inhibition levels"],
        ["LTP threshold vs. rate\n(Yang Fig. 7b)",
         "Inhibition raises the rate\nneeded for LTP (qualitative)",
         "Directional match: free rho\n0.58->0.81 (20->120Hz);\ninhibited stays ~0.01-0.02"],
        ["SOM->PV connection\n(Yang Fig. 6)",
         "P = 0.8",
         "Was missing in our code;\nadded, now matches at P=0.8"],
        ["MD->interneuron wiring\ndirection (Zhang 2025)",
         "MD->VIP disinhibits SOM;\nMD->PV is separate gain control",
         "Matches direction: VIP 0->93Hz,\nSOM 36->0Hz, PV 7->127Hz as\nMD rises 0->40Hz"],
        ["SOM baseline firing rate\n(Yang Methods)",
         "~10 Hz",
         "*Not matched - model needs\n>=~21Hz minimum to gate at all;\ncurrent default is 30 Hz"],
        ["\"Gating selectivity\"\n(Yang Eq. 1)",
         "(r_on - r_off)/(r_on + r_off),\nbounded 0-1. Reports ~0.5\n(network-scale) and ~0.7\n(task-trained subset)",
         "*Not directly comparable -\nwe report a different, unbounded\nratio (rho_free/rho_inhib);\ndifferent setup entirely (single\nneuron vs. network/task model)"],
    ],
    note_lines=["Red/italic rows = open gaps or metric mismatches, not resolved matches - listed so nothing is silently dropped."],
)

# --- Noise + ketamine (current, 30 Hz reruns) -------------------------------
figure_slide("Noise robustness", "figures/phase2_snr_curve.png", [
    "How much biological noise can gating",
    "tolerate before it stops working?",
    "",
    "3 noise sources scaled together:",
    "MD noise input, vesicle-release variance,",
    "SOM/VIP background fluctuation.",
    "",
    "Gating degrades gradually, then collapses",
    "sharply past a breaking-point noise level.",
    "(current baseline: SOM at 30 Hz)",
])

figure_slide("Ketamine / NMDA-hypofunction simulation",
             "figures/phase2_ketamine_failure.png", [
    "Models a standard schizophrenia-dysfunction",
    "circuit disruption: block NMDA on VIP,",
    "i.e. block MD -> VIP synapse (0% -> 100%).",
    "",
    "Below ~50% block: MD can still pick which",
    "branch learns.",
    "",
    "Above ~50% block: SOM returns to its own",
    "baseline rate, permanently shuts its",
    "branch - MD's signal no longer matters.",
    "",
    "Reading: loss of CONTROL over learning,",
    "not a general shutdown of learning.",
])

# --- This session's work: 25 vs 30 Hz reliability + seed44 -----------------
figure_slide("Reliability check: does 25 Hz actually hold up?",
             "figures/reliability_full_circuit.png", [
    "20 seeds (40-59), full circuit, noise = 0.",
    "",
    "25 Hz:  18 / 20 seeds pass",
    "        (seeds 44 and 53 both fail,",
    "        ratio ~1.02 - a real ~10% failure",
    "        rate, not a fluke)",
    "",
    "30 Hz:  20 / 20 seeds pass",
    "        (ratios 3.25 - 5.07)",
    "",
    "Result: SOM baseline relocked to 30 Hz.",
    "This is the current committed default.",
])

figure_slide("What actually differs in a failing seed?",
             "figures/seed44_escape_mechanism.png", [
    "Seed 42 (pass, ratio 4.07) vs.",
    "seed 44 (fail, ratio 1.02), both at 25 Hz.",
    "",
    "SOM inter-spike-gap histograms:",
    "statistically indistinguishable between",
    "the two seeds - the clean \"SOM got an",
    "unlucky gap\" story does NOT show up here.",
    "",
    "What DOES differ: seed 44's calcium trace",
    "sits higher and crosses the LTP threshold",
    "more persistently through the run.",
    "",
    "Honest status: escape is real, mechanism",
    "only partially characterized - not a",
    "single isolated cause yet.",
])

# --- Closing -----------------------------------------------------------------
text_slide("Where things stand right now", [
    "Model: Model A (Brian 2), SOM baseline = 30 Hz, Yang's real Eqs. 32-35 plasticity.",
    "Reliability at current baseline: 20/20 seeds, full circuit, noise = 0.",
    "Both papers' core wiring/mechanism replicated and independently checked",
    "(dendritic I/O formula match, V2-V4 battery, Zhang MD->interneuron direction).",
    "",
    "What this demonstrates so far: the gating mechanism is real, mechanistically",
    "grounded, and now stress-tested for reliability - not just a single lucky seed.",
    "What it does NOT yet demonstrate: MD-gated plasticity at network scale, or any",
    "of the novel predictions that would be this project's actual contribution",
    "beyond replicating the two source papers.",
])

text_slide("Proposed next steps", [
    "Near-term (finish what's already open):",
    "1. Characterize the seed-44-style escape mechanism properly - larger seed batch,",
    "   test whether it's SOM-timing-specific or a joint SOM/excitatory-drive coincidence.",
    "2. Diagnose Test 5 (reproducibility) - same seed currently gives different output.",
    "   Blocks fully trusting any single headline number until resolved.",
    "3. Reconcile the 3 disagreeing Phase-1 ratio measurements (43 / 64.8 / 42.76) -",
    "   likely the same root cause as (2), worth confirming together.",
    "",
    "Medium-term (before claiming novel results):",
    "4. Resolve the Graupner-Brunel/Yang parameter provenance gap - several plasticity",
    "   constants have no traceable published source in this codebase's history.",
    "5. Decide on Models B/C (NumPy prototypes) - repair to match Model A, or retire.",
    "",
    "Longer-term (the project's actual novel contribution, per the roadmap):",
    "6. Scale to a network (Yang's ~3000-neuron regime) - currently 1 soma/2 branches.",
    "7. Test no-catastrophic-forgetting: learn context A, switch to B, verify A retained.",
    "8. A healthy vs. pathological (schizophrenia-framed) phase diagram at network scale.",
])

text_slide("Open questions for discussion", [
    "1. Calibration gap: the model needs SOM to deliver ~2x Yang's rate (>=~21 Hz vs.",
    "   ~10 Hz) and, on the conductance axis, gating never recovers at Yang's own SOM",
    "   rate even at 6x his GABA conductance spec. Is this a defensible 'this spiking",
    "   implementation's own operating regime,' or does it point to a miscalibration",
    "   further upstream (e.g. NMDA/calcium sensitivity) that should be revisited?",
    "",
    "2. How much weight should the seed-44 reliability finding carry? It's a real",
    "   ~10% failure rate at 25 Hz, resolved by moving to 30 Hz - but the mechanism",
    "   is only partially characterized. Worth a deeper mechanistic dig before",
    "   treating 30 Hz as final, or is empirical 20/20 reliability sufficient to move on?",
    "",
    "3. Prioritization: diagnose reproducibility (Test 5) and parameter provenance",
    "   first, or proceed toward network scale and treat those as caveats to flag",
    "   rather than blockers?",
    "",
    "4. Is the current scope of 'borrowing Zhang's wiring labels only' sufficient for",
    "   the project's claims, or does the novel contribution need more of Zhang's",
    "   model (e.g. the PFC<->MD feedback loop) to be defensible?",
])

# ===========================================================================
out_path = os.path.join(DOCS, OUT_NAME)
prs.save(out_path)
print(f"Saved {out_path}")
try:
    prs.save(GDRIVE_PATH)
    print(f"Saved {GDRIVE_PATH}")
except Exception as e:
    print(f"Could not save to Google Drive path ({GDRIVE_PATH}): {e}")
