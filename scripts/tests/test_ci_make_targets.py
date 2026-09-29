"""Guard: every `make <target>` used in CI must exist in the Makefile and do real work.

A missing target fails `make` loudly, but a target with no recipe (for example a phony
target that a `%` pattern rule cannot reach) "succeeds" with "Nothing to be done". A
dry run (`make -n`) prints the commands that would run, so empty output means the target
is vacuous.
"""

import itertools
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CI_FILE = ROOT / ".github" / "workflows" / "ci.yml"
MAKE_INVOCATION = re.compile(r"\bmake\s+([^\n;&|]+)")
MAKE_STATUS_LINE = re.compile(r"^make(\[\d+\])?:")
MATRIX_REF = re.compile(r"\$\{\{\s*matrix\.(\w+)\s*\}\}")


def matrix_combinations(job: dict) -> list[dict[str, str]]:
    matrix = job.get("strategy", {}).get("matrix", {})
    keys = list(matrix)
    return [dict(zip(keys, values, strict=True)) for values in itertools.product(*matrix.values())]


def make_targets_in_ci(ci_file: Path) -> set[str]:
    workflow = yaml.safe_load(ci_file.read_text(encoding="utf-8"))
    targets: set[str] = set()
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            for command in MAKE_INVOCATION.findall(step.get("run", "")):
                for combo in matrix_combinations(job) or [{}]:
                    expanded = MATRIX_REF.sub(lambda m, c=combo: c[m.group(1)], command)
                    targets.update(t for t in expanded.split() if not t.startswith("-"))
    return targets


def dry_run(target: str, makefile: Path) -> subprocess.CompletedProcess[str]:
    # Drop inherited make state so the result is the same under `make test-scripts`.
    env = {k: v for k, v in os.environ.items() if k not in {"MAKEFLAGS", "MAKELEVEL", "MFLAGS"}}
    return subprocess.run(
        ["make", "-n", "-f", str(makefile), "-C", str(makefile.parent), target],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def commands_in(dry_run_output: str) -> list[str]:
    """Drop make's own status lines ("make: Nothing to be done for ...")."""
    lines = (line.strip() for line in dry_run_output.splitlines())
    return [line for line in lines if line and not MAKE_STATUS_LINE.match(line)]


def check_targets(targets: set[str], makefile: Path) -> list[str]:
    """Return one problem description per target that is missing or vacuous."""
    problems = []
    for target in sorted(targets):
        result = dry_run(target, makefile)
        if result.returncode != 0:
            problems.append(f"{target}: not runnable ({result.stderr.strip()})")
        elif not commands_in(result.stdout):
            problems.append(f"{target}: no commands would run ({result.stdout.strip()!r})")
    return problems


pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")


def test_ci_finds_make_targets() -> None:
    targets = make_targets_in_ci(CI_FILE)

    assert {"lint-core", "typecheck-speech", "test-core"} <= targets


def test_every_ci_make_target_runs_real_commands() -> None:
    assert check_targets(make_targets_in_ci(CI_FILE), ROOT / "Makefile") == []


def test_fails_when_target_is_removed_from_makefile(tmp_path: Path) -> None:
    original = (ROOT / "Makefile").read_text(encoding="utf-8")
    broken = tmp_path / "Makefile"
    broken.write_text(original.replace("test-core:", "renamed-test-core:"), encoding="utf-8")

    problems = check_targets(make_targets_in_ci(CI_FILE), broken)

    assert any(p.startswith("test-core:") for p in problems)


def test_fails_when_target_is_vacuous(tmp_path: Path) -> None:
    makefile = tmp_path / "Makefile"
    makefile.write_text(".PHONY: empty\nempty:\n", encoding="utf-8")

    assert check_targets({"empty"}, makefile) != []
