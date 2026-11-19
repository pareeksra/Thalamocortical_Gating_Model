"""
build_pi_report.py
==================
The PI-facing progress report. Owns docs/meetings/Progress_Report.docx -- the filename the
shared Google Drive link points at -- so updating it updates what the PI already has.

2026-11-12 rewrite: one continuous report, start to now:
  0  where we stand (one page)
  1  the question and the approach
  2  what we built (current model, circuit diagram, code map)
  3  how we got here (August -> November, including what the November audit overturned)
  4  replication of the papers' figures
  5  the Yang Fig. 2 / Supp. Fig. 1 notebook
  6  robustness
  7  context experiments (single cell)
  8  towards a network (steps 1-4a)
  9  what we can claim, open points, next steps
The 2026-09-03 version of this report is in git history (docs/meetings/Progress_Report.docx at
commit 504daac); its still-valid content is folded into section 3.

Sources: README.md, docs/reports/PROJECT_STORY.md, REPAIR_LOG.md, AUDIT_2026-11-01.md,
MODEL_STATUS_2026-11-04.md, PLAN_robustness.md, PAPER_COMPARISON.md and the FINDING_* files.
The network alternation table (8) is read from results/current/network_alternation_summary.json
when it exists. The circuit diagram and the V1 figure are drawn here from the model/results.
"""
import os
import json
import numpy as np
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(PROOT, 'docs', 'meetings')
GDRIVE_PATH = r'G:\My Drive\Progress_Report.docx'
TODAY = '12 November 2026'

doc = Document()
doc.styles['Normal'].font.name = 'Calibri'
doc.styles['Normal'].font.size = Pt(11)
GREY = RGBColor(0x55, 0x55, 0x55)


def h1(t): doc.add_heading(t, level=1)
def h2(t): doc.add_heading(t, level=2)


def p(text, italic=False):
    par = doc.add_paragraph(); par.paragraph_format.space_after = Pt(8)
    r = par.add_run(text); r.italic = italic
    return par


def sp(label, text):
    par = doc.add_paragraph(); par.paragraph_format.space_after = Pt(6)
    r = par.add_run(label + ' '); r.bold = True
    par.add_run(text)
    return par


def bullets(items):
    for it in items:
        par = doc.add_paragraph(style='List Bullet'); par.paragraph_format.space_after = Pt(3)
        if isinstance(it, tuple):
            r = par.add_run(it[0] + ' '); r.bold = True; par.add_run(it[1])
        else:
            par.add_run(it)


def figure(relpath, caption, width_in=5.4):
    full = os.path.join(PROOT, relpath)
    if not os.path.exists(full):
        return
    doc.add_picture(full, width=Inches(width_in))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = doc.add_paragraph(); cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cap.add_run(caption); r.italic = True; r.font.size = Pt(9); r.font.color.rgb = GREY


def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = 'Light Grid Accent 1'
    for i, htext in enumerate(headers):
        c = t.rows[0].cells[i]; c.text = str(htext)
        for run in c.paragraphs[0].runs: run.bold = True; run.font.size = Pt(10)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
            for run in cells[i].paragraphs[0].runs: run.font.size = Pt(10)
    doc.add_paragraph()
    return t


# ---------------------------------------------------------------------------
# figures drawn here
# ---------------------------------------------------------------------------
def make_circuit_figure():
    """Diagram of the current (canonical) circuit and its network extensions."""
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    out = os.path.join(PROOT, 'figures', 'circuit_canonical.png')
    fig, ax = plt.subplots(figsize=(10, 6.6)); ax.set_xlim(0, 10); ax.set_ylim(0, 6.6); ax.axis('off')
    C0, C1, CP, CE = '#0072B2', '#D55E00', '#555555', '#009E73'

    def box(x, y, w, h, t, s, col, ls='-'):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.04', fc='white', ec=col, lw=1.6, ls=ls))
        ax.text(x + w / 2, y + h / 2 + (0.11 if s else 0), t, ha='center', va='center', fontsize=10, weight='bold', color=col)
        if s:
            ax.text(x + w / 2, y + h / 2 - 0.17, s, ha='center', va='center', fontsize=7.5, color='#333333')

    def arrow(x0, y0, x1, y1, col, inh=False, ls='-', lab=None, lx=0, ly=0):
        ax.annotate('', (x1, y1), (x0, y0), arrowprops=dict(arrowstyle='-[' if inh else '-|>', color=col, lw=1.4,
                    ls=ls, shrinkA=2, shrinkB=2, mutation_scale=9 if inh else 12))
        if lab:
            ax.text((x0 + x1) / 2 + lx, (y0 + y1) / 2 + ly, lab, fontsize=7, color=col, ha='center')

    box(0.9, 5.55, 1.6, 0.65, 'MD₀', 'context A', C0); box(3.1, 5.55, 1.6, 0.65, 'MD₁', 'context B', C1)
    box(0.2, 4.2, 1.5, 0.65, 'VIP₀', '20 cells', C0); box(3.9, 4.2, 1.5, 0.65, 'VIP₁', '20 cells', C1)
    box(0.2, 2.85, 1.5, 0.65, 'SOM₀', '≈ 30 Hz, noisy', C0); box(3.9, 2.85, 1.5, 0.65, 'SOM₁', '≈ 30 Hz, noisy', C1)
    box(2.05, 3.55, 1.5, 0.65, 'PV', '20 cells', CP)
    box(0.6, 1.35, 1.7, 0.7, 'branch 0', 'NMDA plateau, Ca²⁺', C0); box(3.3, 1.35, 1.7, 0.7, 'branch 1', 'NMDA plateau, Ca²⁺', C1)
    box(2.0, 0.1, 1.6, 0.65, 'soma', '≈ 10 Hz, output', 'black')
    arrow(1.5, 5.55, 1.0, 4.87, C0, lab='MD→VIP', lx=-0.45); arrow(3.9, 5.55, 4.6, 4.87, C1)
    arrow(2.2, 5.55, 2.6, 4.22, CP, lab='MD→PV', lx=0.05, ly=0.25); arrow(3.6, 5.55, 3.1, 4.22, CP)
    arrow(0.95, 4.2, 0.95, 3.52, C0, inh=True)
    ax.text(1.02, 3.86, 'VIP→SOM\n×0.25', fontsize=7, color=C0, ha='left', va='center')
    arrow(4.65, 4.2, 4.65, 3.52, C1, inh=True)
    arrow(1.0, 2.85, 1.3, 2.07, C0, inh=True, lab='SOM→dendrite', lx=-0.65); arrow(4.6, 2.85, 4.3, 2.07, C1, inh=True)
    arrow(1.7, 3.2, 2.15, 3.55, CP, inh=True); arrow(3.9, 3.2, 3.45, 3.55, CP, inh=True)
    ax.text(2.8, 3.32, 'SOM→PV', fontsize=7, color=CP, ha='center')
    arrow(2.8, 3.55, 2.8, 0.77, CP, inh=True)
    ax.text(2.86, 2.45, 'PV→soma', fontsize=7, color=CP, ha='left', va='center')
    arrow(1.45, 1.35, 2.3, 0.77, 'black'); arrow(4.15, 1.35, 3.3, 0.77, 'black')
    ax.text(1.55, 0.85, 'coupling 0.8 nS', fontsize=7, ha='right'); ax.text(4.0, 0.85, 'bAPs back', fontsize=7, ha='left')
    # afferents
    box(6.0, 1.35, 1.9, 0.7, 'afferents', 'patterns A and B', 'black')
    ax.annotate('', (5.05, 1.75), (6.0, 1.75), arrowprops=dict(arrowstyle='-|>', color='black', lw=1.4, ls='--'))
    ax.annotate('', (2.33, 1.95), (6.0, 1.95), arrowprops=dict(arrowstyle='-|>', color='black', lw=1.0, ls='--',
                connectionstyle='arc3,rad=0.25'))
    ax.text(6.95, 1.05, 'plastic NMDA synapses onto both branches\n(Yang weight ρ, calcium rule, Eqs. 32–35)',
            fontsize=7.5, ha='center', va='top')
    # network extensions
    box(6.3, 4.85, 3.4, 1.35, '', '', CE, ls='--')
    ax.text(8.0, 5.95, 'network extensions (step 3)', fontsize=9, weight='bold', color=CE, ha='center')
    ax.text(8.0, 5.45, '20 such cells share the interneurons\nrecurrence E → E, SOM, VIP, PV (Zhang)\n'
            'MD rates from a PFC↔MD rate loop', fontsize=7.8, ha='center', va='center')
    ax.text(8.0, 3.7, 'context k = MD_k on\n→ VIP_k fires → SOM_k silenced\n→ branch k disinhibited → only branch k learns',
            fontsize=8.5, ha='center', va='center', color='#222222',
            bbox=dict(boxstyle='round,pad=0.4', fc='#F3F3F3', ec='none'))
    ax.text(0.2, 6.45, 'Current model (canonical since 10–11 November 2026)', fontsize=11, weight='bold')
    fig.savefig(out, dpi=150, facecolor='white', bbox_inches='tight'); plt.close(fig)
    return 'figures/circuit_canonical.png'


