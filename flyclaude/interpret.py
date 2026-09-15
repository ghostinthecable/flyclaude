"""Turn a pile of spike counts into something a fly could plausibly be on about."""
from __future__ import annotations

import numpy as np

# Descending neurons carry commands from brain to body. FAFB is a *brain*
# dataset -- there is no ventral nerve cord in it -- so these commands are as
# far as we can follow the signal. Only well-established identifications are
# spelled out; everything else gets its nomenclature family, which is just what
# the name means, not a claim about function.
KNOWN_DN = {
    "MDN":   "walk BACKWARD (the 'moonwalker' neuron)",
    "DNp01": "LEAP AWAY RIGHT NOW (the Giant Fiber escape neuron)",
    "DNp09": "freeze and stop walking",
    "DNa01": "steer / turn while walking",
    "DNa02": "steer / turn while walking",
}

FAMILY = {
    "DNp": "a descending command from the upper brain",
    "DNa": "a descending command from the front of the brain",
    "DNb": "a descending command from the brain's underside",
    "DNg": "a descending command from the mouth-region brain",
    "DNd": "a descending command from the rear brain",
    "DNx": "a descending command entering from outside the brain",
}

KNOWN_MN = {
    "MN9": "extend the proboscis (stick the mouth out at it)",
}


def _describe(cell_type: str, motor: bool) -> str:
    if not cell_type:
        return "an unnamed command neuron"
    table = KNOWN_MN if motor else KNOWN_DN
    if cell_type in table:
        return table[cell_type]
    if motor:
        return "a mouthpart muscle command"
    base = cell_type.split("_")[0]
    for pre, desc in FAMILY.items():
        if base.startswith(pre):
            return desc
    return "a descending command"


def readout(conn, result, top=8):
    """Rank the command neurons the simulation actually drove."""
    counts = result.spike_counts
    out = {}
    for group, motor in (("descending", False), ("motor", True)):
        idx = conn.where(super_class=group)
        if len(idx) == 0:
            continue
        c = counts[idx]
        hot = idx[c > 0]
        if len(hot) == 0:
            out[group] = []
            continue
        order = np.argsort(-counts[hot])
        rows, seen = [], {}
        for i in hot[order]:
            ct = conn.meta["cell_type"][i] or ""
            key = ct or f"#{conn.ids[i]}"
            if key in seen:
                seen[key]["spikes"] += int(counts[i])
                seen[key]["cells"] += 1
                continue
            row = {
                "cell_type": ct,
                "spikes": int(counts[i]),
                "cells": 1,
                "meaning": _describe(ct, motor),
            }
            seen[key] = row
            rows.append(row)
            if len(rows) >= top:
                break
        out[group] = rows
    return out


def brain_state(conn, stim, result, rd) -> str:
    """A compact, factual report of what the simulated brain just did."""
    lines = [
        f"STIMULUS: {stim.label}",
        f"SPREAD: {result.n_active:,} of {conn.n:,} neurons fired "
        f"over {result.steps} timesteps.",
    ]
    dn = rd.get("descending") or []
    mn = rd.get("motor") or []
    if dn:
        lines.append("STRONGEST BODY COMMANDS THE BRAIN ISSUED:")
        for r in dn:
            name = r["cell_type"] or "unnamed"
            n_sp = r["spikes"]
            plural = "" if n_sp == 1 else "s"
            lines.append(f"  - {name}: {r['meaning']}  [{n_sp} spike{plural}]")
    else:
        lines.append("BODY COMMANDS: none -- the signal died in the brain.")
    if mn:
        lines.append("MOUTHPART MUSCLE COMMANDS:")
        for r in mn:
            name = r["cell_type"] or "unnamed"
            n_sp = r["spikes"]
            plural = "" if n_sp == 1 else "s"
            lines.append(f"  - {name}: {r['meaning']}  [{n_sp} spike{plural}]")
    return "\n".join(lines)
