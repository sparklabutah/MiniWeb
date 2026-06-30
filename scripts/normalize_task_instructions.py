#!/usr/bin/env python3
"""Normalize login instructions in generated tasks.

Tasks with authenticate_by_form or login_by_form macros: keep login instruction,
add requires_login=true flag.

All other tasks: strip "Log in as..." / "Sign in as..." prefix from instruction
since auto-login handles it.
"""

import json
import re
import sys
from pathlib import Path

VALIDATED_DIR = Path(__file__).resolve().parent.parent / "annotation" / "validated"
AUTH_MACROS = {"authenticate_by_form", "login_by_form"}

# Patterns to strip from instructions (case-insensitive, greedy up to period/then)
LOGIN_PATTERNS = [
    # "Log in as 'james_smith' (password: 'secure111'). Navigate to..."
    r"(?:Log|Sign)\s+in\s+(?:to\s+\w+\s+)?as\s+['\"]?\w+['\"]?\s*\(password:\s*['\"][^'\"]+['\"]\)\s*[.,;]\s*",
    # "Log in with username 'X' and password 'Y'. ..."
    r"(?:Log|Sign)\s+in\s+with\s+username\s+['\"]?\w+['\"]?\s+and\s+password\s+['\"][^'\"]+['\"]\s*[.,;]\s*",
    # "Log in as 'X' with password 'Y'. ..."
    r"(?:Log|Sign)\s+in\s+as\s+['\"]?\w+['\"]?\s+with\s+password\s+['\"][^'\"]+['\"]\s*[.,;]\s*",
    # "Log in using credentials: username='X', password='Y'. ..."
    r"(?:Log|Sign)\s+in\s+using\s+credentials[^.]*\.\s*",
    # "Log in to the ... site as 'X' (password: 'Y'). ..."
    r"(?:Log|Sign)\s+in\s+to\s+the\s+[^.]*?as\s+['\"]?\w+['\"]?\s*\(password:\s*['\"][^'\"]+['\"]\)\s*[.,;]\s*",
    # "First, log in as 'X' (password: 'Y'). ..."
    r"(?:First,?\s+)?(?:Log|Sign)\s+in\s+as\s+['\"]?\w+['\"]?[^.]*?\.\s*",
    # "Login as X. ..." or "Log in. ..." (short forms)
    r"(?:Log\s*in|Login|Sign\s*in)\s+as\s+['\"]?\w+['\"]?\s*[.,;]\s*",
    # "On the X site, log in as ... and ..."
    r"On\s+the\s+.*?,?\s*(?:log|sign)\s+in\s+.*?\(password:.*?\)\s+and\s+",
    # "On the X site, log in as..."
    r"On\s+the\s+\w[\w\s-]*?site,?\s+(?:log|sign)\s+in\s+[^.]*?\.\s*",
    # "Log in to <SiteName> as X (password: Y)." — catches quoted and unquoted passwords
    r"(?:Log|Sign)\s+in\s+to\s+.*?\(password:.*?\)\.\s*",
    # "Log in to <SiteName> as X (password: Y) and ..." — inline continuation
    r"(?:Log|Sign)\s+in\s+to\s+.*?\(password:.*?\)\s+and\s+",
]


def strip_login(instruction):
    """Remove login instruction prefix. Returns cleaned instruction."""
    result = instruction
    for pattern in LOGIN_PATTERNS:
        result = re.sub(pattern, "", result, count=1, flags=re.IGNORECASE)
    # Clean up leading whitespace and "Then, " / "Next, " artifacts
    result = re.sub(r"^\s*(?:Then,?\s+|Next,?\s+|After that,?\s+|Now,?\s+)", "", result, flags=re.IGNORECASE)
    # Capitalize first letter
    if result and result[0].islower():
        result = result[0].upper() + result[1:]
    return result.strip()


def main():
    if not VALIDATED_DIR.exists():
        print("No validated directory found.", file=sys.stderr)
        sys.exit(1)

    total = 0
    stripped = 0
    flagged_auth = 0

    for task_file in sorted(VALIDATED_DIR.glob("*.json")):
        tasks = json.loads(task_file.read_text())
        modified = False

        for task in tasks:
            total += 1
            macros = set(task.get("macros", []))
            instruction = task.get("instruction", "")
            has_auth_macro = bool(macros & AUTH_MACROS)

            if has_auth_macro:
                # Keep login instruction, add flag
                task["requires_login"] = True
                flagged_auth += 1
                modified = True
            else:
                # Strip login prefix if present
                cleaned = strip_login(instruction)
                if cleaned != instruction:
                    task["instruction"] = cleaned
                    task["requires_login"] = False
                    stripped += 1
                    modified = True
                else:
                    task["requires_login"] = False

        if modified:
            task_file.write_text(json.dumps(tasks, indent=2))

    print(f"Processed {total} tasks across {len(list(VALIDATED_DIR.glob('*.json')))} sites")
    print(f"  {flagged_auth} tasks flagged requires_login=true (have auth macro)")
    print(f"  {stripped} tasks had login instructions stripped")
    print(f"  {total - flagged_auth - stripped} tasks unchanged")


if __name__ == "__main__":
    main()
