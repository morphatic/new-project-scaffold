#!/usr/bin/env python3
"""
gitignore-autoupdate.py — Claude Code PostToolUse hook.

After a Bash command runs, scans the current git repo for well-known
build/dep directories that aren't already covered by .gitignore and
appends them under a managed block.

Safety posture: additive only. Never removes existing entries. Silent
no-op outside a git repo. Silent no-op when nothing needs adding.

Debug log: set env GITIGNORE_AUTOUPDATE_LOG=1 to append to
           ~/.claude/hooks/gitignore-autoupdate.log
"""
from __future__ import annotations

import json
import os
import sys

LOG_PATH = os.path.expanduser("~/.claude/hooks/gitignore-autoupdate.log")
LOGGING = os.environ.get("GITIGNORE_AUTOUPDATE_LOG") == "1"

MANAGED_HEADER = "# --- added by gitignore-autoupdate ---"
MANAGED_FOOTER = "# --- end gitignore-autoupdate ---"

# Map of directory name (top-level or, for __pycache__, one level deep) to
# the pattern written into .gitignore.
SIGNATURES: dict[str, str] = {
    "node_modules": "node_modules/",
    "__pycache__": "__pycache__/",
    ".venv": ".venv/",
    "venv": "venv/",
    "target": "target/",
    "dist": "dist/",
    ".next": ".next/",
    ".nuxt": ".nuxt/",
    ".svelte-kit": ".svelte-kit/",
    ".pytest_cache": ".pytest_cache/",
    ".ruff_cache": ".ruff_cache/",
    ".mypy_cache": ".mypy_cache/",
    ".turbo": ".turbo/",
    "coverage": "coverage/",
    ".nyc_output": ".nyc_output/",
    ".parcel-cache": ".parcel-cache/",
}


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


def existing_stems(gitignore_text: str) -> set[str]:
    """Return the set of stems already present in .gitignore.

    Normalizes each non-comment line: strips negation `!`, strips leading
    `/`, `./`, and `**/`, strips trailing `/`. The resulting stem is what
    we compare signature directory names against.
    """
    out: set[str] = set()
    for ln in gitignore_text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("!"):
            s = s[1:]
        changed = True
        while changed:
            changed = False
            for prefix in ("./", "**/", "/"):
                if s.startswith(prefix):
                    s = s[len(prefix):]
                    changed = True
                    break
        s = s.rstrip("/")
        if s:
            out.add(s)
    return out


def scan_signatures(root: str) -> list[tuple[str, str]]:
    """Return (name, pattern) for signatures that exist in root."""
    found: list[tuple[str, str]] = []
    try:
        top_entries = set(os.listdir(root))
    except OSError:
        return found

    for name, pattern in SIGNATURES.items():
        if name in top_entries and os.path.isdir(os.path.join(root, name)):
            found.append((name, pattern))
            continue
        # __pycache__ commonly nests one level down (per-module).
        if name == "__pycache__":
            for entry in top_entries:
                sub = os.path.join(root, entry)
                if not os.path.isdir(sub):
                    continue
                if os.path.isdir(os.path.join(sub, "__pycache__")):
                    found.append((name, pattern))
                    break
    return found


def append_managed_block(gitignore_path: str, patterns: list[str]) -> None:
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = ""

    if MANAGED_HEADER in content and MANAGED_FOOTER in content:
        ftr = content.index(MANAGED_FOOTER)
        insertion = "\n".join(patterns) + "\n"
        new_content = content[:ftr] + insertion + content[ftr:]
    else:
        sep = "" if (not content or content.endswith("\n")) else "\n"
        block = (
            f"{sep}\n{MANAGED_HEADER}\n"
            + "\n".join(patterns)
            + f"\n{MANAGED_FOOTER}\n"
        )
        new_content = content + block

    with open(gitignore_path, "w", encoding="utf-8") as f:
        f.write(new_content)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        log(f"bad json: {e}")
        sys.exit(0)

    cwd = payload.get("cwd") or os.getcwd()
    root = find_git_root(cwd)
    if not root:
        log(f"no git root from {cwd}")
        sys.exit(0)

    gitignore_path = os.path.join(root, ".gitignore")
    existing_text = ""
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                existing_text = f.read()
        except OSError as e:
            log(f"read fail: {e}")
            sys.exit(0)

    stems = existing_stems(existing_text)
    found = scan_signatures(root)
    missing = [pattern for name, pattern in found if name not in stems]

    if not missing:
        sys.exit(0)

    try:
        append_managed_block(gitignore_path, missing)
        log(f"added to {gitignore_path}: {missing}")
    except OSError as e:
        log(f"write fail: {e}")
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
