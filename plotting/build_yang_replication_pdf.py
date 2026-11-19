"""
build_yang_replication_pdf.py -- one PDF with every Yang, Murray & Wang 2016 figure reproduced
from our model (2026-11-19). One landscape page per figure: the image, Yang's claim, our result,
the verdict and how it was made. Figures still running are listed as pending; figures that
cannot be reproduced are listed with the reason.

Images: figures/yang_replication/*.png (written by notebooks/yang_replication.ipynb), with
fallbacks to earlier canonical figures where the notebook has not produced one yet.
Numbers: results/current/yang_replication_summary.json (written by the notebook), or --summary.
Run:  <py> -I plotting/build_yang_replication_pdf.py [--summary path] [--out path]
Out:  docs/reports/Yang2016_replication.pdf
"""
import os, sys, json, argparse, textwrap, datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.backends.backend_pdf import PdfPages

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = lambda *p: os.path.join(PROOT, 'figures', *p)
YR = lambda n: F('yang_replication', n + '.png')
NAVY, BLUE, ORANGE, GREY, GREEN = '#15233B', '#0B62A4', '#C2510B', '#6B7686', '#2E7D32'

# key = row label in the notebook's SUMMARY; images = candidates, first existing wins
ENTRIES = [
    dict(fig='Fig. 1', title='Dendritic disinhibitory motif (schematic)', images=[F('circuit_canonical.png')], key=None,
         yang='Control input → VIP ⊣ SOM ⊣ pyramidal dendrite; each pathway is gated by disinhibiting the dendrites it targets.',
         ours='Our canonical circuit implements the motif with MD as the control: MD_k → VIP_k ⊣ SOM_k ⊣ branch k (Zhang 2025 wiring).',
         verdict='schematic', how='Diagram only; nothing to simulate.'),
    dict(fig='Fig. 2b,c,e–g', title='NMDA plateau, disinhibition opens the gate, tuning is transmitted',
         images=[YR('fig2'), F('yang_fig2_model.png')], key='Fig. 2e',
         yang='Plateau from ~20–25 coactive synapses; disinhibition (35 → 5 Hz) opens the gate; with gate 1 open the neuron is tuned to pathway 1 (S ≈ 0.6).',
         ours='Plateau from ~25 synapses; 27 vs 8 Hz at the preferred stimulus, S = 0.60.', verdict='match',
         how='Our spiking reduced neuron (model/equations.py), canonical NMDA-only synapse, Yang protocol (plotting/yang_fig2_supp1.py).'),
    dict(fig='Fig. 2c fit', title='Dendritic half-activation g½ = 5.56 (g_L,D + g_I)', images=[F('v1_dendrite_io_yang.png')], key=None,
         yang='g½ rises linearly with inhibition: 22.2, 27.8, 33.4, 44.5, 55.6, 77.8 nS at g_I = 0, 1, 2, 4, 6, 10 nS.',
         ours='Measured on our spiking dendrite: 24.9, 26.6, 33.6, 39.7, 52.9, 68.4 nS (fit 4.51 (g_I + 5.27)); within 12%.',
         verdict='match', how='experiments/v1_dendrite_io_measured.py yang (non-circular: measured, not the fit formula).'),
    dict(fig='Supp. Fig. 1f–h', title='Inhibition gates NMDA input strongly, AMPA input weakly',
         images=[YR('supp1_fgh'), F('yang_supp1_fgh_model.png')], key='Supp. 1g,h',
         yang='30 Hz inhibition suppresses the NMDA plateau but barely changes AMPA-driven depolarisation.',
         ours='Same qualitative result on our dendrite.', verdict='match', how='plotting/yang_fig2_supp1.py, Yang protocol.'),
    dict(fig='Supp. Fig. 2c,d', title='NMDA saturation lets mild inhibition control the plateau', images=[YR('supp2_cd')], key='Supp. 2c,d',
         yang='Steady state jumps to a plateau above θ_NMDA; NMDA saturation caps the effective input, so moderate inhibition keeps it below θ.',
         ours='', verdict='', how='Yang Eq. 24 solved with our constants (g_L,D 4 nS, 2.5 nS/synapse, our Mg block and NMDA kinetics).'),
    dict(fig='Supp. Fig. 3c', title='AMPA input degrades gating', images=[YR('supp3c')], key='Supp. 3c',
         yang='Gating selectivity falls as the AMPA fraction of the excitatory conductance rises.',
         ours='', verdict='', how='Fig. 2e protocol on our spiking neuron, total 2.5 nS per synapse split AMPA/NMDA (experiments/yang_figures.py supp3).'),
    dict(fig='Supp. Fig. 4', title='Multi-compartment rate model, refit to our spiking neuron', images=[YR('supp4')], key='Supp. 4',
         yang='Dendrite: sigmoid family, b_g 5.56, k 9.64 nS, γ 6.54 nS, V0 0.78 mV. Soma: r = [max(0, I + 174.86)/45.16]^2.89.',
         ours='', verdict='refit',
         how='15 NMDA synapses at 30 Hz, 0.25–5 nS each; inhibition 0–100 Hz; soma clamped at −60 mV. Soma f–I with V_D held, G_c = 8 nS, 500 Hz background (rest 2.2 Hz vs Yang 1.8 Hz).'),
    dict(fig='Fig. 3b,c', title='Single neuron: sparser and stronger disinhibition gate better', images=[YR('fig3')], key='Fig. 3b,c',
         yang='S falls as N_disinh/N_dend rises (pathways overlap more); higher with stronger disinhibition; non-overlapping patterns highest but < 1.',
         ours='', verdict='',
         how='Points: our SPIKING neuron with 10, 20 or 30 dendrites (Yang used the rate model), 32 random draws per point. Lines: rate model with our fit (solid) and Yang\'s fit (dotted).'),
    dict(fig='Fig. 4c–f', title='SOM–pyramidal column with random connectivity', images=[YR('fig4')], key='Fig. 4',
         yang='S ≈ 0.5 at the measured N_SOM→dend ≈ 5; S is set by N_SOM→dend alone (c–e flat) and is highest when each dendrite has few SOM inputs (f).',
         ours='', verdict='',
         how='Yang\'s network (1,000 pyramidal × 30 dendrites, 160 SOM, 50% of SOM silenced per context, Eq. 31 alignment) with the rate neuron fitted to ours; dotted = Yang\'s fit in the same code.'),
    dict(fig='Fig. 5b,c,e,f', title='Making SOM context-selective with VIP control', images=[YR('fig5')], key='Fig. 5b,c',
         yang='Control to VIP only: S high only if few VIP cells are targeted and VIP→SOM is sparse. Control to VIP and SOM: S depends on SOM targeting, not on VIP targeting or P_VIP→SOM.',
         ours='', verdict='',
         how='Yang\'s VIP–SOM–pyramidal rate network, rate neuron fitted to ours. (Our circuit-level analogue, branch-specific MD→VIP→SOM, gives S = 0.93: robustness_r3_canonical.)'),
    dict(fig='Supp. Fig. 5', title='VIP inhibition onto SOM is nearly uniform; selectivity comes from control to SOM',
         images=[YR('supp5')], key='Fig. 5e,f',
         yang='With dense VIP→SOM, VIP currents onto SOM are nearly uniform; the total current varies through the control input to SOM.',
         ours='', verdict='', how='Same network, scheme d (50% of VIP and SOM targeted, P_VIP→SOM = 0.6).'),
    dict(fig='Fig. 6b, Supp. Fig. 6', title='Somatic PV inhibition improves gating', images=[YR('fig6')], key='Fig. 6b',
         yang='A moderate rise in somatic inhibition always improves S; too strong silences many neurons and S falls. The somatic inhibition is nearly uniform.',
         ours='', verdict='', how='Fig. 5d network plus 200 linear PV cells (Eqs. 29–30); x-axis = weight of each SOM→PV connection.'),
    dict(fig='Fig. 7b', title='Inhibition raises the potentiation threshold', images=[YR('fig7b'), F('paper_comparison_v2.png')], key='Fig. 7b',
         yang='Weak inhibition: no change → LTD → LTP with rate. Medium: LTP threshold shifts up. Strong: no LTP in a reasonable range.',
         ours='Disinhibited branch: Δw 0 at ≤ 5 Hz, LTD at 10 Hz, LTP from 15 Hz. SOM 13 Hz: LTP only from 150 Hz. SOM 31/60 Hz: no LTP up to 150 Hz.',
         verdict='match', how='Canonical circuit, inhibition from its own SOM cells, 300 s, post 10 Hz (experiments/paper_comparison.py).'),
    dict(fig='Fig. 7c', title='Learning aligns excitation with disinhibition', images=[YR('fig7c')], key='Fig. 7c',
         yang='Activated synapses onto disinhibited branches strengthen; onto inhibited branches they weaken.',
         ours='Earlier runs: free branch w 2.78 (ρ 0.93), inhibited branch unchanged at w 1.0.', verdict='partial',
         how='Canonical circuit: A then B, 8 × 3 s each at 50 Hz, MD opening the branch (experiments/yang_figures.py fig7).'),
    dict(fig='Fig. 7d,e', title='No gate preference before learning, pathway-specific gating after', images=[YR('fig7de')], key='Fig. 7d,e',
         yang='Before learning S ≈ 0; after learning S ≈ 0.7, with tuning dominated by the gated pathway.',
         ours='Earlier runs (no tuning curves): S ≈ 0 before, 0.88 after (10 Hz readout).', verdict='match',
         how='Canonical circuit, frozen readout, tuning u = U exp(−z²); drive equalised before/after as Yang (U 10 Hz after, scaled by Σw before).'),
]
NOT_REPRODUCIBLE = [
    ('Fig. 8a–f, Supp. Fig. 8', 'Fits to a monkey\'s choices in the context-dependent task (Mante et al. 2013) through a Wong–Wang decision network: needs the behavioural data and a model that is not part of this project.'),
    ('Supp. Fig. 1a–d', 'Reconstructed pyramidal neuron in NEURON; our model is the reduced compartmental neuron.'),
    ('Supp. Fig. 2a,b,e–h', 'Needs a non-saturating NMDA variant; low-rate inhibition is covered by Fig. 2c.'),
    ('Supp. Fig. 3d,e', 'GABA_B fraction: GABA_B is not part of the canonical dendrite.'),
    ('Supp. Fig. 7', 'Plasticity model fitted to Sjöström et al. 2001 slice data: needs the data; our plasticity uses Yang\'s fitted constants.'),
]


