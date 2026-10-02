"""Shared kernel: infrastructure every bounded context may use, and nothing else.

Nothing in here may import a bounded context. The import contract in pyproject.toml
(`lint-imports`) enforces that, so a context can never reach another one through here.
"""
