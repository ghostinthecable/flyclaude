"""Fetch and cache the FlyWire FAFB v783 connectome.

Public Google Cloud Storage mirror -- no login, no API key, no credentials of
any kind. Data is CC BY-SA 4.0 (Dorkenwald et al. 2024; Schlegel et al. 2024),
so we download it at runtime rather than redistributing it in the repo.
"""
from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

BUCKET = (
    "https://storage.googleapis.com/"
    "lee-lab_brain-and-nerve-cord-fly-connectome/compiled_data/fafb_783"
)

FILES = {
    "meta": ("fafb_783_meta.feather", 13_539_866),
    "edges": ("fafb_783_simple_edgelist.feather", 302_625_658),
}


def data_dir() -> Path:
    d = Path(os.environ.get("FLYCLAUDE_DATA", Path(__file__).resolve().parent.parent / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _download(url: str, dest: Path, expected: int) -> None:
    print(f"  fetching {dest.name} ({expected / 1e6:.0f} MB) ...", file=sys.stderr)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        got = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            got += len(chunk)
            pct = 100 * got / expected if expected else 0
            print(f"\r    {got / 1e6:7.1f} MB  {pct:5.1f}%", end="", file=sys.stderr)
    print(file=sys.stderr)
    tmp.replace(dest)


def ensure(which: str) -> Path:
    name, size = FILES[which]
    dest = data_dir() / name
    if not dest.exists():
        _download(f"{BUCKET}/{name}", dest, size)
    return dest


def ensure_all() -> dict[str, Path]:
    return {k: ensure(k) for k in FILES}
