#!/usr/bin/env bash
#
# flyclaude setup: fetch a fly, check you can talk to Claude.
#
# Safe to re-run -- every step is skipped if it's already done.
# Needs no sudo, no API key, and no credentials of any kind.
#
#   ./setup.sh           full setup
#   ./setup.sh --check   verify an existing install, change nothing
#   ./setup.sh --no-data skip the 316 MB download (fetched on first run instead)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"
DATA="$ROOT/data"
BUCKET="https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/compiled_data/fafb_783"

CHECK_ONLY=0
WANT_DATA=1
for arg in "$@"; do
  case "$arg" in
    --check)   CHECK_ONLY=1 ;;
    --no-data) WANT_DATA=0 ;;
    -h|--help) sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

if [ -t 1 ]; then
  B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; N=$'\033[0m'
else
  B=; G=; Y=; R=; D=; N=
fi
ok()   { printf '  %s✓%s %s\n' "$G" "$N" "$1"; }
warn() { printf '  %s!%s %s\n' "$Y" "$N" "$1"; }
bad()  { printf '  %s✗%s %s\n' "$R" "$N" "$1"; }
step() { printf '\n%s==>%s %s%s%s\n' "$B" "$N" "$B" "$1" "$N"; }

FAILED=0

# ---------------------------------------------------------------- 1. python
step "Python"
if ! command -v python3 >/dev/null 2>&1; then
  bad "python3 not found. Install Python 3.9+ and re-run."
  exit 1
fi
PYVER=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)'; then
  bad "Python $PYVER is too old; need 3.9+."
  exit 1
fi
ok "python3 $PYVER at $(command -v python3)"

# ------------------------------------------------------------------ 2. venv
step "Virtual environment"
if [ -x "$PY" ]; then
  ok "venv already exists at .venv"
elif [ "$CHECK_ONLY" = 1 ]; then
  bad "no .venv -- run ./setup.sh without --check"
  FAILED=1
else
  if ! python3 -m venv "$VENV" 2>/dev/null; then
    bad "could not create a venv."
    echo "      On Debian/Ubuntu this usually means:"
    echo "        sudo apt install python3-venv"
    exit 1
  fi
  ok "created .venv"
fi

# ------------------------------------------------------------ 3. python deps
step "Python packages"
if [ -x "$PY" ]; then
  if "$PY" -c 'import numpy, scipy, pyarrow' 2>/dev/null; then
    ok "numpy, scipy, pyarrow present"
  elif [ "$CHECK_ONLY" = 1 ]; then
    bad "dependencies missing -- run ./setup.sh without --check"
    FAILED=1
  else
    echo "      installing (this takes a minute)..."
    "$VENV/bin/pip" install -q --upgrade pip >/dev/null 2>&1 || true
    if "$VENV/bin/pip" install -q -r "$ROOT/requirements.txt"; then
      ok "installed numpy, scipy, pyarrow"
    else
      bad "pip install failed -- see the output above"
      exit 1
    fi
  fi
fi

# ------------------------------------------------------------------ 4. a fly
step "Connectome data"
mkdir -p "$DATA"
# name:expected-bytes -- from the public bucket, no auth required
FILES="fafb_783_meta.feather:13539866 fafb_783_simple_edgelist.feather:302625658"
for entry in $FILES; do
  name="${entry%%:*}"; want="${entry##*:}"
  dest="$DATA/$name"
  if [ -f "$dest" ]; then
    have=$(stat -c%s "$dest" 2>/dev/null || stat -f%z "$dest")
    if [ "$have" -ge "$want" ]; then
      ok "$name ($(( have / 1000000 )) MB)"
      continue
    fi
    warn "$name looks truncated ($have bytes); re-fetching"
    rm -f "$dest"
  fi
  if [ "$CHECK_ONLY" = 1 ]; then
    bad "$name missing"; FAILED=1; continue
  fi
  if [ "$WANT_DATA" = 0 ]; then
    warn "$name skipped (--no-data); it'll download on first run"
    continue
  fi
  echo "      downloading $name ($(( want / 1000000 )) MB) from the public bucket..."
  if curl -fL --retry 3 --progress-bar -o "$dest.part" "$BUCKET/$name"; then
    mv "$dest.part" "$dest"
    ok "$name"
  else
    rm -f "$dest.part"
    bad "download failed for $name"
    FAILED=1
  fi
