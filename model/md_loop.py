"""
md_loop.py -- step 3b (2026-11-11): a PFC <-> MD loop that produces the MD context signal,
in place of the fixed Poisson MD rates of the canonical model.

Rate units, as in Zhang 2025's rate RNN (a spiking LIF version had no regime between
silence and 100-400 Hz latching, so it was dropped):
    C_k   context-coding PFC population for context k (k = 0, 1)
    M_k   MD channel k
    tau_C dC_k/dt = -C_k + phi(cue_k + w_mc*M_k' + w_cc*C_k - w_inh*(C_0 + C_1) - th_C, C_max)
    tau_M dM_k/dt = -M_k + phi(w_cm*C_k' + w_em*r_E - th_M, M_max)
  where M_k' = (1-x)*M_k + x*M_j and C_k' = (1-x)*C_k + x*C_j (x = loop_cross, the fraction of
  loop drive that reaches the wrong channel), r_E = population rate of the plastic pyramidal
  cells (the network's E cells, not context-coding: their feedback reaches BOTH MD channels
  equally), and phi(u, r_max) = min(max(u, 0), r_max).
MD_k spikes are Poisson at rate M_k and enter VIP_k and PV through the canonical synapses.

Two loop regimes:
  'amp'      loop gain < 1: the loop amplifies a held cue and decays when the cue moves.
  'persist'  loop gain > 1 with saturation: a brief cue switches the loop into a self-
             sustained state; the cue of the other context must win through w_inh.
The parameters are ours. They are set so that the ON channel sits at the canonical
MD rate (~25 Hz) and the OFF channel at 0 Hz.
"""
import numpy as np

LOOP_PRESETS = {
    # held cue, loop gain w_mc*w_cm = 0.4: C(1 + w_inh - w_mc*w_cm) = cue - th_C -> C = M = 25 Hz;
    # OFF channel 0 Hz; when the cue moves, the old channel decays within ~0.1 s
    'amp': dict(cue_hz=30.0, w_mc=0.4, w_cm=1.0, w_cc=0.0, w_inh=0.4, th_C=5.0, th_M=0.0,
                C_max=60.0, M_max=40.0, tau_C=0.02, tau_M=0.02),
    # self-sustained: loop gain 2 > 1 + w_inh, MD saturates at 25 Hz (C 30 Hz) after a brief cue;
    # the other context's cue (30 Hz) wins through w_inh and switches the loop
    'persist': dict(cue_hz=30.0, w_mc=2.0, w_cm=1.0, w_cc=0.0, w_inh=0.5, th_C=5.0, th_M=0.0,
                    C_max=60.0, M_max=25.0, tau_C=0.02, tau_M=0.02),
    # as 'persist' with a stronger loop (3): the other cue no longer silences the old context,
    # both channels stay on after a switch (competition too weak for the loop)
    'persist_weakcomp': dict(cue_hz=30.0, w_mc=3.0, w_cm=1.0, w_cc=0.0, w_inh=0.5, th_C=5.0, th_M=0.0,
                             C_max=60.0, M_max=25.0, tau_C=0.02, tau_M=0.02),
}


class MDLoop:
    """Integrates the rate loop with Euler at step dt (s). State: C (2,), M (2,)."""

    def __init__(self, regime='amp', loop_cross=0.0, w_em=0.0, **over):
        self.c = dict(LOOP_PRESETS[regime]); self.c.update(over)
        self.x = float(loop_cross); self.w_em = float(w_em)
        self.C = np.zeros(2); self.M = np.zeros(2); self.cue = np.zeros(2)

    def set_cue(self, k):
        self.cue = np.zeros(2)
        if k is not None:
            self.cue[k] = self.c['cue_hz']

    def step(self, dt, r_E=0.0):
        c, x = self.c, self.x
        phi = lambda u, m: np.clip(u, 0.0, m)
        Mx = (1 - x) * self.M + x * self.M[::-1]
        Cx = (1 - x) * self.C + x * self.C[::-1]
        uC = self.cue + c['w_mc'] * Mx + c['w_cc'] * self.C - c['w_inh'] * self.C.sum() - c['th_C']
        uM = c['w_cm'] * Cx + self.w_em * r_E - c['th_M']
        self.C = self.C + dt / c['tau_C'] * (-self.C + phi(uC, c['C_max']))
        self.M = self.M + dt / c['tau_M'] * (-self.M + phi(uM, c['M_max']))
        return self.M


def loop_steady(regime='amp', plan=((0, 3.0), (1, 3.0)), dt=1e-3, r_E=0.0, **kw):
    """Standalone run (no network): returns per-ms M and C traces for a cue plan."""
    L = MDLoop(regime, **kw)
    Ms, Cs = [], []
    for k, d in plan:
        L.set_cue(k)
        for _ in range(int(round(d / dt))):
            L.step(dt, r_E); Ms.append(L.M.copy()); Cs.append(L.C.copy())
    return np.array(Ms), np.array(Cs)
