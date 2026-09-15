from __future__ import annotations

import argparse
import random
import sys
import textwrap

from . import ask, converse, explore, graph, interpret, sim
from .stimuli import STIMULI, resolve

W = 76
C = {"dim": "\033[2m", "b": "\033[1m", "fly": "\033[38;5;179m",
     "cl": "\033[38;5;110m", "hum": "\033[38;5;108m", "r": "\033[0m"}


def _c(k, s):
    return f"{C[k]}{s}{C['r']}" if sys.stdout.isatty() else s


def _wrap(s, indent="    "):
    out = []
    for para in s.split("\n"):
        out.append(textwrap.fill(para, W, initial_indent=indent,
                                 subsequent_indent=indent) if para.strip() else "")
    return "\n".join(out)


def _banner():
    print(_c("dim", "=" * W))
    print(f"  {_c('b', 'FLYCLAUDE')}  ::  FlyWire FAFB v783  ::  144,837 neurons, one fly")
    print(_c("dim", "=" * W))


def _think(conn, stim, a, seed=None):
    """Run the connectome once and return (readout, state-report)."""
    idx = resolve(conn, stim)
    res = sim.run(conn, idx, drive=stim.drive, steps=a.steps,
                  threshold=a.threshold, leak=a.leak, seed=seed)
    rd = interpret.readout(conn, res)
    return res, rd, interpret.brain_state(conn, stim, res, rd)


