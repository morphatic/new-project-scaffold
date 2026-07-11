#!/usr/bin/env python3
"""
tdd-guard.py — Claude Code PreToolUse hook on Write|Edit.

Blocks edits that introduce test-skip/disable patterns in test files, or that
empty out a test file entirely. The test-driven workflow requires fixing
source code to make tests pass — not disabling tests to dodge the fix.

Scope:
  - Applies only to files whose path looks like a test file (see
    TEST_PATH_PATTERNS). Source-file edits are not inspected.
  - Detects skip/disable annotations *added* by the edit (not pre-existing).
  - Detects Write operations that replace an existing test file with empty
    content.

Escape hatch:
  Include the literal marker `tdd-guard: allow-skip` anywhere in the added
  content (as a comment). The hook treats this as explicit intent and allows
  the edit. The marker is auditable in git history.

Exit codes / output:
  - Allow / pass-through: exit 0, no output.
  - Block: exit 0 with PreToolUse deny JSON on stdout.

Debug log: set env TDD_GUARD_LOG=1 to append to
           ~/.claude/hooks/tdd-guard.log
"""
from __future__ import annotations

import json
import os
import re
import sys

LOG_PATH = os.path.expanduser("~/.claude/hooks/tdd-guard.log")
LOGGING = os.environ.get("TDD_GUARD_LOG") == "1"

OVERRIDE_MARKER = "tdd-guard: allow-skip"

TEST_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p) for p in (
        r"(^|[\\/])tests?[\\/]",           # /test/ or /tests/
        r"(^|[\\/])spec[\\/]",             # /spec/
        r"(^|[\\/])__tests__[\\/]",        # /__tests__/
        r"(^|[\\/])features[\\/]",         # /features/ (cucumber/gherkin)
        r"(^|[\\/])test_[^\\/]+\.py$",     # test_foo.py
        r"_test\.py$",                     # foo_test.py
        r"\.test\.[cm]?[jt]sx?$",          # foo.test.ts, .tsx, .jsx, .mjs, .cjs
        r"\.spec\.[cm]?[jt]sx?$",          # foo.spec.ts etc.
        r"_test\.go$",                     # foo_test.go
        r"_test\.rs$",                     # foo_test.rs
        r"_spec\.rb$",                     # foo_spec.rb
        r"\.feature$",                     # foo.feature (gherkin)
    )
]

# (pattern, human-readable name). Patterns are compiled once.
_RAW_SKIP_PATTERNS: list[tuple[str, str]] = [
    (r"\.skip\s*\(",                    "test.skip(...)"),
    (r"\bxit\s*\(",                     "xit(...) [skipped jasmine test]"),
    (r"\bxdescribe\s*\(",               "xdescribe(...) [skipped jasmine suite]"),
    (r"\bfit\s*\(",                     "fit(...) [focused — causes siblings to skip]"),
    (r"\bfdescribe\s*\(",               "fdescribe(...) [focused — causes siblings to skip]"),
    (r"\.only\s*\(",                    ".only(...) [focused — causes siblings to skip]"),
    (r"@pytest\.mark\.skip\b",          "@pytest.mark.skip"),
    (r"@pytest\.mark\.skipif\b",        "@pytest.mark.skipif"),
    (r"@pytest\.mark\.xfail\b",         "@pytest.mark.xfail"),
    (r"@unittest\.skip\b",              "@unittest.skip"),
    (r"\bpytest\.skip\s*\(",            "pytest.skip(...)"),
    (r"@Ignore\b",                      "@Ignore (JUnit 4)"),
    (r"@Disabled\b",                    "@Disabled (JUnit 5)"),
    (r"#\[ignore[\]\s(=]",              "#[ignore] / #[ignore = ...] (Rust)"),
    (r"\bt\.Skip(?:Now)?\s*\(",         "t.Skip / t.SkipNow (Go)"),
    (r"(?m)^\s*@skip\b",                "@skip tag (gherkin)"),
    (r"(?m)^\s*@ignore\b",              "@ignore tag (gherkin)"),
    (r"(?m)^\s*@wip\b",                 "@wip tag (gherkin — typically skipped)"),
]

SKIP_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p), name) for p, name in _RAW_SKIP_PATTERNS
]


def log(msg: str) -> None:
    if not LOGGING:
        return
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def is_test_path(path: str) -> bool:
    norm = path.replace("\\", "/")
    return any(p.search(norm) for p in TEST_PATH_PATTERNS)


