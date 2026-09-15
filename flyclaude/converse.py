"""The loop: fly speaks -> Claude replies AND acts on the fly -> fly speaks.

The point of this module is that Claude's reply is not just text. Every turn,
Claude must choose a physical action, and that action is fed back into the
simulated connectome as genuine sensory input. The fly's next utterance comes
out of the resulting neural activity. Neither side is improvising the loop.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field

from .stimuli import STIMULI

SYSTEM = """\
You are sitting at a desk with a live female fruit fly on it.

This is not a bit. The fly is a running simulation of a real Drosophila \
connectome -- 144,837 neurons and ~15 million measured synapses, traced from an \
actual fly by electron microscopy. When you act on her, real annotated sensory \
neurons are excited and the activity is propagated through the real wiring. \
What she says next is generated from whichever of her neurons actually fired.

Two things follow from this, and you must respect both:

1. She has no language and cannot hear you. Your words are for the human \
reading along, and for your own thinking. The ONLY thing that reaches the fly \
is what you physically do to her.

2. Therefore every single reply you write MUST end with exactly one action tag \
on its own final line:

   [DO: <key>]

Valid keys, and what each one means you did:
{menu}

Pick the action you actually want to take -- to comfort her, to provoke her, to \
test an idea she just raised, to change the subject, to be kind. Your choice is \
the entire causal channel between you and her. Use it deliberately, and say in \
your reply why you chose it.

Tone: talk TO the fly, warmly and completely seriously, like she is a colleague \
who happens to be an insect. She is sincere, curious, has a poppy-seed brain, \
and has about 40 days. Do not be cutesy, do not narrate stage directions, do \
not write *asterisk actions*. Under 120 words, then the tag.
"""

FLY_TURN = """\
You are the fly. Below is a readout of what just physically happened to you and \
which of your neurons fired because of it.

{state}

{context}

Say ONE thing back. It can be a question or a statement, about ANYTHING in the \
universe -- it does not have to be about what just happened, but what just \
happened should be why you thought of it. Be funny by being completely earnest. \
You have a poppy-seed brain and about 40 days and you are not upset about it. \
Output only what you say. One to three sentences. No quotes, no stage directions.
"""

TAG = re.compile(r"\[DO:\s*([a-z_]+)\s*\]", re.I)


@dataclass
class Turn:
    stimulus: str
    fly: str
    claude: str = ""
    action: str = ""


@dataclass
class Conversation:
    turns: list = field(default_factory=list)

    def transcript(self, last: int = 6) -> str:
        if not self.turns:
            return ""
        lines = ["Conversation so far:"]
        for t in self.turns[-last:]:
            lines.append(f"  FLY: {t.fly}")
            if t.claude:
                lines.append(f"  YOU: {t.claude}")
        return "\n".join(lines)

    def fly_context(self, last: int = 6) -> str:
        if not self.turns:
            return "This is the first thing you have said."
        lines = ["What has been said so far (you are FLY):"]
        for t in self.turns[-last:]:
            lines.append(f"  FLY: {t.fly}")
            if t.claude:
                lines.append(f"  HUMAN: {t.claude}")
        return "\n".join(lines)


def _menu() -> str:
    return "\n".join(
        f"   [DO: {k}]  -- you {s.action}" for k, s in sorted(STIMULI.items())
    )


def system_prompt() -> str:
    return SYSTEM.format(menu=_menu())


class ClaudeMissing(RuntimeError):
    pass


def _call(prompt: str, system: str | None = None, timeout: int = 180) -> str:
    exe = shutil.which("claude")
    if not exe:
        raise ClaudeMissing(
            "the `claude` CLI is not on PATH -- install Claude Code, or use "
            "--dry-run."
        )
    cmd = [exe, "-p", prompt]
    if system:
        cmd += ["--append-system-prompt", system]
    # DEVNULL is essential: without it the subprocess inherits our stdin
    # and eats the keystrokes meant for the chat prompt.
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:400]}")
    return proc.stdout.strip()


def fly_says(state: str, convo: Conversation) -> str:
    out = _call(FLY_TURN.format(state=state, context=convo.fly_context()))
    return out.strip().strip('"')


def claude_replies(convo: Conversation, fly_line: str, interjection: str = ""):
    """Returns (reply_text, next_stimulus_key)."""
    parts = [convo.transcript()] if convo.turns else []
    if interjection:
        parts.append(f"The human watching just said to you: {interjection}")
    parts.append(f"The fly just said:\n\n  {fly_line}\n\nReply, then act.")
    raw = _call("\n\n".join(p for p in parts if p), system=system_prompt())

    m = None
    for m in TAG.finditer(raw):
        pass                      # take the last tag if it emitted several
    key = m.group(1).lower() if m else None
    text = TAG.sub("", raw).strip()
    if key not in STIMULI:
        # Claude didn't give us a usable action; don't invent one silently.
        key = None
    return text, key
