from contextlib import asynccontextmanager
from datetime import UTC, datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError
from sqlmodel import Session, select

import app.classifier as classifier
from app.db import get_session, init_db
from app.models import (
    ALLOWED_CATEGORIES,
    ALLOWED_PRIORITIES,
    ALLOWED_STATUSES,
    Technician,
    TechnicianCreate,
    TechnicianResponse,
    Ticket,
    TicketCreate,
    TicketResponse,
    TicketStats,
    TicketTechnician,
)

load_dotenv()


class TicketUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    technician_ids: list[int] | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="TriageBot", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


# ---------------------------------------------------------------------------
# Helpers — technicians
# ---------------------------------------------------------------------------

def _get_technician_ids(session: Session, ticket_id: int) -> list[int]:
    links = session.exec(
        select(TicketTechnician).where(TicketTechnician.ticket_id == ticket_id)
    ).all()
    return [link.technician_id for link in links]


def _set_technicians(session: Session, ticket_id: int, technician_ids: list[int]) -> None:
    old = session.exec(
        select(TicketTechnician).where(TicketTechnician.ticket_id == ticket_id)
    ).all()
    for link in old:
        session.delete(link)
    for tid in technician_ids:
        session.add(TicketTechnician(ticket_id=ticket_id, technician_id=tid))
    session.commit()


def _build_ticket_technicians(session: Session, tickets: list) -> dict[int, list[str]]:
    """Returns {ticket_id: [technician_name, ...]} using two queries."""
    ids = [t.id for t in tickets if t.id is not None]
    if not ids:
        return {}
    links = session.exec(
        select(TicketTechnician).where(TicketTechnician.ticket_id.in_(ids))
    ).all()
    if not links:
        return {}
    tech_ids = list({lnk.technician_id for lnk in links})
    techs = {
        t.id: t.name
        for t in session.exec(select(Technician).where(Technician.id.in_(tech_ids))).all()
    }
    result: dict[int, list[str]] = {}
    for lnk in links:
        result.setdefault(lnk.ticket_id, []).append(techs.get(lnk.technician_id, "?"))
    return result


def _ticket_to_response(ticket: Ticket, session: Session) -> TicketResponse:
    resp = TicketResponse.model_validate(ticket)
    resp.technician_ids = _get_technician_ids(session, ticket.id)
    return resp


def _all_technicians(session: Session) -> list[Technician]:
    return session.exec(select(Technician).order_by(Technician.name)).all()


# ---------------------------------------------------------------------------
# Helpers — tickets
# ---------------------------------------------------------------------------

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

    if body.technician_ids:
        _set_technicians(session, ticket.id, body.technician_ids)

    return ticket


def _query_tickets(
    session: Session,
    category: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    technician_id: int | None = None,
) -> list[Ticket]:
    query = select(Ticket)
    if category is not None:
        query = query.where(Ticket.category == category)
    if priority is not None:
        query = query.where(Ticket.priority == priority)
    if status is not None:
        query = query.where(Ticket.status == status)
    if technician_id is not None:
        query = query.join(TicketTechnician, Ticket.id == TicketTechnician.ticket_id)
        query = query.where(TicketTechnician.technician_id == technician_id)
    query = query.order_by(Ticket.created_at.desc())
    return session.exec(query).all()


# ---------------------------------------------------------------------------
# HTML endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def index(request: Request, session: Session = Depends(get_session)):
    tickets = _query_tickets(session)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tickets": tickets,
            "ticket_technicians": _build_ticket_technicians(session, tickets),
            "all_technicians": _all_technicians(session),
        },
    )


@app.get("/tickets/table")
def tickets_table(
    request: Request,
    category: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    technician_id: int | None = None,
    session: Session = Depends(get_session),
):
    tickets = _query_tickets(
        session,
        category or None,
        priority or None,
        status or None,
        technician_id or None,
    )
    return templates.TemplateResponse(
        "_tickets_table.html",
        {
            "request": request,
            "tickets": tickets,
            "ticket_technicians": _build_ticket_technicians(session, tickets),
        },
    )


@app.post("/tickets/form")
def create_ticket_form(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    technician_ids: list[int] = Form(default=[]),
    session: Session = Depends(get_session),
):
    try:
        body = TicketCreate(title=title, description=description, technician_ids=technician_ids)
    except ValidationError:
        tickets = _query_tickets(session)
        return templates.TemplateResponse(
            "_tickets_table.html",
            {
                "request": request,
                "tickets": tickets,
                "ticket_technicians": _build_ticket_technicians(session, tickets),
                "error": "No se ha podido crear el ticket. Revisa el título y la descripción.",
            },
        )

    _create_ticket(body, session)
    tickets = _query_tickets(session)
    return templates.TemplateResponse(
        "_tickets_table.html",
        {
            "request": request,
            "tickets": tickets,
            "ticket_technicians": _build_ticket_technicians(session, tickets),
        },
    )


@app.post("/technicians/form")
def create_technician_form(
    request: Request,
    name: str = Form(...),
    email: str = Form(default=""),
    session: Session = Depends(get_session),
):
    try:
        body = TechnicianCreate(name=name, email=email or None)
    except ValidationError:
        technicians = _all_technicians(session)
        return templates.TemplateResponse(
            "_technicians_list.html",
            {
                "request": request,
                "all_technicians": technicians,
                "tech_error": "Nombre de técnico inválido.",
            },
        )

    technician = Technician(name=body.name, email=body.email)
    session.add(technician)
    session.commit()
    session.refresh(technician)
    technicians = _all_technicians(session)
    return templates.TemplateResponse(
        "_technicians_list.html",
        {"request": request, "all_technicians": technicians},
    )


# ---------------------------------------------------------------------------
# JSON API endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tickets", status_code=201, response_model=TicketResponse)
def create_ticket(body: TicketCreate, session: Session = Depends(get_session)):
    ticket = _create_ticket(body, session)
    return _ticket_to_response(ticket, session)


@app.get("/tickets", response_model=list[TicketResponse])
def list_tickets(
    category: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
):
    tickets = _query_tickets(session, category, priority, status)
    return [_ticket_to_response(t, session) for t in tickets]


@app.get("/tickets/stats", response_model=TicketStats)
def get_ticket_stats(session: Session = Depends(get_session)):
    tickets = session.exec(select(Ticket)).all()

    by_category = {cat: 0 for cat in ALLOWED_CATEGORIES}
    by_priority = {prio: 0 for prio in ALLOWED_PRIORITIES}
    by_status = {st: 0 for st in ALLOWED_STATUSES}

    for t in tickets:
        if t.category in by_category:
            by_category[t.category] += 1
        if t.priority in by_priority:
            by_priority[t.priority] += 1
        if t.status in by_status:
            by_status[t.status] += 1

    return TicketStats(by_category=by_category, by_priority=by_priority, by_status=by_status)


@app.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: int, session: Session = Depends(get_session)):
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _ticket_to_response(ticket, session)


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

    if body.technician_ids is not None:
        _set_technicians(session, ticket.id, body.technician_ids)

    return _ticket_to_response(ticket, session)


@app.post("/technicians", status_code=201, response_model=TechnicianResponse)
def create_technician(body: TechnicianCreate, session: Session = Depends(get_session)):
    technician = Technician(name=body.name, email=body.email)
    session.add(technician)
    session.commit()
    session.refresh(technician)
    return TechnicianResponse.model_validate(technician)


@app.get("/technicians", response_model=list[TechnicianResponse])
def list_technicians(session: Session = Depends(get_session)):
    techs = _all_technicians(session)
    return [TechnicianResponse.model_validate(t) for t in techs]
