# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Este repo es una plantilla docente para construir **TriageBot**, una aplicación
FastAPI que clasifica tickets de soporte con un LLM (`openai/gpt-oss-120b` vía OpenRouter).

## Stack (innegociable)

- Python 3.11+
- FastAPI + Jinja2 templates
- SQLite (archivo `triagebot.db`; en tests se inyecta `DATABASE_URL`)
- HTMX + Tailwind por CDN (sin build tools)
- SDK de OpenAI apuntado a OpenRouter (`base_url="https://openrouter.ai/api/v1"`)
- pytest + ruff

## Comandos

```bash
# Desarrollo
uvicorn app.main:app --reload

# Tests
pytest -v
pytest -v -k "test_post_ticket"   # test individual por nombre
pytest --cov=app

# Lint
ruff check .
ruff check . --fix
```

## Arquitectura

El repo arranca como plantilla con stubs y TODOs. Hay cuatro módulos en `app/`:

- **`app/main.py`** — entrada FastAPI. Todos los endpoints viven aquí: `POST /tickets`, `GET /tickets`, `GET /tickets/{id}`, `PATCH /tickets/{id}`, `GET /`.
- **`app/classifier.py`** — **único módulo que llama al LLM**. Expone `classify_ticket(title, description) -> dict`. Si falla (excepción o respuesta inválida), devuelve `FALLBACK_CLASSIFICATION` y reintenta una vez antes de rendirse. Nunca propaga excepciones al endpoint.
- **`app/db.py`** — inicialización de SQLite y operaciones de persistencia.
- **`app/models.py`** — schemas Pydantic y los tres enums permitidos (`ALLOWED_CATEGORIES`, `ALLOWED_PRIORITIES`, `ALLOWED_STATUSES`).

Templates:

- `templates/index.html` — página principal servida en `GET /`.
- `templates/_tickets_table.html` — parcial devuelto por HTMX para refrescar la tabla sin recargar la página.

## Contrato del clasificador

```python
# Salida esperada — valores deben pertenecer a los enums de models.py
{"category": "bug", "priority": "P1", "tags": ["login", "error_500"]}

# Fallback ante cualquier error del SDK o valor fuera de enum
{"category": "question", "priority": "P3", "tags": []}
```

El prompt debe pedir JSON estricto (sin markdown, sin explicaciones).

## Variables de entorno

| Variable | Uso |
|----------|-----|
| `OPENROUTER_API_KEY` | API key de OpenRouter para el clasificador |
| `DATABASE_URL` | Ruta SQLite — los tests inyectan una DB temporal vía monkeypatch |

## Tests de aceptación

`tests/test_acceptance.py` **no se modifica**. Los tests mockean `app.classifier.classify_ticket` con monkeypatch para no consumir tokens en CI. La fixture `client` inyecta `DATABASE_URL` apuntando a un directorio temporal para aislamiento.

## Reglas del taller

1. No modifiques `tests/test_acceptance.py` salvo indicación expresa del profesor.
2. Nunca hardcodees una API key en el código.
3. Lee la API key desde `OPENROUTER_API_KEY`.
4. `.env` nunca se commitea — comprueba que está en `.gitignore`.
 