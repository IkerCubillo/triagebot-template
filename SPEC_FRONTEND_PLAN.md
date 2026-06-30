# SPEC_FRONTEND_PLAN.md — Plan de implementación paso a paso

> Checklist derivado de `SPEC_FRONTEND.md`, adaptado al estado real del código.
> Se ejecuta un paso por turno. Marcar cada paso como hecho (`[x]`) al completarlo
> y verificarlo con `pytest` + `ruff check .`.

---

## Estado de partida (confirmado leyendo el código)

- `app/main.py` ya tiene los endpoints JSON: `POST /tickets`, `GET /tickets`,
  `GET /tickets/{id}`, `PATCH /tickets/{id}`. **No** tiene `Jinja2Templates`, ni
  `GET /`, ni `GET /tickets/table`, ni `POST /tickets/form`.
- `templates/index.html` ya carga Tailwind + HTMX por CDN, tiene cabecera y un
  único `<!-- TODO: formulario + filtros + tabla HTMX -->`.
- `templates/_tickets_table.html` ya tiene `<thead>` completo y un
  `<tbody id="tickets-table-body">` vacío con `<!-- TODO -->`.
- `app/models.py` define `ALLOWED_CATEGORIES`, `ALLOWED_PRIORITIES`,
  `ALLOWED_STATUSES`, `TicketCreate` (valida longitud/trim) y `TicketResponse`.
- `list_tickets()` (`app/main.py:55-71`) ya construye el `select(Ticket)` con
  `.where()` condicionales por `category`/`priority`/`status`. Esa lógica se debe
  **reutilizar**, no duplicar, en los endpoints HTMX nuevos.

No se toca: `tests/test_acceptance.py`, `app/models.py`, `app/db.py`,
`app/classifier.py`.

---

## Pasos

- [x] **1. Configurar `Jinja2Templates` en `app/main.py`**
  `from fastapi.templating import Jinja2Templates` +
  `templates = Jinja2Templates(directory="templates")`.

- [x] **2. Extraer la lógica de filtrado a una función reutilizable**
  Encapsular el `select(Ticket)` + `.where()` + `.order_by()` de `list_tickets`
  en una función común (p. ej. `_query_tickets(...)`) y hacer que `list_tickets`
  la use.

- [x] **3. Crear `GET /`**
  Renderiza `templates/index.html` con `{"request": request, "tickets": tickets}`
  (sin filtrar, usando la función del paso 2). No toca `GET /tickets`.

- [x] **4. Crear `GET /tickets/table`**
  Acepta `category`, `priority`, `status` como query params opcionales, reutiliza
  la función del paso 2, devuelve solo `templates/_tickets_table.html` (fragmento,
  sin `<html>`).

- [x] **5. Crear `POST /tickets/form`**
  Acepta `title` y `description` vía `Form(...)`. Reutiliza la misma lógica de
  creación que `POST /tickets` (clasificación + fallback + guardado, extraída a
  función auxiliar). Aplica las mismas validaciones que el API (`title`/`description`
  no vacíos tras trim, longitud máxima). Si falla, devuelve un fragmento con
  mensaje de error. Si tiene éxito, devuelve el tablero actualizado
  (`_tickets_table.html`).

- [ ] **6. Completar `templates/_tickets_table.html`**
  Loop Jinja2 sobre `tickets` en el `<tbody>` existente:
  - badge de prioridad (P1 rojo/destacado, P2 ámbar, P3 gris/verde),
  - badge de categoría con traducción visual (bug→Error, feature_request→Nueva
    funcionalidad, question→Consulta, urgent→Urgente),
  - badge de estado (open→Abierto, in_progress→En progreso, closed→Cerrado),
  - chips para tags,
  - estado vacío ("Todavía no hay tickets. Crea el primer ticket para empezar.")
    si `tickets` está vacío.

- [ ] **7. Completar `templates/index.html`**
  Sustituir el TODO por:
  - card con formulario (`title` input, `description` textarea, botón
    "Crear ticket"), con `hx-post="/tickets/form" hx-target="#tickets-table"
    hx-swap="innerHTML"`,
  - bloque de filtros (`<select>` para category/priority/status + botón
    "Limpiar filtros"), cada `<select>` con `hx-get="/tickets/table"
    hx-trigger="change" hx-include="#ticket-filters" hx-target="#tickets-table"
    hx-swap="innerHTML"`,
  - `<div id="tickets-table">{% include "_tickets_table.html" %}</div>`.
  Labels en español; opción vacía en cada filtro ("Todas las categorías" /
  "Todas las prioridades" / "Todos los estados").

- [ ] **8. Accesibilidad mínima**
  `<label>` en cada input/select, `name` correctos para que HTMX envíe los datos,
  badges con texto visible (no solo color).

- [ ] **9. Verificación manual end-to-end**
  `uvicorn app.main:app --reload`, abrir `http://localhost:8000/`, crear un
  ticket desde el formulario, comprobar que aparece sin recargar la página,
  probar los tres filtros, confirmar que P1 destaca visualmente.

- [ ] **10. Checks finales**
  `pytest -v` (debe seguir verde, sin tocar `tests/test_acceptance.py`) y
  `ruff check .` (sin errores). Actualizar `DEV_LOG.md` según el protocolo de
  `CLAUDE.md`.

---

## Archivos a tocar

- `app/main.py` — Jinja2Templates, función de filtrado/creación reutilizable, 3
  endpoints nuevos (`GET /`, `GET /tickets/table`, `POST /tickets/form`).
- `templates/index.html` — formulario + filtros + contenedor de tabla.
- `templates/_tickets_table.html` — loop Jinja2 + badges + chips + estado vacío.

## Verificación general

- `pytest -v` → todos los tests existentes en verde.
- `ruff check .` → sin errores.
- Manual: crear ticket, ver aparición en tablero sin recargar, filtrar por
  category/priority/status, confirmar que `GET /tickets` sigue devolviendo JSON.