def make_v1_figure():
    """Measured dendritic half-activation vs Yang's fit (results/current/v1_dendrite_io_yang.json)."""
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    src = os.path.join(PROOT, 'results', 'current', 'v1_dendrite_io_yang.json')
    out = os.path.join(PROOT, 'figures', 'v1_dendrite_io_yang.png')
    if not os.path.exists(src):
        return None
    d = json.load(open(src))
    gi = sorted(float(k) for k in d if k != 'linear_fit')
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
    cols = plt.cm.viridis(np.linspace(0, 0.85, len(gi)))
    for g, c in zip(gi, cols):
        v = d[str(g)]
        ax[0].plot(v['gE_nS'], v['V_mV'], 'o-', ms=3, color=c, label=f'g_inh = {g:g} nS')
    ax[0].set_xlabel('excitatory conductance g_E (nS)'); ax[0].set_ylabel('mean dendritic V (mV)')
    ax[0].set_title('measured dendritic input-output'); ax[0].legend(frameon=False, fontsize=7)
    gx = np.linspace(0, 10, 50)
    ax[1].plot(gx, 5.56 * (4 + gx), 'k-', label='Yang: g½ = 5.56 (4 + g_inh)')
    ax[1].plot(gi, [d[str(g)]['g_half_measured_nS'] for g in gi], 'o', color='#0072B2', label='our dendrite (measured)')
    ax[1].set_xlabel('inhibitory conductance g_inh (nS)'); ax[1].set_ylabel('half-activation g½ (nS)')
    ax[1].set_title('half-activation vs inhibition'); ax[1].legend(frameon=False, fontsize=8)
    for a in ax:
        a.spines[['top', 'right']].set_visible(False)
    fig.tight_layout(); fig.savefig(out, dpi=140, facecolor='white'); plt.close(fig)
    return 'figures/v1_dendrite_io_yang.png'


SINGLE_CELL_ALT = {0.0: ((0.94, 0.95), (0.94, 0.95)), 0.25: ((0.63, 0.50), (0.91, 0.90)),
                   0.5: ((0.28, 0.12), (0.82, 0.11)), 0.75: ((0.06, -0.01), (0.46, -0.14)),
                   1.0: ((0.02, -0.05), (0.10, -0.16))}


def network_alternation():
    """(rows, no-gating summaries) for the network alternation table, or None if not analysed yet."""
    src = os.path.join(PROOT, 'results', 'current', 'network_alternation_summary.json')
    if not os.path.exists(src):
        return None
    S = json.load(open(src))
    rows = []
    for L in (4, 1):
        for f in (0.0, 0.25, 0.5, 0.75, 1.0):
            a, q = S.get(f'amp_f{f}_L{L}'), S.get(f'poisson_f{f}_L{L}')
            if a is None:
                continue
            s = SINGLE_CELL_ALT[f][0 if L == 1 else 1]
            rows.append([f'{f:g}', str(L), f"{a['S_current'][0]:.2f} / {a['S_previous'][0]:.2f}",
                         f"{q['S_current'][0]:.2f} / {q['S_previous'][0]:.2f}" if q else '—',
                         f'{s[0]:.2f} / {s[1]:.2f}'])
    none = {k: v for k, v in S.items() if k.startswith('none_')}
    return rows, none


# Filled in once the network alternation run is analysed (sections 0, 8, 9).
NET_ALT_READING = ("Reading: for overlap ≤ 0.5 the network reproduces the single cell within about 0.05, and the "
                   "MD loop gives the same result as a fixed MD input (within 0.01). Without MD gating nothing is "
                   "recalled. New: at high overlap with 12-s blocks the network is more biased toward the latest "
                   "context than the single cell (f = 1: 0.41 / −0.41 against 0.10 / −0.16). Step 4b (19 November) traced "
                   "this: it is not a network effect. At f = 0.75 the single-cell value in this table is a 10-seed mean; on "
                   "the same 5 seeds the cell and the network agree exactly (0.68 / −0.15). At f = 1 it is the learning "
                   "rate: a single cell learning at 50 Hz, as the network does, gives 0.41 / −0.45. The conclusion is "
                   "unchanged: both contexts are recalled only for ≤ 25% overlap with 12-s blocks.")
