from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app
from app.models import Ticket, compute_deadline


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Test client with an isolated database path when the app supports DATABASE_URL."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    return TestClient(app)


def fake_classification(category="bug", priority="P1", tags=None):
    return {
        "category": category,
        "priority": priority,
        "tags": tags if tags is not None else ["login", "customer-impact"],
    }


def test_patch_ticket_rejects_invalid_status(client, monkeypatch):
    monkeypatch.setattr(
        "app.classifier.classify_ticket",
        lambda title, description: fake_classification(),
    )

    created = client.post(
        "/tickets",
        json={
            "title": "El login falla intermitentemente",
            "description": "Algunos usuarios no pueden iniciar sesión desde ayer",
        },
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    response = client.patch(f"/tickets/{ticket_id}", json={"status": "invalid_status"})

    assert response.status_code == 422


def test_deadline_computed_from_priority(client, monkeypatch):
    monkeypatch.setattr(
        "app.classifier.classify_ticket",
        lambda title, description: fake_classification(priority="P2"),
    )

    before = datetime.now(UTC)
    created = client.post(
        "/tickets",
        json={"title": "Algo se rompe", "description": "Descripción suficientemente larga"},
    )
    assert created.status_code == 201
    data = created.json()

    expected = compute_deadline("P2", before)
    deadline = datetime.fromisoformat(data["deadline"])
    assert deadline.date() == expected.date()
    assert (deadline.hour, deadline.minute, deadline.second) == (23, 59, 59)


def test_patch_priority_recalculates_deadline(client, monkeypatch):
    monkeypatch.setattr(
        "app.classifier.classify_ticket",
        lambda title, description: fake_classification(priority="P3"),
    )

    created = client.post(
        "/tickets",
        json={"title": "Mejora menor", "description": "No es urgente pero hay que hacerlo"},
    )
    ticket_id = created.json()["id"]
    original_deadline = created.json()["deadline"]

    patched = client.patch(f"/tickets/{ticket_id}", json={"priority": "P1"})
    assert patched.status_code == 200
    new_deadline = patched.json()["deadline"]

    assert new_deadline != original_deadline
    expected_date = compute_deadline("P1", datetime.now(UTC)).date()
    assert datetime.fromisoformat(new_deadline).date() == expected_date


def test_overdue_only_excludes_closed_tickets(client, monkeypatch):
    monkeypatch.setattr(
        "app.classifier.classify_ticket",
        lambda title, description: fake_classification(priority="P1"),
    )

    open_ticket = client.post(
        "/tickets",
        json={"title": "Ticket abierto vencido", "description": "Lleva tiempo sin atender"},
    ).json()
    closed_ticket = client.post(
        "/tickets",
        json={"title": "Ticket cerrado vencido", "description": "Ya se resolvió hace tiempo"},
    ).json()

    client.patch(f"/tickets/{closed_ticket['id']}", json={"status": "closed"})

    # Forzamos ambos deadlines al pasado directamente en la BD para simular vencimiento.
    session = next(get_session())
    past = datetime.now(UTC) - timedelta(days=5)
    for ticket_id in (open_ticket["id"], closed_ticket["id"]):
        ticket = session.get(Ticket, ticket_id)
        ticket.deadline = past
        session.add(ticket)
    session.commit()

    response = client.get("/tickets", params={"overdue_only": "true"})
    assert response.status_code == 200
    ids = [t["id"] for t in response.json()]
    assert open_ticket["id"] in ids
    assert closed_ticket["id"] not in ids
