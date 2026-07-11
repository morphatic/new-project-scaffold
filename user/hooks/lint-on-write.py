#!/usr/bin/env python3
"""
lint-on-write.py — Claude Code PostToolUse hook for Write and Edit.

After a file is written or edited, runs cspell on text files and
markdownlint on markdown files when the repo carries the relevant
config (`cspell.json` / `.markdownlint.json`). Findings are surfaced
back to the assistant via additionalContext; this hook NEVER blocks.

Requires `cspell` and `markdownlint` on PATH (installed globally via
pnpm per Morgan's toolchain).

Debug log: set env LINT_ON_WRITE_LOG=1 to append to
           ~/.claude/hooks/lint-on-write.log
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

LOG_PATH = os.path.expanduser("~/.claude/hooks/lint-on-write.log")
LOGGING = os.environ.get("LINT_ON_WRITE_LOG") == "1"

TIMEOUT_SEC = 15
MAX_OUTPUT_CHARS = 2000


def log(msg: str) -> None:
    if not LOGGING:
        return
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def find_git_root(start: str) -> str | None:
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def run_linter(cmd: list[str], cwd: str) -> tuple[int, str]:
    """Run a linter, returning (exitcode, combined output). -1 on failure."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
            shell=False,
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, combined
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        log(f"linter run failed for {cmd[0]}: {e}")
        return -1, ""


def truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n...(truncated)"


def maybe_run_cspell(file_path: str, repo_root: str) -> str | None:
    if not os.path.exists(os.path.join(repo_root, "cspell.json")):
        return None
    exe = shutil.which("cspell")
    if not exe:
        log("cspell not on PATH")
        return None
    rel = os.path.relpath(file_path, repo_root)
    code, out = run_linter([exe, "--no-progress", "--no-summary", rel], repo_root)
    if code <= 0:
        return None
    text = out.strip()
    return truncate(text) if text else None


def maybe_run_markdownlint(file_path: str, repo_root: str) -> str | None:
    if not file_path.lower().endswith(".md"):
        return None
    if not os.path.exists(os.path.join(repo_root, ".markdownlint.json")):
        return None
    exe = shutil.which("markdownlint")
    if not exe:
        log("markdownlint not on PATH")
        return None
    rel = os.path.relpath(file_path, repo_root)
    code, out = run_linter([exe, rel], repo_root)
    if code <= 0:
        return None
    text = out.strip()
    return truncate(text) if text else None


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        log(f"bad json: {e}")
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not file_path or not os.path.exists(file_path):
        sys.exit(0)

    repo_root = find_git_root(os.path.dirname(file_path))
    if not repo_root:
        sys.exit(0)

    findings: list[str] = []

    md = maybe_run_markdownlint(file_path, repo_root)
    if md:
        findings.append(
            f"markdownlint findings in {os.path.relpath(file_path, repo_root)}:\n{md}"
        )

    cs = maybe_run_cspell(file_path, repo_root)
    if cs:
        findings.append(
            f"cspell findings in {os.path.relpath(file_path, repo_root)}:\n{cs}"
        )

    if not findings:
        sys.exit(0)

    context = "\n\n".join(findings)
    log(f"surfacing findings for {file_path}: {len(context)} chars")
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }
    print(json.dumps(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
