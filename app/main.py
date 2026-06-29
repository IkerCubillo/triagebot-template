import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Column
from sqlmodel import Field, JSON, Session, SQLModel, create_engine, select

from app.models import ALLOWED_PRIORITIES, ALLOWED_STATUSES

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///triagebot.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Ticket(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str
    category: str
    priority: str
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: str = "open"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="TriageBot", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tickets")
def list_tickets(
    category: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
) -> list[Ticket]:
    with Session(engine) as session:
        stmt = select(Ticket)
        if category:
            stmt = stmt.where(Ticket.category == category)
        if priority:
            stmt = stmt.where(Ticket.priority == priority)
        if status:
            stmt = stmt.where(Ticket.status == status)
        stmt = stmt.order_by(Ticket.created_at.desc())
        return session.exec(stmt).all()


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int) -> Ticket:
    with Session(engine) as session:
        ticket = session.get(Ticket, ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return ticket


@app.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: int, update: TicketUpdate) -> Ticket:
    if update.status is not None and update.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {update.status}")
    if update.priority is not None and update.priority not in ALLOWED_PRIORITIES:
        raise HTTPException(status_code=422, detail=f"Invalid priority: {update.priority}")

    with Session(engine) as session:
        ticket = session.get(Ticket, ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")
        if update.status is not None:
            ticket.status = update.status
        if update.priority is not None:
            ticket.priority = update.priority
        ticket.updated_at = datetime.now(timezone.utc)
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        return ticket


# TODO: implementar durante el bootcamp.
# Endpoints pendientes:
# - POST /tickets
# - GET /
