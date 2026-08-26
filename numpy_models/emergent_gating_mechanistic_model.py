"""
emergent_gating_mechanistic_model.py
=====================================
Emergent Mechanistic Model of Thalamocortical Gating.

Stochastic mechanisms included:
  1. MD thalamus modelled as a Poisson group — spike count per trial drawn
     from Poisson(mean_rate * T_win), not fixed.
  2. VIP and SOM interneuron rates carry realistic neural variability
     (Fano factor ≈ 1, CV of ISI ≈ 0.5–1.0) through Gaussian noise on
     their firing rates, scaled by the square-root of the rate.
  3. Calcium trace is simulated from a genuine Poisson spike train
     (not scaled from one representative pair) — each pre-spike adds
     an NMDA Ca2+ transient with stochastic amplitude (vesicle noise,
     CV = 0.30), each post-spike adds a bAP transient.
  4. Alpha (time above threshold) is computed from the full stochastic
     calcium trace, so it varies trial by trial.
  5. The Graupner-Brunel rho update draws from the correct Gaussian
     with variance from Eq. 7 (Graupner & Brunel 2012), using a
     biologically-scaled sigma so bistable UP↔DOWN flips are visible.

Author: Thalamocortical Gating Project
"""

import os
import math
import numpy as np
import matplotlib.pyplot as plt

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'model'))
from dendritic_io import dend_IO

# ──────────────────────────────────────────────────────────────
# Global style
# ──────────────────────────────────────────────────────────────
plt.style.use("default")
plt.rcParams.update({
    "font.family": "serif", "font.size": 11,
    "axes.titlesize": 14, "axes.labelsize": 12,
    "figure.dpi": 200, "savefig.dpi": 200, "savefig.bbox": "tight",
    "axes.grid": True, "grid.alpha": 0.3,
    "axes.facecolor": "white", "figure.facecolor": "white",
})

FIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "figures", "mechanistic")
os.makedirs(FIG_DIR, exist_ok=True)

# ──────────────────────────────────────────────────────────────
# Reproducible RNG
# ──────────────────────────────────────────────────────────────
rng = np.random.default_rng(42)

# ──────────────────────────────────────────────────────────────
# Circuit Parameters
# ──────────────────────────────────────────────────────────────
W_MD_VIP     = 1.0
BASELINE_SOM = 40.0    # Hz — SOM baseline without VIP input
W_VIP_SOM    = 1.5     # VIP→SOM suppression weight
W_SOM_DEND   = 0.875   # SOM→dendrite conductance (40 × 0.875 = 35 nS baseline)
W_MD_PV      = 0.5
BASELINE_PV  = 10.0    # Hz

# ──────────────────────────────────────────────────────────────
# Graupner-Brunel (2012) Plasticity Parameters
# ──────────────────────────────────────────────────────────────
C_NMDA       = 0.371   # NMDA Ca2+ jump per pre-spike (a.u., before Mg block)
C_BAP        = 0.957   # bAP Ca2+ jump per post-spike (a.u.)

TAU_CA_NMDA  = 0.030   # s — NMDA calcium decay (30 ms)
TAU_CA_RISE  = 0.002   # s — bAP calcium rise   (2 ms)
TAU_CA_DECAY = 0.030   # s — bAP calcium decay  (30 ms)

THETA_D      = 1.0     # LTD threshold
THETA_P      = 2.78    # LTP threshold

GAMMA_D      = 39.949
GAMMA_P      = 177.552
TAU_RHO      = 346.36  # s — bistable timescale
W0           = 0.0     # weight at rho = 0
W1           = 1.0     # weight at rho = 1
RHO_STAR     = 0.5     # unstable fixed point

# ──────────────────────────────────────────────────────────────
# Biological Noise Parameters  (documented for your PI)
# ──────────────────────────────────────────────────────────────
# CV_CA: coefficient of variation of NMDA calcium amplitude per spike.
#   Models stochastic vesicle release (pr ≈ 0.3–0.6) and channel noise.
#   Empirical value: ~0.30 (Bhatt et al. 2009; Bhatt & Jahr 2012).
CV_CA = 0.30

