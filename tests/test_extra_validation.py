import pytest
from fastapi.testclient import TestClient

from app.main import app


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
