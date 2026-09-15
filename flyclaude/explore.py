"""Browse what the dataset actually contains, so you can invent new stimuli.

Everything printed here is a legal value to paste into stimuli.toml.
"""
from __future__ import annotations

import collections
import shutil
import textwrap

from .stimuli import SELECTORS


def _width(cap=92):
    try:
        w = shutil.get_terminal_size(fallback=(80, 24)).columns
    except Exception:
        w = 80
    return max(46, min(w - 2, cap))


def _counts(conn, col, only_sensory=True, contains=""):
    idx = range(conn.n)
    if only_sensory:
        sc = conn.meta["super_class"]
        idx = [i for i in idx if sc[i] and sc[i].startswith("sensory")]
    vals = conn.meta[col]
    c = collections.Counter(vals[i] for i in idx if vals[i])
    if contains:
        c = collections.Counter(
            {k: v for k, v in c.items() if contains.lower() in str(k).lower()}
        )
    return c


def overview(conn) -> str:
    out = ["", "  Selectors you can use in stimuli.toml, and how many sensory",
           "  neurons carry each value. Use `flyclaude explore <selector>` for",
           "  the full list, and add a filter: `flyclaude explore cell_type ORN`.",
           ""]
    w = _width()
    for col in SELECTORS:
        c = _counts(conn, col)
        if not c:
            continue
        head = ", ".join(f"{k} ({v:,})" for k, v in c.most_common(4))
        more = f", +{len(c) - 4} more" if len(c) > 4 else ""
        out.append(f"  {col}")
        for line in textwrap.wrap(head + more, w - 6, break_long_words=False):
            out.append(f"      {line}")
    out.append("")
    return "\n".join(out)


def listing(conn, col, contains="", limit=60, only_sensory=True) -> str:
    if col not in SELECTORS:
        return (f"  '{col}' is not a selector.\n"
                f"  valid: {', '.join(SELECTORS)}")
    c = _counts(conn, col, only_sensory, contains)
    if not c:
        what = f" matching '{contains}'" if contains else ""
        return f"  no sensory neurons have a {col}{what}."
    rows = c.most_common(limit)
    width = max(len(str(k)) for k, _ in rows)
    w = _width()
    head = (f"{col}" + (f"  (filtered by '{contains}')" if contains else "")
            + f"  --  {len(c)} distinct value(s)"
            + (", sensory only" if only_sensory else ""))
    out = [""] + [f"  {ln}" for ln in textwrap.wrap(head, w - 4)] + [""]
    for k, v in rows:
        out.append(f"    {str(k):<{width}}  {v:>6,}")
    if len(c) > limit:
        out.append(f"    ... and {len(c) - limit} more (raise --limit)")
    out.append("")
    return "\n".join(out)


def validate(conn, stimuli) -> tuple[str, bool]:
    """Resolve every stimulus against the dataset. Reports, never guesses."""
    lines, ok = ["", "  Checking every stimulus against the loaded dataset:", ""], True
    width = max(len(k) for k in stimuli)
    for key in sorted(stimuli):
        s = stimuli[key]
        try:
            n = len(conn.where(**s.select))
        except Exception as e:                       # bad column name, etc.
            lines.append(f"    {key:<{width}}  ERROR  {e}")
            ok = False
            continue
        if n == 0:
            lines.append(f"    {key:<{width}}  ✗ 0 neurons  [{s.describe_selection()}]")
            ok = False
        else:
            tag = "" if s.source == "stimuli.toml" else f"  ({s.source})"
            lines.append(f"    {key:<{width}}  ✓ {n:>6,} neurons{tag}")
    lines.append("")
    lines.append("  all stimuli resolve." if ok
                 else "  SOME STIMULI MATCH NOTHING -- fix the selectors above.")
    lines.append("")
    return "\n".join(lines), ok
