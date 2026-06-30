from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import JSON, Column
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

ALLOWED_CATEGORIES = {"bug", "feature_request", "question", "urgent"}
ALLOWED_PRIORITIES = {"P1", "P2", "P3"}
ALLOWED_STATUSES = {"open", "in_progress", "closed"}

PRIORITY_DEADLINE_DAYS = {"P1": 0, "P2": 1, "P3": 2}


def compute_deadline(priority: str, from_dt: datetime) -> datetime:
    """Fin del día (23:59:59 UTC) del día de `from_dt` + offset según prioridad."""
    days = PRIORITY_DEADLINE_DAYS[priority]
    target_day = from_dt + timedelta(days=days)
    return target_day.replace(hour=23, minute=59, second=59, microsecond=0)


class Ticket(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    title: str
    description: str
    category: str
    priority: str
    tags: list[str] = SQLField(default=[], sa_column=Column(JSON))
    status: str = "open"
    deadline: datetime
    created_at: datetime = SQLField(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = SQLField(default_factory=lambda: datetime.now(UTC))


class Technician(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    name: str
    email: str | None = SQLField(default=None)
    created_at: datetime = SQLField(default_factory=lambda: datetime.now(UTC))


class TicketTechnician(SQLModel, table=True):
    ticket_id: int = SQLField(foreign_key="ticket.id", primary_key=True)
    technician_id: int = SQLField(foreign_key="technician.id", primary_key=True)


class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    technician_ids: list[int] = Field(default_factory=list)

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
    deadline: datetime
    created_at: datetime
    updated_at: datetime
    technician_ids: list[int] = []


class TechnicianCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str | None = None


class TechnicianResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str | None
    created_at: datetime


class TicketStats(BaseModel):
    by_category: dict[str, int]
    by_priority: dict[str, int]
    by_status: dict[str, int]
