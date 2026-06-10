#!/usr/bin/env bash
# Find OpenAlice workspace .mcp.json files and open them in Windows Notepad (WSL).
#
# Usage (from WSL/Ubuntu):
#   bash open-mcp-notepad.sh
#
# It searches the usual OpenAlice locations, lists what it finds, and opens each
# in notepad.exe. If none exist yet, it tells you to create a workspace first.

set -uo pipefail

echo "Searching for OpenAlice .mcp.json files..."
echo

# Common roots where OpenAlice stores per-workspace configs.
roots=(
  "$HOME/.openalice"
  "$HOME/OpenAlice"
)

mapfile -t files < <(
  for r in "${roots[@]}"; do
    [[ -d "$r" ]] && find "$r" -name ".mcp.json" 2>/dev/null
  done | sort -u
)

if [[ ${#files[@]} -eq 0 ]]; then
  echo "No .mcp.json found yet."
  echo
  echo "Fix: in the OpenAlice UI (http://localhost:5173) create or open a"
  echo "workspace, then run this script again. OpenAlice writes .mcp.json the"
  echo "first time a workspace session starts."
  echo
  echo "Searched:"
  printf '  %s\n' "${roots[@]}"
  exit 1
fi

echo "Found ${#files[@]} file(s):"
printf '  %s\n' "${files[@]}"
echo

if ! command -v notepad.exe >/dev/null 2>&1; then
  echo "notepad.exe not on PATH (are you in WSL on Windows?)."
  echo "Open these paths manually, or use: nano '<path>'"
  exit 1
fi

for f in "${files[@]}"; do
  echo "Opening in Notepad: $f"
  # notepad.exe accepts WSL paths via the \\wsl$ share; pass the path directly.
  notepad.exe "$(wslpath -w "$f")" &
done

echo
echo "Notepad windows opened. Add the market-terminal block inside \"mcpServers\","
echo "save (Ctrl+S), then restart the workspace session in OpenAlice."