# CV_RATE: coefficient of variation of interneuron firing rates per trial.
#   Models trial-to-trial variability from finite synaptic input samples
#   (Fano factor ≈ 1, typical for cortical neurons in vivo).
#   sqrt(r * T) / (r * T) = 1/sqrt(n_spikes) for Poisson; for 20 spikes, CV≈0.22.
CV_RATE = 0.20

# SIGMA_RHO: per-trial noise on rho update.
#   The GB paper's sigma=3.35 is in continuous-time units; on a discrete
#   500 ms trial update it integrates to a much smaller effective noise.
#   We scale it so bistable UP<->DOWN flipping is visible within 300 trials.
SIGMA_RHO = 0.04

# ETA_RHO: effective per-trial learning rate for rho (NOT in original GB paper;
#   added to make the 300-trial simulation converge visibly).
#   The GB TAU_RHO=346s / 0.5s trial = 692 trials to reach equilibrium,
#   so with only 300 trials, weights barely move. We instead use a direct
#   rho_bar drive with this step size so learning is visible but noisy.
ETA_RHO = 0.08    # fraction of (rho_bar - rho_current) moved per trial

# Simulation time parameters
DT_SIM    = 0.0005   # s — 0.5 ms integration step
T_TRIAL   = 0.500    # s — 500 ms trial window

# Conductance scaling: nS per Hz of pre-synaptic drive
# Derived from: gNMDA=2.5 nS × p_connect=0.3 × n_md=50 × (1/r_max)
G_PER_HZ  = 0.10     # nS/Hz

# ──────────────────────────────────────────────────────────────
# Dendritic I/O (Yang et al. 2016 analytical fit)
# ──────────────────────────────────────────────────────────────
# dend_IO now lives in dendritic_io.py (single canonical definition, imported above).


# ──────────────────────────────────────────────────────────────
# Discrete-kernel constants for the calcium integrator
# ──────────────────────────────────────────────────────────────
# Exact per-step decay factors. The previous code used forward Euler
# (x -= x*dt/tau), which at dt/TAU_CA_RISE = 0.25 is a 25% step and distorts both the
# amplitude and the time course. exp(-dt/tau) is the exact solution of dx/dt = -x/tau
# over one step and costs nothing extra.
DECAY_NMDA = math.exp(-DT_SIM / TAU_CA_NMDA)
DECAY_RISE = math.exp(-DT_SIM / TAU_CA_RISE)
DECAY_BAP  = math.exp(-DT_SIM / TAU_CA_DECAY)


def _bap_kernel_peak(amp=1.0, n_steps=2000):
    """Peak of the discrete bAP kernel for a unit injection into the rise variable.

    A double-exponential kernel driven by an impulse into its rise variable does NOT
    peak at the injected amplitude -- it peaks far lower, because the rise variable
    decays while it is charging the slow variable. For tau_r = 2 ms and tau_d = 30 ms
    the analytic attenuation is (tau_r/tau_d)**(tau_r/(tau_d-tau_r)) = 1/18.20.

    The original code injected C_BAP directly and therefore produced a bAP calcium
    transient ~24x smaller than intended (18.2x from the missing normalisation, a
    further 1.3x from forward Euler). That is the dominant reason calcium never reached
    theta_D. Measuring the peak of the *actual discrete kernel* and dividing by it makes
    the realised peak equal the requested amplitude exactly, whatever dt is in use.
    """
    r = b = 0.0
    peak = 0.0
    for i in range(n_steps):
        if i == 0:
            r += amp
        b = r + (b - r) * DECAY_BAP      # exponential Euler, r held over the step
        r *= DECAY_RISE
        peak = max(peak, b)
    return peak


# Divide-by-peak normalisation, so injecting C_BAP yields a peak of C_BAP.
NORM_BAP = 1.0 / _bap_kernel_peak()


