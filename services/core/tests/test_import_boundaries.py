"""The cross-context import check is what makes ADR-0001's "never join across contexts"
enforceable. These tests prove it fails on a bad import, and that the real contract
covers every context package.

The fixture packages under tests/fixtures/import_boundaries mirror the real layout with
`fixture_core` in place of `sonari_core`. `clean` is the control: without a passing
control, a "failure" could be a broken configuration rather than a caught import.
"""

import importlib
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from sonari_core.shared.contexts import CORE_CONTEXTS

CORE_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "import_boundaries"
LINT_IMPORTS = Path(sys.executable).with_name("lint-imports")

CONTRACTS = """
[importlinter]
root_package = fixture_core

[importlinter:contract:independence]
name = Bounded contexts never import each other
type = independence
modules =
    fixture_core.identity
    fixture_core.learning

[importlinter:contract:layers]
name = Layers
type = layers
layers =
    fixture_core.identity | fixture_core.learning
    fixture_core.shared
"""


def lint(case: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    config = tmp_path / "importlinter.ini"
    config.write_text(CONTRACTS)
    return subprocess.run(
        [str(LINT_IMPORTS), "--config", str(config), "--no-cache"],
        cwd=FIXTURES / case,
        capture_output=True,
        text=True,
        check=False,
    )


def test_clean_packages_pass_both_contracts(tmp_path: Path) -> None:
    result = lint("clean", tmp_path)

    assert result.returncode == 0, result.stdout
    assert "Contracts: 2 kept, 0 broken." in result.stdout


def test_one_context_importing_another_fails_the_check(tmp_path: Path) -> None:
    result = lint("cross_context", tmp_path)

    assert result.returncode == 1
    assert "BROKEN" in result.stdout
    assert "fixture_core.identity is not allowed to import fixture_core.learning" in result.stdout


def test_a_context_reached_through_the_shared_kernel_fails_the_check(tmp_path: Path) -> None:
    result = lint("via_shared", tmp_path)

    assert result.returncode == 1
    assert "fixture_core.shared is not allowed to import fixture_core.learning" in result.stdout


def test_dynamic_import_is_not_detected_so_review_must_catch_it(tmp_path: Path) -> None:
    """Records a known gap: only static `import` statements are analysed.

    If this ever fails, the checker has learnt to see `importlib`; update the PR notes.
    """
    result = lint("dynamic", tmp_path)

    assert result.returncode == 0


def _real_contracts() -> list[dict[str, object]]:
    config = tomllib.loads((CORE_ROOT / "pyproject.toml").read_text())
    return list(config["tool"]["importlinter"]["contracts"])


def test_real_independence_contract_lists_exactly_the_core_contexts() -> None:
    (independence,) = [c for c in _real_contracts() if c["type"] == "independence"]

    assert set(independence["modules"]) == {  # type: ignore[call-overload]
        f"sonari_core.{context.value}" for context in CORE_CONTEXTS
    }


def test_every_package_under_sonari_core_is_covered_by_the_contract() -> None:
    """A new context package that nobody added to the contract would escape the check."""
    (independence,) = [c for c in _real_contracts() if c["type"] == "independence"]
    covered = {name.removeprefix("sonari_core.") for name in independence["modules"]}  # type: ignore[attr-defined]
    packages = {
        path.name for path in (CORE_ROOT / "src" / "sonari_core").iterdir() if path.is_dir()
    } - {"__pycache__"}

    assert packages - covered == {"shared"}


@pytest.mark.parametrize("context", [context.value for context in CORE_CONTEXTS])
def test_each_context_package_exports_the_spec_of_its_own_context(context: str) -> None:
    package = importlib.import_module(f"sonari_core.{context}")

    assert package.SPEC.context.value == context
