# TriageBot — Especificación funcional (referencia, Equipo B)

> **Documento de trabajo del Equipo B.** No está en el repo: lo recibís a mitad
> del Lab 1 como referencia. La habéis empezado a escribir vosotros a partir de
> `BRIEF.md`; esto es el patrón con el que **reconciliarla**, no un reemplazo.
> Comparad la vuestra con esta, adoptad lo que mejore vuestra versión y conservad
> lo vuestro que ya esté bien.

---

## 1. Objetivo

TriageBot es una aplicación web interna donde un usuario crea **tickets**
(incidencias descritas en lenguaje natural) y el sistema, vía LLM, los
**clasifica automáticamente** por categoría, prioridad y tags. El usuario puede
consultar, filtrar y gestionar los tickets desde un tablero web.

El proyecto debe estar **funcionando end-to-end** al final del Día 2: backend,
base de datos, integración con LLM, frontend mínimo, tests verdes y CI verde en
GitHub Actions.

---

## 2. Stack técnico (innegociable)

| Capa | Tecnología |
|------|------------|
| Lenguaje | Python 3.11+ |
| Framework web | FastAPI |
| ORM / modelos | SQLModel |
| Base de datos | SQLite (archivo local `triagebot.db`) |
| LLM | gpt-oss-120b (OpenAI), vía OpenRouter — SDK de OpenAI |
| Frontend | HTMX + Tailwind CSS por CDN (sin build tools) |
| Tests | pytest + `fastapi.testclient.TestClient` |
| Lint | ruff |
| CI | GitHub Actions (incluido en el repo) |

No se permite cambiar de framework, base de datos ni añadir build tools
(webpack, vite…). Si un equipo quiere cambiar de stack, se queda sin experimento.

---

## 3. Modelo de datos

Una sola entidad: `Ticket`.

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | int | Primary key, autoincremental |
| `title` | str | Obligatorio, longitud 1–200 tras `trim` |
| `description` | str | Obligatorio, longitud 1–5000 tras `trim` |
| `category` | str | Uno de: `bug`, `feature_request`, `question`, `urgent` |
| `priority` | str | Uno de: `P1`, `P2`, `P3` |
| `tags` | list[str] | Lista (puede estar vacía). Máx. 5 tags, máx. 30 chars cada uno |
| `status` | str | Uno de: `open`, `in_progress`, `closed`. Default: `open` |
| `created_at` | datetime | UTC, generado en servidor |
| `updated_at` | datetime | UTC, actualizado en cambios relevantes |

`category`, `priority` y `tags` los rellena el clasificador (sección 5) en el
momento de crear el ticket.

> **Los enums son vinculantes.** Si vuestro código devuelve `"URGENT"` en
> mayúsculas o un valor fuera de la lista, los tests fallan.

---

## 4. Endpoints HTTP

Cinco endpoints. Todos viven en el módulo `app.main`.

### `POST /tickets`

Crea un ticket nuevo y lo clasifica automáticamente. **La clasificación ocurre
síncronamente durante la petición**: la respuesta ya trae el ticket clasificado.

**Request body** (JSON):
```json
{
  "title": "La página de login no carga",
  "description": "Al pulsar el botón de login, sale un error 500 del servidor."
}
```

**Response `201 Created`**:
```json
{
  "id": 1,
  "title": "La página de login no carga",
  "description": "Al pulsar el botón de login, sale un error 500 del servidor.",
  "category": "bug",
  "priority": "P1",
  "tags": ["login", "error_500", "backend"],
  "status": "open",
  "created_at": "2026-06-29T09:30:00Z",
  "updated_at": "2026-06-29T09:30:00Z"
}
```

**Errores**:
- `422 Unprocessable Entity` si `title` o `description` faltan, están vacíos o
  exceden su longitud máxima.

> El `POST /tickets` **nunca** devuelve `5xx` por un fallo del LLM. Si el LLM
> falla, el clasificador aplica el fallback (sección 5) y el endpoint devuelve
> `201` igualmente.

### `GET /tickets`

Devuelve la lista de tickets, ordenada por `created_at` descendente.

**Query params opcionales** (combinables): `category`, `priority`, `status`.

```text
GET /tickets?category=bug&priority=P1&status=open
```

**Response `200 OK`**: lista JSON de tickets.

### `GET /tickets/{id}`

Devuelve un ticket por id.

- **Response `200 OK`**: ticket JSON.
- **Response `404 Not Found`**: si no existe.

### `PATCH /tickets/{id}`

Actualiza **solo** `status` o `priority`. El resto de campos son inmutables tras
la creación.

**Request body**:
```json
{ "status": "in_progress", "priority": "P2" }
```

- **Response `200 OK`**: ticket actualizado.
- **Response `404 Not Found`**: si no existe.
- **Response `422`**: si el valor no pertenece al enum permitido.

### `GET /`

