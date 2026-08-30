"""
formula_comparison.py  --  Step 2a diagnostic
=============================================
Compares two ways of turning a calcium-threshold-crossing summary (alpha_d,
alpha_p) into a post-epoch synaptic state rho_new:

  (C) Model C's linearised relaxation  (numpy_models/*.py `_synapse_change`):
        rho_new = rho_bar + (rho_init - rho_bar) * exp(-(Gp+Gd)/tau)
      i.e. the deterministic exponential relaxation of the Graupner-Brunel
      double-well toward its fixed point rho_bar, with NO variance / switching term.

  (Y) Yang, Murray & Wang (2016), Nat. Commun. 7:12815, Methods p.12, Eqs. 32-35:
      the erf-based bistable UP/DOWN switching probabilities, including the
      sigma_rho^2 variance term (Eq. 33).

Both are evaluated with Yang's PUBLISHED parameters so the ONLY thing that
differs is the FORMULA, not the constants:
    w0 = 0, w1 = 3, rho* = 0.5, sigma = 3.35, tau = 346.36 s,
    gamma_d = 39.949, gamma_p = 177.552, theta_d = 1.0, theta_p = 2.78.

The alpha operating points come from Phase-1's actual calcium traces, measured by
docs/extract_phase1_alpha.py (docs/phase1_alpha_operating_points.json).

Run: python docs/formula_comparison.py
Outputs: prints a table, writes docs/formula_comparison_table.csv and
docs/figures/formula_comparison.png.
"""
import os, json
import numpy as np
from numpy import exp
from scipy.special import erf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- Yang 2016 published plasticity parameters (Methods p.12) ---------------
SIGMA   = 3.35        # noise amplitude
TAU     = 346.36      # s, weight-change time constant
GAMMA_D = 39.949      # depression strength gamma_d
GAMMA_P = 177.552     # potentiation strength gamma_p
W0      = 0.0         # DOWN-state weight
W1      = 3.0         # UP-state weight  (Yang's actual value; NOT the 1.0 in Model C)
RHO_STAR = 0.5        # unstable fixed point / barrier
THETA_D = 1.0
THETA_P = 2.78


# ---------------------------------------------------------------------------
# (C) Model C's linearised relaxation formula
# ---------------------------------------------------------------------------
def rho_linear(alpha_d, alpha_p, rho_init=RHO_STAR,
               tau=TAU, gamma_d=GAMMA_D, gamma_p=GAMMA_P):
    """Deterministic Graupner-Brunel relaxation (Model C `_synapse_change`).

    rho_new = rho_bar + (rho_init - rho_bar) * exp(-(Gp+Gd)/tau),
    with Gp = gamma_p*alpha_p, Gd = gamma_d*alpha_d, rho_bar = Gp/(Gp+Gd).
    No variance / switching term.
    """
    Gp = gamma_p * alpha_p
    Gd = gamma_d * alpha_d
    total = Gp + Gd
    if total < 1e-12:
        return float(rho_init)      # no calcium activity -> no change
    rho_bar = Gp / total
    return float(rho_bar + (rho_init - rho_bar) * exp(-total / tau))


# ---------------------------------------------------------------------------
# (Y) Yang 2016 Eqs. 32-35 -- the real bistable UP/DOWN switching formula
# ---------------------------------------------------------------------------
def yang_synapse_update(alpha_d, alpha_p, rho_init=RHO_STAR,
                        sigma=SIGMA, tau=TAU, gamma_d=GAMMA_D, gamma_p=GAMMA_P,
                        w0=W0, w1=W1, rho_star=RHO_STAR):
    """Yang, Murray & Wang (2016) Nat. Commun. 7:12815, Methods p.12, Eqs. 32-35.

    Over a stimulation epoch the calcium trace spends time alpha_p above theta_p
    and alpha_d above theta_d. Average potentiation Gp = gamma_p*alpha_p and
    average depression Gd = gamma_d*alpha_d (both dimensionless: gamma has units
    1/s, alpha is seconds). The bistable synapse's UP-state occupancy rho has
    long-term mean and variance:

        Eq. 32:  rho_bar   = Gp / (Gp + Gd)
        Eq. 33:  sigma_r^2 = sigma^2 * (alpha_p + alpha_d) / (Gp + Gd)

    and the DOWN->UP (U) and UP->DOWN (D) switching probabilities are

        Eq. 34:  U = 1/2 * ( 1 + erf( -(0.5 - rho_bar + rho_bar*E)
                                       / sqrt(sigma_r^2 * (1 - E^2)) ) )
        Eq. 35:  D = 1/2 * ( 1 - erf( -(0.5 - rho_bar + (rho_bar-1)*E)
                                       / sqrt(sigma_r^2 * (1 - E^2)) ) )

    where E = exp(-(Gp+Gd)/tau). The post-epoch weight (Yang, same page) is

        w_post = w_pre*(1 - D) + (w1 - w_pre)*U ,   w_pre = w0 + (w1-w0)*rho_init.

    The `rho_star` argument is the barrier location (0.5 in Yang); it is exposed
    for completeness and defaults to Yang's value. Returns a dict with U, D,
    w_pre, w_post, rho_bar, sigma_r2, and rho_new = (w_post - w0)/(w1 - w0).
    """
    Gp = gamma_p * alpha_p
    Gd = gamma_d * alpha_d
    total = Gp + Gd
    w_pre = w0 + (w1 - w0) * rho_init

    if total < 1e-12 or (alpha_p + alpha_d) < 1e-12:
        # No calcium activity above either threshold: no switching, weight held.
        return dict(U=0.0, D=0.0, w_pre=w_pre, w_post=w_pre,
                    rho_bar=float('nan'), sigma_r2=0.0, rho_new=float(rho_init))

    rho_bar = Gp / total
    sigma_r2 = sigma**2 * (alpha_p + alpha_d) / total     # Eq. 33
    E = exp(-total / tau)
    var = sigma_r2 * (1.0 - E**2)                          # denominator variance
    denom = np.sqrt(var) if var > 1e-300 else 1e-150

    argU = -(rho_star - rho_bar + rho_bar * E) / denom
    argD = -(rho_star - rho_bar + (rho_bar - 1.0) * E) / denom
    U = 0.5 * (1.0 + erf(argU))                            # Eq. 34
    D = 0.5 * (1.0 - erf(argD))                            # Eq. 35

    w_post = w_pre * (1.0 - D) + (w1 - w_pre) * U
    rho_new = (w_post - w0) / (w1 - w0)
    return dict(U=float(U), D=float(D), w_pre=float(w_pre), w_post=float(w_post),
                rho_bar=float(rho_bar), sigma_r2=float(sigma_r2), rho_new=float(rho_new))