done

# ------------------------------------------------------- 5. build the matrix
step "Connectivity matrix"
if [ -x "$PY" ] && [ -f "$DATA/fafb_783_simple_edgelist.feather" ]; then
  if ls "$DATA"/connectome_cache_v*.npz >/dev/null 2>&1; then
    ok "cached matrix present"
  elif [ "$CHECK_ONLY" = 1 ]; then
    warn "not built yet -- it builds automatically on first run (~30s)"
  else
    echo "      building (one-time, ~30s)..."
    if (cd "$ROOT" && "$PY" -c 'from flyclaude import graph; graph.load()' >/dev/null); then
      ok "built and cached"
    else
      bad "matrix build failed"
      FAILED=1
    fi
  fi
else
  warn "skipped (needs the venv and the edge list)"
fi

# ------------------------------------------------------------------ 6. claude
step "Claude Code"
CLAUDE_OK=0
if ! command -v claude >/dev/null 2>&1; then
  bad "the \`claude\` CLI is not on your PATH."
  cat <<'EOF'
      Install it with one of:
        curl -fsSL https://claude.ai/install.sh | bash     # native installer
        npm install -g @anthropic-ai/claude-code           # via npm

      If you've already installed it, your PATH may just be missing the
      install dir. Try:
        export PATH="$HOME/.local/bin:$PATH"

      Docs: https://docs.claude.com/en/docs/claude-code
EOF
  FAILED=1
else
  ok "claude found at $(command -v claude)  ($(claude --version 2>/dev/null | head -1))"

  # Presence is not enough -- this project shells out to `claude -p`, so the
  # thing that actually matters is whether THIS user can complete a prompt.
  echo "      checking that it can actually answer (this uses your existing login)..."
  REPLY=$(timeout 90 claude -p 'Reply with exactly the word: FLYCLAUDE' 2>"$ROOT/.setup-claude-err" || true)
  ERR=$(cat "$ROOT/.setup-claude-err" 2>/dev/null || true)
  rm -f "$ROOT/.setup-claude-err"

  if printf '%s' "$REPLY" | grep -qi 'FLYCLAUDE'; then
    ok "claude responded -- you're authenticated and good to go"
    CLAUDE_OK=1
  elif printf '%s\n%s' "$REPLY" "$ERR" | grep -qiE 'log ?in|logged out|authenticat|unauthori[sz]ed|api key|credential|/login'; then
    bad "claude is installed but this user isn't logged in."
    echo "      Run \`claude\` once and complete the login, then re-run ./setup.sh --check"
    FAILED=1
  elif [ -z "$REPLY" ]; then
    bad "claude produced no output (timed out, or exited early)."
    [ -n "$ERR" ] && echo "      stderr: $(printf '%s' "$ERR" | head -3)"
    echo "      Try running \`claude -p hello\` yourself to see what it says."
    FAILED=1
  else
    warn "claude answered, but not as expected. Probably fine."
    echo "      got: $(printf '%s' "$REPLY" | head -2)"
    CLAUDE_OK=1
  fi
fi

# ------------------------------------------------------------------- verdict
step "Result"
if [ "$FAILED" = 0 ]; then
  ok "everything is ready."
  cat <<EOF

  ${B}Start talking to the fly:${N}

      ${D}\$${N} ./bin/flyclaude              ${D}# or: .venv/bin/python bin/flyclaude${N}

  Other things to try:

      ./bin/flyclaude chat --auto 5   ${D}# five rounds, hands off${N}
      ./bin/flyclaude ask             ${D}# one question, one answer${N}
      ./bin/flyclaude ask --brain-only ${D}# just the neuroscience${N}
      ./bin/flyclaude stimuli         ${D}# what you can do to her${N}

EOF
  [ "$CLAUDE_OK" = 0 ] && warn "(Claude wasn't verified, so only --brain-only will work.)"
  exit 0
else
  bad "setup incomplete -- see the failures above."
  echo
  echo "  Re-run ./setup.sh once you've fixed them, or ./setup.sh --check to re-verify."
  exit 1
fi
