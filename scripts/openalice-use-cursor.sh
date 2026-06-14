#!/usr/bin/env bash
# Point OpenAlice workspace research at Cursor Agent (when Claude Code is capped).
#
# Run from WSL inside an OpenAlice workspace, or pass the workspace path:
#   bash ~/market-terminal/scripts/openalice-use-cursor.sh
#   bash ~/market-terminal/scripts/openalice-use-cursor.sh ~/.openalice/workspaces/workspaces/<wsId>
#
# See docs/openalice-cursor-fallback.md

set -euo pipefail

_ws="${1:-}"
if [[ -z "$_ws" ]]; then
  _ws=$(find "${HOME}/.openalice/workspaces" -name '.mcp.json' -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | head -1 | cut -d' ' -f2- | xargs -r dirname)
fi

if [[ -z "$_ws" || ! -f "${_ws}/.mcp.json" ]]; then
  echo "ERROR: no OpenAlice workspace .mcp.json found." >&2
  echo "Pass the workspace dir: bash $0 ~/.openalice/workspaces/workspaces/<wsId>" >&2
  exit 1
fi

if ! command -v agent >/dev/null 2>&1; then
  echo "ERROR: Cursor Agent CLI not found. Install:" >&2
  echo "  curl https://cursor.com/install -fsS | bash" >&2
  echo "  agent login" >&2
  exit 127
fi

if ! agent status 2>/dev/null | grep -qi 'logged in'; then
  echo "ERROR: Cursor Agent not logged in. Run: agent login" >&2
  exit 1
fi

echo "Workspace: $_ws"
mkdir -p "${HOME}/.cursor"

python3 - "$_ws" <<'PY'
import json, os, sys
from urllib.parse import urlparse, urlunparse

ws = sys.argv[1]
src = json.load(open(os.path.join(ws, ".mcp.json")))
mt = src.get("mcpServers", {}).get("market-terminal")
if not mt:
    print("WARN: no market-terminal entry in workspace .mcp.json", file=sys.stderr)
    print("      Add it per docs/openalice.md (Railway URL + Bearer token).", file=sys.stderr)
    sys.exit(2)

entry = {"url": mt["url"]}
if "headers" in mt:
    entry["headers"] = mt["headers"]
if mt.get("type"):
    entry["type"] = mt["type"]

# Cursor needs trailing slash on Railway-mounted /mcp (else SSE 404).
parsed = urlparse(entry["url"])
if parsed.path.rstrip("/").endswith("/mcp") and not parsed.path.endswith("/"):
    entry["url"] = urlunparse(parsed._replace(path=parsed.path.rstrip("/") + "/"))

dst = os.path.expanduser("~/.cursor/mcp.json")
data = {"mcpServers": {}}
if os.path.exists(dst):
    try:
        data = json.load(open(dst))
    except Exception:
        pass
data.setdefault("mcpServers", {})["market-terminal"] = entry
json.dump(data, open(dst, "w"), indent=2)
print("Wrote", dst)
print("URL:", entry["url"])
PY

echo ""
echo "Next:"
echo "  1. cd '$_ws'"
echo "  2. agent          # interactive — approve market-terminal MCP when prompted"
echo "     agent -f        # skip trust prompt (only if you trust this workspace)"
echo ""
echo "Smoke test (after MCP approval):"
echo '  agent -f -p "List MCP servers. Call decision_brief for AAPL and summarize."'
echo ""
echo "OpenAlice UI still spawns Claude by default — use this terminal for research"
echo "while Claude is capped. Execution (orders) stays in OpenAlice UTA unchanged."
