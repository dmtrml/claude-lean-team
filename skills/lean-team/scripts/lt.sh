#!/usr/bin/env bash
# Run lt.py with the first working Python 3.8+. On Windows `python3` can be a
# Microsoft Store stub that prints "Python" and exits 49, so each candidate is
# probed silently first; the one that works is cached in $LEAN_TEAM_HOME/.python.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
data="${LEAN_TEAM_HOME:-$HOME/.claude/lean-team}"
cache="$data/.python"

works() { "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; }

py=""
if [ -f "$cache" ]; then
  py="$(cat "$cache" 2>/dev/null)"
  works "$py" || py=""
fi
if [ -z "$py" ]; then
  for c in python3 python py; do
    if command -v "$c" >/dev/null 2>&1 && works "$c"; then py="$c"; break; fi
  done
  [ -n "$py" ] && mkdir -p "$data" 2>/dev/null && printf '%s' "$py" > "$cache" 2>/dev/null
fi

if [ -n "$py" ]; then
  exec "$py" -I "$here/lt.py" "$@"
fi

# No Python: hooks still remind, everything else reports the problem.
case "$1" in
  start) echo "lean-team is installed. For multi-step work load the lean-team skill first; do small fixes yourself. (Python 3.8+ not found: token counts and learning status are unavailable.)" ;;
  prompt) cat >/dev/null ;;
  *) echo "lean-team: Python 3.8+ not found (tried python3, python, py)" >&2; exit 3 ;;
esac
exit 0
