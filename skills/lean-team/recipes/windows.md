# Recipe: Windows hosts

Read this file when Claude Code runs on Windows. Facts are tagged with the date they were observed.

- Claude Code's Bash (Git Bash): a heredoc that contains backticks (template strings) can break the shell wrapper — write such scripts to a file in the scratchpad and run the file.
- PowerShell 5.1: `>` writes UTF-16 and `2>&1` wraps every stderr line in `NativeCommandError`. Prefer Git Bash for CLI runs whose output you parse, or send stderr to its own file.
- Git Bash rewrites Unix-looking paths passed to Windows programs: `wsl -e bash /mnt/c/...` becomes `C:/Program Files/Git/mnt/c/...`. Prefix such calls with `MSYS_NO_PATHCONV=1` (2026-10-15).
- WSL as a Linux test host: a WSL restart empties `/tmp`, so keep virtualenvs and source snapshots in the WSL home. Copying the Windows tree over `/mnt/c` with a plain `rsync` is very slow; copy only `git ls-files -co --exclude-standard` (2026-10-15).
- The OS temp directory can hold unwritable leftovers from sandboxed tools; give test runners an explicit temp root inside the project's ignored work folder (for pytest, `--basetemp`) (2026-10-15).