def rho_yang(alpha_d, alpha_p, rho_init=RHO_STAR):
    return yang_synapse_update(alpha_d, alpha_p, rho_init)['rho_new']


# ---------------------------------------------------------------------------
def load_operating_points():
    fp = os.path.join(HERE, 'phase1_alpha_operating_points.json')
    with open(fp) as f:
        d = json.load(f)
    b0 = d['inhibited_branch0']; b1 = d['free_branch1']
    return {
        'inhibited': (b0['alpha_d_mean'], b0['alpha_p_mean']),
        'free': (b1['alpha_d_mean'], b1['alpha_p_mean']),
    }


def main():
    ops = load_operating_points()
    rho0 = RHO_STAR

    print("=" * 78)
    print("Step 2a: Model C linear relaxation  vs  Yang 2016 Eqs. 32-35")
    print(f"Yang params: w0={W0} w1={W1} rho*={RHO_STAR} sigma={SIGMA} tau={TAU}s "
          f"gamma_d={GAMMA_D} gamma_p={GAMMA_P}")
    print("=" * 78)

    # ---- headline: the two measured Phase-1 operating points ----
    print("\n-- Phase-1 measured operating points (rho_init = 0.5) --")
    hdr = f"{'branch':<12}{'alpha_d':>9}{'alpha_p':>9}{'rho_lin':>9}{'rho_Yang':>10}{'U':>8}{'D':>8}{'d(rho)':>9}"
    print(hdr)
    pts = {}
    for name, (ad, ap) in ops.items():
        rl = rho_linear(ad, ap, rho0)
        y = yang_synapse_update(ad, ap, rho0)
        pts[name] = dict(alpha_d=ad, alpha_p=ap, rho_lin=rl, **y)
        print(f"{name:<12}{ad:>9.4f}{ap:>9.4f}{rl:>9.4f}{y['rho_new']:>10.4f}"
              f"{y['U']:>8.4f}{y['D']:>8.4f}{y['rho_new']-rl:>9.4f}")

    ratio_lin = pts['free']['rho_lin'] / pts['inhibited']['rho_lin']
    ratio_yang = pts['free']['rho_new'] / pts['inhibited']['rho_new']
    print(f"\n  rho ratio (free/inhibited):  linear = {ratio_lin:.3f}   Yang = {ratio_yang:.3f}")
    wlin_ratio = (W0 + (W1-W0)*pts['free']['rho_lin']) / (W0 + (W1-W0)*pts['inhibited']['rho_lin'])
    wyang_ratio = pts['free']['w_post'] / pts['inhibited']['w_post']
    print(f"  w   ratio (free/inhibited):  linear = {wlin_ratio:.3f}   Yang = {wyang_ratio:.3f}")

    # ---- grid sweep table across the representative alpha range [0, T=3] ----
    print("\n-- Grid sweep, rho_init = 0.5 (alpha in seconds; T=3 s protocol) --")
    grid = [0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 2.97]
    rows = []
    print(f"{'alpha_d':>8}{'alpha_p':>8}{'rho_bar':>9}{'sigma_r':>9}{'rho_lin':>9}{'rho_Yang':>10}{'d(rho)':>9}")
    for ad in grid:
        for ap in grid:
            rl = rho_linear(ad, ap, rho0)
            y = yang_synapse_update(ad, ap, rho0)
            sr = np.sqrt(y['sigma_r2']) if y['sigma_r2'] > 0 else 0.0
            rb = y['rho_bar']
            rows.append((ad, ap, rb, sr, rl, y['rho_new'], y['rho_new'] - rl))
            # print a readable subset (ap in {0, 1, 2.97}) to keep console compact
            if ap in (0.0, 1.0, 2.97):
                rbs = f"{rb:.3f}" if rb == rb else "  -  "
                print(f"{ad:>8.2f}{ap:>8.2f}{rbs:>9}{sr:>9.3f}{rl:>9.4f}{y['rho_new']:>10.4f}{y['rho_new']-rl:>9.4f}")

    # write full CSV
    csv = os.path.join(HERE, 'formula_comparison_table.csv')
    with open(csv, 'w') as f:
        f.write("alpha_d,alpha_p,rho_bar,sigma_r,rho_linear,rho_yang,delta_rho\n")
        for r in rows:
            f.write(",".join(f"{v:.6f}" for v in r) + "\n")
    print(f"\nWrote {csv}")

    # ---- figure ----
    figdir = os.path.join(os.path.dirname(HERE), 'figures')
    os.makedirs(figdir, exist_ok=True)
    figpath = os.path.join(figdir, 'formula_comparison.png')
    _make_figure(ops, figpath)
    print(f"Wrote {figpath}")
    return pts, ratio_lin, ratio_yang