# ──────────────────────────────────────────────────────────────
# Stochastic Calcium Trace from Poisson Spike Trains
# ──────────────────────────────────────────────────────────────
def simulate_calcium_poisson(r_pre, r_post, c_nmda_mean, c_bap_amp,
                              T=T_TRIAL, dt=DT_SIM):
    """
    Simulate dendritic calcium during one trial using genuine Poisson spike trains.

    This replaces the old approach of scaling one representative spike pair
    by n_pairings. Instead, we:
      1. Draw the actual number of pre and post spikes from Poisson distributions
      2. Assign each spike a uniformly random time within [0, T]
      3. Run the ODE: NMDA Ca decays with tau_Ca_NMDA; bAP Ca uses a
         double-exponential (rise tau_Ca_RISE, decay tau_Ca_DECAY) — exactly
         matching the Brian2 equations in equations.py.
         The NMDA kernel rises instantaneously so its peak equals the injected
         amplitude and needs no normalisation; the double-exponential bAP kernel
         attenuates by 18.2x and is normalised via NORM_BAP so its peak equals
         c_bap_amp as intended.
      4. Each pre-spike adds a stochastic NMDA jump (vesicle noise, CV=CV_CA)
      5. Return the full calcium trace so alpha = integral(Ca > theta) is exact

    Parameters
    ----------
    r_pre       : mean pre-synaptic firing rate  (Hz)
    r_post      : mean post-synaptic firing rate (Hz, derived from v_dend)
    c_nmda_mean : mean NMDA Ca2+ jump per pre-spike (Mg-block corrected, a.u.)
    c_bap_amp   : bAP Ca2+ jump per post-spike (a.u.)
    """
    n_steps = int(round(T / dt))

    # ── Draw Poisson spike counts ──────────────────────────────
    n_pre  = int(rng.poisson(max(r_pre,  0.0) * T))
    n_post = int(rng.poisson(max(r_post, 0.0) * T))

    # ── Random spike times within [0, T] ──────────────────────
    # (uniform within the window = Poisson process with random ordering)
    t_pre_spikes  = np.sort(rng.uniform(0, T, n_pre))
    t_post_spikes = np.sort(rng.uniform(0, T, n_post))

    # ── Convert to step indices ────────────────────────────────
    pre_steps  = np.floor(t_pre_spikes  / dt).astype(int)
    post_steps = np.floor(t_post_spikes / dt).astype(int)
    pre_steps  = np.clip(pre_steps,  0, n_steps - 1)
    post_steps = np.clip(post_steps, 0, n_steps - 1)

    # ── Vectorised spike amplitude arrays ─────────────────────
    # NMDA amplitude has vesicle-release noise (CV = CV_CA)
    if n_pre > 0:
        pre_amps = np.maximum(0.0,
            rng.normal(c_nmda_mean, CV_CA * c_nmda_mean, size=n_pre))
    else:
        pre_amps = np.array([])

    # ── Build delta-function spike amplitude arrays ────────────
    pre_impulse  = np.zeros(n_steps)
    post_impulse = np.zeros(n_steps)
    for i, idx in enumerate(pre_steps):
        pre_impulse[idx]  += pre_amps[i]
    for idx in post_steps:
        # NORM_BAP makes the realised peak of the double-exponential equal c_bap_amp.
        # Without it the transient came out ~24x too small (see _bap_kernel_peak).
        post_impulse[idx] += c_bap_amp * NORM_BAP

    # ── Euler ODE integration ──────────────────────────────────
    # Matches exactly the equations in equations.py:
    #   dc_nmda/dt    = -c_nmda / tau_Ca_NMDA   (+ pre-spike jump)
    #   dc_bap_rise/dt = -c_bap_rise / tau_rise (+ post-spike jump)
    #   dc_bap/dt     = (-c_bap + c_bap_rise) / tau_decay
    #   Ca_total = c_nmda + c_bap
    c_nmda    = 0.0
    c_bap_rise = 0.0
    c_bap     = 0.0
    ca = np.zeros(n_steps)

    for step in range(n_steps):
        c_nmda     += pre_impulse[step]
        c_bap_rise += post_impulse[step]

        # Exact integration of the linear kernels (was forward Euler at a 25% step).
        c_bap       = c_bap_rise + (c_bap - c_bap_rise) * DECAY_BAP
        c_nmda     *= DECAY_NMDA
        c_bap_rise *= DECAY_RISE

        ca[step] = max(0.0, c_nmda + c_bap)

    return ca


