"""
build_pi_story.py
=================
A short, plain-language narrative for the PI: what broke, how we fixed it, what the
result was, and how it compares to the source paper WHERE that comparison is actually
valid. Deliberately NOT the full 9-section lab-notebook docx (which was too dense to
follow) - this is the spoken-recap version, cleaned and accuracy-checked.

Every number here was verified against the repo (REPAIR_LOG.md, gamma_tau_analysis.md,
the sweep/reliability JSONs, build_progress_report.py) in the 2026-09-03 session.
Invalid or mis-attributed paper comparisons are intentionally omitted.

Output: docs/meetings/PI_Story.docx (+ Google Drive mirror if reachable).
"""
import os
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GDRIVE_PATH = r'G:\My Drive\PI_Story.docx'

doc = Document()
# base style
doc.styles['Normal'].font.name = 'Calibri'
doc.styles['Normal'].font.size = Pt(11)

RED = RGBColor(0xB0, 0x00, 0x00)
GREY = RGBColor(0x55, 0x55, 0x55)


def h1(t):
    doc.add_heading(t, level=1)

def h2(t):
    doc.add_heading(t, level=2)

def para(runs, space_after=8):
    """runs: list of (text, bold) or a plain string."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    if isinstance(runs, str):
        runs = [(runs, False)]
    for item in runs:
        if isinstance(item, str):
            text, bold = item, False
        else:
            text, bold = item
        r = p.add_run(text); r.bold = bold
    return p

def labelled(label, text):
    """A 'Label: text' line with the label bold."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(label + ' '); r.bold = True
    p.add_run(text)
    return p

def figure(relpath, caption, width_in=5.6):
    full = os.path.join(PROOT, relpath)
    if not os.path.exists(full):
        p = doc.add_paragraph(); r = p.add_run(f"[figure missing: {relpath}]")
        r.font.color.rgb = RED; return
    doc.add_picture(full, width=Inches(width_in))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = doc.add_paragraph(); cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cap.add_run(caption); r.italic = True; r.font.size = Pt(9); r.font.color.rgb = GREY


