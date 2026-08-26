"""
print_network_summary.py — Live Brian 2 Network & Synapses Inspection

Builds the same network as `demo_v2_zhang2025.py` and reports what actually exists:
population sizes are read with len(group), synapse counts with len(synapses), and
equations are printed from the Brian 2 objects themselves.

Nothing here is hardcoded. An earlier version of this script printed a fixed list of
string literals, seven of which had drifted from the code (it claimed 30 dendritic
branches against an actual 2, 10 interneurons per class against 20, 20 MD cells
against 50, and p=0.50 for two projections whose real probability is 0.6). Reading
from the live objects makes that class of drift impossible.

The network is constructed but never run, so this stays fast.
"""
import sys, os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'model'))

import builtins
import numpy as np
from brian2 import *
prefs.codegen.target = 'numpy'
import brian2

from parameters import params, plasticity_params, pv_params, som_params, vip_params, md_params
from equations import (attach_rho_clipper, eqs_soma, eqs_dend, eqs_pv, eqs_som, eqs_vip,
                       eqs_synapse_plasticity, on_pre_plasticity)

RULE = '=' * 78
THIN = '-' * 78


def build_reference_network():
    """Construct the demo network. Mirrors demo_v2_zhang2025.py exactly."""
    p = params.copy()
    for extra in (plasticity_params, pv_params, som_params, vip_params, md_params):
        p.update(extra)

    num_pyr, num_dend_each = 1, 2
    p['num_Soma'] = num_pyr
    p['num_DendEach'] = num_dend_each
    p['num_Dend'] = num_pyr * num_dend_each
    p['gTotCouple_pyr'] = p['gEachCouple_pyr'] * num_dend_each

    t = p['tau_Ca_bAP_rise'] / p['tau_Ca_bAP_decay']
    p['norm_factor_Ca'] = t ** (1 / (t - 1))
    t = p['tauGABABRise'] / p['tauGABABDecay']
    p['norm_factor_GABAB'] = t ** (1 / (t - 1))

    groups, synapses = {}, {}

    groups['Soma'] = NeuronGroup(
        num_pyr, eqs_soma, threshold='V > vThres_pyr',
        reset='V = vReset_pyr',
        refractory=p['refracTime_pyr'], method='euler', namespace=p, name='Soma')
    groups['Dend'] = NeuronGroup(
        p['num_Dend'], eqs_dend, method='euler', namespace=p, name='Dend')
    groups['PV'] = NeuronGroup(
        p['n_pv'], eqs_pv, threshold='V > vThres_pv', reset='V = vReset_pv',
        refractory=p['refrac_pv'], method='euler', namespace=p, name='PV')
    groups['SOM'] = NeuronGroup(
        p['n_som_spike'], eqs_som, threshold='V > vThres_som', reset='V = vReset_som',
        refractory=p['refrac_som'], method='euler', namespace=p, name='SOM')
    groups['VIP'] = NeuronGroup(
        p['n_vip_spike'], eqs_vip, threshold='V > vThres_vip', reset='V = vReset_vip',
        refractory=p['refrac_vip'], method='euler', namespace=p, name='VIP')
    groups['MD'] = PoissonGroup(p['n_md'], rates=5 * Hz, name='MD')
    groups['BG_pv'] = PoissonGroup(p['n_pv'], rates=p['rate_bg_pv'], name='BG_pv')
    groups['Pathway'] = PoissonGroup(30, rates=80 * Hz, name='Pathway')

    synapses['bAP'] = Synapses(groups['Soma'], groups['Dend'],
                               on_pre='V_post += bAP_amp\nbAPCa_rise_post += norm_factor_Ca', delay=p['bAP_delay'],
                               namespace=p, name='bAP')
    synapses['bAP'].connect(j='i*num_DendEach + k for k in range(num_DendEach)')

    spec = [
        ('BG->PV',   'BG_pv', 'PV',   'gTotAMPA_post += weight_bg_pv',  None,               'weight_bg_pv'),
        ('MD->PV',   'MD',  'PV',   'gTotAMPA_post += gAMPA_pv',       'p_md2pv',          'gAMPA_pv'),
        ('MD->VIP',  'MD',  'VIP',  'gTotAMPA_post += gAMPA_vip',      'p_md2vip',         'gAMPA_vip'),
        ('VIP->SOM', 'VIP', 'SOM',  'gTotGABA_post += gGABA_som',      'p_vip2som_spike',  'gGABA_som'),
        ('SOM->Dend','SOM', 'Dend', 'gTotGABA_post += gGABA',          'p_som2dend_spike', 'gGABA'),
        ('PV->Soma', 'PV',  'Soma', 'gTotGABA_post += gGABA_pv2soma',  'p_pv2soma',        'gGABA_pv2soma'),
    ]
    meta = {}
    for label, src, tgt, on_pre, pkey, gkey in spec:
        syn = Synapses(groups[src], groups[tgt], on_pre=on_pre, namespace=p,
                       name=label.replace('->', '_to_'))
        if pkey is None:
            syn.connect(j='i')
        else:
            syn.connect(p=p[pkey])
        synapses[label] = syn
        meta[label] = (pkey, p[pkey] if pkey else 1.0, gkey, p[gkey], on_pre)

    syn_plastic = Synapses(groups['Pathway'], groups['Dend'],
                           model=eqs_synapse_plasticity, on_pre=on_pre_plasticity,
                           method='heun', namespace=p, name='Pathway_to_Dend')
    syn_plastic.connect()
    syn_plastic.rho = 0.5
    attach_rho_clipper(syn_plastic)
    synapses['Pathway->Dend'] = syn_plastic
    meta['Pathway->Dend'] = (None, 1.0, 'gAMPA', p['gAMPA'], on_pre_plasticity.strip())

    net = Network(list(groups.values()) + list(synapses.values()))
    return net, groups, synapses, meta, p


