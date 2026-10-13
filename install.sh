#!/usr/bin/env bash
# Copy the lean-team skill and its two agents into Claude Code.
#   ./install.sh                 -> user level (~/.claude): available in every project
#   ./install.sh /path/project   -> project level (<project>/.claude): only that project (commit it to share with a team)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
if [ $# -gt 0 ]; then dest="$1/.claude"; else dest="$HOME/.claude"; fi
mkdir -p "$dest/skills" "$dest/agents"
cp -R "$here/skills/lean-team" "$dest/skills/"
cp "$here/agents/lean-worker.md" "$here/agents/lean-builder.md" "$dest/agents/"
echo "lean-team installed into $dest — start a new Claude Code session to pick it up."
