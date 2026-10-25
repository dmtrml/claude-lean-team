#!/usr/bin/env bash
# Copy the lean-team skill and its two agents into Claude Code.
#   ./install.sh                 -> user level (~/.claude): available in every project
#   ./install.sh /path/project   -> project level (<project>/.claude): only that project (commit it to share with a team)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
if [ $# -gt 0 ]; then dest="$1/.claude"; lt='$CLAUDE_PROJECT_DIR/.claude/skills/lean-team/scripts/lt.sh'
else dest="$HOME/.claude"; lt='$HOME/.claude/skills/lean-team/scripts/lt.sh'; fi
mkdir -p "$dest/skills" "$dest/agents"
cp -R "$here/skills/lean-team" "$dest/skills/"
cp "$here/agents/lean-worker.md" "$here/agents/lean-builder.md" "$dest/agents/"
echo "lean-team installed into $dest — start a new Claude Code session to pick it up."
# A plugin install wires the hooks itself; a copied skill needs them in settings.json.
cat <<EOF

Optional, recommended: turn the skill on automatically. Merge this into "hooks" in $dest/settings.json:
  "SessionStart": [{"matcher": "startup|clear|compact", "hooks": [{"type": "command", "command": "bash \\"$lt\\" start", "timeout": 10}]}],
  "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "bash \\"$lt\\" prompt", "timeout": 5}]}]
EOF