def inspect_network():
    print(RULE)
    print('  BRIAN 2 THALAMOCORTICAL NETWORK — LIVE INSPECTION')
    print(f'  brian2 {brian2.__version__} | numpy {np.__version__} | '
          f'python {sys.version.split()[0]}')
    print(RULE)

    net, groups, synapses, meta, p = build_reference_network()

    # ── 1. Populations, read from the objects ──────────────────────
    print('\n[1] NEURON POPULATIONS  (size read via len(group))')
    print(THIN)
    print(f'  {"Group":<10} {"N":>5}  {"Type":<14} {"State variables"}')
    for key, g in groups.items():
        kind = type(g).__name__
        if isinstance(g, PoissonGroup):
            # A constant rate is stored as a 0-d array, a per-cell rate as 1-d.
            r = np.atleast_1d(np.asarray(g._rates))
            svars = ('rates = %g Hz (uniform)' % r[0] if r.size == 1
                     else 'rates = %g..%g Hz' % (r.min(), r.max()))
        else:
            svars = ', '.join(sorted(v for v in g.variables
                                     if not v.startswith('_') and v not in ('N', 't', 'dt', 'i')))
            if len(svars) > 44:
                svars = svars[:41] + '...'
        print(f'  {key:<10} {len(g):>5}  {kind:<14} {svars}')

    total_neurons = builtins.sum(len(g) for g in groups.values())
    print(f'\n  Total units in network: {total_neurons}')
    print(f'  Dendritic branches per pyramidal cell: '
          f'{len(groups["Dend"]) // len(groups["Soma"])}  (num_DendEach = {p["num_DendEach"]})')

    # ── 2. Synapses, counts read from the objects ──────────────────
    print('\n[2] SYNAPTIC WIRING  (synapse count read via len(synapses))')
    print(THIN)
    print(f'  {"Projection":<15} {"src":>5} {"tgt":>5} {"syn":>6} {"p_req":>7} '
          f'{"p_meas":>7}  {"weight":<12} on_pre')
    for label, syn in synapses.items():
        if label == 'bAP':
            pkey, preq, gkey, gval, on_pre = None, None, 'bAP_amp', p['bAP_amp'], 'V_post += bAP_amp'
        else:
            pkey, preq, gkey, gval, on_pre = meta[label]
        ns, nt, n = len(syn.source), len(syn.target), len(syn)
        pmeas = n / (ns * nt) if ns * nt else float('nan')
        preq_s = f'{preq:.2f}' if preq is not None else '  —'
        print(f'  {label:<15} {ns:>5} {nt:>5} {n:>6} {preq_s:>7} {pmeas:>7.2f}  '
              f'{str(gval):<12} {on_pre.splitlines()[0]}')

    n_syn_total = builtins.sum(len(sy) for sy in synapses.values())
    print(f'\n  Total synapses: {n_syn_total}')
    print('  p_req is the probability requested from parameters.py; p_meas is the')
    print('  realised fraction after Brian 2 drew the connections.')

    # ── 3. Connection probabilities, straight from parameters.py ───
    print('\n[3] CONNECTION PROBABILITIES  (values read from parameters.py)')
    print(THIN)
    for k in ('p_md2pv', 'p_md2vip', 'p_vip2som_spike', 'p_som2dend_spike', 'p_pv2soma'):
        print(f'  {k:<20} = {p[k]}')

    # ── 4. Equations, printed from the live objects ────────────────
    print('\n[4] MEMBRANE EQUATIONS  (printed from group.equations)')
    print(THIN)
    for key in ('Soma', 'Dend', 'PV', 'SOM', 'VIP'):
        print(f'\n  --- {key} (N={len(groups[key])}) ---')
        for line in str(groups[key].equations).splitlines():
            if line.strip():
                print(f'    {line}')

    # ── 5. Plasticity, printed from the live Synapses object ───────
    syn = synapses['Pathway->Dend']
    print('\n[5] GRAUPNER-BRUNEL PLASTICITY SYNAPSE')
    print(THIN)
    print(f'  {len(syn.source)} pathway inputs x {len(syn.target)} branches '
          f'= {len(syn)} plastic synapses')
    print(f'  rho initialised to {syn.rho[0]:.3f}\n')
    for line in str(syn.equations).splitlines():
        if line.strip():
            print(f'    {line}')

    print('\n  on_pre:')
    for line in on_pre_plasticity.strip().splitlines():
        print(f'    {line}')

    # Probe the postsynaptic calcium pathway. `on_post` is deliberately NOT the
    # mechanism here: Dend has no threshold, so an on_post rule could never fire. The
    # postsynaptic term is read from the branch's bAPCa trace instead.
    eq_names = set(syn.equations.names)
    reads_post = any('bAPCa_post' in str(syn.equations[n].expr)
                     for n in eq_names if syn.equations[n].type == SUBEXPRESSION)
    dend_has_bapca = 'bAPCa' in groups['Dend'].variables
    bap_injects = 'bAPCa_rise' in synapses['bAP'].pre.code
    print('\n  Postsynaptic calcium pathway:')
    print(f'    Dend carries a bAPCa trace          : {dend_has_bapca}')
    print(f'    bAP synapse injects norm_factor_Ca  : {bap_injects}')
    print(f'    plasticity reads bAPCa_post         : {reads_post}')
    if dend_has_bapca and bap_injects and reads_post:
        print('    -> pathway CONNECTED: soma spike -> bAP (delay '
              f'{p["bAP_delay"]}) -> branch bAPCa -> c_total -> thresholds')
    else:
        print('    -> pathway BROKEN: synaptic calcium is presynaptic-only, so')
        print('       dendritic state cannot gate plasticity.')

    print('\n[6] PLASTICITY PARAMETERS  (values read from parameters.py)')
    print(THIN)
    for k in sorted(plasticity_params):
        print(f'  {k:<12} = {plasticity_params[k]}')

    print('\n' + RULE)
    print('  Inspection complete — every number above was read from a live object')
    print('  or from parameters.py, not hardcoded.')
    print(RULE)


if __name__ == '__main__':
    inspect_network()
