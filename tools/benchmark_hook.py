#!/usr/bin/env python3
"""
benchmark_hook.py — feed every command from bash_commands.json through the
compound-approver hook logic and aggregate outcomes.

Purpose: find high-frequency bail reasons so we can decide whether v2 features
($(...) unwrapping, CWD-scoped redirects, safe-command additions) are worth
the complexity.

Usage: python benchmark_hook.py [--top N]
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from collections import Counter, defaultdict
from pathlib import Path

# Benchmark the VERSIONED sources in user/hooks/ (what you edit), not the
# live copies in ~/.claude/hooks/ (what install.sh syncs).
_REPO_HOOKS = Path(__file__).resolve().parent.parent / "user" / "hooks"
HOOK_PATH = _REPO_HOOKS / "compound-approver.py"
CONFIG_PATH = _REPO_HOOKS / "compound-approver-config.json"
# The 7.7 MB corpus stays in claude_research; override with BENCH_CORPUS.
COMMANDS_PATH = Path(
    os.environ.get(
        "BENCH_CORPUS",
        Path.home() / "dev" / "claude_research" / "permissions-mastery" / "bash_commands.json",
    )
)


def load_hook_module():
    spec = importlib.util.spec_from_file_location("compound_approver", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def classify(
    command: str, hook, safe_cmds: set, dangerous_cmds: set, safe_with_arg_check: dict
) -> tuple[str, str]:
    """Return (outcome, detail). outcome in {approve, bail}."""
    if not isinstance(command, str) or not command.strip():
        return ("bail", "empty command")

    for bad in hook.BAIL_SUBSTRINGS:
        if bad in command:
            return ("bail", f"bail substring {bad!r}")

    if hook.has_file_redirect(command):
        return ("bail", "file redirect")

    components = hook.SPLIT_PATTERN.split(command.strip())
    if not components:
        return ("bail", "empty components")

    for c in components:
        if not hook.component_is_safe(c, safe_cmds, dangerous_cmds, safe_with_arg_check):
            first = hook.first_real_token(c) or "<untokenizable>"
            if first in dangerous_cmds:
                return ("bail", f"dangerous first token: {first}")
            if first in safe_with_arg_check:
                return ("bail", f"arg-check rejected: {first}")
            return ("bail", f"unsafe first token: {first}")

    return ("approve", "all components safe")


SUBSHELL_PATTERN = re.compile(r"\$\(([^()`]*)\)")


def would_approve_with_subshell_unwrap(
    command: str, hook, safe_cmds: set, dangerous_cmds: set
) -> bool:
    """Simulate v2 feature #1: unwrap $(safe-cmd ...) and re-classify."""
    if "$(" not in command:
        return False
    # Only unwrap if every inner subshell command is safe AND there are no
    # nested $(...) or backticks (keep it simple for the simulation).
    if "`" in command:
        return False
    unwrapped = command
    while True:
        m = SUBSHELL_PATTERN.search(unwrapped)
        if not m:
            break
        inner = m.group(1).strip()
        inner_first = hook.first_real_token(inner)
        if inner_first is None or inner_first in dangerous_cmds or inner_first not in safe_cmds:
            return False
        unwrapped = unwrapped[: m.start()] + "PLACEHOLDER" + unwrapped[m.end():]
    if "$(" in unwrapped:  # nested, bail
        return False
    outcome, _ = classify(unwrapped, hook, safe_cmds, dangerous_cmds, {})
    return outcome == "approve"


REDIRECT_TARGET_PATTERN = re.compile(r"(?:^|\s)[012]?>{1,2}\s*(\S+)")


