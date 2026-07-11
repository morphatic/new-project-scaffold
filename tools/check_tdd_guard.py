#!/usr/bin/env python3
"""
check_tdd_guard.py — regression checks for user/hooks/tdd-guard.py.

Feeds PreToolUse payloads to the VERSIONED hook source (user/hooks/) via
subprocess and asserts allow vs deny. Run after any tdd-guard change:

    python3 tools/check_tdd_guard.py

Named check_* (not test_*) deliberately: the live tdd-guard hook scopes
test_*.py paths, and this file legitimately contains skip-pattern
fixtures.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "user" / "hooks" / "tdd-guard.py"


def run_hook(tool_name: str, file_path: str, **tool_input) -> bool:
    """Return True if the hook DENIES the edit."""
    payload = {
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path, **tool_input},
    }
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    if not proc.stdout.strip():
        return False
    out = json.loads(proc.stdout)
    return (
        out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    )


def edit(path: str, old: str, new: str) -> bool:
    return run_hook("Edit", path, old_string=old, new_string=new)


CASES = [
    # (description, expect_deny, callable)
    ("Rust Iterator::skip in test file is ALLOWED",
     False, lambda: edit("tests/scoring_test.rs", "", "let top = xs.iter().skip(1).take(5);")),
    ("Rust Iterator::skip_while in inline-test .rs is ALLOWED",
     False, lambda: edit("src/lib.rs", "", "mod tests { fn f() { xs.iter().skip_while(|x| *x < 2); } }")),
    ("Rust #[ignore] is still BLOCKED",
     True, lambda: edit("tests/scoring_test.rs", "", "#[ignore]\nfn test_slow() {}")),
    ("JS it.skip is still BLOCKED",
     True, lambda: edit("foo.test.ts", "", "it.skip('later', () => {})")),
    ("JS describe.only is still BLOCKED",
     True, lambda: edit("foo.test.ts", "", "describe.only('just this', () => {})")),
    ("Python model.fit(...) is ALLOWED (fit( is a JS-only idiom)",
     False, lambda: edit("tests/test_model.py", "", "model.fit(X, y)")),
    ("Python @pytest.mark.skip is still BLOCKED",
     True, lambda: edit("tests/test_model.py", "", "@pytest.mark.skip\ndef test_x(): ...")),
    ("Python bare @skip decorator is BLOCKED",
     True, lambda: edit("tests/test_model.py", "", "@skip('reason')\ndef test_x(): ...")),
    ("Go t.Skip is still BLOCKED",
     True, lambda: edit("pkg/foo_test.go", "", "t.Skip()")),
    ("Gherkin @wip tag is still BLOCKED",
     True, lambda: edit("features/x.feature", "", "@wip\nScenario: later")),
    ("Gherkin-style @skip line in Python file does not double-fire",
     True, lambda: edit("tests/test_model.py", "", "@skip\ndef test_x(): ...")),
    ("Override marker still ALLOWS",
     False, lambda: edit("foo.test.ts", "",
                         "// tdd-guard: allow-skip (flaky, tracked in #42)\nit.skip('x', () => {})")),
    ("Pre-existing skip preserved during unrelated edit is ALLOWED",
     False, lambda: edit("foo.test.ts", "it.skip('x'); a()", "it.skip('x'); b()")),
    ("Non-test source file with .skip( is out of scope, ALLOWED",
     False, lambda: edit("src/pipeline.ts", "", "rows.skip(1)")),
]


def main() -> int:
    failures = 0
    for desc, expect_deny, fn in CASES:
        denied = fn()
        ok = denied == expect_deny
        print(f"  {'PASS' if ok else 'FAIL'}  {desc} (denied={denied})")
        failures += 0 if ok else 1
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