Renderiza la página HTML con el tablero (sección 6). **Devuelve HTML, no JSON**
— no confundir con `GET /tickets`.

---

## 5. El módulo clasificador (`app/classifier.py`)

Encapsula toda la lógica de IA. **Es el único módulo que llama al LLM (vía
OpenRouter).** El resto del código depende solo de su contrato. Si hay llamadas
al SDK de OpenAI/OpenRouter en `main.py`, algo se ha torcido.

### Contrato público

```python
def classify_ticket(title: str, description: str) -> dict:
    """
    Clasifica un ticket usando el LLM.

    Devuelve un dict con esta forma exacta:
    {
        "category": "bug" | "feature_request" | "question" | "urgent",
        "priority": "P1" | "P2" | "P3",
        "tags": list[str]  # máx. 5 elementos, cada uno máx. 30 chars
    }
    """
```

### Requisitos del clasificador (no negociables)

1. **Llama al modelo `openai/gpt-oss-120b` vía OpenRouter.** OpenRouter es
   compatible con OpenAI: se usa el SDK de OpenAI con
   `base_url="https://openrouter.ai/api/v1"` y la key `OPENROUTER_API_KEY`. La
   respuesta llega en `response.choices[0].message.content`. El prompt debe pedir
   la clasificación en JSON estructurado.
2. **Valida la salida.** Si el LLM devuelve algo fuera de los enums permitidos
   (`"URGENT"` en mayúsculas, una categoría alucinada…), aplica el fallback en
   lugar de propagar basura al cliente.
3. **Reintenta una vez** si la llamada falla. Si vuelve a fallar, fallback.
4. **No propaga excepciones del SDK** al endpoint.

Fallback estructurado:

```python
{"category": "question", "priority": "P3", "tags": []}
```

### Prompt sugerido (orientativo, no obligatorio)

> Eres un sistema de clasificación de tickets de soporte técnico. Recibirás el
> título y la descripción de un ticket. Devuelve EXCLUSIVAMENTE un JSON con tres
> campos: `category` (uno de: bug, feature_request, question, urgent), `priority`
> (uno de: P1, P2, P3) y `tags` (lista de máx. 5 strings cortos en minúscula).
> No devuelvas explicaciones ni markdown. P1 = urgente, P2 = importante,
> P3 = normal.

No es obligatorio usarlo tal cual. Sí es obligatorio que la salida cumpla el
contrato.

---

## 6. Frontend mínimo

Una sola página HTML servida en `GET /`. Debe contener:

1. **Formulario** con dos campos (`title`, `description`) y un botón "Crear
   ticket". Al enviarse, hace `POST /tickets` (vía HTMX) y refresca la lista sin
   recargar la página.
2. **Tablero** con la lista de tickets, mostrando: `id`, `title`, `category`
   (con color según valor), `priority` (con badge), `tags`, `status`,
   `created_at`.
3. **Filtros**: tres selects para filtrar por `category` / `priority` / `status`.

Recomendaciones: usar Jinja2 templates; usar HTMX para refrescar la tabla sin
recargar; no escribir HTML grande como string dentro de `main.py`. No se exige
diseño espectacular — la gracia es que sea funcional.

---

## 7. Tests de aceptación obligatorios

Los tests están en `tests/test_acceptance.py`. **Este fichero no se modifica.**
Son cinco y todos deben estar verdes para considerar el proyecto entregado:

| # | Test | Verifica |
|---|------|----------|
| 1 | `test_post_ticket_creates_with_classification` | `POST /tickets` retorna `201` con clasificación poblada (category válida, priority válida, tags lista). |
| 2 | `test_get_tickets_returns_list` | `GET /tickets` retorna la lista de tickets creados. |
| 3 | `test_get_ticket_by_id_not_found` | `GET /tickets/99999` retorna `404`. |
| 4 | `test_post_ticket_empty_title_returns_422` | `POST /tickets` con `title=""` retorna `422`. |
| 5 | `test_classifier_module_contract` | El módulo `app.classifier` existe y expone `classify_ticket(title, description) -> dict`. |

Los tests mockean el clasificador para no consumir tokens en CI
(`unittest.mock.patch`).

---

## 8. Criterios de aceptación finales (entrega del Día 2)

- [ ] Repo en GitHub con todos los commits del equipo.
- [ ] Los 5 tests obligatorios verdes (`pytest`).
- [ ] CI verde en GitHub Actions (último commit en `main`).
- [ ] App arranca con `uvicorn app.main:app --reload` y funciona en
      `http://localhost:8000`.
- [ ] Se puede crear un ticket por web y verlo en el tablero.
- [ ] El clasificador devuelve resultados sensatos para al menos 3 tickets
      distintos durante la demo.
- [ ] `README.md` actualizado con instrucciones de arranque.

---

## 9. No negociable