_RUST_TEST_MOD = re.compile(r"#\[cfg\(test\)\]|\bmod\s+tests?\b")


def has_rust_test_module(text: str) -> bool:
    """True if the text contains a Rust inline-test marker (#[cfg(test)] or `mod tests`)."""
    if not text:
        return False
    return _RUST_TEST_MOD.search(text) is not None


def is_rust_test_context(file_path: str, extra_text: str = "") -> bool:
    """True if a .rs file contains inline unit tests (either already on disk, or
    in the new content being written)."""
    if not file_path.lower().endswith(".rs"):
        return False
    if has_rust_test_module(read_if_exists(file_path)):
        return True
    return has_rust_test_module(extra_text)


def has_override(text: str) -> bool:
    return OVERRIDE_MARKER in (text or "")


def detect_added_skips(old_text: str, new_text: str) -> list[tuple[str, str]]:
    """Return (name, matched_snippet) for skip patterns whose count increased."""
    added: list[tuple[str, str]] = []
    old_text = old_text or ""
    new_text = new_text or ""
    for pattern, name in SKIP_PATTERNS:
        new_matches = pattern.findall(new_text)
        old_matches = pattern.findall(old_text)
        if len(new_matches) > len(old_matches):
            m = pattern.search(new_text)
            snippet = m.group(0) if m else pattern.pattern
            added.append((name, snippet))
    return added


def read_if_exists(path: str) -> str:
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def build_block_reason(file_path: str, added: list[tuple[str, str]], kind: str) -> str:
    lines = [
        f"BLOCKED by tdd-guard: test-tampering detected in `{file_path}`.",
        "",
    ]
    if kind == "empty":
        lines.append(
            "This edit empties an existing test file, removing all test coverage."
        )
    else:
        lines.append("This edit introduces skip/disable annotations:")
        for name, snippet in added:
            lines.append(f"  - {name}  (matched: `{snippet.strip()}`)")
    lines += [
        "",
        "This project follows a test-driven workflow. Tests are the specification:",
        "fix the source to make them pass. Do not disable or delete tests to",
        "avoid fixing the underlying code.",
        "",
        "What to do instead:",
        "  1. If the test is failing from a real bug, fix the SOURCE.",
        "  2. If the test encodes outdated behavior, ASK THE USER before changing it.",
        "  3. If the skip is genuinely intentional (flaky, slow, external-dep gated),",
        "     ask the user to approve explicitly. Once approved, include the marker",
        "     `tdd-guard: allow-skip` as a comment in the edit along with a stated",
        "     REASON. The marker is audited in git history.",
        "",
        "Do NOT retry this edit without the user's explicit approval.",
    ]
    return "\n".join(lines)


def emit_deny(reason: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(payload))
    sys.exit(0)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        log(f"bad json: {e}")
        sys.exit(0)

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""

    if not file_path:
        sys.exit(0)

    if tool_name == "Write":
        new_content = tool_input.get("content", "") or ""
        old_content = read_if_exists(file_path)

        if not is_test_path(file_path) and not is_rust_test_context(file_path, new_content):
            sys.exit(0)

        if old_content and new_content.strip() == "":
            reason = build_block_reason(file_path, [], kind="empty")
            log(f"BLOCK empty Write: {file_path}")
            emit_deny(reason)

        if has_override(new_content):
            log(f"ALLOW (override marker): {file_path}")
            sys.exit(0)

        added = detect_added_skips(old_content, new_content)
        if added:
            reason = build_block_reason(file_path, added, kind="skip")
            log(f"BLOCK Write skip in {file_path}: {[n for n,_ in added]}")
            emit_deny(reason)

    elif tool_name == "Edit":
        old_string = tool_input.get("old_string", "") or ""
        new_string = tool_input.get("new_string", "") or ""

        if not is_test_path(file_path) and not is_rust_test_context(file_path, new_string):
            sys.exit(0)

        if has_override(new_string):
            log(f"ALLOW (override marker): {file_path}")
            sys.exit(0)

        added = detect_added_skips(old_string, new_string)
        if added:
            reason = build_block_reason(file_path, added, kind="skip")
            log(f"BLOCK Edit skip in {file_path}: {[n for n,_ in added]}")
            emit_deny(reason)

    sys.exit(0)


if __name__ == "__main__":
    main()
