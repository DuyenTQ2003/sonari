"""The identity bounded context (ADR-0001).

Owns: accounts, sessions and refresh-token families.

It may import `sonari_core.shared` and nothing from another context; the import contract
in pyproject.toml enforces that. Other contexts reach it through events.
"""

from sonari_core.identity.models import RefreshTokenDocument, User
from sonari_core.identity.router import router
from sonari_core.shared.contexts import Context, ContextSpec

SPEC = ContextSpec(Context.IDENTITY, document_models=[User, RefreshTokenDocument])

__all__ = ["SPEC", "router"]