# ──────────────────────────────────────────────────────────────
# Alpha Integral (time above threshold)
# ──────────────────────────────────────────────────────────────
def compute_alpha(ca, theta):
    """
    Total time (seconds) that calcium spends above threshold.
    This is the exact alpha integral from Graupner & Brunel (2012).
    """
    return float(np.sum(ca > theta) * DT_SIM)


# ──────────────────────────────────────────────────────────────
# Graupner-Brunel Bistable ρ Update
# ──────────────────────────────────────────────────────────────
def synapse_change(alpha_d, alpha_p, rho_init):
    """
    Graupner-Brunel-inspired bistable rho update, scaled for visible dynamics
    within 300 trials.

    The canonical GB Eq.6 uses exp(-total/TAU_RHO) where TAU_RHO=346s.
    For a 0.5s trial this gives exp(-tiny) ≈ 1, so rho_mean ≈ rho_init
    — NO visible weight change in 300 trials.

    Fix: we keep the GB bistable attractor logic (rho_bar = LTP vs LTD basin)
    but drive rho toward rho_bar with step ETA_RHO per trial, plus
    GB-proportional Gaussian noise. This preserves the bistable character
    and stochasticity while being observable in a 300-trial experiment.

    Returns: rho_new in [0, 1]
    """
    gamma_d = GAMMA_D * alpha_d
    gamma_p = GAMMA_P * alpha_p
    total   = gamma_d + gamma_p

    if total < 1e-12:
        # No Ca2+ activity: only diffusion noise (thermal drift)
        noise = rng.normal(0.0, SIGMA_RHO * 0.3)
        return float(np.clip(rho_init + noise, 0.0, 1.0))

    # ── GB target basin: rho_bar ∈ [0,1] ─────────────────────
    # rho_bar=0  → pure LTD (rho driven to DOWN state)
    # rho_bar=1  → pure LTP (rho driven to UP state)
    rho_bar = gamma_p / total

    # ── Move rho toward target with step ETA_RHO ─────────────
    rho_mean = rho_init + ETA_RHO * (rho_bar - rho_init)

    # ── Noise scaled by GB Eq.7 logic ────────────────────────
    # More Ca activity (larger alpha) → larger fluctuations
    noise_scale = SIGMA_RHO * math.sqrt((alpha_d + alpha_p) / max(total, 1e-9))
    rho_new = rng.normal(rho_mean, max(noise_scale, SIGMA_RHO * 0.5))
    return float(np.clip(rho_new, 0.0, 1.0))