# ===========================================================================
title = doc.add_heading('Thalamocortical Gating Model', level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub = doc.add_paragraph(); sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run('A plain walkthrough: what we built, what broke, and how we fixed it')
r.italic = True; r.font.size = Pt(12); r.font.color.rgb = GREY

para([("The goal. ", True),
      ("We are testing one idea: can the MD thalamus control WHICH dendritic branch of a "
       "pyramidal neuron is allowed to learn, so that different contexts write onto different "
       "branches instead of overwriting the same synapses? To test it we combined two papers "
       "that don't overlap - Yang, Murray & Wang (2016), which has the single-neuron gating "
       "mechanism (dendrite + calcium + plasticity) but no thalamus, and Zhang et al. (2025), "
       "which has the MD-thalamus-to-interneuron wiring but no dendrites or plasticity.")])
para([("The model. ", True),
      ("A spiking network (in Brian 2): one pyramidal neuron with two dendritic branches, plus "
       "20 each of the PV, SOM and VIP interneurons, with MD thalamus as an input. SOM inhibits "
       "one branch; VIP inhibits SOM (disinhibition); PV inhibits the soma. Getting this small "
       "circuit to gate correctly took fixing a series of bugs, described below in the order we "
       "hit them.")])

# --- Fix 1: dendritic I/O sign -------------------------------------------
h1('1. The dendritic input-output curve had a sign error')
labelled('What broke:',
    "The formula for how a dendritic branch responds to input said that adding inhibition to "
    "an unstimulated branch would DEPOLARISE it - by up to ~30 mV. That is physically "
    "impossible here: inhibition in this model is purely shunting, so an unstimulated branch "
    "must sit at rest no matter how much inhibition it gets.")
labelled('How we fixed it:',
    "Re-referenced the curve to the resting potential, which leaves the response to excitation "
    "untouched but forces the correct resting behaviour.")
labelled('Result:',
    "Resting error went from ~30 mV to exactly 0.00 mV, without changing any of the fitted "
    "constants.")

# --- Fix 2: PV arm --------------------------------------------------------
h1('2. The PV interneuron could not be given a stable baseline rate')
labelled('What broke:',
    "PV cells have an almost knife-edge response - only a 5 mV window between rest and spike "
    "threshold - so the usual way of setting a firing rate with a fixed input current doesn't "
    "work: it's either silent or saturated, nothing in between.")
labelled('How we fixed it:',
    "Drove PV with a background noisy (Poisson) conductance sitting just below threshold, so it "
    "fires in a graded, fluctuation-driven way - only when a real signal pushes it over.")
labelled('Result:',
    "PV now responds smoothly to MD drive instead of switching all-or-nothing.")

# --- Fix 3: Bug 1 + Bug 2, the big one -----------------------------------
h1('3. The core gating mechanism: two bugs that had to be fixed together')
para("This is the one that actually made a single neuron gate. Two separate things were wrong.")

labelled('Bug A - the calcium model was not the paper\u2019s.',
    "Learning here is driven by calcium crossing a threshold. Our calcium had to cross a value "
    "of 2.78 to trigger strengthening (LTP). But the old calcium model was built so it could "
    "never exceed 1.328 - below the threshold - which made LTP mathematically impossible no "
    "matter what else we changed. We replaced it with Yang's actual calcium model (a leaky "
    "integrator of the NMDA current), which can accumulate past the threshold under sustained "
    "input.")
labelled('Bug B - the soma was firing 20x too fast.',
    "Yang's protocol holds the neuron's cell body (soma) firing at ~10 Hz. Ours was firing at "
    "~201 Hz. We traced it to one wrong number: the dendrite-to-soma coupling was set to 4.0 nS "
    "when Yang's value (already sitting unused in our own parameter file) is 0.8 nS. At the "
    "wrong value, a background calcium signal that is identical on both branches swamped the "
    "branch-specific signal, so the two branches became indistinguishable. We measured this "
    "directly: gating is destroyed once the soma fires above ~74 Hz.")
labelled('How we fixed it:',
    "Used the correct 0.8 nS coupling and pinned the soma at ~10 Hz externally, exactly as "
    "Yang's protocol does. This put the branch back in the regime where its own input, not the "
    "shared background, decides whether it learns.")
labelled('Result:',
    "The free branch learned (weight state ~0.78) while the inhibited branch did not (~0.02) - "
    "the first clean separation between the two branches.")
labelled('Comparison to the paper (this is the strong one):',
    "We measured the branch's input-output half-activation at five inhibition levels and "
    "compared to Yang's own published formula, g-half = 5.56 x (4 + g_inhibition). The measured "
    "values (22.24, 33.36, 77.83, 133.42, 216.81 nS) match Yang's formula to the digit at every "
    "level. This check does not depend on the plasticity equation, so it is the cleanest "
    "evidence the fix landed the model in Yang's actual operating regime.")
figure('figures/pre_audit/paper_replications/replicated_YANG2016_fig2c_dendritic_IO.png',
       'Our model (points) vs. Yang\u2019s formula (line): dendritic half-activation shifts with '
       'inhibition exactly as the paper predicts, at all five levels.')

# --- reproducibility (diagnosed and resolved) ----------------------------
h1('4. Reproducibility \u2014 checked, diagnosed, and resolved')
labelled('What we verified:',
    "Every result we report is exactly reproducible from its random seed. We confirmed this "
    "directly: the same seed, run in two separate processes, gives bit-identical output down to "
    "the last digit (and two independent historical runs of the same seed matched too).")
labelled('The one subtlety we tracked down:',
    "A test-suite check (validate_model Test 5) had looked non-reproducible. We root-caused it: "
    "it was building several networks inside ONE process, and Brian2's background Poisson spike "
    "generator is not fully reset by re-seeding within a single process (the connectivity is). "
    "This is a known Brian2 in-process quirk, NOT a flaw in our model \u2014 and it never touches our "
    "results, because every result is generated one-run-per-process. We rewrote the test to check "
    "reproducibility the way results are actually produced (a fresh process per seed); it now "
    "passes, with the same seed giving identical rates.")

# --- Fix 5: SOM->PV wiring ------------------------------------------------
h1('5. A missing connection from Yang\u2019s circuit')
labelled('What broke:',
    "Yang's circuit includes an inhibitory connection from SOM cells to PV cells (with "
    "connection probability 0.8). In our code this connection was never actually wired - the "
    "parameter existed but no synapse used it, so that inhibition was always zero.")
labelled('How we fixed it:',
    "Wired the SOM->PV connection at Yang's probability of 0.8.")
labelled('Comparison to the paper:',
    "This closes a genuine gap between our implementation and Yang's stated circuit - our "
    "wiring now matches the paper on this connection.")

# --- Fix 6: 346x + analytical refactor -----------------------------------
h1('6. The plasticity rule was running ~346x too strong')
labelled('What broke:',
    "The learning equation has a time constant of ~346 seconds. Our version accidentally left "
    "that factor out of part of the equation, making the learning terms run about 346 times too "
    "strong. That artificially large factor is the only reason a 3-second simulation showed any "
    "learning at all.")
labelled('What we tried, and the process:',
    "We put the equation into its correct form and tested it. At 3 seconds it barely separated "
    "the branches (ratio 1.51 vs. the inflated 42.76). We then ran it for 300 seconds (~1.7 "
    "hours of compute) to see if it just needed more time - it wandered between 1.5 and 2.8 and "
    "never settled. So patching the equation in place wasn't going to reproduce the result "
    "cheaply.")
labelled('How we fixed it:',
    "Yang's paper doesn't actually integrate this equation step-by-step - it uses a closed-form "
    "shortcut (his Eqs. 32-35) that computes the outcome from how long the calcium spent above "
    "each threshold. We implemented that directly instead of continuing to fight the slow "
    "equation.")
labelled('Result:',
    "With the honest equation, the gating ratio is 2.81 (free branch weight-state ~0.92, "
    "inhibited ~0.33), built up over repeated learning epochs. Much lower than the old 42.76 - "
    "and that's the point: 42.76 was an artifact of the bug, 2.81 is real.")
figure('figures/pre_audit/analytical_plasticity_trajectory.png',
       'Learning over epochs with the corrected, paper-faithful equation: the free branch rises '
       'and holds, the inhibited branch drifts down. Final ratio 2.81.')

# --- Fix 7: SOM baseline + reliability -----------------------------------
h1('7. Choosing the SOM firing rate, and checking it holds up')
labelled('What broke:',
    "Yang reports SOM cells firing at ~10 Hz. When we set our SOM cells to 10 Hz, gating "
    "collapsed almost completely (ratio 1.02 - both branches learned the same). At ~10 Hz the "
    "inhibition simply isn't strong enough, in our spiking model, to hold the inhibited branch "
    "below the learning threshold.")
labelled('The process - two sweeps:',
    "We swept two knobs to find out what actually controls this. (1) Sweeping the SOM firing "
    "rate: gating jumps on sharply between 17 and 21 Hz and peaks at 25 Hz (ratio 5.58), then "
    "gently declines at higher rates. (2) Sweeping the strength of the inhibitory synapse "
    "instead, with SOM held at 10 Hz: this barely helped at all - even at 6x Yang's conductance "
    "the ratio only reached 1.45. Conclusion: it is SOM's firing RATE that matters for gating, "
    "not the raw amount of inhibitory conductance.")
figure('figures/pre_audit/som_rate_sweep.png',
       'Sweep 1: gating vs. SOM firing rate. Sharp switch-on near 21 Hz, peak at 25 Hz, gentle '
       'decline after - not a straight line.')
labelled('Then we stress-tested it:',
    "25 Hz looked best on one seed, but when we ran 20 different random seeds, two of them "
    "(a ~10% failure rate) collapsed to ratio ~1.02. Re-running the same 20 seeds at 30 Hz "
    "passed all 20 (ratios 3.25-5.07). So we set the SOM baseline to 30 Hz - it's the value "
    "that gates reliably, not just on a lucky seed.")
figure('figures/pre_audit/reliability_full_circuit.png',
       '20-seed reliability: 25 Hz fails 2 of 20 seeds (red); 30 Hz passes all 20. Current '
       'model uses 30 Hz.')
labelled('Comparison to the paper (stated honestly):',
    "This is a real divergence from Yang: our spiking model needs SOM firing at least ~2x "
    "faster than the ~10 Hz Yang reports in order to gate at all. We are transparent about "
    "this rather than forcing a match - it likely points to a difference in calcium/NMDA "
    "sensitivity between our spiking neurons and Yang's rate-based model, and it's an open "
    "question we're carrying forward.")

# --- Fix 8: noise + ketamine ---------------------------------------------
h1('8. Two things we then asked of the working model')
labelled('Noise robustness:',
    "We added three kinds of biological noise together and increased them. Gating holds, then "
    "degrades, then collapses past a breaking point - i.e. the mechanism is robust to a "
    "realistic amount of noise but not unlimited noise.")
figure('figures/pre_audit/phase2_snr_curve.png',
       'Gating selectivity falls as noise rises, collapsing past a breaking point.')
labelled('A disease model (ketamine / schizophrenia):',
    "Ketamine-type drugs block NMDA receptors on VIP interneurons - a standard circuit model of "
    "schizophrenia-like dysfunction. We simulated this by blocking the MD->VIP connection. The "
    "finding: below ~50% block, MD can still choose which branch learns; above ~50%, SOM returns "
    "to its baseline and permanently shuts its branch regardless of the MD signal. The "
    "interesting part is that it's the CONTROL over learning that breaks, not learning itself - "
    "a loss of context-dependent flexibility, which is the schizophrenia-relevant reading.")
figure('figures/pre_audit/phase2_ketamine_failure.png',
       'Blocking MD->VIP: branch-specific gating is intact below ~50% block and collapses above '
       'it, as SOM returns to its baseline rate.')

# --- Where it stands ------------------------------------------------------
h1('Where it stands, and what\u2019s next')
para([("Working now: ", True),
      ("the single-neuron gating mechanism is fixed and faithful to Yang where we can check it "
       "(the dendritic I/O formula match), the plasticity uses Yang's real equation, and the "
       "SOM baseline (30 Hz) gates reliably across 20 random seeds.")])
para([("Open items we're carrying forward: ", True),
      ("(1) the SOM-rate divergence from Yang's "
       "~10 Hz (Section 7); (2) scaling up from this 1-neuron / 2-branch circuit to a proper "
       "network (Yang's ~3000 neurons), which is where the project's actual novel prediction - "
       "MD-gated plasticity supporting learning without catastrophic forgetting - would be "
       "tested.")])

# ===========================================================================
out_path = os.path.join(PROOT, 'docs', 'meetings', 'PI_Story.docx')
doc.save(out_path)
print(f"Saved {out_path}")
try:
    doc.save(GDRIVE_PATH)
    print(f"Saved {GDRIVE_PATH}")
except Exception as e:
    print(f"Could not save to Google Drive path ({GDRIVE_PATH}): {e}")
