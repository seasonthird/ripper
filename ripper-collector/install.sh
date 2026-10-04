#!/usr/bin/env bash
#
# Ripper Collector installer.
#
# This script assumes the complete Ripper bundle is present and this directory
# remains beside ripper-core, ripper-archive-manager and ripper-exporter.
# It sets up the Python virtual environment and installs dependencies in
# place. No copying, no moving.
#
# Usage:
#   bash <ripper-root>/ripper-collector/install.sh
#   bash <ripper-root>/ripper-collector/install.sh --dev
#
# After this runs, restart Claude Code to pick up the skill.

set -euo pipefail

# Parse flags. Only --dev is recognized; anything else is an error.
INSTALL_DEV=0
for arg in "$@"; do
  case "$arg" in
    --dev)
      INSTALL_DEV=1
      ;;
    *)
      echo "ERROR: unknown flag: $arg" >&2
      echo "Usage: bash install.sh [--dev]" >&2
      exit 2
      ;;
  esac
done

# Resolve the directory this script lives in — that IS the install location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RIPPER_BUNDLE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
for required in \
  "$RIPPER_BUNDLE_ROOT/ripper-core/asset_store.py" \
  "$RIPPER_BUNDLE_ROOT/ripper-archive-manager/scripts/archive_manager.py" \
  "$RIPPER_BUNDLE_ROOT/ripper-exporter/export_assets.py"; do
  if [ ! -f "$required" ]; then
    echo "ERROR: incomplete Ripper bundle; missing $required" >&2
    echo "Install or copy the complete Ripper repository, not ripper-collector alone." >&2
    exit 2
  fi
done

if [ "$INSTALL_DEV" = "1" ]; then
  echo "Setting up ripper-collector (with dev deps) at: $SCRIPT_DIR"
else
  echo "Setting up ripper-collector at: $SCRIPT_DIR"
fi

# Find a Python 3.10+ interpreter. Honor RIPPER_COLLECTOR_PYTHON first for
# hosts whose managed runtime is not on PATH, then prefer `python3`
# (standard on macOS/Linux);
# fall back to `python` (standard on Windows/Git Bash, where `python3` is
# typically absent — or is a Microsoft Store App Execution Alias stub that
# prints "Python was not found" and exits non-zero when invoked). Since
# `command -v` can't tell a working interpreter from a broken stub, actually
# invoke each candidate and confirm it runs AND reports 3.10+.
_is_python_310_plus() {
  command -v "$1" >/dev/null 2>&1 \
    && "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

if [ -n "${RIPPER_COLLECTOR_PYTHON:-}" ] && _is_python_310_plus "$RIPPER_COLLECTOR_PYTHON"; then
  PYTHON="$RIPPER_COLLECTOR_PYTHON"
elif _is_python_310_plus python3; then
  PYTHON=python3
elif _is_python_310_plus python; then
  PYTHON=python
else
  echo "ERROR: Python 3.10+ is not installed or not on PATH." >&2
  echo "Install Python 3.10+, add it to PATH, or set RIPPER_COLLECTOR_PYTHON to its executable." >&2
  exit 1
fi

# Create or reuse the venv.
VENV="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV" ]; then
  echo "Creating venv at $VENV"
  "$PYTHON" -m venv "$VENV"
else
  echo "Reusing existing venv at $VENV"
fi

# Windows CPython's venv layout uses Scripts/ instead of bin/. Pick whichever
# exists so the rest of this script and the wrapper in bin/ripper-collector-exec
# work on both layouts.
if [ -d "$VENV/bin" ]; then
  VENV_BIN="$VENV/bin"
elif [ -d "$VENV/Scripts" ]; then
  VENV_BIN="$VENV/Scripts"
else
  echo "ERROR: venv created at $VENV but neither bin/ nor Scripts/ subdirectory found." >&2
  exit 1
fi

# Install dependencies. Use a generous timeout and retry count so students
# on coffee-shop / hotel / airport wifi still see a successful install.
# PIP_OPTS is overridable from the environment so students on especially
# slow connections can bump timeout/retries without editing this file.
: "${PIP_OPTS:=--default-timeout=120 --retries=5}"
echo "Installing dependencies (this can take ~30s on a fast connection, longer on slow wifi)..."

# Friendly error wrapper around pip. set -e would turn a pip failure into
# a raw Python traceback. Catch it instead and print an actionable message.
#
# Invoke pip via `python -m pip` instead of the pip.exe/pip binary. On
# Windows, pip.exe can't overwrite itself when a self-upgrade is requested
# (the file is locked by the running process); pip detects this and refuses,
# redirecting to `python -m pip install --upgrade pip` — which copies pip
# to a temp location before replacing. Using `python -m pip` here uniformly
# sidesteps the issue and behaves identically on POSIX.
_pip_install() {
  local label="$1"; shift
  if ! "$VENV_BIN/python" -m pip install $PIP_OPTS --quiet "$@"; then
    cat >&2 <<EOF

ERROR: pip install for ${label} failed (exit code $?).

This is almost always a network issue, not a bug in ripper-collector. Try:

  1. Re-run the installer — transient PyPI slowness is common:
       bash $SCRIPT_DIR/install.sh

  2. If you're on slow wifi (coffee shop, hotel, conference), bump
     pip's tolerance and retry:
       PIP_OPTS="--default-timeout=300 --retries=10" bash $SCRIPT_DIR/install.sh

  3. If you're behind a corporate proxy, set HTTPS_PROXY before running:
       export HTTPS_PROXY=http://your.proxy:port
       bash $SCRIPT_DIR/install.sh

  4. Still failing? Save the full pip output and consult the README shipped
     with this Ripper bundle. No upstream issue tracker is hard-coded.
EOF
    exit 2
  fi
}