- No commitear `.env`.
- No hardcodear API keys (leer de `OPENROUTER_API_KEY`).
- No propagar excepciones del SDK del LLM al endpoint.
- No modificar los tests de aceptación para hacerlos pasar.
- No introducir React ni frontend complejo.

---

## 10. Tests

Catálogo de los tests existentes organizados por caso de uso. Para cada uno: nombre, qué caso de uso cubre y qué bug o regresión detectaría.

> Los tests viven en `tests/test_acceptance.py` (no se modifica) y `tests/test_extra_validation.py`.

---

### UC-1 — `POST /tickets` (crear ticket)

**`test_post_ticket_creates_ticket_with_classification`** · `test_acceptance.py`
- **Cubre:** `POST /tickets` devuelve `201` con todos los campos clasificados: `category` válida, `priority` válida, `tags` como lista, `status = "open"`, `id` entero, timestamps presentes.
- **Detectaría:** regresión en el endpoint que omita campos de clasificación, devuelva un código distinto de `201`, o rompa la serialización del ticket en respuesta.

**`test_post_ticket_rejects_invalid_input`** · `test_acceptance.py`
- **Cubre:** cinco variantes de input inválido — `title` vacío, `title` solo espacios, `title` de 201 caracteres, `description` vacía, `description` de 5001 caracteres — todas deben devolver `422`.
- **Detectaría:** pérdida de validación de longitud o de trim-and-reject que permitiría guardar títulos en blanco o descripciones desbordadas en base de datos.

**`test_post_ticket_missing_required_fields`** · `test_acceptance.py`
- **Cubre:** tres payloads incompletos — solo `title`, solo `description`, cuerpo vacío — todos deben devolver `422`.
- **Detectaría:** regresión donde campos obligatorios dejan de ser requeridos y el endpoint acepta tickets a medio completar.

**`test_classifier_failure_uses_safe_fallback`** · `test_acceptance.py`
- **Cubre:** cuando `classify_ticket` lanza una excepción, `POST /tickets` aun así devuelve `201` con el fallback `{category: "question", priority: "P3", tags: []}`.
- **Detectaría:** propagación de excepciones del SDK al endpoint (que convertiría el `201` en un `5xx`), o un fallback con valores que no pertenecen a los enums permitidos.

---

### UC-2 — `GET /tickets` (listar y filtrar)

**`test_created_ticket_is_persisted_and_listed`** · `test_acceptance.py`
- **Cubre:** un ticket creado vía `POST /tickets` aparece en `GET /tickets` con `category` y `title` correctos.
- **Detectaría:** fallo de persistencia (ticket no guardado en SQLite) o endpoint `GET /tickets` que devuelva lista vacía sin haber consultado la base de datos.

**`test_update_ticket_and_filter_by_status_priority_category`** · `test_acceptance.py` *(cubre también UC-4)*
- **Cubre (UC-2):** `GET /tickets?category=urgent&priority=P2&status=in_progress` devuelve exactamente el ticket que acaba de ser actualizado.
- **Detectaría:** filtros que no apliquen la condición `AND` entre los tres parámetros, o que devuelvan tickets que no cumplen todos los filtros simultáneamente.

---

### UC-3 — `GET /tickets/{id}` (obtener por id)

**`test_get_ticket_by_id`** · `test_acceptance.py`
- **Cubre:** `GET /tickets/{id}` devuelve `200` con los datos exactos del ticket (id, title, category, priority, tags).
- **Detectaría:** endpoint que devuelva el ticket equivocado, que omita campos, o que no busque por id en la base de datos.

**`test_get_ticket_by_id_not_found`** · `test_acceptance.py`
- **Cubre:** `GET /tickets/99999` devuelve `404`.
- **Detectaría:** ausencia del manejo de "not found", que haría que el endpoint devolviera `200` con body nulo o lanzara una excepción no controlada.

---

### UC-4 — `PATCH /tickets/{id}` (actualizar)

**`test_update_ticket_and_filter_by_status_priority_category`** · `test_acceptance.py` *(cubre también UC-2)*
- **Cubre (UC-4):** `PATCH /tickets/{id}` con `{status: "in_progress", priority: "P2"}` devuelve `200` con los valores actualizados.
- **Detectaría:** endpoint que ignore los campos del body, que no persista el cambio, o que devuelva el ticket sin actualizar.

**`test_patch_ticket_not_found`** · `test_acceptance.py`
- **Cubre:** `PATCH /tickets/99999` devuelve `404`.
- **Detectaría:** ausencia del guard de existencia en el endpoint, provocando un error de base de datos no controlado o una respuesta `200` sobre un id inexistente.

**`test_patch_ticket_rejects_invalid_status`** · `test_extra_validation.py`
- **Cubre:** `PATCH /tickets/{id}` con `{status: "invalid_status"}` devuelve `422`.
- **Detectaría:** pérdida de la validación de enum en el endpoint, que permitiría persistir un `status` fuera de `{open, in_progress, closed}`.
