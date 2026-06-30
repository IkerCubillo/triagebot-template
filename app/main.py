import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError
from sqlmodel import Session, select

import app.classifier as classifier
from app.db import get_engine, get_session, init_db
from app.models import ALLOWED_PRIORITIES, ALLOWED_STATUSES, Ticket, TicketCreate, TicketResponse

load_dotenv()


class TicketUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None


def _seed_from_file(session: Session) -> None:
    existing = session.exec(select(Ticket).limit(1)).first()
    if existing is not None:
        return

    seed_path = Path(__file__).parent.parent / "seed_tickets.json"
    if not seed_path.exists():
        return

    with seed_path.open() as f:
        items = json.load(f)

    for item in items:
        try:
            body = TicketCreate(title=item["title"], description=item["description"])
        except Exception:
            continue
        try:
            cls = classifier.classify_ticket(body.title, body.description)
        except Exception:
            cls = classifier.FALLBACK_CLASSIFICATION
        created_at = datetime.fromisoformat(item["created_at"])
        ticket = Ticket(
            title=body.title,
            description=body.description,
            category=cls["category"],
            priority=cls["priority"],
            tags=cls["tags"],
            created_at=created_at,
            updated_at=created_at,
        )
        session.add(ticket)

    session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(get_engine()) as session:
        _seed_from_file(session)
    yield


app = FastAPI(title="TriageBot", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


@app.get("/")
def index(request: Request, session: Session = Depends(get_session)):
    tickets = _query_tickets(session)
    return templates.TemplateResponse("index.html", {"request": request, "tickets": tickets})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _create_ticket(body: TicketCreate, session: Session) -> Ticket:
    try:
        cls = classifier.classify_ticket(body.title, body.description)
    except Exception:
        cls = classifier.FALLBACK_CLASSIFICATION

    ticket = Ticket(
        title=body.title,
        description=body.description,
        category=cls["category"],
        priority=cls["priority"],
        tags=cls["tags"],
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


@app.post("/tickets", status_code=201, response_model=TicketResponse)
def create_ticket(body: TicketCreate, session: Session = Depends(get_session)):
    ticket = _create_ticket(body, session)
    return TicketResponse.model_validate(ticket)


@app.post("/tickets/form")
def create_ticket_form(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    session: Session = Depends(get_session),
):
    try:
        body = TicketCreate(title=title, description=description)
    except ValidationError:
        tickets = _query_tickets(session)
        return templates.TemplateResponse(
            "_tickets_table.html",
            {
                "request": request,
                "tickets": tickets,
                "error": "No se ha podido crear el ticket. Revisa el título y la descripción.",
            },
        )

    _create_ticket(body, session)
    tickets = _query_tickets(session)
    return templates.TemplateResponse(
        "_tickets_table.html", {"request": request, "tickets": tickets}
    )


def _query_tickets(
    session: Session,
    category: str | None = None,
    priority: str | None = None,
    status: str | None = None,
) -> list[Ticket]:
    query = select(Ticket)
    if category is not None:
        query = query.where(Ticket.category == category)
    if priority is not None:
        query = query.where(Ticket.priority == priority)
    if status is not None:
        query = query.where(Ticket.status == status)
    query = query.order_by(Ticket.created_at.desc())
    return session.exec(query).all()


@app.get("/tickets", response_model=list[TicketResponse])
def list_tickets(
    category: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
):
    tickets = _query_tickets(session, category, priority, status)
    return [TicketResponse.model_validate(t) for t in tickets]


@app.get("/tickets/table")
def tickets_table(
    request: Request,
    category: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
):
    tickets = _query_tickets(session, category or None, priority or None, status or None)
    return templates.TemplateResponse(
        "_tickets_table.html", {"request": request, "tickets": tickets}
    )


@app.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: int, session: Session = Depends(get_session)):
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return TicketResponse.model_validate(ticket)


@app.patch("/tickets/{ticket_id}", response_model=TicketResponse)
def update_ticket(ticket_id: int, body: TicketUpdate, session: Session = Depends(get_session)):
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if body.status is not None:
        if body.status not in ALLOWED_STATUSES:
            raise HTTPException(status_code=422, detail=f"Invalid status: {body.status}")
        ticket.status = body.status

    if body.priority is not None:
        if body.priority not in ALLOWED_PRIORITIES:
            raise HTTPException(status_code=422, detail=f"Invalid priority: {body.priority}")
        ticket.priority = body.priority

    ticket.updated_at = datetime.now(UTC)
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return TicketResponse.model_validate(ticket)