def pick_stimulus(rng, prompt="  what happens to her first?"):
    """Numbered menu. Enter = random, q = quit."""
    keys = sorted(STIMULI)
    print(f"\n{prompt}\n")
    width = max(len(k) for k in keys)
    half = (len(keys) + 1) // 2
    for i in range(half):
        cells = []
        for j in (i, i + half):
            if j < len(keys):
                k = keys[j]
                cells.append(f"  {_c('b', f'{j + 1:2}')}. {k:<{width}} "
                             f"{_c('dim', STIMULI[k].action[:34])}")
        print("".join(f"{c:<58}" for c in cells).rstrip())
    print(_c("dim", "\n   ENTER for random, or type a name/number  (q to quit)"))
    while True:
        try:
            raw = input(_c("dim", "   > ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not raw:
            k = rng.choice(keys)
            print(_c("dim", f"   -> {k}"))
            return STIMULI[k]
        if raw.lower() in {"q", "quit", "exit"}:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(keys):
            return STIMULI[keys[int(raw) - 1]]
        if raw in STIMULI:
            return STIMULI[raw]
        matches = [k for k in keys if k.startswith(raw.lower())]
        if len(matches) == 1:
            return STIMULI[matches[0]]
        if matches:
            print(_c("dim", f"   ambiguous: {', '.join(matches)}"))
        else:
            print(_c("dim", "   no such stimulus. try a number, or the name."))


def _show_brain(stim, res, state, verbose):
    print(f"\n  {_c('dim', 'stimulus')} : {_c('b', stim.key)}  "
          f"{_c('dim', '(' + stim.action + ')')}")
    if verbose:
        print(_c("dim", "  " + "-" * (W - 2)))
        print(_c("dim", textwrap.indent(state, "  ")))
        print(_c("dim", "  " + "-" * (W - 2)))
    else:
        print(f"  {_c('dim', 'neurons firing')} : {res.n_active:,}")


# ---------------------------------------------------------------- ask (one-shot)

def cmd_ask(a, conn, rng):
    if a.stimulus:
        stim = STIMULI[a.stimulus]
    elif a.random:
        stim = STIMULI[rng.choice(sorted(STIMULI))]
    else:
        stim = pick_stimulus(rng)
        if stim is None:
            return 0
    res, rd, state = _think(conn, stim, a, seed=a.seed)
    _show_brain(stim, res, state, verbose=True)

    if a.brain_only:
        return 0
    if a.dry_run:
        print("\n[dry run] prompt:\n")
        print(ask.ASK_PROMPT.format(state=state))
        return 0

    print(_c("dim", "\n  ...the fly is formulating a question...\n"))
    q = ask.question_from(state)
    print(f"  {_c('fly', 'THE FLY ASKS:')}")
    print(_c("fly", _wrap(q)))
    print(_c("dim", "\n  ...asking Claude...\n"))
    print(f"  {_c('cl', 'CLAUDE ANSWERS:')}")
    print(_c("cl", _wrap(ask.answer_to(q))))
    print()
    return 0


# ---------------------------------------------------------------------- chat

HELP = """
  just press ENTER   let it run another round
  type something     say it to Claude (the fly can't hear you)
  !                  open the menu and pick what happens next
  !taste  !light     or name it directly
  ?                  show the fly's full neural readout for the last round
  q                  leave
"""


def cmd_chat(a, conn, rng):
    convo = converse.Conversation()
    if a.stimulus:
        stim = STIMULI[a.stimulus]
    elif a.random or a.auto:
        stim = STIMULI[rng.choice(sorted(STIMULI))]
    else:
        stim = pick_stimulus(rng)
        if stim is None:
            return 0
    interject = ""
    last_state = ""
    verbose = a.verbose
    rounds = 0

    print(_c("dim", HELP) if not a.auto else "")

    while a.auto == 0 or rounds < a.auto:
        rounds += 1
        seed = (a.seed + rounds) if a.seed is not None else None
        res, rd, state = _think(conn, stim, a, seed=seed)
        last_state = state
        _show_brain(stim, res, state, verbose)

        try:
            fly_line = converse.fly_says(state, convo)
        except converse.ClaudeMissing as e:
            print(f"\n  ! {e}", file=sys.stderr)
            return 2
        print(f"\n  {_c('fly', 'FLY')}")
        print(_c("fly", _wrap(fly_line)))

        reply, key = converse.claude_replies(convo, fly_line, interject)
        interject = ""
        print(f"\n  {_c('cl', 'CLAUDE')}")
        print(_c("cl", _wrap(reply)))

        convo.turns.append(converse.Turn(stimulus=stim.key, fly=fly_line,
                                         claude=reply, action=key or ""))

        if key is None:
            key = rng.choice(sorted(STIMULI))
            print(_c("dim", f"\n  (no action chosen; falling back to '{key}')"))
        stim = STIMULI[key]

        if a.auto:
            continue
        try:
            line = input(_c("dim", f"\n  [{stim.key}] > ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.lower() in {"q", "quit", "exit"}:
            break
        if line == "?":
            print(_c("dim", textwrap.indent(last_state, "  ")))
            continue
        if line.startswith("!"):
            k = line[1:].strip().lower()
            if not k:
                chosen = pick_stimulus(rng, "  what do you do to her instead?")
                if chosen is not None:
                    stim = chosen
            elif k in STIMULI:
                stim = STIMULI[k]
            else:
                matches = [x for x in sorted(STIMULI) if x.startswith(k)]
                if len(matches) == 1:
                    stim = STIMULI[matches[0]]
                else:
                    print(_c("dim", "  unknown. !  on its own opens the menu."))
                    rounds -= 1
            continue
        if line:
            interject = line
            print(f"  {_c('hum', 'YOU')} {_c('dim', '(to Claude)')}")

    print(_c("dim", f"\n  {rounds} round{'' if rounds == 1 else 's'}. the fly is fine.\n"))
    return 0


# ----------------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="flyclaude",
        description="Simulate a real fly connectome and put it in a room with Claude.",
    )
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("--stimulus", "-s", choices=sorted(STIMULI), default=None,
                       help="what happens to the fly first (default: random)")
        p.add_argument("--seed", type=int, default=None)
        p.add_argument("--steps", type=int, default=192)
        p.add_argument("--threshold", type=float, default=0.12)
        p.add_argument("--leak", type=float, default=0.94)
        p.add_argument("--random", "-r", action="store_true",
                       help="pick the first stimulus at random, skip the menu")
        p.add_argument("--rebuild", action="store_true",
                       help="rebuild the cached connectivity matrix")

    pc = sub.add_parser("chat", help="open-ended loop: fly <-> Claude (default)")
    common(pc)
    pc.add_argument("--auto", type=int, default=0, metavar="N",
                    help="run N rounds without stopping for input")
    pc.add_argument("--verbose", "-v", action="store_true",
                    help="show the full neural readout every round")

    pa = sub.add_parser("ask", help="one question, one answer, done")
    common(pa)
    pa.add_argument("--brain-only", action="store_true")
    pa.add_argument("--dry-run", action="store_true")

    ps = sub.add_parser("stimuli", help="list what you can do to the fly")
    ps.add_argument("--check", action="store_true",
                    help="resolve every stimulus against the dataset")

    pe = sub.add_parser("explore",
                        help="browse the dataset to invent new stimuli")
    pe.add_argument("selector", nargs="?",
                    help="e.g. cell_type, cell_class, body_part_sensory")
    pe.add_argument("contains", nargs="?", default="",
                    help="only values containing this substring")
    pe.add_argument("--limit", type=int, default=60)
    pe.add_argument("--all", action="store_true",
                    help="include non-sensory neurons too")

    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0].startswith("-") and argv[0] not in {"-h", "--help"}):
        argv = ["chat"] + argv        # bare `flyclaude` and `flyclaude -s x` -> chat
    a = ap.parse_args(argv)

    if a.cmd == "stimuli" and not a.check:
        width = max(len(k) for k in STIMULI)
        for k, st in sorted(STIMULI.items()):
            tag = "" if st.source == "stimuli.toml" else f"  [{st.source}]"
            print(f"\n  {_c('b', k)}{tag}")
            print(f"    {st.label}")
            if st.action:
                print(f"    {_c('dim', 'you ' + st.action)}")
            print(f"    {_c('dim', st.describe_selection())}")
        print(f"\n  {len(STIMULI)} stimuli. Add your own in stimuli.toml "
              f"(or stimuli.local.toml).")
        print(f"  {_c('dim', 'flyclaude explore  -- see what else you can stimulate')}\n")
        return 0

    _banner()
    rng = random.Random(getattr(a, "seed", None))
    conn = graph.load(rebuild=getattr(a, "rebuild", False))

    if a.cmd == "explore":
        if a.selector:
            print(explore.listing(conn, a.selector, a.contains,
                                  limit=a.limit, only_sensory=not a.all))
        else:
            print(explore.overview(conn))
        return 0

    if a.cmd == "stimuli":
        report, ok = explore.validate(conn, STIMULI)
        print(report)
        return 0 if ok else 1

    try:
        return cmd_ask(a, conn, rng) if a.cmd == "ask" else cmd_chat(a, conn, rng)
    except converse.ClaudeMissing as e:
        print(f"\n  ! {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print()
        return 130
    except Exception as e:
        print(f"\n  ! {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
