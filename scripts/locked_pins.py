"""Print `--with name==version` for packages and what they pull in, as the core lock pins them.

    python scripts/locked_pins.py pydantic beanie [--lock services/core/uv.lock]

`make test-scripts` installs the content models for the ADR-0008 drift tests. Left unpinned, a
release upstream could turn CI red with no change in this repo, and a version copied into the
Makefile would go stale the day the service's lock moves. The lock is the one place that says which
version, so it is read here at run time. Exit status 0 and one line on stdout, or 1 and a reason on
stderr: a package that cannot be pinned (missing from the lock, a lock format this script does not
read, a dependency under a marker, which would need evaluating) must stop the run, because an
unpinned package is exactly what this exists to prevent.
"""

import argparse
import sys
import tomllib
from pathlib import Path
from typing import Any

DEFAULT_LOCK = Path(__file__).resolve().parents[1] / "services" / "core" / "uv.lock"
LOCK_FORMAT = 1


class Unpinnable(Exception):
    """A package in the closure cannot be pinned from the lock."""


def locked_pins(lock: dict[str, Any], roots: list[str]) -> list[str]:
    """`name==version` of each root and of every package it depends on, sorted by name."""
    if lock.get("version") != LOCK_FORMAT:
        raise Unpinnable(f"uv.lock format version {lock.get('version')!r} is not {LOCK_FORMAT}")
    packages = {package["name"]: package for package in lock["package"]}
    pins: dict[str, str] = {}
    todo = list(roots)
    while todo:
        name = todo.pop()
        if name in pins:
            continue
        if name not in packages:
            raise Unpinnable(f"{name} is not in the lock")
        pins[name] = packages[name]["version"]
        for dependency in packages[name].get("dependencies", []):
            if "marker" in dependency:
                raise Unpinnable(
                    f"{name} depends on {dependency['name']} only under a marker "
                    f"({dependency['marker']}): teach this script to evaluate it, or pin it by hand"
                )
            todo.append(dependency["name"])
    return [f"{name}=={version}" for name, version in sorted(pins.items())]


def main() -> int:
    parser = argparse.ArgumentParser(description="Pin packages to the core service's lock.")
    parser.add_argument("packages", nargs="+", help="packages to pin, with their dependencies")
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK, help="the uv.lock to read")
    args = parser.parse_args()
    try:
        pins = locked_pins(tomllib.loads(args.lock.read_text(encoding="utf-8")), args.packages)
    except (Unpinnable, OSError, tomllib.TOMLDecodeError, KeyError) as error:
        print(f"locked_pins: {error}", file=sys.stderr)
        return 1
    print(" ".join(f"--with {pin}" for pin in pins))
    return 0


if __name__ == "__main__":
    sys.exit(main())