NET_ALT_STAND = ('done (12 November): matches the single cell, with the MD loop as with fixed MD; the apparent '
                 'extra recency at high overlap was traced to seed choice and learning rate (19 November, step 4b)')


# ===========================================================================
# TITLE
# ===========================================================================
title = doc.add_heading('Thalamocortical Gating Model — Progress Report', level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub = doc.add_paragraph(); sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run(f'The whole project from the start: what we built, what changed recently, and where we '
                f'stand. Status as of {TODAY}.')
r.italic = True; r.font.size = Pt(12); r.font.color.rgb = GREY

# ===========================================================================
h1('0. Where we stand (one page)')
p("Question. Can the mediodorsal (MD) thalamus decide which dendritic branch of a prefrontal "
  "pyramidal neuron is allowed to learn, so that different contexts are written onto different "
  "branches instead of overwriting each other? We test this by combining Yang, Murray & Wang (2016) "
  "(dendritic disinhibition and calcium-based plasticity, no thalamus) with Zhang et al. (2025) "
  "(MD→VIP and MD→PV wiring, no dendrites or plasticity).")
sp('What we have built.', "A spiking model (Brian 2) of one pyramidal cell with two dendritic "
   "branches, Yang’s NMDA-plastic synapses and calcium plasticity rule, PV/SOM/VIP interneurons, and "
   "two MD channels, one per context (§2). It has been extended to a 20-cell recurrent network with "
   "an MD signal generated by a PFC↔MD loop.")
sp('What works and is tested.', "")
bullets([
    "MD selects which branch learns, in every seed (20/20), independent of the time step, with no "
    "fragile parameter at ±25% on 16 parameters, and 19/19 automated regression checks.",
    "The main context result (both contexts kept at 25% input overlap, the old one lost at 50%) holds "
    "when each of 16 parameters is changed by ±25%, in 30 of 32 cases; it breaks only with stronger NMDA "
    "or weaker SOM drive, where learning itself degrades (§6).",
    "Learning changes behaviour: after learning, the cell responds to a pattern only when that "
    "pattern’s context gate is open (selectivity 0.86–0.89, from ≈ 0 before) — Yang Fig. 7d,e.",
    "Every reproducible figure of Yang 2016 is reproduced from our model (13 match: Figs. 2–7 and "
    "Supp. Figs. 1–6, including Fig. 3 on a spiking neuron with 10–30 dendrites and Figs. 4–6 with Yang’s "
    "rate model refit to our neuron), plus Zhang’s wiring — §4. One partial mismatch: the inhibited branch "
    "weakens only slowly.",
    "The mechanism survives a recurrent network up to a stability limit, and works with MD produced "
    "by a PFC↔MD loop instead of a fixed input; the context-alternation results carry over to the network.",
])
sp('What we can claim today.', "MD gating decides where learning happens and is necessary for any "
   "context-specific recall. It protects an old memory when the two contexts use different inputs, "
   "or share at most 25% of them with 12-s context blocks. Protection against forgetting comes from "
   "input sparsity, not from inhibition itself.")
sp('What we can not claim (yet).', "That MD gating prevents forgetting in general (at ≥ 50% input "
   "overlap the old memory is lost); that the network results hold at biological recurrence strength "
   "(our recurrent weights are guesses); the learning results at Yang’s network scale (~3000 neurons; "
   "his network figures are reproduced with a rate model, not with learning spiking cells).")
sp('Main open points.', "Slow weakening on the inhibited branch; learned gating shows only for "
   "readout drive ≤ 15 Hz per synapse; the branch-specific MD→VIP channels are our assumption; SOM "
   "must fire at ≈ 30 Hz against Yang’s ≈ 10 Hz.")
sp('Network alternation (§8, step 4a).', NET_ALT_STAND[0].upper() + NET_ALT_STAND[1:] + '.')

# ===========================================================================
h1('1. The question and the approach')
p("Neither paper alone answers the question. Yang 2016 has the mechanism — a reduced-compartment "
  "pyramidal neuron whose dendrites are gated by a disinhibitory circuit (VIP inhibits SOM, SOM "
  "inhibits the dendrite, PV inhibits the soma), with calcium-based (Graupner–Brunel) plasticity — but "
  "only an abstract control input. Zhang 2025 has the thalamus — a trained rate network in which MD "
  "projects to PV (MD^GRIK4 cells) and to VIP (MD^DRD2 cells) — but no dendrites and no plasticity.")
p("Plan: reproduce Yang’s single-neuron gating, attach Zhang’s MD→interneuron wiring, and test "
  "whether MD activity controls which branch learns; then test what that buys for learning two "
  "contexts, and whether it survives in a network. We borrow Zhang’s wiring, not its trained task. "
  "Of three implementations in the repository only the Brian 2 spiking model (Model A) is used; the "
  "two NumPy prototypes (B, C) are frozen sketches with an inert plasticity rule.")

# ===========================================================================
h1('2. What we built')
cf = make_circuit_figure()
if cf:
    figure(cf, 'The current model. Each context k has its own MD → VIP → SOM channel that controls one '
               'dendritic branch; MD also drives PV, which inhibits the soma. Plastic afferents reach both '
               'branches; only the disinhibited branch learns.', 6.4)
table(['Component', 'What it is', 'Source'],
      [['Pyramidal cell', 'Soma + 2 dendritic branches, coupled at 0.8 nS (Yang in vivo); dendrites make NMDA plateaus; soma ≈ 10 Hz with a balanced, fluctuation-driven background; its spikes back-propagate (bAPs)', 'Yang 2016'],
       ['Plastic synapse', 'NMDA synapse whose weight w = 3ρ scales the NMDA conductance (ρ₀ = 1/3); no plastic AMPA', 'Yang 2016'],
       ['Plasticity rule', 'Calcium (NMDA + bAP ×0.2) above θ_d depresses, above θ_p potentiates; applied per 3-s epoch with Yang’s closed form (Eqs. 32–35)', 'Yang 2016 / Graupner–Brunel'],
       ['SOM (2 × 20)', 'One population per branch, ≈ 30 Hz baseline from noisy input, inhibits its branch', 'Yang; rate is ours'],
       ['VIP (2 × 20)', 'Driven by its MD channel, inhibits its SOM population (weight ×0.25)', 'Yang / Zhang'],
       ['PV (20)', 'Driven by MD and background, inhibited by SOM, inhibits the soma', 'Yang / Zhang'],
       ['MD (2 channels)', '25 Hz Poisson for the active context, 0 for the other; or produced by a PFC↔MD rate loop', 'Zhang 2025'],
       ['Inputs', 'Afferent patterns A and B (20 synapses each; 80 Hz while learning in the single cell, 50 Hz in the network) with a chosen overlap', 'ours'],
       ['Readout', 'Plasticity frozen; each pattern presented with each gate open at 10 Hz; selectivity S = (r_on − r_off)/(r_on + r_off)', 'Yang Eq. 1'],
       ['Network', '20 cells sharing the interneurons; Zhang’s E→E/SOM/VIP/PV recurrence', 'Zhang (signs); weights ours']])
table(['Code', 'Role'],
      [['model/context_circuit.py', 'single-cell model (canonical defaults)'],
       ['model/network_circuit.py, model/md_loop.py', '20-cell network; PFC↔MD loop'],
       ['src/v2/plasticity.py', 'Yang’s closed-form plasticity update'],
       ['experiments/*.py', 'one script per experiment; results in results/current/, figures in figures/'],
       ['tests/test_replication.py', 'regression tests (fast tier ~1 min, full tier ~8 min)'],
       ['notebooks/yang_fig2_supp1.ipynb', 'interactive reproduction of Yang Fig. 2 and Supp. Fig. 1 (§5)'],
       ['docs/reports/', 'plans, results and the paper comparison, kept up to date']])

# ===========================================================================
h1('3. How we got here')
table(['When', 'Stage', 'Outcome'],
      [['Aug 2026', 'Repair pass and Phase 1: make one neuron gate', 'Calcium model, dendrite–soma coupling and a 346× plasticity error fixed; Yang’s closed-form rule adopted; first real gating (ratio 2.8)'],
       ['late Aug – early Sep', 'Phase 2: SOM baseline, noise, ketamine', 'SOM baseline locked at 30 Hz after a 20-seed reliability test; noise tolerance; MD→VIP block breaks MD control above ~50%'],
       ['Sep – Oct', 'Yang supplementary figures; reproducibility; three findings', 'Supp. Figs. 1–2 reproduced; results reproducible per seed; findings on SOM rate, reliability and forgetting (PI meeting 15 Oct)'],
       ['1–2 Nov', 'Audit of the whole model', 'Eight problems fixed; three findings overturned; MD now selects the branch; first overlap and alternation experiments (PI meeting 2 Nov)'],
       ['4–10 Nov', 'Robustness plan and canonical model', 'Yang’s NMDA-plastic synapse; learning creates gating; noisy SOM; bAP ×0.2; paper table; regression tests; A/B experiments re-run'],
       ['10–12 Nov', 'Towards a network', 'VIP→SOM ×0.25; channel specificity; Zhang’s extra wiring; 20-cell recurrent network; PFC↔MD loop; context alternation on the network']])

h2('3.1  August: making one neuron gate')
p("Before any experiment, a repair pass fixed several silent defects: a sign error in the dendritic "
  "input-output curve (inhibition could depolarise a resting branch by 30 mV), a back-propagating "
  "calcium pathway that was never wired, a PV baseline that could not work as a current (replaced by "
  "a noisy conductance), and an unwired SOM→PV connection from Yang’s circuit. Then three bugs blocked "
  "gating:")
bullets([
    ('The calcium model was not Yang’s.', "It was capped at 1.328, below the potentiation threshold "
     "of 2.78, so LTP was impossible. Replaced by Yang’s leaky integral of the NMDA current."),
    ('The soma fired at ~201 Hz instead of ~10 Hz,', "because the dendrite–soma coupling was 4 nS "
     "instead of Yang’s 0.8 nS. Back-propagating calcium then swamped the branch-specific signal "
     "(gating died above ~74 Hz)."),
    ('The plasticity rule ran 346× too strong,', "a missing time constant. That error alone produced "
     "the early headline ratio of 42.8. The corrected equation never settled in 300 s, so we "
     "implemented Yang’s published closed-form update (Eqs. 32–35). Honest result: ratio 2.8 (free "
     "branch 0.92, inhibited 0.33)."),
])
h2('3.2  Late August to October: baseline, stress tests, findings')
bullets([
    ('SOM baseline.', "Gating failed with SOM at Yang’s 10 Hz. Sweeps suggested SOM rate, not "
     "conductance, controls gating; 25 Hz failed on 2/20 seeds, 30 Hz passed 20/20, so the baseline "
     "was locked at 30 Hz."),
    ('Noise and a disease model.', "Gating tolerates moderate noise and collapses past a breaking "
     "point. Blocking MD→VIP (a ketamine / NMDA-hypofunction model) leaves MD in control below ~50% "
     "block; above it the branch stays shut whatever MD does — a loss of context flexibility."),
    ('Yang Supp. Figs. 1–2', "were reproduced panel by panel (17 Sep)."),
    ('Reproducibility.', "Every result is bit-identical per seed across processes; an apparent "
     "failure was a Brian 2 quirk in the test harness, not the model (11 Oct)."),
    ('Three findings (14–15 Oct):', "the 25 Hz failures were explained as small-population "
     "variance; the need for 30 Hz SOM as inhibition ‘coverage’ (rate × time constant); and a "
     "first forgetting test suggested that both input gating and inhibition are needed to retain a "
     "memory. These were presented at the 15 October meeting."),
])
h2('3.3  1–2 November: the audit')
p("A line-by-line audit found eight problems. Three of them overturned earlier findings:")
table(['Earlier claim', 'What the audit found', 'Current understanding'],
      [['SOM must fire ≥ 25–30 Hz; gating tracks coverage (rate × τ); 25 Hz fails on 10% of seeds',
        'All SOM cells fired in perfect lockstep (one big volley per cycle) in every earlier run',
        'With desynchronised SOM, gating follows mean inhibition; 25 Hz passes 20/20; the remaining gap to 10 Hz is a less-shunted dendrite'],
       ['MD gating is the context switch', 'Every headline run had MD off; SOM was wired to one branch only',
        'A per-branch MD_k → VIP_k → SOM_k channel was built; MD now selects the branch'],
       ['Retention needs both input gating and inhibition', 'The control “idle input off, no inhibition” was missing; it retains 100%',
        'Retention comes from input sparsity; inhibition with active input erases'],
       ['Dendritic I/O matches Yang “to the digit”', 'The check plotted Yang’s formula against itself',
        'Measured on the simulated dendrite: within 12% (§4)']])
p("The audit also checked the integration step (results converged), compiled the dendrite–soma "
  "coupling (2× faster), fixed worker reuse in parallel sweeps, recalibrated PV, added a balanced "
  "soma, and ran the first overlap and alternation experiments. Branch-specific VIP→SOM channels "
  "were recorded as a modelling assumption.")
h2('3.4  4–19 November: a robust canonical model, then a network')
p("A status review (4 Nov) found the largest gap: with the old synapse, learned weights scaled only "
  "a small AMPA conductance, so learning did not change the cell’s output. A five-step robustness "
  "plan followed: R1 choose the synapse, R2 numerics, R3 parameter sensitivity, R4 agreement with "
  "the papers, R5 regression tests. It led to the canonical model:")
table(['Change', 'Why', 'Effect'],
      [['Yang’s NMDA-plastic synapse (weight scales NMDA; ρ₀ = 1/3)',
        'The old synapse’s learned weights did not change the output',
        'Learning now produces gating of the output (S ≈ 0 → 0.89)'],
       ['Fluctuation-driven SOM baseline (6 pA bias + 60 Hz × 2 nS Poisson input, ≈ 30 Hz)',
        'The old bias sat at SOM’s threshold: −25% silenced SOM, +25% took it to 76 Hz',
        'No knife-edge: SOM 27–35 Hz at ±25%'],
       ['bAP calcium ×0.2 (Yang’s in-vivo value)',
        'At ×1, back-propagating spikes alone depressed idle synapses (Δw −0.70 over 300 s); per-epoch updates had hidden this',
        'Synapses with silent inputs keep their weight (retention 1.000)'],
       ['VIP→SOM weight ×0.25',
        'The calibrated weight was far stronger than needed and made gating fragile to cross-talk',
        'Tolerates 7.5% VIP→SOM cross-talk; all results re-run']])
p("Then the network work (§8): how specific the MD channels must be, Zhang’s remaining connections, "
  "a 20-cell recurrent network, and a PFC↔MD loop producing the MD signal.")
p("19 November: the remaining checks. The context-alternation claim was stress-tested against ±25% of 16 "
  "parameters (§6); the network’s apparent extra recency was traced to seed choice and learning rate (§8); "
  "the two outdated figures were re-made on the canonical model; and every reproducible Yang 2016 figure "
  "was reproduced, with a notebook and a PDF (§4, §5).")

# ===========================================================================
h1('4. Replication of the papers’ figures')
p("Every row is run from the canonical model. Yang’s figures give mostly qualitative or plot-read "
  "values; Zhang 2025 is a trained rate network, so it supplies wiring, not rates. Full table with "
  "sources: docs/reports/PAPER_COMPARISON.md.")
table(['Paper figure', 'What the paper shows', 'Our model', 'Verdict'],
      [['Yang Supp. Fig. 1f–h', 'NMDA plateau above a threshold number of synapses; inhibition gates NMDA input strongly, AMPA weakly',
        'Same, from the model equations (notebook)', 'match (qualitative)'],
       ['Yang Fig. 2b,c', 'NMDA plateau; disinhibition opens the dendritic gate', 'Plateau from ~25 synapses; open and closed dendrite separate from 40 Hz input', 'match (qualitative)'],
       ['Yang Fig. 2e–g', 'An open gate transmits tuning, selectivity ≈ 0.6', '27 vs 8 Hz at the preferred stimulus, S = 0.60', 'match'],
       ['Yang Fig. 2c fit (Eqs. 20–22)', 'g½ = 5.56 (4 + g_inh)', 'g½ within 12% for g_inh 0–10 nS; fit 4.51 (g_inh + 5.27)', 'match'],
       ['Yang Fig. 7b', 'Weak inhibition: no change / LTD / LTP as the rate rises; more inhibition raises the LTP threshold; strong inhibition: no LTP',
        'Free branch: 0 at ≤ 5 Hz, LTD at 10 Hz, LTP from 15 Hz; SOM 13 Hz: LTP only from 150 Hz; SOM 31/60 Hz: no LTP up to 150 Hz', 'match'],
       ['Yang Methods (bAP ×0.2)', 'Non-activated synapses do not change', 'Δw = 0.000 at 0–2 Hz; 300-s idle phase keeps 1.000', 'match'],
       ['Yang Fig. 7c', 'Free branch strengthens, inhibited branch weakens', 'Learned pattern w 2.78 on its branch; stays at 1.00 on the other (weakens only with longer exposure)', 'partial'],
       ['Yang Fig. 7d,e', 'No gate preference before learning; strong pathway gating after (S ≈ 0.7)', 'Tuning curves with Yang’s equalised drive: S 0.06 before, 0.92 ± 0.10 after', 'match'],
       ['Yang Supp. Fig. 2c,d', 'NMDA saturation lets moderate inhibition keep the input below the plateau threshold', 'Same, analytic with our constants (θ ≈ 4.9; ceiling 4.7 / 3.1 at 4 / 8 nS)', 'match'],
       ['Yang Supp. Fig. 3c', 'AMPA input degrades gating', 'S 0.73 (NMDA only) → 0.15 (AMPA only)', 'match'],
       ['Yang Supp. Fig. 4', 'Rate model fitted to the spiking neuron', 'Refit to ours: b_g 5.62 (Yang 5.56), k 8.9 (9.64), γ 5.6 (6.54); soma exponent 2.63 (2.89)', 'close'],
       ['Yang Fig. 3', 'One neuron: sparser and stronger disinhibition gate better; non-overlapping patterns best, < 1', 'Spiking neuron with 10–30 dendrites: S 0.44–0.73 sparse → 0 dense; rises with disinhibition; rate model on the points', 'match'],
       ['Yang Fig. 4', 'SOM–pyramidal column: S ≈ 0.5 at ≈ 5 SOM per dendrite, set by that number alone', 'S = 0.38 (Yang’s own fit in the same code: 0.41); flat when the number is held', 'match'],
       ['Yang Fig. 5 (network)', 'VIP-only control needs sparse targeting; VIP+SOM control is set by SOM targeting', 'Peak 0.42 at 5–10% VIP targeted → 0; SOM targeting changes S by 0.56, VIP by ≤ 0.05', 'match'],
       ['Yang Fig. 6, Supp. 5–6', 'Somatic PV inhibition raises S until it silences cells; uniform', 'S 0.39 → 0.68 → 0.08; PV→soma change −44 ± 1 pA', 'match'],
       ['Yang Fig. 5 (circuit analogue)', 'Selectivity 0.5–0.9, needs branch-specific control', 'S = 0.93 with branch-specific channels; collapses when mixed', 'match (given our assumption)'],
       ['Not reproducible', 'Fig. 1 (schematic), Fig. 8 and Supp. 8 (monkey behaviour), Supp. 1a–d, 2a,b,e–h, 3d,e, 7', 'Need data or models outside this project', '—'],
       ['Zhang 2025 wiring', 'MD→PV, MD→VIP, VIP→SOM, SOM→E/PV/VIP, PV→E/PV, E→all, PFC↔MD loop',
        'All present; SOM→VIP and PV→PV as options; E→all and the loop in the network (§8)', 'match (signs)'],
       ['Zhang 2025, MD activation', 'MD disinhibits through VIP and adds PV gain', 'MD 0→40 Hz: VIP 0→85 Hz, own SOM 31→0.1 Hz, other SOM unchanged, PV 2→95 Hz', 'match']])
p("All figures below are in one PDF with Yang’s claim, our number and the verdict per page: "
  "docs/reports/Yang2016_replication.pdf (built from notebooks/yang_replication.ipynb).")
figure('figures/yang_replication/supp1_fgh.png',
       'Yang Supp. Fig. 1f–h reproduced: NMDA plateau and its gating by inhibition (NMDA 41 mV vs AMPA 7 mV).', 6.2)
figure('figures/yang_replication/fig2.png',
       'Yang Fig. 2b,c,e–g reproduced: plateau, disinhibition, and pathway-specific tuning (S = 0.60).', 6.4)
v1 = make_v1_figure()
if v1:
    figure(v1, 'Yang Fig. 2c fit: measured half-activation of our dendrite (points) against Yang’s formula '
               '(line). Within 12% at every inhibition level.', 6.2)
figure('figures/paper_comparison_v2.png',
       'Yang Fig. 7b analogue (300 s, 3 seeds): the three plasticity regimes, and the LTP threshold moving up '
       'with SOM inhibition.', 5.4)
figure('figures/yang_replication/supp4.png',
       'Yang Supp. Fig. 4: Yang’s rate model fitted to our spiking dendrite and soma (black) against Yang’s '
       'published fit (dotted). The two neurons are close.', 6.4)
figure('figures/yang_replication/fig3.png',
       'Yang Fig. 3, on our spiking neuron with 10–30 dendrites (points) and the rate model (lines): sparser and '
       'stronger disinhibition gate better.', 6.4)
figure('figures/yang_replication/fig4.png',
       'Yang Fig. 4c–f: SOM–pyramidal column with random connectivity (rate model fitted to our neuron; band = '
       '10–90% of neurons; dotted = Yang’s fit).', 6.6)
figure('figures/yang_replication/fig5.png', 'Yang Fig. 5b,c,e,f: making SOM context-selective with VIP (and SOM) control.', 6.6)
figure('figures/yang_replication/fig6.png', 'Yang Fig. 6b and Supp. Fig. 6: somatic PV inhibition improves gating until it silences cells.', 6.4)
figure('figures/yang_replication/fig7c.png',
       'Yang Fig. 7c: learning aligns excitation with disinhibition in our circuit (synapses onto the inhibited '
       'branch stay at w = 1: the partial mismatch).', 6.4)
figure('figures/yang_replication/fig7de.png',
       'Yang Fig. 7d,e: tuning before and after learning, drive equalised as in Yang (S 0.06 → 0.92).', 5.6)
figure('figures/robustness_r4_readout_canonical.png',
       'Learned gating against readout drive (canonical model, re-made 19 November, 7 seeds): S 0.90–0.91 at '
       '5–10 Hz per synapse, 0.62 at 15 Hz, ≈ 0 from 30 Hz. Open symbols: no response, S undefined.', 6.2)

# ===========================================================================
h1('5. The notebooks')
p("notebooks/yang_replication.ipynb (new, 19 November) goes through every figure of Yang 2016 and its "
  "supplement: each is reproduced from our model or listed as not reproducible with the reason, and a "
  "summary table compares our numbers with Yang’s. The spiking simulations run on toothless "
  "(experiments/yang_figures.py, about 20 min on 38 cores) and are loaded from "
  "results/current/yang_figures.json; the rate-network figures (Figs. 3–6) are computed in the notebook "
  "in about a minute (plotting/yang_rate_model.py). plotting/build_yang_replication_pdf.py turns its "
  "figures into docs/reports/Yang2016_replication.pdf.")
p("notebooks/yang_fig2_supp1.ipynb (the earlier, interactive notebook) re-runs Yang Fig. 2b,c,e–g and Supp. Fig. 1f–h directly from the "
  "model files (model/equations.py, model/parameters.py) through plotting/yang_fig2_supp1.py; "
  "nothing is re-implemented in the notebook, so changing model/parameters.py changes the figures.")
bullets([
    ('How to run.', "Open it in JupyterLab (command: jupyter lab notebooks/yang_fig2_supp1.ipynb, with "
     "the project environment) and run all cells. Supp. Fig. 1 takes about 30 s, Fig. 2 1–3 min. "
     "Each run overwrites figures/yang_supp1_fgh_model.png and figures/yang_fig2_model.png."),
    ('Parameters cell.', "P['model_overrides'] changes any model parameter (e.g. gNMDA, dendritic leak, "
     "gGABA, tauGABA, with units); the other entries are Yang’s protocol settings."),
    ('Interactive panel.', "Sliders for 12 parameters (NMDA conductance, leak, inhibition, coupling, input "
     "rates, soma background) and a checkbox for the synapse; press Run Interact to re-simulate. Needs "
     "ipywidgets (installed)."),
    ('Two deliberate deviations from Yang,', "both adjustable: 0.8 nS dendrite–soma coupling for the "
     "clamped-soma panels (at Yang’s 4 nS the clamped soma prevents any plateau), and a 300 Hz soma "
     "background instead of 500 Hz (500 Hz drives our soma to ~20 Hz instead of Yang’s 3–4 Hz)."),
    ('Valid for the current model.', "The notebook’s dendritic input is NMDA-only (AMPA off), as in Yang’s "
     "figure and the canonical synapse, with weights frozen at the pre-learning value (w = 1, ρ = 1/3). "
     "At that weight the old synapse, the ‘Yang NMDA-plastic’ checkbox and the canonical setting give "
     "the same result (checked 12 November: S = 0.60 in all three). The notebook does not simulate "
     "learning; setting P['rho'] (w = 3ρ) shows the effect of a learned weight."),
])

# ===========================================================================
h1('6. Robustness of the canonical model')
table(['Check', 'Criterion', 'Result'],
      [['Gating over 20 seeds', '≥ 19/20', '20/20 (free branch 0.928, inhibited 0.333, ratio 2.8)'],
       ['Time step 0.1 vs 0.05 ms', 'Δρ < 0.01', 'max 0.00014'],
       ['Soma background', '5–15 Hz, irregular', '8.8–11.5 Hz, CV 0.96–1.38'],
       ['16 parameters × {0.5, 0.75, 1.25, 1.5}, 5 seeds', 'gating; S > 0.5; learned S > 0.5',
        'No failure at ±25% (S 0.84–0.99, learned S 0.64–0.95). Failures only at ×0.5 of six parameters '
        '(NMDA conductance, dendritic leak, MD rate, MD→VIP weight, SOM input rate and weight). bAP calcium '
        'and VIP→SOM weight (added 19 Nov) change nothing from ×0.5 to ×1.5'],
       ['Alternation claim, 16 parameters × {0.75, 1.25}, 5 seeds (330 runs)',
        'previous context kept at 25% overlap (S > 0.5), lost at 50%',
        'Holds in 30/32. Breaks at NMDA ×1.25 (previous 0.42) and SOM Poisson weight ×0.75 (0.39): learning '
        'itself degrades there (current context at 50% overlap 0.09 / −0.10)'],
       ['Regression tests (tests/test_replication.py)', 'all pass', 'fast tier 11/11; full tier 19/19 (456 s)']])
figure('figures/robustness_r3_canonical.png',
       'Parameter sensitivity: 16 parameters scaled ×0.5–×1.5 (grey band ±25%). Gating, selectivity, learned '
       'selectivity and retention with silent inputs hold inside the band.', 6.6)
figure('figures/robustness_claims.png',
       'Is the alternation claim robust? Recall of the current (open) and previous (filled) context with each '
       'parameter ×0.75 / ×1.25. It holds except for stronger NMDA and weaker SOM drive, where the inhibited '
       'branch becomes easier to potentiate.', 6.6)
p("Reading: the claim needs SOM inhibition of the closed branch to be strong relative to the NMDA drive. "
  "That is a stated condition, not a hidden tuning: the same two directions already lowered the learned "
  "selectivity in the single-parameter sweep.")

# ===========================================================================
h1('7. Context experiments (learn A, then B), single cell')
p("Recall is measured functionally: plasticity frozen, each pattern presented with each gate open, "
  "selectivity S for each pattern at 10 Hz per synapse. 10 seeds each.")
sp('Retention (A learned, then 24 s of context B).', "If A’s inputs are silent during B, A is kept "
   "completely (1.000), whether or not A’s branch is inhibited. If A’s inputs stay active while its "
   "branch is inhibited, retention is 0.69 ± 0.26 and bimodal (6/10 seeds partly erased); we do not "
   "claim this result.")
sp('Overlap (B shares a fraction f of A’s synapses).', "")
table(['overlap f', 'recall of A after learning B', 'recall of B', 'no MD gating'],
      [['0', '0.93', '0.92', '≈ 0'], ['0.25', '0.49', '0.92', '≈ 0'], ['0.5', '0.03', '0.90', '≈ 0'],
       ['0.75', '−0.18', '0.60', '≈ 0'], ['1.0', '−0.28', '0.36', '≈ 0']])
sp('Alternation (32 × 3-s epochs, A and B in blocks of L epochs).', "Recall at the end of the run, "
   "current / previous context:")
table(['overlap f', 'L = 1 (3-s blocks)', 'L = 4 (12-s blocks)'],
      [['0', '0.94 / 0.95', '0.94 / 0.95'], ['0.25', '0.63 / 0.50', '0.91 / 0.90'],
       ['0.5', '0.28 / 0.12', '0.82 / 0.11'], ['0.75', '0.06 / −0.01', '0.46 / −0.14'],
       ['1.0', '0.02 / −0.05', '0.10 / −0.16']])
p("Reading: MD gating is necessary for any recall. It protects the old memory for disjoint inputs, "
  "and for ≤ 25% overlap when contexts come in 12-s blocks. At higher overlap the shared synapses move "
  "to the latest context’s branch. The MD→PV arm changes output gain, not what is stored (retention "
  "unchanged over MD→PV ×0–×3).")
figure('figures/alternation_experiment_canonical.png',
       'Alternation, single cell: synapse classes on each branch across epochs, and steady-state retention '
       'and branch preference against overlap.', 6.6)

# ===========================================================================
h1('8. Towards a network')
sp('Step 1: how branch-specific must the MD→VIP→SOM→dendrite channels be?', "Each stage was mixed from "
   "specific to uniform. SOM→dendrite tolerates 20% wrong-branch synapses; VIP→SOM tolerates 7.5% at "
   "the canonical weight ×0.25 (20% at ×0.1); MD→VIP must respect the channel. So the one requirement "
   "on the anatomy is a channel-specific MD→VIP projection.")
figure('figures/specificity_test_canonical.png', 'Step 1, re-made on the canonical model (VIP→SOM ×0.25, 19 November): '
       'gating and learning as each stage of the channel is mixed. SOM→dendrite tolerates 20%, VIP→SOM 7.5%; '
       'MD→VIP spill-over of 25% already loses one seed in five.', 6.4)
sp('Step 2: Zhang’s other connections.', "SOM→VIP is compatible with gating when weak (≲ 0.1 nS, a "
   "quarter of the MD drive), within-channel (any strength tested), or opposed by stronger MD. PV→PV has "
   "no effect on gating or learning.")
sp('Step 3a: a 20-cell recurrent network', "(20 canonical cells sharing the interneurons; Zhang’s E→E, "
   "E→SOM, E→VIP and E→PV, scaled by a common gain; the reference weights are ours).")
table(['recurrence', 'works up to', 'breaks at', 'how'],
      [['all four pathways', 'gain 0.6 (S after learning 0.84)', '0.7 (80% of cells gated), 1.0 (20%)', 'the other context’s VIP ignites'],
       ['E→E only', '0.6', '0.7', 'runaway firing'],
       ['E→VIP only', '0.7', '0.8', 'the other context’s VIP ignites'],
       ['E→SOM or E→PV only', '≥ 1.0', '—', 'harmless']])
p("The failure is a cliff: while the network stays at low rates, gating and learning are as in the single "
  "cell. The limit is network stability, not the dendritic mechanism.")
figure('figures/network_test.png', 'Step 3a: gating and learning against recurrence gain, all pathways and one at a time.', 6.4)
sp('Step 3b: MD from a PFC↔MD loop', "(rate units; context populations excite their MD channel and "
   "receive excitation back; shared inhibition makes contexts compete; recurrence gain 0.35).")
table(['loop', 'result'],
      [['amplifies a held cue (loop gain 0.4)', 'works (S after learning 0.93); tolerates 10% loop cross-talk and strong non-specific E→MD feedback'],
       ['self-sustained after a 0.5-s cue (gain 2)', 'works (0.92); needs ≤ 5% loop cross-talk and weak E→MD feedback'],
       ['self-sustained, competition too weak', 'fails: the old context stays on, B is learned on both branches'],
       ['all conditions', 'the stored memory of A is never touched (retention 1.000)']])
figure('figures/network_loop_test.png', 'Step 3b: MD source, non-specific PFC→MD feedback, and loop specificity.', 6.4)
na = network_alternation()
sp('Step 4a: the alternation experiment on the network', "(20 cells, recurrence gain 0.35, MD from the "
   "amplifying loop, and fixed MD as a reference; 5 seeds). Recall, current / previous context:")
if na and na[0]:
    rows, none = na
    table(['overlap f', 'blocks L', 'network, MD loop', 'network, fixed MD', 'single cell'], rows)
    if none:
        p("Without MD gating during learning (L = 4), recall of the current context is "
          + ', '.join(f"{v['S_current'][0]:.2f} at f = {k.split('_f')[1].split('_')[0]}" for k, v in sorted(none.items()))
          + ".")
    if NET_ALT_READING:
        p(NET_ALT_READING)
    figure('figures/network_alternation.png', 'Step 4a: alternation on the network against the single cell.', 6.6)
else:
    p("Running at the time of writing (115 simulations); results will be added here.", italic=True)
sp('Step 4b: what caused the extra recency?', "A 2 × 2 design on the same 5 seeds: single cell vs network, "
   "learning at 50 vs 80 Hz, plus the network without recurrence (60 runs). Recall at 12-s blocks, current / "
   "previous context:")
table(['overlap f', 'cell, 80 Hz', 'cell, 50 Hz', 'network, 50 Hz', 'network, no recurrence', 'network, 80 Hz'],
      [['0.5', '0.91 / 0.02', '0.89 / 0.04', '0.85 / 0.08', '0.80 / 0.06', '0.86 / 0.53'],
       ['0.75', '0.68 / −0.15', '0.71 / −0.13', '0.68 / −0.15', '0.58 / −0.14', '0.64 / −0.14'],
       ['1.0', '0.11 / −0.18', '0.41 / −0.45', '0.41 / −0.41', '0.30 / −0.30', '0.33 / −0.32']])
p("Reading: the network adds no recency of its own. At 75% overlap the cell and the network agree on the same "
  "seeds (single-cell seeds vary from 0.84 to −0.23; the network averages 20 cells). At full overlap a cell "
  "learning at 50 Hz behaves like the network. One new, unexplained result: the network learning at 80 Hz "
  "keeps the previous context at 50% overlap (0.53 ± 0.13, every seed); it is not a claim until understood.")
figure('figures/recency_cause.png', 'Step 4b: recall against overlap for the five conditions.', 6.4)

# ===========================================================================
h1('9. What we can claim, open points, next steps')
table(['Claim', 'Status', 'Evidence'],
      [['MD selects which dendritic branch learns', 'supported, robust', '20/20 seeds, ±25% on 16 parameters, regression tests'],
       ['Learning creates context-specific output gating (Yang Fig. 7d,e)', 'supported, for readout ≤ 15 Hz per synapse', '§4, §6'],
       ['The model reproduces Yang’s single-neuron figures and Zhang’s wiring', 'supported; inhibited-branch weakening partial', '§4'],
       ['MD gating is needed for context-specific recall', 'supported', 'no gating: S ≈ 0 at every overlap (§7)'],
       ['MD gating protects an old memory', 'only for disjoint inputs, or ≤ 25% overlap with 12-s blocks', '§7'],
       ['Inhibition erases a memory whose inputs stay active', 'not robust (0.69 ± 0.26, bimodal); not claimed', '§7'],
       ['The mechanism survives a recurrent network', 'supported up to a stability limit (gain 0.6 of our weights)', '§8'],
       ['MD can come from a PFC↔MD loop', 'supported (rate loop); a self-sustained loop needs competition and specificity', '§8'],
       ['Context alternation works the same in the network', 'supported at every overlap (the apparent extra recency was seeds and learning rate)', '§8 steps 4a, 4b'],
       ['The alternation result is robust to parameters', 'supported in 30/32 ±25% changes; needs SOM inhibition strong relative to NMDA', '§6'],
       ['Our neuron and circuit reproduce Yang’s network-level figures (3–6)', 'supported with Yang’s method (rate model refit to our neuron)', '§4']])
sp('Open points.', "")
bullets([
    ('Inhibited-branch weakening', "is slow at our learning length (8 × 3 s); gating does not depend on it."),
    ('Readout regime.', "Learned gating shows only for readout drive ≤ 15 Hz per synapse; above that an "
     "open gate makes any branch plateau."),
    ('Assumptions.', "Branch-specific MD→VIP channels (needed, not given by either paper); the recurrent "
     "weights (our guesses, so the safe gain has no biological calibration yet); the PFC↔MD loop in rate "
     "units (a spiking version had no working regime)."),
    ('SOM rate.', "Gating needs SOM at ≈ 30 Hz against Yang’s ≈ 10 Hz, because our dendrite is less "
     "shunted by inhibition than Yang’s fit."),
    ('Network at 80 Hz learning', "keeps the previous context at 50% overlap (0.53), unlike the single cell "
     "and the network at 50 Hz. Unexplained."),
])
sp('Next steps.', "")
bullets([
    "Understand why the network learning at 80 Hz keeps the previous context at 50% overlap.",
    "Overlap and retention experiments on the network.",
    "A more realistic E/I balance or a larger network, to see whether the stability limit moves.",
    "Re-run the ketamine / MD→VIP block experiment on the canonical model.",
    "Toward Yang’s network scale and Zhang’s task-level question (MD and task uncertainty).",
])

# ===========================================================================
out_path = os.path.join(DOCS, 'Progress_Report.docx')
doc.save(out_path)
print(f"Saved {out_path}")
if os.name == 'nt':      # the Drive path is a Windows path; on Linux it would create a stray local file
    try:
        doc.save(GDRIVE_PATH)
        print(f"Saved {GDRIVE_PATH}")
    except Exception as e:
        print(f"Could not save to Google Drive path ({GDRIVE_PATH}): {e}")
else:
    print(f"Not on Windows: Google Drive copy ({GDRIVE_PATH}) skipped; upload docs/meetings/Progress_Report.docx by hand")
