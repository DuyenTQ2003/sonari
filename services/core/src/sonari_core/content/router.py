"""HTTP surface of the content context: GET /v1/speaking-items (read-only).

Not imported by `content/__init__`: that package is also imported by scripts that have no FastAPI.
`app.py` includes this router.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sonari_core.content.speaking import SpeakingItem
from sonari_core.shared.errors import ErrorEnvelope

router = APIRouter(prefix="/v1/speaking-items", tags=["content"])


class ItemOut(BaseModel):
    """What a client needs to show a sentence and to score a recording of it."""

    id: str
    text: str  # also the `referenceText` of POST /v1/score on the speech service
    unit: str


class ItemsOut(BaseModel):
    items: list[ItemOut]


async def load_items() -> list[ItemOut]:
    """Every stored item, ordered by id, which is its Source, line and offset (a dependency, so
    the route can be tested without a database)."""
    documents = await SpeakingItem.find_all().sort("_id").to_list()
    return [ItemOut(id=d.id, text=d.text, unit=d.unit) for d in documents]


@router.get("", response_model=ItemsOut, responses={500: {"model": ErrorEnvelope}})
async def speaking_items(items: Annotated[list[ItemOut], Depends(load_items)]) -> ItemsOut:
    return ItemsOut(items=items)
