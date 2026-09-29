"""Reject Vietnamese characters in Python files.

Learner-facing Vietnamese copy lives only in apps/web/messages/vi.json. Files under
tests/fixtures are exempt because fixtures may need real Vietnamese text.

Usage: check_no_vietnamese.py PATH [PATH ...]  (files or directories)
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path

# Letters that occur in Vietnamese but not in English, as inclusive code point ranges:
# Latin-1 accented vowels, the breve/horn letters, d-with-stroke, and the Latin Extended
# Additional block. Written as numbers so this file itself contains no such characters.
VIETNAMESE_RANGES = (
    (0x00C0, 0x00C3),
    (0x00C8, 0x00CA),
    (0x00CC, 0x00CD),
    (0x00D2, 0x00D5),
    (0x00D9, 0x00DA),
    (0x00DD, 0x00DD),
    (0x00E0, 0x00E3),
    (0x00E8, 0x00EA),
    (0x00EC, 0x00ED),
    (0x00F2, 0x00F5),
    (0x00F9, 0x00FA),
    (0x00FD, 0x00FD),
    (0x0102, 0x0103),
    (0x0110, 0x0111),
    (0x0128, 0x0129),
    (0x0168, 0x0169),
    (0x01A0, 0x01A1),
    (0x01AF, 0x01B0),
    (0x1EA0, 0x1EF9),
)
VIETNAMESE_CHARS = re.compile(
    "[" + "".join(f"{chr(lo)}-{chr(hi)}" for lo, hi in VIETNAMESE_RANGES) + "]"
)
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__"}


def is_exempt(path: Path) -> bool:
    """Return True for files under a tests/fixtures directory."""
    parts = path.parts
    return any(a == "tests" and b == "fixtures" for a, b in pairwise(parts))


def iter_python_files(paths: list[Path]) -> Iterator[Path]:
    for path in paths:
        if path.is_dir():
            for child in sorted(path.rglob("*.py")):
                if not SKIP_DIRS.intersection(child.parts):
                    yield child
        elif path.suffix == ".py":
            yield path


def find_violations(path: Path) -> list[tuple[int, str]]:
    """Return (line number, line text) for each line holding Vietnamese characters."""
    text = path.read_text(encoding="utf-8")
    return [
        (number, line.strip())
        for number, line in enumerate(text.splitlines(), start=1)
        if VIETNAMESE_CHARS.search(line)
    ]


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    failed = False
    checked = 0
    for path in iter_python_files([Path(arg) for arg in argv]):
        if is_exempt(path):
            continue
        checked += 1
        for number, line in find_violations(path):
            print(f"{path}:{number}: Vietnamese text in .py file: {line}")
            failed = True
    if failed:
        print("Move learner-facing copy to apps/web/messages/vi.json.")
    else:
        print(f"OK: no Vietnamese text in {checked} Python files.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
