"""The content bounded context (ADR-0001).

Owns: Level, Unit, Lesson, Exercise, Learnable and Source.

It may import `sonari_core.shared` and nothing from another context; the import contract
in pyproject.toml enforces that. Other contexts reach it through events.
"""

from sonari_core.shared.contexts import Context, ContextSpec

SPEC = ContextSpec(Context.CONTENT)