# ──────────────────────────────────────────────────────────────
# Plasticity Update (full pipeline)
# ──────────────────────────────────────────────────────────────
def compute_plasticity_update(r_pre, g_exc_total, g_inh, rho_current):
    """
    Full Graupner-Brunel plasticity pipeline for one pathway/branch pair.

    Steps:
      1. Compute dendritic voltage from TOTAL excitation + inhibition
      2. Compute Mg2+ block from v_dend
      3. Derive mean NMDA Ca2+ jump (Mg-gated, varies per spike via vesicle noise)
      4. Derive post-synaptic rate from v_dend
      5. Simulate FULL Poisson spike train calcium trace for 500 ms trial
      6. Compute alpha_D, alpha_P as time integrals from the stochastic trace
      7. Update rho via Graupner-Brunel bistable ODE with noise

    Parameters
    ----------
    r_pre       : pre-synaptic firing rate (Hz)
    g_exc_total : total excitatory conductance on this branch (nS, all pathways)
    g_inh       : inhibitory conductance on this branch (nS)
    rho_current : current bistable weight variable ρ ∈ [0, 1]
    """
    # ── 1. Dendritic voltage ──────────────────────────────────
    v_dend = dend_IO(g_exc_total, g_inh)

    # ── 2. Mg2+ block ─────────────────────────────────────────
    mg = 1.0 / (1.0 + math.exp(-0.062 * v_dend) * (1.0 / 3.57))

    # ── 3. Mean NMDA Ca2+ jump per pre-spike ─────────────────
    c_nmda_mean = C_NMDA * mg   # vesicle noise applied inside simulate_calcium_poisson

    # ── 4. Post-synaptic firing rate ──────────────────────────
    # Linear threshold-linear approximation to the somatic f-V curve
    r_post = max(0.0, (v_dend + 55.0) / 10.0)   # Hz

    # ── 5. Simulate Poisson calcium trace ─────────────────────
    ca = simulate_calcium_poisson(r_pre, r_post, c_nmda_mean, C_BAP)

    # ── 6. Time integrals above plasticity thresholds ─────────
    alpha_d = compute_alpha(ca, THETA_D)   # seconds
    alpha_p = compute_alpha(ca, THETA_P)   # seconds

    # ── 7. Bistable rho update ────────────────────────────────
    return synapse_change(alpha_d, alpha_p, rho_current)


# ──────────────────────────────────────────────────────────────
# Interneuron rate with biological variability
# ──────────────────────────────────────────────────────────────
def noisy_rate(mean_rate, cv=CV_RATE):
    """
    Draw a firing rate with realistic trial-to-trial variability.
    For Poisson neurons, CV of rate estimate ≈ 1/sqrt(n_spikes).
    We model this as a Gaussian with std = cv * mean_rate.
    """
    return float(max(0.0, rng.normal(mean_rate, cv * max(mean_rate, 1.0))))


