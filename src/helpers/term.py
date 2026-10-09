"""Terminal styling for CLI output: ANSI codes + tiny formatting helpers."""
import os
import sys

_ON = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

BOLD = "\033[1m" if _ON else ""
DIM = "\033[2m" if _ON else ""
RESET = "\033[0m" if _ON else ""
GREEN = "\033[32m" if _ON else ""
RED = "\033[31m" if _ON else ""
YELLOW = "\033[33m" if _ON else ""
CYAN = "\033[36m" if _ON else ""


def badge(passed) -> str:
    """A colored PASS/FAIL marker."""
    return f"{GREEN}{BOLD}PASS{RESET}" if passed else f"{RED}{BOLD}FAIL{RESET}"
