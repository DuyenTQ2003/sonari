"""`scripts/locked_pins.py`: the versions `make test-scripts` installs come from the core lock.

The drift tests import the content models, so `test-scripts` needs pydantic and beanie. Left
unpinned, a release upstream could turn CI red with no change in this repo. The versions are
read from `services/core/uv.lock` at run time instead of copied into the Makefile, so there is
one place that says which version, and a pin cannot go stale.
"""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "locked_pins.py"
LOCK = ROOT / "services" / "core" / "uv.lock"

SAMPLE = """\
version = 1
requires-python = "==3.11.*"

[[package]]
name = "app"
version = "0.1.0"
source = { virtual = "." }
dependencies = [{ name = "top" }]

[[package]]
name = "top"
version = "2.0.0"
dependencies = [{ name = "middle" }, { name = "shared" }]

[[package]]
name = "middle"
version = "1.5.0"
dependencies = [{ name = "shared" }]

[[package]]
name = "shared"
version = "0.3.1"

[[package]]
name = "unrelated"
version = "9.9.9"
"""


def run(*args: str, lock: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), *args]
    if lock is not None:
        command += ["--lock", str(lock)]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def sample_lock(tmp_path: Path, text: str = SAMPLE) -> Path:
    path = tmp_path / "uv.lock"
    path.write_text(text, encoding="utf-8")
    return path


def test_it_pins_a_package_and_everything_it_pulls_in(tmp_path: Path) -> None:
    result = run("top", lock=sample_lock(tmp_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == [
        "--with", "middle==1.5.0", "--with", "shared==0.3.1", "--with", "top==2.0.0",
    ]  # fmt: skip


def test_a_package_nothing_asked_for_is_not_pinned(tmp_path: Path) -> None:
    stdout = run("top", lock=sample_lock(tmp_path)).stdout

    assert "top==2.0.0" in stdout
    assert "unrelated" not in stdout


def test_a_package_missing_from_the_lock_fails_instead_of_going_unpinned(tmp_path: Path) -> None:
    result = run("top", "ghost", lock=sample_lock(tmp_path))

    assert result.returncode != 0
    assert "ghost" in result.stderr
    assert result.stdout == ""


def test_a_lock_format_it_does_not_know_fails(tmp_path: Path) -> None:
    unknown_format = SAMPLE.replace("version = 1\n", "version = 2\n", 1)

    result = run("top", lock=sample_lock(tmp_path, unknown_format))

    assert result.returncode != 0
    assert "version" in result.stderr


def test_a_dependency_with_a_marker_fails_instead_of_being_guessed(tmp_path: Path) -> None:
    plain = '{ name = "shared" }]\n\n[[package]]\nname = "middle"'
    under_a_marker = plain.replace('"shared" }', '"shared", marker = "sys_platform == \'win32\'" }')
    marked = SAMPLE.replace(plain, under_a_marker)
    assert marked != SAMPLE  # the replacement found its place

    result = run("top", lock=sample_lock(tmp_path, marked))

    assert result.returncode != 0
    assert "marker" in result.stderr


def test_it_reads_the_real_core_lock() -> None:
    locked = {p["name"]: p["version"] for p in tomllib.loads(LOCK.read_text())["package"]}

    result = run("pydantic", "beanie")

    assert result.returncode == 0, result.stderr
    pins = result.stdout.split()[1::2]
    assert {"pydantic", "beanie", "pydantic-core", "pymongo"} <= {p.split("==")[0] for p in pins}
    assert all(pin == f"{pin.split('==')[0]}=={locked[pin.split('==')[0]]}" for pin in pins)


def test_make_test_scripts_installs_the_models_only_through_the_pins() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    recipe = re.search(r"^test-scripts:\n((?:\t.*\n)+)", makefile, re.MULTILINE)

    assert recipe is not None
    assert "locked_pins.py pydantic beanie" in recipe.group(1)
    assert not re.search(r"--with (pydantic|beanie)\b", recipe.group(1))  # never unpinned
