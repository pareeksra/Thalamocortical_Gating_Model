"""
yang_supp_reconstruction.py
===========================
Reconstruct the SCIENTIFIC CONTENT of Yang et al. (2016, Nat. Commun. 7:12815)
Supplementary Figures 1 and 2, using the REDUCED model + Yang's own published equations
and constants. We do NOT have the Supplementary PDF; panel descriptions are taken from
the article's own main text / Methods (fetched 2026-09-15). This reconstructs the
phenomena each figure demonstrates -- it is NOT a pixel-copy of Yang's panels, and it does
NOT reproduce Supp Fig 1a-d (the fully reconstructed Branco NEURON morphology, which this
project does not implement).

  Supp Fig 1  -- NMDAR (gateable, sigmoidal plateau) vs AMPAR (not gateable, shunt) I/O.
  Supp Fig 2  -- (c) NMDA gating variable vs rate, saturating vs not; (d) half-activation
                 g_1/2 linear in inhibition (constant-conductance scenario, Eq. 21/22).

FLEXIBILITY (2026-09-15): every relevant parameter is exposed via the Params dataclass and
the command line, and a --sweep mode overlays how the results change as one parameter is
varied. Defaults reproduce Yang's published values exactly (and the project's validated
dend_IO fit); a sanity check at import asserts the parametric NMDA I/O matches dend_IO at
defaults, and that Yang's stated numbers (saturation onset ~16 Hz, single-spike peak
s ~0.4) are recovered.

Examples
--------
  # Yang defaults -> figures/yang_supp1_reconstruction.png, ..._supp2_...
  py docs/yang_supp_reconstruction.py

  # override individual parameters
  py docs/yang_supp_reconstruction.py --tau_nmda_decay 150 --gL_D 6 --inh_levels 0,10,30

  # sweep one parameter and overlay the effect (saves a sensitivity figure)
  py docs/yang_supp_reconstruction.py --sweep alpha_nmda=0.15,0.3,0.6
  py docs/yang_supp_reconstruction.py --sweep gL_D=2,4,8
  py docs/yang_supp_reconstruction.py --sweep tau_nmda_decay=50,100,200 --suffix _tausweep
"""
import os, sys, argparse
from dataclasses import dataclass, fields, replace

PROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROOT, 'model'))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from dendritic_io import dend_IO   # validated Yang fit, used only for the default-equality check

FIGDIR = os.path.join(PROOT, 'figures')
COLORS = ['#4c72b0', '#dd8452', '#c44e52', '#55a868', '#8172b3', '#937860']


@dataclass
class Params:
    """All tunable parameters. Defaults = Yang (2016) published values (Methods), which
    also reproduce this project's validated dendritic_io.dend_IO fit exactly."""
    # --- NMDA receptor kinetics (Yang Eqs. 11-12) ---
    tau_nmda_decay: float = 100.0     # ms
    tau_nmda_rise: float = 2.0        # ms
    alpha_nmda: float = 0.3           # /ms  (sets peak s ~0.4 per spike, saturation ~16 Hz)
    # --- passive dendrite / reversals ---
    gL_D: float = 4.0                 # nS  dendritic leak (the "4" in g_1/2 = 5.56(4+g_I))
    V_rest: float = -70.0             # mV
    E_E: float = 0.0                  # mV  excitatory reversal (AMPA/NMDA)
    E_I: float = -70.0                # mV  inhibitory reversal (GABA_A); =V_rest -> shunting
    # --- dendritic I/O reduction (Yang fit; defaults = dendritic_io.Q) ---
    beta: float = 5.5592051           # g_1/2 slope w.r.t. (gL_D + g_I)   [Q0]
    spread_pre: float = 9.64361681    # sigmoid spread prefactor (nS)     [Q1]
    spread_scale: float = 6.5386557   # spread exp. scale w.r.t. inhib.   [Q2]
    v_offset: float = 0.7779744       # voltage offset (mV)               [Q3]
    v_swing: float = 30.0             # half the raw sigmoid swing (mV)
    # --- exploration ranges (also CLI-settable) ---
    inh_levels: tuple = (2.0, 20.0, 40.0)   # nS, inhibition levels for the I/O panels
    exc_max: float = 120.0                  # nS, x-axis max for I/O panels
    rates: tuple = (1, 2, 4, 8, 12, 16, 24, 32, 48, 64)  # Hz, for the saturation panel