def wrap(s, w):
    return '\n'.join(textwrap.fill(p, w) for p in s.split('\n'))


def page_figure(pdf, e, idx, n):
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.text(0.04, 0.95, e['fig'], fontsize=11, color=BLUE, weight='bold')
    fig.text(0.04, 0.91, e['title'], fontsize=17, color=NAVY, weight='bold')
    fig.text(0.96, 0.95, f'{idx} / {n}', fontsize=9, color=GREY, ha='right')
    img = next((p for p in e['images'] if os.path.exists(p)), None)
    ax = fig.add_axes([0.04, 0.27, 0.92, 0.6]); ax.axis('off')
    if img:
        ax.imshow(mpimg.imread(img)); ax.set_aspect('equal')
        fig.text(0.96, 0.255, os.path.relpath(img, PROOT), fontsize=7, color=GREY, ha='right')
    else:
        ax.text(0.5, 0.5, 'PENDING — simulation still running on toothless', ha='center', va='center', fontsize=16, color=ORANGE)
        ax.add_patch(plt.Rectangle((0.02, 0.05), 0.96, 0.9, fill=False, ls='--', color=ORANGE, transform=ax.transAxes))
    vc = {'match': GREEN, 'partial': ORANGE, 'check': ORANGE, 'refit': BLUE, 'schematic': GREY}.get(e['verdict'].split()[0] if e['verdict'] else '', GREY)
    rows = [('Yang', e['yang']), ('Ours', e['ours'] or '—'), ('How', e['how'])]
    y = 0.215
    for lab, txt in rows:
        fig.text(0.04, y, lab, fontsize=9.5, weight='bold', color=NAVY, va='top')
        t = wrap(txt, 140)
        fig.text(0.10, y, t, fontsize=9.5, color='#222222', va='top')
        y -= 0.028 * (t.count('\n') + 1) + 0.012
    fig.text(0.96, 0.91, (e['verdict'] or 'pending').upper(), fontsize=14, weight='bold', color=vc if img else ORANGE, ha='right')
    pdf.savefig(fig); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--summary', default=os.path.join(PROOT, 'results', 'current', 'yang_replication_summary.json'))
    ap.add_argument('--out', default=os.path.join(PROOT, 'docs', 'reports', 'Yang2016_replication.pdf'))
    a = ap.parse_args()
    summ = {}
    if os.path.exists(a.summary):
        summ = {r[0]: r for r in json.load(open(a.summary))}
    for e in ENTRIES:
        r = summ.get(e['key'])
        if r:
            e['ours'] = r[2]
            e['verdict'] = r[3]
        if not any(os.path.exists(p) for p in e['images']):
            e['verdict'] = ''
    done = [e for e in ENTRIES if any(os.path.exists(p) for p in e['images'])]
    pend = [e for e in ENTRIES if e not in done]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with PdfPages(a.out) as pdf:
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.text(0.05, 0.88, 'Yang, Murray & Wang 2016 — replicated with our model', fontsize=24, weight='bold', color=NAVY)
        fig.text(0.05, 0.83, 'Thalamocortical gating project · every reproducible figure of the paper and its supplement · '
                 + datetime.date.today().isoformat(), fontsize=11, color=GREY)
        y = 0.76
        fig.text(0.05, y, 'Figure', fontsize=10, weight='bold', color=NAVY); fig.text(0.22, y, 'Content', fontsize=10, weight='bold', color=NAVY)
        fig.text(0.80, y, 'Status', fontsize=10, weight='bold', color=NAVY); y -= 0.028
        for e in ENTRIES:
            st = (e['verdict'] or 'pending') if e in done else 'pending (running)'
            c = GREEN if st.startswith('match') else (ORANGE if st.startswith(('pending', 'partial', 'check')) else BLUE if st == 'refit' else GREY)
            fig.text(0.05, y, e['fig'], fontsize=9.5); fig.text(0.22, y, e['title'], fontsize=9.5); fig.text(0.80, y, st, fontsize=9.5, color=c, weight='bold')
            y -= 0.026
        for f_, why in NOT_REPRODUCIBLE:
            fig.text(0.05, y, f_, fontsize=9.5, color=GREY); fig.text(0.22, y, textwrap.shorten(why, 95), fontsize=9.5, color=GREY)
            fig.text(0.80, y, 'not reproducible', fontsize=9.5, color=GREY, weight='bold'); y -= 0.026
        fig.text(0.05, 0.06, wrap('Spiking panels use the project\'s reduced neuron and canonical circuit (model/). Figs. 3–6 are rate-network '
                 'results in Yang too: here Yang\'s rate model is refit to our spiking neuron (Supp. Fig. 4) and placed in Yang\'s interneuron '
                 'networks; dotted lines repeat the computation with Yang\'s published fit. Source: notebooks/yang_replication.ipynb.', 150),
                 fontsize=8.5, color=GREY)
        pdf.savefig(fig); plt.close(fig)
        for i, e in enumerate(ENTRIES, 1):
            page_figure(pdf, e, i, len(ENTRIES))
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.text(0.05, 0.9, 'Not reproducible with this model', fontsize=18, weight='bold', color=NAVY)
        y = 0.82
        for f_, why in NOT_REPRODUCIBLE:
            fig.text(0.05, y, f_, fontsize=11, weight='bold', color=NAVY, va='top')
            t = wrap(why, 110); fig.text(0.25, y, t, fontsize=11, va='top'); y -= 0.05 * (t.count('\n') + 1) + 0.02
        pdf.savefig(fig); plt.close(fig)
    print('wrote', a.out, f'({len(done)} figures, {len(pend)} pending: {", ".join(e["fig"] for e in pend) or "none"})')


if __name__ == '__main__':
    main()