def _make_figure(ops, figpath):
    rho0 = RHO_STAR
    ad_free = ops['free'][0]
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.5))

    # Panel A: potentiation arm -- vary alpha_p, alpha_d fixed at free-branch value
    aps = np.linspace(0, 3.0, 121)
    rl = [rho_linear(ad_free, ap, rho0) for ap in aps]
    ry = [rho_yang(ad_free, ap, rho0) for ap in aps]
    ax[0].plot(aps, rl, label='Model C linear', lw=2)
    ax[0].plot(aps, ry, label='Yang Eq.32-35', lw=2)
    ax[0].axhline(0.5, color='k', ls=':', lw=1)
    ax[0].scatter([ops['free'][1]], [rho_yang(ops['free'][0], ops['free'][1], rho0)], c='C1', zorder=5)
    ax[0].scatter([ops['free'][1]], [rho_linear(ops['free'][0], ops['free'][1], rho0)], c='C0', zorder=5)
    ax[0].set_title(f'Potentiation arm\n(alpha_d fixed = {ad_free:.2f} s, free branch)')
    ax[0].set_xlabel('alpha_p (s above theta_p)'); ax[0].set_ylabel('rho_new')
    ax[0].legend(); ax[0].set_ylim(0, 1)

    # Panel B: depression arm -- vary alpha_d, alpha_p = 0 (inhibited-type)
    ads = np.linspace(0, 3.0, 121)
    rl = [rho_linear(ad, 0.0, rho0) for ad in ads]
    ry = [rho_yang(ad, 0.0, rho0) for ad in ads]
    ax[1].plot(ads, rl, label='Model C linear', lw=2)
    ax[1].plot(ads, ry, label='Yang Eq.32-35', lw=2)
    ax[1].axhline(0.5, color='k', ls=':', lw=1)
    ax[1].scatter([ops['inhibited'][0]], [rho_yang(ops['inhibited'][0], 0.0, rho0)], c='C1', zorder=5)
    ax[1].scatter([ops['inhibited'][0]], [rho_linear(ops['inhibited'][0], 0.0, rho0)], c='C0', zorder=5)
    ax[1].set_title('Depression arm\n(alpha_p = 0, inhibited branch)')
    ax[1].set_xlabel('alpha_d (s above theta_d)'); ax[1].set_ylabel('rho_new')
    ax[1].legend(); ax[1].set_ylim(0, 1)

    # Panel C: |delta rho| heatmap over the (alpha_d, alpha_p) plane
    ad_grid = np.linspace(0, 3.0, 61)
    ap_grid = np.linspace(0, 3.0, 61)
    Z = np.zeros((len(ap_grid), len(ad_grid)))
    for i, ap in enumerate(ap_grid):
        for j, ad in enumerate(ad_grid):
            Z[i, j] = rho_yang(ad, ap, rho0) - rho_linear(ad, ap, rho0)
    im = ax[2].pcolormesh(ad_grid, ap_grid, Z, shading='auto', cmap='RdBu_r',
                          vmin=-abs(Z).max(), vmax=abs(Z).max())
    ax[2].scatter([ops['inhibited'][0]], [ops['inhibited'][1]], c='k', marker='o', label='inhibited')
    ax[2].scatter([ops['free'][0]], [ops['free'][1]], c='k', marker='^', label='free')
    ax[2].set_title('rho_Yang - rho_linear')
    ax[2].set_xlabel('alpha_d (s)'); ax[2].set_ylabel('alpha_p (s)')
    ax[2].legend(loc='upper left')
    fig.colorbar(im, ax=ax[2])

    fig.tight_layout()
    fig.savefig(figpath, dpi=130)


if __name__ == '__main__':
    main()