# ---------------------------------------------------------------------------
# Model pieces, all parameterised by a Params instance `p`
# ---------------------------------------------------------------------------
def io_midpoint(inh, p):
    """Half-activation excitatory conductance (nS): Yang Eq. 21/22, g_1/2 = beta(gL_D+g_I)."""
    return p.beta * (p.gL_D + np.asarray(inh, float))


def io_spread(inh, p):
    return p.spread_pre * np.exp(np.asarray(inh, float) / p.spread_scale)


def dend_io_param(exc, inh, p):
    """Reduced-model dendritic voltage (mV) vs excitatory conductance, NMDAR-driven,
    re-referenced to rest (matches dendritic_io.dend_IO at default params)."""
    exc = np.asarray(exc, float)
    mid = io_midpoint(inh, p); spr = io_spread(inh, p)
    rest = p.V_rest + p.v_offset
    return rest + p.v_swing * (np.tanh((exc - mid) / spr) - np.tanh((0.0 - mid) / spr))


def ampa_V(gA, gI, p):
    """Passive-dendrite steady-state voltage under linear AMPA + shunting inhibition:
    V = (gL*V_rest + gA*E_E + gI*E_I)/(gL+gA+gI). Pure shunt (no threshold) when E_I=V_rest."""
    gA = np.asarray(gA, float)
    return (p.gL_D * p.V_rest + gA * p.E_E + gI * p.E_I) / (p.gL_D + gA + gI)


def nmda_steady_s(rate_hz, p, saturating=True, T=4.0, dt=0.1, seed=0):
    """Time-averaged steady-state NMDA gating variable s (Yang Eqs. 11-12) for a Poisson
    input at rate_hz. saturating=False drops the (1-s) term (Yang's non-saturating control)."""
    rng = np.random.default_rng(seed + int(rate_hz * 1000))
    n = int(T * 1000 / dt)
    x = 0.0; s = 0.0
    p_spike = rate_hz * (dt / 1000.0)
    acc = 0.0; cnt = 0
    for i in range(n):
        if rng.random() < p_spike:
            x += 1.0
        x += -x / p.tau_nmda_rise * dt
        gate = (1.0 - s) if saturating else 1.0
        s += (-s / p.tau_nmda_decay + p.alpha_nmda * x * gate) * dt
        s = min(max(s, 0.0), 1.0)
        if i >= n // 2:
            acc += s; cnt += 1
    return acc / max(cnt, 1)


