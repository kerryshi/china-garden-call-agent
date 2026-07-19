#!/bin/sh
# .githooks/env.sh — per-OS toolchain resolution for china-garden hooks.
# Secret-free. Sourced by hooks; sets REPO_DIR and VENV_PY (absolute paths).
# Refuse-over-skip: a missing venv is a NAMED refusal in the hook, never a skip.

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    REPO_DIR="/c/Users/PC/china-garden"
    VENV_PY="$REPO_DIR/.venv/Scripts/python.exe"
    ;;
  Darwin)
    REPO_DIR="$HOME/Projects/china-garden"
    VENV_PY="$REPO_DIR/.venv/bin/python"
    ;;
  *)
    REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
    VENV_PY="$REPO_DIR/.venv/bin/python"
    ;;
esac
