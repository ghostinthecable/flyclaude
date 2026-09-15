"""A leaky integrate-and-fire pass over the connectome.

This is the same order of approximation every connectome-simulation project
makes: real wiring, real signs, cartoon dynamics. There are no learned
parameters, no synaptic delays, no neuropeptides, no compartments. It shows
how activity *spreads* through the measured graph -- not what a fly thinks.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SimResult:
    spike_counts: np.ndarray   # per neuron, over the whole run
    raster: np.ndarray         # [steps, n] bool, if kept
    steps: int
    n_active: int


def run(conn, stim_idx, drive=1.2, steps=192, threshold=0.12,
        leak=0.94, refractory=2, stim_steps=24, seed=None, jitter=0.15):
    """Inject `drive` into `stim_idx` for `stim_steps`, then let it ring out."""
    rng = np.random.default_rng(seed)
    n = conn.n
    W = conn.W

    v = np.zeros(n, dtype=np.float32)
    refrac = np.zeros(n, dtype=np.int16)
    spikes = np.zeros(n, dtype=np.float32)
    counts = np.zeros(n, dtype=np.int32)
    raster = np.zeros((steps, n), dtype=bool)

    for t in range(steps):
        inp = W.dot(spikes)
        if t < stim_steps:
            # a little jitter so repeated runs aren't identical unless seeded
            noise = 1.0 + jitter * rng.standard_normal(len(stim_idx)).astype(np.float32)
            inp[stim_idx] += drive * noise

        v = v * leak + inp
        v[refrac > 0] = 0.0
        np.maximum(v, 0.0, out=v)   # no negative charge accumulation

        fired = v >= threshold
        spikes = fired.astype(np.float32)
        counts += fired
        raster[t] = fired

        refrac = np.maximum(refrac - 1, 0)
        refrac[fired] = refractory
        v[fired] = 0.0

    return SimResult(
        spike_counts=counts,
        raster=raster,
        steps=steps,
        n_active=int((counts > 0).sum()),
    )
