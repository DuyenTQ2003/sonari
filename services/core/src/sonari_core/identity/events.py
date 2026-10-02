"""The UserRegistered event. Its shape is the JSON Schema in packages/contracts.

Hand-written until P12 generates models from the schemas; a test keeps the two in step.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

EVENT_TYPE = "UserRegistered"


class UserRegistered(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    event_id: UUID
    occurred_at: datetime
    version: Literal[1] = 1
    user_id: str

    @classmethod
    def now(cls, user_id: str, occurred_at: datetime) -> "UserRegistered":
        return cls(event_id=uuid4(), occurred_at=occurred_at, user_id=user_id)