def would_approve_with_cwd_redirect(
    command: str, hook, safe_cmds: set, dangerous_cmds: set, cwd: str | None
) -> bool:
    """Simulate v2 feature #2: allow file redirects whose target is inside
    the session CWD or /tmp. This is a rough heuristic for the benchmark —
    production logic would resolve symlinks."""
    if "$(" in command or "`" in command:
        return False
    targets = REDIRECT_TARGET_PATTERN.findall(command)
    if not targets:
        return False
    for t in targets:
        t = t.strip("\"'")
        if t == "/dev/null" or t.startswith("&"):
            continue
        # Accept relative paths (scoped to CWD) and /tmp/*.
        if t.startswith("/tmp/") or t.startswith("~/"):
            continue
        if t.startswith("/") or (len(t) > 1 and t[1] == ":"):
            return False  # absolute outside /tmp
        # relative — assume under cwd
    # Strip redirects and re-classify.
    stripped = re.sub(r"(?:^|\s)[012]?>{1,2}\s*\S+", " ", command)
    stripped = re.sub(r"(?:^|\s)&>\s*\S+", " ", stripped)
    outcome, _ = classify(stripped.strip(), hook, safe_cmds, dangerous_cmds, {})
    return outcome == "approve"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    hook = load_hook_module()
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    safe_cmds = set(config["safe_commands"])
    dangerous_cmds = set(config["dangerous_first_tokens"])
    safe_with_arg_check = config.get("safe_with_arg_check", {}) or {}
    safe_with_arg_check = {k: v for k, v in safe_with_arg_check.items() if isinstance(v, dict)}

    with open(COMMANDS_PATH, encoding="utf-8") as f:
        records = json.load(f)

    outcomes = Counter()
    bail_reasons = Counter()
    unsafe_tokens = Counter()
    redirect_bail_samples = []
    subshell_bail_samples = []
    subshell_unwrap_wins = 0
    redirect_cwd_wins = 0
    v2_win_samples = defaultdict(list)

    total = len(records)
    for rec in records:
        cmd = rec.get("command", "")
        outcome, detail = classify(cmd, hook, safe_cmds, dangerous_cmds, safe_with_arg_check)
        outcomes[outcome] += 1
        if outcome == "bail":
            bail_reasons[detail] += 1
            if detail.startswith("unsafe first token: "):
                unsafe_tokens[detail.removeprefix("unsafe first token: ")] += 1
            if detail == "file redirect":
                if len(redirect_bail_samples) < 5:
                    redirect_bail_samples.append(cmd)
                if would_approve_with_cwd_redirect(cmd, hook, safe_cmds, dangerous_cmds, None):
                    redirect_cwd_wins += 1
                    if len(v2_win_samples["cwd_redirect"]) < 5:
                        v2_win_samples["cwd_redirect"].append(cmd)
            if detail == "bail substring '$('":
                if len(subshell_bail_samples) < 5:
                    subshell_bail_samples.append(cmd)
                if would_approve_with_subshell_unwrap(cmd, hook, safe_cmds, dangerous_cmds):
                    subshell_unwrap_wins += 1
                    if len(v2_win_samples["subshell_unwrap"]) < 5:
                        v2_win_samples["subshell_unwrap"].append(cmd)

    print(f"=== BENCHMARK over {total} commands ===\n")
    for outcome, n in outcomes.most_common():
        print(f"  {outcome:10s} {n:6d}  ({n/total*100:.1f}%)")
    print()

    print(f"=== Top {args.top} bail reasons ===")
    for reason, n in bail_reasons.most_common(args.top):
        print(f"  {n:6d}  {reason}")
    print()

    print(f"=== Top {args.top} unsafe first tokens (candidates for safe_commands) ===")
    for tok, n in unsafe_tokens.most_common(args.top):
        print(f"  {n:6d}  {tok}")
    print()

    print("=== V2 feature projections ===")
    redirect_bails = bail_reasons.get("file redirect", 0)
    subshell_bails = bail_reasons.get("bail substring '$('", 0)
    print(f"  Subshell unwrap (#1): would rescue {subshell_unwrap_wins}/{subshell_bails} "
          f"subshell bails ({subshell_unwrap_wins/total*100:.1f}% of all commands)")
    print(f"  CWD redirect (#2):    would rescue {redirect_cwd_wins}/{redirect_bails} "
          f"redirect bails ({redirect_cwd_wins/total*100:.1f}% of all commands)")
    print()

    if subshell_bail_samples:
        print("--- sample $(...) bails ---")
        for s in subshell_bail_samples:
            print(f"  {s[:160]}")
        print()
    if v2_win_samples["subshell_unwrap"]:
        print("--- sample $(...) commands v2 would approve ---")
        for s in v2_win_samples["subshell_unwrap"]:
            print(f"  {s[:160]}")
        print()
    if redirect_bail_samples:
        print("--- sample redirect bails ---")
        for s in redirect_bail_samples:
            print(f"  {s[:160]}")
        print()
    if v2_win_samples["cwd_redirect"]:
        print("--- sample redirect commands v2 would approve ---")
        for s in v2_win_samples["cwd_redirect"]:
            print(f"  {s[:160]}")


if __name__ == "__main__":
    main()
