# Copy the lean-team skill and its two agents into Claude Code.
#   .\install.ps1                          -> user level (~\.claude): available in every project
#   .\install.ps1 -Project C:\path\project -> project level (<project>\.claude): only that project
param([string]$Project)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = if ($Project) { Join-Path $Project '.claude' } else { Join-Path $HOME '.claude' }
New-Item -ItemType Directory -Force -Path (Join-Path $dest 'skills'), (Join-Path $dest 'agents') | Out-Null
Copy-Item -Recurse -Force (Join-Path $here 'skills\lean-team') (Join-Path $dest 'skills')
Copy-Item -Force (Join-Path $here 'agents\lean-worker.md'), (Join-Path $here 'agents\lean-builder.md') (Join-Path $dest 'agents')
Write-Host "lean-team installed into $dest - start a new Claude Code session to pick it up."