_pip_install "pip itself" --upgrade pip
if [ "$INSTALL_DEV" = "1" ]; then
  # requirements-dev.txt includes `-r requirements.txt` at the top, so this
  # single install covers both runtime and dev (pytest, jupyter).
  _pip_install "ripper-collector dependencies (runtime + dev)" -r "$SCRIPT_DIR/requirements-dev.txt"
else
  _pip_install "ripper-collector dependencies" -r "$SCRIPT_DIR/requirements.txt"
fi


# Ensure the wrapper scripts in bin/ are executable. Git preserves the exec
# bit, but a zip download or a Windows-transit clone can drop it.
if [ -d "$SCRIPT_DIR/bin" ]; then
  chmod +x "$SCRIPT_DIR/bin/"* 2>/dev/null || true
fi


# OpenCode slash-command shim. OpenCode resolves `/ripper-collector <args>` by
# reading `~/.config/opencode/commands/ripper-collector.md` and substituting
# `$ARGUMENTS` into its body. Without the shim, OpenCode falls back to
# pasting the full SKILL.md as a user message and silently drops the
# argument — observed under qwen3.6-35b in run ses_235c, where the model
# replied "I've loaded the ripper-collector skill. What would you like me to do?"
# instead of executing. The shim ensures `/ripper-collector design.md source/`
# actually runs the deposit pipeline. Skipped silently if OpenCode isn't installed.
OPENCODE_CMD_SRC="$SCRIPT_DIR/commands/ripper-collector.md"
if [ -f "$OPENCODE_CMD_SRC" ] && command -v opencode >/dev/null 2>&1; then
  OPENCODE_CMD_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/opencode/commands"
  if mkdir -p "$OPENCODE_CMD_DIR" 2>/dev/null; then
    if cp "$OPENCODE_CMD_SRC" "$OPENCODE_CMD_DIR/ripper-collector.md" 2>/dev/null; then
      echo "Installed OpenCode slash-command shim at $OPENCODE_CMD_DIR/ripper-collector.md"
    fi
  fi
fi

# OpenCode tool_output.max_bytes detection. Compare the installed SKILL.md
# dynamically with OpenCode's default 51,200-byte cap. If future workflow
# growth crosses the configured cap, truncation can silently remove the final
# validation or deposit stages, especially on smaller local models.
#
# We READ the user's opencode config (never write to it) and warn if the
# cap is below SKILL.md's size. The user's config stays the user's
# concern. See samples-issue42/session-ses_2359.md for the failure mode.
if command -v opencode >/dev/null 2>&1; then
  OPENCODE_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/opencode/opencode.json"
  SKILL_BYTES=$(wc -c < "$SCRIPT_DIR/SKILL.md" 2>/dev/null | tr -d ' ')
  # Use the venv Python we just built — every host has Python after install.
  # Falls back to the documented OpenCode default (51200) on any parse error
  # so we err on the side of warning (false positive is harmless; missing a
  # real warning would let a student silently ship a half-truncated SKILL.md).
  OPENCODE_MAX=$("$VENV_BIN/python" -c '
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
try:
    data = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    print(int(data.get("tool_output", {}).get("max_bytes", 51200)))
except Exception:
    print(51200)
' "$OPENCODE_CONFIG" 2>/dev/null || echo 51200)
  if [ -n "$SKILL_BYTES" ] && [ -n "$OPENCODE_MAX" ] && [ "$OPENCODE_MAX" -lt "$SKILL_BYTES" ]; then
    echo ""
    echo "NOTE: OpenCode detected. Your tool_output.max_bytes is $OPENCODE_MAX,"
    echo "      but ripper-collector's SKILL.md is $SKILL_BYTES bytes. OpenCode will"
    echo "      truncate the skill when it loads, which can omit validation or"
    echo "      transactional deposit instructions on any model."
    echo ""
    echo "      To fix, add to $OPENCODE_CONFIG:"
    echo '        { "tool_output": { "max_bytes": 102400 } }'
    echo ""
    echo "      (We never modify your opencode config — this is a heads-up,"
    echo "      not an action item, and you can ignore it on cloud models.)"
    echo ""
  fi
fi

echo ""
echo "Ripper Collector dependencies installed at $SCRIPT_DIR"
echo ""
echo "Next steps:"
echo "  1. Restart your AI CLI (Claude Code, Codex, Gemini, or OpenCode) so it picks up the new skill."
echo "  2. Keep ripper-collector beside the other Ripper bundle components."
echo "  3. Run: /ripper-collector /absolute/path/to/project.md"
if [ "$INSTALL_DEV" = "0" ]; then
  echo ""
  echo "  (Contributors: re-run with --dev to add pytest/jupyter for running the test suite.)"
fi
