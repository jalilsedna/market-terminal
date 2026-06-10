#!/usr/bin/env bash
# OpenAlice workspace helper: prefer Claude Code, fall back to Cursor Agent on limits.
#
# OpenAlice workspaces normally spawn `claude` directly. When Anthropic usage caps
# hit (429 / "rate limit" / "usage limit"), run this from a **shell** workspace or
# paste into the workspace terminal:
#
#   bash /path/to/market-terminal/scripts/openalice-claude-or-cursor.sh
#
# Or symlink as ~/bin/alice-agent and set the workspace CLI to `shell`, then run
# `alice-agent` as your first command.
#
# Prerequisites:
#   - claude  (Claude Code CLI, logged in)
#   - agent   (Cursor Agent CLI — `curl https://cursor.com/install -fsS | bash`, then `agent login`)
#
# See docs/openalice-cursor-fallback.md

set -euo pipefail

_limit_pattern='rate limit|usage limit|too many requests|429|quota exceeded|limit reached'

_pick_agent() {
  if command -v claude >/dev/null 2>&1; then
    echo claude
  elif command -v agent >/dev/null 2>&1; then
    echo agent
  else
    echo ""
  fi
}

_run() {
  local bin=$1
  shift
  if [[ "$bin" == claude ]]; then
    exec claude "$@"
  fi
  exec agent "$@"
}

primary=$(_pick_agent)
if [[ -z "$primary" ]]; then
  echo "ERROR: need 'claude' (Claude Code) or 'agent' (Cursor) on PATH." >&2
  echo "See docs/openalice-cursor-fallback.md" >&2
  exit 127
fi

if [[ "$primary" == agent ]]; then
  echo "Claude Code not found — starting Cursor Agent." >&2
  _run agent "$@"
fi

# Claude first: if it exits with a limit-ish message, retry once with Cursor.
err_file=$(mktemp)
trap 'rm -f "$err_file"' EXIT

set +e
claude "$@" 2> >(tee "$err_file" >&2)
code=$?
set -e

if [[ $code -eq 0 ]]; then
  exit 0
fi

if grep -qiE "$_limit_pattern" "$err_file" && command -v agent >/dev/null 2>&1; then
  echo "" >&2
  echo ">>> Claude Code limit reached — continuing with Cursor Agent (same workspace, same MCP)." >&2
  echo ">>> market-terminal tools stay available via .mcp.json in both CLIs." >&2
  echo "" >&2
  _run agent "$@"
fi

exit "$code"