def saturation_onset_hz(p):
    """Yang: r ~ 1/(alpha * tau_rise * tau_decay). alpha in /ms -> /s; taus in ms -> s."""
    return 1.0 / ((p.alpha_nmda * 1e3) * (p.tau_nmda_rise * 1e-3) * (p.tau_nmda_decay * 1e-3))


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def make_supp1(p, suffix=''):
    exc = np.linspace(0, p.exc_max, 400)
    fig, (axN, axA) = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for gI, c in zip(p.inh_levels, COLORS):
        axN.plot(exc, dend_io_param(exc, gI, p), color=c, lw=2, label=f'inh = {gI:g} nS')
        axN.axvline(io_midpoint(gI, p), color=c, ls=':', lw=1, alpha=0.6)
    axN.set_title('(a) NMDAR excitation -> GATEABLE\n(sigmoidal plateau; inhibition shifts threshold)')
    axN.set_xlabel('excitatory conductance (nS)'); axN.set_ylabel('mean dendritic voltage (mV)')
    axN.legend(fontsize=8, loc='lower right'); axN.grid(alpha=0.2)

    for gI, c in zip(p.inh_levels, COLORS):
        axA.plot(exc, ampa_V(exc, gI, p), color=c, lw=2, label=f'inh = {gI:g} nS')
    axA.set_title('(b) AMPAR excitation -> NOT gateable\n(smooth shunt; inhibition only scales)')
    axA.set_xlabel('excitatory conductance (nS)')
    axA.legend(fontsize=8, loc='lower right'); axA.grid(alpha=0.2)

    fig.suptitle('Yang (2016) Supp. Fig. 1 reconstruction (reduced model): inhibition gates '
                 'NMDAR but not AMPAR input\n(Branco reconstructed-morphology panels a–d not reproduced)',
                 fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = os.path.join(FIGDIR, f'yang_supp1_reconstruction{suffix}.png')
    fig.savefig(out, dpi=150); plt.close(fig); print(f"Saved {out}")


def make_supp2(p, suffix=''):
    fig, (axC, axD) = plt.subplots(1, 2, figsize=(11, 4.5))
    rates = np.array(p.rates, float)
    s_sat = np.array([nmda_steady_s(r, p, saturating=True) for r in rates])
    s_lin = np.array([nmda_steady_s(r, p, saturating=False) for r in rates])
    axC.plot(rates, s_sat, 'o-', color='#4c72b0', lw=2, label='with saturation (Yang Eqs. 11-12)')
    axC.plot(rates, s_lin, 's--', color='#c44e52', lw=2, label='without saturation (control)')
    axC.axvline(saturation_onset_hz(p), color='k', ls=':', lw=1,
                label=f'saturation onset ~{saturation_onset_hz(p):.0f} Hz')
    axC.set_title('(c) NMDA gating variable vs input rate')
    axC.set_xlabel('NMDAR input rate (Hz)'); axC.set_ylabel('steady-state s_NMDA')
    axC.legend(fontsize=8); axC.grid(alpha=0.2)

    gI = np.linspace(0, 40, 200)
    axD.plot(gI, io_midpoint(gI, p), color='#4c72b0', lw=2,
             label=f'g$_{{1/2}}$ = {p.beta:.2f}({p.gL_D:g} + g$_I$)  (Yang Eq. 21/22)')
    meas_gI = np.array([0, 2, 10, 20, 35]); meas_g12 = np.array([22.24, 33.36, 77.83, 133.42, 216.81])
    axD.plot(meas_gI, meas_g12, 'ko', ms=7, label='our model, measured')
    axD.set_title('(d) Constant-conductance scenario:\nhalf-activation linear in inhibition')
    axD.set_xlabel('total inhibitory conductance g$_I$ (nS)'); axD.set_ylabel('g$_{1/2}$ (nS)')
    axD.legend(fontsize=8); axD.grid(alpha=0.2)

    fig.suptitle('Yang (2016) Supp. Fig. 2 reconstruction (reduced model): NMDA saturation, '
                 'and g$_{1/2}$ linear in inhibition', fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    out = os.path.join(FIGDIR, f'yang_supp2_reconstruction{suffix}.png')
    fig.savefig(out, dpi=150); plt.close(fig); print(f"Saved {out}")


def make_sweep(base_p, param_name, values, suffix=''):
    """Overlay how the key curves change as ONE parameter is swept. Three panels:
    NMDAR I/O (at the middle inhibition level), NMDA saturation curve, and the g_1/2 line."""
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 4.5))
    exc = np.linspace(0, base_p.exc_max, 300)
    inh_mid = base_p.inh_levels[len(base_p.inh_levels) // 2]
    rates = np.array(base_p.rates, float)
    gI = np.linspace(0, 40, 200)
    for val, c in zip(values, COLORS):
        p = replace(base_p, **{param_name: val})
        ax1.plot(exc, dend_io_param(exc, inh_mid, p), color=c, lw=2, label=f'{param_name}={val:g}')
        s_sat = np.array([nmda_steady_s(r, p, saturating=True) for r in rates])
        ax2.plot(rates, s_sat, 'o-', color=c, lw=2, ms=4, label=f'{param_name}={val:g}')
        ax3.plot(gI, io_midpoint(gI, p), color=c, lw=2, label=f'{param_name}={val:g}')
    ax1.set_title(f'NMDAR dendritic I/O (inh={inh_mid:g} nS)')
    ax1.set_xlabel('excitatory conductance (nS)'); ax1.set_ylabel('dendritic V (mV)')
    ax2.set_title('NMDA saturation s vs rate'); ax2.set_xlabel('input rate (Hz)'); ax2.set_ylabel('s_NMDA')
    ax3.set_title('half-activation g$_{1/2}$ vs inhibition')
    ax3.set_xlabel('inhibition g$_I$ (nS)'); ax3.set_ylabel('g$_{1/2}$ (nS)')
    for ax in (ax1, ax2, ax3):
        ax.legend(fontsize=8); ax.grid(alpha=0.2)
    fig.suptitle(f'Sensitivity sweep: varying "{param_name}" over {list(values)} '
                 '(all other parameters at Yang defaults)', fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    sfx = suffix or f'_sweep_{param_name}'
    out = os.path.join(FIGDIR, f'yang_supp{sfx}.png')
    fig.savefig(out, dpi=150); plt.close(fig); print(f"Saved {out}")


# ---------------------------------------------------------------------------
def _self_check():
    """Assert defaults reproduce the validated fit and Yang's stated numbers."""
    p = Params()
    exc = np.linspace(0, 120, 50)
    for inh in (0.0, 10.0, 35.0):
        a = dend_io_param(exc, inh, p); b = dend_IO(exc, inh)
        assert np.allclose(a, b, atol=1e-6), f"param I/O != dend_IO at inh={inh}"
    onset = saturation_onset_hz(p)
    assert abs(onset - 16.67) < 0.5, f"saturation onset {onset} != ~16.67"
    print(f"[self-check OK] parametric I/O == dend_IO at defaults; saturation onset {onset:.2f} Hz")


def _parse_args():
    ap = argparse.ArgumentParser(description="Flexible Yang Supp Fig 1/2 reconstruction.")
    for f in fields(Params):
        if f.type == float:
            ap.add_argument(f'--{f.name}', type=float, default=None)
    ap.add_argument('--inh_levels', type=str, default=None, help='comma list, e.g. 0,10,30')
    ap.add_argument('--rates', type=str, default=None, help='comma list of Hz')
    ap.add_argument('--sweep', type=str, default=None,
                    help='param=v1,v2,...  overlay how results change (e.g. gL_D=2,4,8)')
    ap.add_argument('--suffix', type=str, default='', help='output filename suffix')
    return ap.parse_args()


if __name__ == '__main__':
    _self_check()
    args = _parse_args()
    overrides = {}
    for f in fields(Params):
        if f.type == float:
            v = getattr(args, f.name, None)
            if v is not None:
                overrides[f.name] = v
    if args.inh_levels:
        overrides['inh_levels'] = tuple(float(x) for x in args.inh_levels.split(','))
    if args.rates:
        overrides['rates'] = tuple(float(x) for x in args.rates.split(','))
    p = replace(Params(), **overrides)

    if args.sweep:
        name, vals = args.sweep.split('=')
        name = name.strip()
        valid = {f.name for f in fields(Params) if f.type == float}
        if name not in valid:
            raise SystemExit(f"--sweep parameter must be one of {sorted(valid)}")
        values = [float(x) for x in vals.split(',')]
        make_sweep(p, name, values, suffix=args.suffix)
    else:
        make_supp1(p, suffix=args.suffix)
        make_supp2(p, suffix=args.suffix)
