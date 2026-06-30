from datetime import UTC, datetime
import os

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import JSON, Column
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

ALLOWED_CATEGORIES = set(os.environ.get("ALLOWED_CATEGORIES", "bug,feature_request,question,urgent").split(","))
ALLOWED_PRIORITIES = set(os.environ.get("ALLOWED_PRIORITIES", "P1,P2,P3").split(","))
ALLOWED_STATUSES = set(os.environ.get("ALLOWED_STATUSES", "open,in_progress,closed").split(","))


class Ticket(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    title: str
    description: str
    category: str
    priority: str
    tags: list[str] = SQLField(default=[], sa_column=Column(JSON))
    status: str = "open"
    created_at: datetime = SQLField(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = SQLField(default_factory=lambda: datetime.now(UTC))


class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)

    @field_validator("title", "description", mode="before")
    @classmethod
    def strip_and_reject_blank(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
        return v


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    category: str
    priority: str
    tags: list[str]
    status: str
    created_at: datetime
    updated_at: datetime
