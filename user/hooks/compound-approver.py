#!/usr/bin/env python3
"""
compound-approver.py — Claude Code PreToolUse hook.

Auto-approves Bash compound commands (commands joined by &&, ||, ;, or pipes)
when every component is a safe read-only command from the config allow list.

Safety posture: false negatives (failing to approve a safe command) are
acceptable — they fall through to the normal permission prompt. False
positives (approving something unsafe) are NOT acceptable. When in doubt,
this hook bails and lets the normal flow handle the command.

Config: ~/.claude/hooks/compound-approver-config.json
Debug log: set env COMPOUND_APPROVER_LOG=1 to append to
           ~/.claude/hooks/compound-approver.log
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from typing import Iterable

CONFIG_PATH = os.path.expanduser("~/.claude/hooks/compound-approver-config.json")
LOG_PATH = os.path.expanduser("~/.claude/hooks/compound-approver.log")
LOGGING = os.environ.get("COMPOUND_APPROVER_LOG") == "1"

# Substrings that cause an immediate bail to the normal permission flow.
# Signals of command substitution, process substitution, privilege escalation,
# dynamic evaluation, or runtime execution. Redirect handling is separate
# (see has_file_redirect).
BAIL_SUBSTRINGS: tuple[str, ...] = (
    "`",         # backtick command substitution
    "$(",        # $() command substitution
    "<(", ">(",  # process substitution
    " | tee ",   # tee writes to files
    " xargs ",   # xargs executes arbitrary commands at runtime
    "eval ",     # dynamic evaluation
    " exec ",    # replaces the shell process
)

# Whitelist of redirect forms that do NOT write to a file: fd duplication
# (>&1, 2>&1, etc.), /dev/null, and fd closing (>&-).
SAFE_REDIRECT_PATTERN = re.compile(
    r"""
    (?:^|\s)
    (?:
        [012]?>&[012-]              # >&1, 2>&1, >&-, etc.
      | [012]?>/dev/null            # >/dev/null, 2>/dev/null
      | &>/dev/null                 # &>/dev/null
      | <&[0-9-]                    # <&0, <&-
    )
    """,
    re.VERBOSE,
)

# Any remaining > or < after masking safe redirects indicates a file redirect
# (write or read). Bail on these in v1 — file I/O is out of scope.
ANY_REDIRECT_PATTERN = re.compile(r"[<>]")

# Split a command into components on &&, ||, ;, and pipe. Requires whitespace
# around the operator to reduce false splits on operator characters inside
# quoted strings. Commands without whitespace around operators will bail.
SPLIT_PATTERN = re.compile(r"\s+(?:&&|\|\||;|\|)\s+")


def has_file_redirect(cmd: str) -> bool:
    """Return True if the command contains a file redirect not covered by
    the safe-redirect whitelist (fd duplication, /dev/null, fd close)."""
    masked = SAFE_REDIRECT_PATTERN.sub(" ", cmd)
    return bool(ANY_REDIRECT_PATTERN.search(masked))


def log(msg: str) -> None:
    if not LOGGING:
        return
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def bail(reason: str = "") -> None:
    """Exit silently without emitting JSON; normal permission flow handles it."""
    if reason:
        log(f"BAIL: {reason}")
    sys.exit(0)


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        bail("config file missing")
    except json.JSONDecodeError as e:
        bail(f"config file invalid JSON: {e}")
    return {}


def tokenize_component(component: str) -> tuple[str | None, list[str]]:
    """Return (first_token, remaining_args) with leading VAR=value assignments
    stripped, or (None, []) if the component can't be tokenized cleanly."""
    try:
        tokens = shlex.split(component, posix=True)
    except ValueError:
        return (None, [])
    while tokens and "=" in tokens[0] and not tokens[0].startswith("-"):
        head, _, _ = tokens[0].partition("=")
        if not head or any(ch in head for ch in " /\\"):
            break
        tokens = tokens[1:]
    if not tokens:
        return (None, [])
    return (tokens[0], tokens[1:])


def first_real_token(component: str) -> str | None:
    """Backwards-compatible wrapper — returns only the first token."""
    return tokenize_component(component)[0]


def has_deny_flag(args: list[str], deny_flags: Iterable[str]) -> bool:
    """Return True if any arg matches a denied flag.

    Supports three flag forms:
      - long flags '--foo'           (exact token match)
      - single-dash long '-delete'   (exact token match; find/tar convention)
      - short flags '-o'             (character match inside clumped '-sLo')
    """
    exact_flags: set[str] = set()
    short_chars: set[str] = set()
    for f in deny_flags:
        if f.startswith("--"):
            exact_flags.add(f)
        elif f.startswith("-") and len(f) == 2:
            short_chars.add(f[1])
            exact_flags.add(f)  # also allow exact '-o' match
        elif f.startswith("-") and len(f) > 2:
            exact_flags.add(f)  # single-dash long flag
    for raw in args:
        # Split on shell-operator chars to catch adjacency attacks like
        # '-delete;rm' — shlex.split keeps this as one token, but the ';'
        # here is an unquoted shell separator (quotes would have been
        # stripped by shlex). Splitting lets exact-match catch '-delete'.
        for piece in re.split(r"[;&|]", raw):
            if not piece:
                continue
            if piece in exact_flags:
                return True
            if piece.startswith("-") and not piece.startswith("--") and len(piece) > 1:
                if short_chars and piece not in exact_flags:
                    if any(c in short_chars for c in piece[1:]):
                        return True
    return False


def component_is_safe(
    component: str,
    safe_cmds: Iterable[str],
    dangerous_cmds: Iterable[str],
    safe_with_arg_check: dict | None = None,
) -> bool:
    component = component.strip()
    if not component:
        return False
    first, rest = tokenize_component(component)
    if first is None:
        return False
    if first in dangerous_cmds:
        return False
    if first in safe_cmds:
        return True
    if safe_with_arg_check and first in safe_with_arg_check:
        rule = safe_with_arg_check[first] or {}
        deny_flags = rule.get("deny_flags", [])
        deny_subcommands = set(rule.get("deny_subcommands", []))
        if deny_subcommands and rest and rest[0] in deny_subcommands:
            return False
        if has_deny_flag(rest, deny_flags):
            return False
        return True
    return False


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        bail("stdin not JSON")
        return

    if payload.get("tool_name") != "Bash":
        bail("not a Bash tool invocation")
        return

    command = (payload.get("tool_input") or {}).get("command", "")
    if not isinstance(command, str) or not command.strip():
        bail("no command")
        return

    log(f"CMD: {command}")

    for bad in BAIL_SUBSTRINGS:
        if bad in command:
            bail(f"bail substring: {bad!r}")
            return

    if has_file_redirect(command):
        bail("file redirect present")
        return

    config = load_config()
    safe_cmds = set(config.get("safe_commands", []))
    dangerous_cmds = set(config.get("dangerous_first_tokens", []))
    safe_with_arg_check = config.get("safe_with_arg_check", {}) or {}

    components = SPLIT_PATTERN.split(command.strip())
    if not components:
        bail("empty component list")
        return

    for c in components:
        if not component_is_safe(c, safe_cmds, dangerous_cmds, safe_with_arg_check):
            bail(f"unsafe component: {c!r}")
            return

    # All components safe. Emit approval in both the current and legacy
    # Claude Code hook formats so this works across versions.
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "compound-approver: all components safe",
        },
        "decision": "approve",
        "reason": "compound-approver: all components safe",
    }
    log(f"APPROVE: {command}")
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
