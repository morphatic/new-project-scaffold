#!/usr/bin/env bash
#
# install.sh — sync the user-level pieces of this repo into ~/.claude/.
#
# The versioned sources in user/ are the single source of truth for the
# global Claude Code hooks and slash commands. Edit them HERE, then run
# this script — never hand-edit the live copies in ~/.claude/.
#
# What it does:
#   - Copies user/hooks/*  -> ~/.claude/hooks/
#   - Copies user/commands/* -> ~/.claude/commands/
#   - Does NOT touch ~/.claude/settings.json (hook registration lives
#     there; it changes rarely and is easy to clobber — see README
#     "Global hooks" for the expected registration blocks).
#
# Usage:  bash install.sh [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "install.sh: unknown arg: $arg" >&2; exit 2 ;;
  esac
done

sync_dir() {
  local src="$1" dest="$2"
  mkdir -p "$dest"
  local f base
  for f in "$src"/*; do
    [[ -f "$f" ]] || continue
    base="$(basename "$f")"
    if [[ -f "$dest/$base" ]] && cmp -s "$f" "$dest/$base"; then
      echo "  = $base (unchanged)"
      continue
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
      echo "  ~ $base (would copy)"
    else
      cp "$f" "$dest/$base"
      echo "  + $base"
    fi
  done
}

echo "Syncing hooks -> $CLAUDE_DIR/hooks/"
sync_dir "$SCRIPT_DIR/user/hooks" "$CLAUDE_DIR/hooks"

echo "Syncing commands -> $CLAUDE_DIR/commands/"
sync_dir "$SCRIPT_DIR/user/commands" "$CLAUDE_DIR/commands"

echo ""
echo "Done. Reminder: hook registration lives in $CLAUDE_DIR/settings.json"
echo "and is not managed by this script. If you added a NEW hook, register"
echo "it there manually (see README, 'Global hooks')."
