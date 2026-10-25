# Copy the lean-team skill and its two agents into Claude Code.
#   .\install.ps1                          -> user level (~\.claude): available in every project
#   .\install.ps1 -Project C:\path\project -> project level (<project>\.claude): only that project
param([string]$Project)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = if ($Project) { Join-Path $Project '.claude' } else { Join-Path $HOME '.claude' }
$lt = if ($Project) { '$CLAUDE_PROJECT_DIR/.claude/skills/lean-team/scripts/lt.sh' } else { '$HOME/.claude/skills/lean-team/scripts/lt.sh' }
New-Item -ItemType Directory -Force -Path (Join-Path $dest 'skills'), (Join-Path $dest 'agents') | Out-Null
Copy-Item -Recurse -Force (Join-Path $here 'skills\lean-team') (Join-Path $dest 'skills')
Copy-Item -Force (Join-Path $here 'agents\lean-worker.md'), (Join-Path $here 'agents\lean-builder.md') (Join-Path $dest 'agents')
Write-Host "lean-team installed into $dest - start a new Claude Code session to pick it up."
# A plugin install wires the hooks itself; a copied skill needs them in settings.json (Claude Code runs hooks in Git Bash).
Write-Host ""
Write-Host "Optional, recommended: turn the skill on automatically. Merge this into `"hooks`" in $dest\settings.json:"
Write-Host "  `"SessionStart`": [{`"matcher`": `"startup|clear|compact`", `"hooks`": [{`"type`": `"command`", `"command`": `"bash \`"$lt\`" start`", `"timeout`": 10}]}],"
Write-Host "  `"UserPromptSubmit`": [{`"hooks`": [{`"type`": `"command`", `"command`": `"bash \`"$lt\`" prompt`", `"timeout`": 5}]}]"
