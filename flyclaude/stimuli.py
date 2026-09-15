"""Things that can happen to the fly.

Every stimulus selects a real population of annotated neurons. The selectors
below are just column filters over the FlyWire metadata, ANDed together -- so
anything you can name in the dataset, you can stimulate. Nothing here is
invented, and a stimulus that matches zero neurons is an error, not a shrug.

Definitions live in stimuli.toml so you can add your own without touching code.
`flyclaude explore` shows you what's legal to put in there.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:            # Python < 3.11
    try:
        import tomli as tomllib        # type: ignore
    except ModuleNotFoundError:
        tomllib = None                 # type: ignore

ROOT = Path(__file__).resolve().parent.parent
SHIPPED = ROOT / "stimuli.toml"
LOCAL = ROOT / "stimuli.local.toml"    # yours, gitignored

# Metadata columns a stimulus may filter on. Keep this list honest: every one
# is a real column in fafb_783_meta.feather.
SELECTORS = ("cell_class", "body_part_sensory", "cell_type", "side", "nerve",
             "super_class", "region")


@dataclass(frozen=True)
class Stimulus:
    key: str
    label: str                       # what happened, from the fly's side
    action: str = ""                 # how a human in the room would cause it
    drive: float = 1.2               # injected current per timestep
    group: str = "other"             # menu heading
    select: dict = field(default_factory=dict)
    source: str = "built-in"

    def describe_selection(self) -> str:
        # spaces around the separators so this can be word-wrapped
        return ",  ".join(
            f"{k}={' | '.join(v) if isinstance(v, list) else v}"
            for k, v in self.select.items()
        )


def _parse(raw: dict, source: str) -> dict:
    out = {}
    for key, body in (raw.get("stimuli") or {}).items():
        if not isinstance(body, dict):
            raise SystemExit(f"{source}: [stimuli.{key}] must be a table")
        select = {k: v for k, v in body.items() if k in SELECTORS}
        unknown = set(body) - set(SELECTORS) - {"label", "action", "drive", "group"}
        if unknown:
            raise SystemExit(
                f"{source}: [stimuli.{key}] has unknown field(s): "
                f"{', '.join(sorted(unknown))}\n"
                f"  valid selectors: {', '.join(SELECTORS)}\n"
                f"  valid fields   : label, action, drive"
            )
        if not select:
            raise SystemExit(
                f"{source}: [stimuli.{key}] selects no neurons -- "
                f"give it at least one of: {', '.join(SELECTORS)}"
            )
        if not body.get("label"):
            raise SystemExit(f"{source}: [stimuli.{key}] needs a `label`")
        out[key] = Stimulus(
            key=key,
            label=body["label"],
            action=body.get("action", ""),
            drive=float(body.get("drive", 1.2)),
            group=body.get("group", "other"),
            select=select,
            source=source,
        )
    return out


def load_stimuli() -> dict:
    if tomllib is None:
        raise SystemExit(
            "stimuli.toml needs a TOML parser. On Python < 3.11:\n"
            "    .venv/bin/pip install tomli"
        )
    if not SHIPPED.exists():
        raise SystemExit(f"missing {SHIPPED} -- it ships with the repo.")
    stim = _parse(tomllib.loads(SHIPPED.read_text()), SHIPPED.name)
    if LOCAL.exists():
        stim.update(_parse(tomllib.loads(LOCAL.read_text()), LOCAL.name))
    return stim


STIMULI = load_stimuli()


def resolve(conn, stim: Stimulus):
    """Return the neuron indices this stimulus excites. Never guesses."""
    idx = conn.where(**stim.select)
    if len(idx) == 0:
        raise SystemExit(
            f"stimulus '{stim.key}' ({stim.source}) matched no neurons.\n"
            f"  selection: {stim.describe_selection()}\n"
            f"  Run `flyclaude explore` to see what actually exists in the "
            f"dataset -- refusing to fake it."
        )
    return idx
