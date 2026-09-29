import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check_no_vietnamese.py"
# Built from code points so this test file itself contains no Vietnamese characters.
VIETNAMESE_GREETING = "Xin ch" + chr(0xE0) + "o"


def run_check(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, paths)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_catches_xin_chao_in_py_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(f'GREETING = "{VIETNAMESE_GREETING}"\n', encoding="utf-8")

    result = run_check(bad)

    assert result.returncode == 1
    assert "bad.py:1" in result.stdout


def test_catches_stroked_d(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(f'x = "{chr(0x111)}i"\n', encoding="utf-8")

    assert run_check(bad).returncode == 1


def test_allows_english(tmp_path: Path) -> None:
    good = tmp_path / "good.py"
    good.write_text('GREETING = "Hello, world"\n', encoding="utf-8")

    assert run_check(good).returncode == 0


def test_allows_tests_fixtures(tmp_path: Path) -> None:
    fixture = tmp_path / "tests" / "fixtures" / "sample.py"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(f'GREETING = "{VIETNAMESE_GREETING}"\n', encoding="utf-8")

    assert run_check(fixture).returncode == 0


def test_scans_directories_recursively(tmp_path: Path) -> None:
    nested = tmp_path / "pkg" / "mod.py"
    nested.parent.mkdir()
    nested.write_text(f'GREETING = "{VIETNAMESE_GREETING}"\n', encoding="utf-8")

    assert run_check(tmp_path).returncode == 1