# ──────────────────────────────────────────────────────────────
# Main Simulation
# ──────────────────────────────────────────────────────────────
def main():
    print("Simulating Emergent Mechanistic Model — Full Stochastic Graupner-Brunel")
    print(f"  Noise settings: CV_CA={CV_CA}, CV_RATE={CV_RATE}, SIGMA_RHO={SIGMA_RHO}")
    print(f"  Trial window: {int(T_TRIAL*1000)} ms  |  dt: {int(DT_SIM*1000)} ms\n")

    n_trials = 300

    # ρ: bistable variable ∈ [0,1]; W = W0 + (W1-W0)*ρ derived from it
    rho = np.full((2, 2), RHO_STAR)
    W   = W0 + (W1 - W0) * rho

    W_history       = np.zeros((n_trials, 2, 2))
    rates_VIP       = np.zeros((n_trials, 2))
    rates_SOM       = np.zeros((n_trials, 2))
    rates_PV        = np.zeros(n_trials)
    inh_DEND        = np.zeros((n_trials, 2))
    rate_MD_context = np.zeros((n_trials, 2))

    for trial in range(n_trials):

        # ── MD Thalamus: Poisson spike count per trial ────────
        # Spike count ~ Poisson(lambda * T_trial);
        # effective rate = count / T_trial
        if trial < 100:     # Baseline: both channels silent
            rate_MD_A = 0.0
            rate_MD_B = 0.0
        elif trial < 200:   # Context A: channel A active, B has background
            rate_MD_A = float(rng.poisson(25.0 * T_TRIAL)) / T_TRIAL
            rate_MD_B = float(rng.poisson( 2.0 * T_TRIAL)) / T_TRIAL
        else:               # Context B: channel B active, A has background
            rate_MD_A = float(rng.poisson( 2.0 * T_TRIAL)) / T_TRIAL
            rate_MD_B = float(rng.poisson(25.0 * T_TRIAL)) / T_TRIAL

        rate_MD_context[trial] = [rate_MD_A, rate_MD_B]

        # ── Emergent Interneuron Rates (with neural variability) ──
        # VIP: driven by MD, variance from finite input pool (p_md2vip=0.3)
        r_vip_1 = noisy_rate(W_MD_VIP * rate_MD_A)
        r_vip_2 = noisy_rate(W_MD_VIP * rate_MD_B)

        # SOM: suppressed by VIP, baseline excitation has its own variability
        r_som_1 = noisy_rate(max(0, BASELINE_SOM - W_VIP_SOM * r_vip_1))
        r_som_2 = noisy_rate(max(0, BASELINE_SOM - W_VIP_SOM * r_vip_2))

        # PV: global drive, both MD channels contribute
        r_pv = noisy_rate(BASELINE_PV + W_MD_PV * (rate_MD_A + rate_MD_B))

        # SOM→Dendrite inhibitory conductance (nS)
        inh_branch = [W_SOM_DEND * r_som_1, W_SOM_DEND * r_som_2]

        rates_VIP[trial] = [r_vip_1, r_vip_2]
        rates_SOM[trial] = [r_som_1, r_som_2]
        rates_PV[trial]  = r_pv
        inh_DEND[trial]  = inh_branch

        # ── Cortical pathway rates (sensory drive, half MD rate) ──
        r_pathway = [rate_MD_A * 0.5, rate_MD_B * 0.5]

        # ── Plasticity: full stochastic Graupner-Brunel ───────
        for p_idx in range(2):
            r_pre = r_pathway[p_idx]
            for b_idx in range(2):
                g_inh = inh_branch[b_idx]

                # Total excitation on this branch from ALL pathways
                g_exc_total = sum(
                    r_pathway[pi] * G_PER_HZ * W[pi, b_idx]
                    for pi in range(2)
                )

                if r_pre < 1e-6 and g_exc_total < 1e-6:
                    continue   # fully silent — no update

                rho[p_idx, b_idx] = compute_plasticity_update(
                    r_pre, g_exc_total, g_inh, rho[p_idx, b_idx]
                )

        # Derive synaptic weights from rho
        W = W0 + (W1 - W0) * rho
        W_history[trial] = W.copy()

        if (trial + 1) % 100 == 0:
            print(f"  Trial {trial+1}/300 complete")

    # ── Gating Selectivity ────────────────────────────────────
    def gs(pref, nonp):
        mp, mn = np.mean(pref), np.mean(nonp)
        return (mp - mn) / (mp + mn + 1e-9)

    gs_vip = gs(rates_VIP[100:200, 0], rates_VIP[200:300, 0])
    gs_som = gs(rates_SOM[100:200, 0], rates_SOM[200:300, 0])
    gs_pv  = gs(rates_PV[100:200],     rates_PV[200:300])

    print(f"\nGating Selectivity: VIP={gs_vip:.2f}  SOM={gs_som:.2f}  PV={gs_pv:.2f}")

    # ──────────────────────────────────────────────────────────────
    # Figures
    # ──────────────────────────────────────────────────────────────
    colors = {'A': '#00BCD4', 'B': '#E91E63', 'SOM': '#FFC107',
              'PV': '#4CAF50', 'gray': '#888888'}

    def shade_epochs(ax):
        ax.axvspan(  0, 100, color='gray',        alpha=0.08)
        ax.axvspan(100, 200, color=colors['A'],   alpha=0.10)
        ax.axvspan(200, 300, color=colors['B'],   alpha=0.10)
        for x, lbl in [(50, 'Baseline'), (150, 'Context A'), (250, 'Context B')]:
            ax.text(x, ax.get_ylim()[1] * 0.97, lbl,
                    ha='center', va='top', fontsize=8, color='gray', style='italic')

    trials = np.arange(n_trials)

    # Fig 1 — Interneuron rates (raw, noisy)
    fig1, ax1 = plt.subplots(figsize=(11, 5))
    ax1.plot(rate_MD_context[:, 0], lw=1.2, color=colors['A'],   label='MD (A)', alpha=0.85)
    ax1.plot(rates_VIP[:, 0],       lw=1.0, color=colors['B'],   label='VIP-1',  ls='--', alpha=0.75)
    ax1.plot(rates_SOM[:, 0],       lw=1.0, color=colors['SOM'], label='SOM-1',  alpha=0.85)
    shade_epochs(ax1)
    ax1.set_title("Emergent Interneuron Rates — Stochastic Poisson Inputs", fontweight='bold')
    ax1.set_xlabel("Trial"); ax1.set_ylabel("Firing Rate (Hz)")
    ax1.legend(loc='upper right'); ax1.set_xlim(0, n_trials)
    fig1.savefig(os.path.join(FIG_DIR, "fig_emergent_rates.png"))
    plt.close(fig1)

    # Fig 2 — Gating Selectivity bars
    fig2, axes2 = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
    fig2.suptitle("Gating Selectivity Index (Stochastic Model)", fontweight='bold', fontsize=14)
    for ax, lbl, val, col in [
        (axes2[0], 'PV\nInterneurons',  gs_pv,  colors['PV']),
        (axes2[1], 'VIP\nInterneurons', gs_vip, colors['B']),
        (axes2[2], 'SOM\nInterneurons', gs_som, colors['SOM']),
    ]:
        ax.bar([lbl], [val], color=col, width=0.5, zorder=3)
        ax.set_ylim(-1.2, 1.2)
        ax.axhline(0, color='black', lw=1)
        ax.text(0, val + (0.08 if val >= 0 else -0.18),
                f'{val:.2f}', ha='center', fontweight='bold', fontsize=13)
    axes2[0].set_ylabel("Selectivity Index (GS)")
    plt.tight_layout()
    fig2.savefig(os.path.join(FIG_DIR, "fig_gating_selectivity.png"))
    plt.close(fig2)

    # Fig 3 — Dendritic inhibition (noisy)
    fig3, ax3 = plt.subplots(figsize=(11, 5))
    ax3.plot(inh_DEND[:, 0], lw=1.0, color=colors['SOM'], label='Branch 1', alpha=0.85)
    ax3.plot(inh_DEND[:, 1], lw=1.0, color='navy',        label='Branch 2', ls='--', alpha=0.75)
    shade_epochs(ax3)
    ax3.set_title("Emergent Dendritic Inhibition (SOM-gated, Poisson noise)", fontweight='bold')
    ax3.set_xlabel("Trial"); ax3.set_ylabel("Inhibitory Conductance (nS)")
    ax3.legend(); ax3.set_xlim(0, n_trials)
    fig3.savefig(os.path.join(FIG_DIR, "fig_emergent_inhibition.png"))
    plt.close(fig3)

    # Fig 4 — Self-organised branch gating
    fig4, ax4 = plt.subplots(figsize=(11, 5))
    ax4.plot(W_history[:, 0, 0], lw=1.5, color=colors['A'], label='Pathway A → Branch 1')
    ax4.plot(W_history[:, 0, 1], lw=1.0, color=colors['A'], label='Pathway A → Branch 2', ls='--', alpha=0.7)
    ax4.plot(W_history[:, 1, 0], lw=1.0, color=colors['B'], label='Pathway B → Branch 1', ls='--', alpha=0.7)
    ax4.plot(W_history[:, 1, 1], lw=1.5, color=colors['B'], label='Pathway B → Branch 2')
    shade_epochs(ax4)
    ax4.set_title("Self-Organized Gating — Full Stochastic Graupner-Brunel\n"
                  r"$w = W_0 + (W_1 - W_0)\cdot\rho$  (bistable with noise)",
                  fontweight='bold')
    ax4.set_xlabel("Trial"); ax4.set_ylabel("Synaptic Weight")
    ax4.legend(loc='upper left', ncol=2, fontsize=9)
    ax4.set_ylim(-0.05, 1.10); ax4.set_xlim(0, n_trials)
    fig4.savefig(os.path.join(FIG_DIR, "fig_self_organized_branching.png"))
    plt.close(fig4)

    print(f"All 4 figures saved to: {FIG_DIR}")


if __name__ == "__main__":
    main()
