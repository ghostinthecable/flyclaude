"""Hand the fly's brain state to Claude Code.

Shells out to the `claude` CLI, which uses whatever login you already have.
No API key is read, stored, or needed by this project.
"""
from __future__ import annotations

import shutil
import subprocess

ASK_PROMPT = """\
You are a single female Drosophila melanogaster. Below is a readout from an \
actual simulation of your connectome -- your real wiring, 140k neurons, just \
stimulated.

{state}

Ask ONE question. Out loud. To an AI.

Rules:
- It does NOT have to be about flies, or about what just happened to you. It \
can be about ANYTHING in the universe: tax law, the moon, sandwiches, grief, \
submarines, whatever.
- But the thing that just happened to your brain should be the reason you \
thought of it. Let the neural state derail you into the question.
- You have a brain the size of a poppy seed and roughly 40 days to live. You \
are not sad about this. You are deeply, sincerely curious.
- Be funny by being earnest, not by telling jokes.
- Output ONLY the question. One or two sentences. No preamble, no quotes, no \
stage directions.
"""

ANSWER_PROMPT = """\
A housefly asked you this, sincerely:

  "{question}"

Answer it properly. Take the question completely seriously, give it a real \
answer with real information in it, and pitch it to someone with a poppy-seed \
brain and about 40 days left. Warm, not condescending. Under 150 words.
"""


class ClaudeMissing(RuntimeError):
    pass


def _call(prompt: str, timeout: int = 180) -> str:
    exe = shutil.which("claude")
    if not exe:
        raise ClaudeMissing(
            "the `claude` CLI is not on PATH -- install Claude Code, or "
            "run with --dry-run to see the prompt instead."
        )
    proc = subprocess.run(
        [exe, "-p", prompt],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude exited {proc.returncode}: {proc.stderr.strip()[:400]}"
        )
    return proc.stdout.strip()


def question_from(state: str) -> str:
    return _call(ASK_PROMPT.format(state=state))


def answer_to(question: str) -> str:
    return _call(ANSWER_PROMPT.format(question=question))
