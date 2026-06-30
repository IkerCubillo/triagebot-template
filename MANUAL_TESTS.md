# Guía de pruebas manuales — TriageBot

Servidor corriendo en `http://localhost:8000`. Arrancarlo con:

```bash
uvicorn app.main:app --reload
```

---

## Fallos detectados en la revisión de seguridad

La revisión no encontró vulnerabilidades explotables. Los puntos verificados fueron:

| Área | Resultado | Por qué es seguro |
|------|-----------|-------------------|
| SQL injection | ✅ No vulnerable | SQLModel usa queries parametrizadas (`WHERE Ticket.category == category`) |
| XSS | ✅ No vulnerable | Jinja2 auto-escapa todo por defecto; no se usa `\| safe` en datos de usuario |
| Hardcoded secrets | ✅ No vulnerable | API key leída de `OPENROUTER_API_KEY`, nunca en código |
| Valores inválidos en PATCH | ✅ Validado | `ALLOWED_STATUSES` / `ALLOWED_PRIORITIES` rechaza valores fuera de enum |

---

## Casos de prueba

### 1. Title vacío o solo espacios

**Qué se espera:** el validador `strip_and_reject_blank` elimina espacios y luego `min_length=1` falla → 422.

**Via API (JSON):**
```bash
curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"title": "", "description": "descripción válida"}' | python -m json.tool

curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"title": "   ", "description": "descripción válida"}' | python -m json.tool
```

**Resultado esperado:**
```json
{"detail": [{"type": "string_too_short", "loc": ["body", "title"], ...}]}
```
HTTP 422 en ambos casos.

**Via formulario web:** Ir a `http://localhost:8000`, enviar el formulario con el campo Título vacío. Debe aparecer el banner rojo de error en la tabla sin crear ticket.

---

### 2. Title de 5000 caracteres

**Qué se espera:** `max_length=200` en `TicketCreate.title` → 422. La descripción acepta hasta 5000; probar en el límite exacto y sobrepasarlo.

```bash
# Title de 201 caracteres → debe fallar
python -c "print('A'*201)" | xargs -I{} curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d "{\"title\": \"$(python -c 'print(\"A\"*201)')\", \"description\": \"ok\"}" | python -m json.tool

# Con Python (más cómodo para strings largos)
python - <<'EOF'
import requests, json

# Title de 201 chars → 422
r = requests.post("http://localhost:8000/tickets", json={
    "title": "A" * 201,
    "description": "descripción normal"
})
print(f"Title 201 chars: HTTP {r.status_code}")
print(json.dumps(r.json(), indent=2))

# Description exactamente en el límite (5000) → 201
r = requests.post("http://localhost:8000/tickets", json={
    "title": "Ticket límite",
    "description": "B" * 5000
})
print(f"\nDescription 5000 chars: HTTP {r.status_code}")

# Description 5001 chars → 422
r = requests.post("http://localhost:8000/tickets", json={
    "title": "Ticket excede",
    "description": "B" * 5001
})
print(f"Description 5001 chars: HTTP {r.status_code}")
EOF
```

**Resultados esperados:**
- Title 201 chars → HTTP 422
- Description 5000 chars → HTTP 201 (límite exacto permitido)
- Description 5001 chars → HTTP 422

---

### 3. Emojis y caracteres Unicode no latinos

**Qué se espera:** Pydantic acepta cualquier string Unicode; SQLite almacena UTF-8; Jinja2 renderiza correctamente. Ticket creado y visible en tabla.

```bash
curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"title": "Error en módulo 日本語 🚀", "description": "Fallo crítico: 한국어 テスト العربية émojis 🐛🔥💥"}' \
  | python -m json.tool
```

**Verificar en UI:** Abrir `http://localhost:8000` y confirmar que el título y descripción aparecen con los caracteres correctos, sin reemplazos ni corrupción.

**Resultado esperado:** HTTP 201, ticket visible con todos los caracteres intactos.

---

### 4. HTML/JS en la descripción (XSS potencial)

**Qué se espera:** Jinja2 auto-escapa las variables `{{ ticket.title }}` y `{{ ticket.description }}`. El HTML se almacena como texto plano y se renderiza escapado (`<` → `&lt;`). No debe ejecutarse ningún script.

```bash
curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"title": "<script>alert(\"XSS\")</script>", "description": "<img src=x onerror=alert(1)> also <b>bold</b>"}' \
  | python -m json.tool
```

**Verificar en UI:**
1. Ir a `http://localhost:8000`.
2. El título debe mostrarse como texto literal `<script>alert("XSS")</script>`, no ejecutarse.
3. Abrir DevTools → Console: no debe aparecer ningún `alert`.
4. Inspeccionar el HTML generado: `View Source` → buscar el título → debe verse `&lt;script&gt;alert...&lt;/script&gt;`.

**Resultado esperado:** HTTP 201, texto escapado en pantalla, cero ejecución de JS.

---

### 5. Inyección SQL básica

**Qué se espera:** SQLModel/SQLAlchemy usa queries parametrizadas. El payload se almacena como texto literal y la tabla `ticket` no se ve afectada.

```bash
curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"title": "test'\'''; DROP TABLE ticket;--", "description": "1'\'' OR '\''1'\''='\''1"}' \
  | python -m json.tool
```

Con Python (más legible):
```python
import requests

payloads = [
    {"title": "'; DROP TABLE ticket;--",    "description": "normal"},
    {"title": "normal",                      "description": "1' OR '1'='1"},
    {"title": "\" UNION SELECT * FROM ticket--", "description": "normal"},
]
for p in payloads:
    r = requests.post("http://localhost:8000/tickets", json=p)
    print(f"HTTP {r.status_code} — title: {p['title'][:40]!r}")

# Comprobar que la tabla sigue viva
r = requests.get("http://localhost:8000/tickets")
print(f"\nGET /tickets → HTTP {r.status_code}, {len(r.json())} tickets")
```

**Resultado esperado:** HTTP 201 en todos los casos, payloads guardados como texto, `GET /tickets` sigue respondiendo correctamente.

---

### 6. LLM caído (simulación)

El clasificador captura cualquier excepción y devuelve `FALLBACK_CLASSIFICATION = {"category": "question", "priority": "P3", "tags": []}`.

**Método A — sin API key (más rápido):**
```bash
# En PowerShell
$env:OPENROUTER_API_KEY = ""
uvicorn app.main:app --reload
```
```bash
# En bash
OPENROUTER_API_KEY="" uvicorn app.main:app --reload
```

**Método B — key inválida (simula error de auth del LLM):**
```bash
OPENROUTER_API_KEY="sk-invalid-key-for-testing" uvicorn app.main:app --reload
```

**Crear ticket con LLM caído:**
```bash
curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"title": "Ticket con LLM caído", "description": "Debe usar fallback"}' \
  | python -m json.tool
```

**Resultado esperado:**
```json
{
  "category": "question",
  "priority": "P3",
  "tags": []
}
```
HTTP 201, el ticket se crea con la clasificación de fallback. No debe devolver 500 ni propagar la excepción.

---

### 7. Mismo ticket enviado dos veces seguidas

**Qué se espera:** No hay lógica de deduplicación. Se crean dos tickets distintos con IDs diferentes.

```bash
DATA='{"title": "Login falla con Google SSO", "description": "El botón de login con Google no redirige correctamente"}'

curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d "$DATA" | python -m json.tool

curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d "$DATA" | python -m json.tool
```

**Resultado esperado:** Dos respuestas HTTP 201 con IDs distintos (ej. `"id": 5` y `"id": 6`). Ambos visibles en `GET /tickets`.

---

### 8. IDs malformados

**`GET /tickets/{id}` y `PATCH /tickets/{id}` esperan un entero.**

```bash
# ID negativo — válido como int, pero no existe en BD
curl -s http://localhost:8000/tickets/-1 | python -m json.tool
# Esperado: HTTP 404 {"detail": "Ticket not found"}

# ID no numérico — FastAPI falla la conversión a int
curl -s http://localhost:8000/tickets/abc | python -m json.tool
# Esperado: HTTP 422 {"detail": [{"type": "int_parsing", ...}]}

# ID entero muy grande — válido como int, no existe en BD
curl -s http://localhost:8000/tickets/99999999999 | python -m json.tool
# Esperado: HTTP 404 {"detail": "Ticket not found"}

# PATCH con ID inválido
curl -s -X PATCH http://localhost:8000/tickets/abc \
  -H "Content-Type: application/json" \
  -d '{"status": "closed"}' | python -m json.tool
# Esperado: HTTP 422
```

**Resumen de resultados esperados:**

| Endpoint | Resultado |
|----------|-----------|
| `GET /tickets/-1` | 404 |
| `GET /tickets/abc` | 422 |
| `GET /tickets/99999999999` | 404 |
| `PATCH /tickets/abc` | 422 |

---

### 9. PATCH con valores inválidos

**Qué se espera:** `ALLOWED_STATUSES = {"open", "in_progress", "closed"}` y `ALLOWED_PRIORITIES = {"P1", "P2", "P3"}`. Valores fuera de estos conjuntos devuelven HTTP 422.

Primero obtener un ID válido:
```bash
TICKET_ID=$(curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"title": "Ticket para PATCH", "description": "Test de valores inválidos"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Usando ticket ID: $TICKET_ID"
```

```bash
# Status inventado → 422
curl -s -X PATCH http://localhost:8000/tickets/$TICKET_ID \
  -H "Content-Type: application/json" \
  -d '{"status": "inventado"}' | python -m json.tool
# Esperado: HTTP 422 {"detail": "Invalid status: inventado"}

# Priority inventada → 422
curl -s -X PATCH http://localhost:8000/tickets/$TICKET_ID \
  -H "Content-Type: application/json" \
  -d '{"priority": "P0"}' | python -m json.tool
# Esperado: HTTP 422 {"detail": "Invalid priority: P0"}

# Status válido → 200
curl -s -X PATCH http://localhost:8000/tickets/$TICKET_ID \
  -H "Content-Type: application/json" \
  -d '{"status": "closed"}' | python -m json.tool
# Esperado: HTTP 200, campo status = "closed"

# PATCH vacío (sin campos) → 200 sin cambios
curl -s -X PATCH http://localhost:8000/tickets/$TICKET_ID \
  -H "Content-Type: application/json" \
  -d '{}' | python -m json.tool
# Esperado: HTTP 200, ticket sin cambios
```

---

### 10. 20 POSTs concurrentes

**Qué se espera:** SQLite con WAL mode o serialización de escrituras — todos los tickets se crean sin error ni corrupción. 20 tickets distintos con IDs únicos.

**Con Python (threading):**
```python
import requests
import threading
import json

results = []
lock = threading.Lock()

def post_ticket(i):
    r = requests.post("http://localhost:8000/tickets", json={
        "title": f"Ticket concurrente #{i}",
        "description": f"Enviado en paralelo, índice {i}"
    })
    with lock:
        results.append((i, r.status_code, r.json().get("id")))

threads = [threading.Thread(target=post_ticket, args=(i,)) for i in range(20)]
for t in threads:
    t.start()
for t in threads:
    t.join()

results.sort()
statuses = [r[1] for r in results]
ids = [r[2] for r in results]

print(f"Total requests: {len(results)}")
print(f"HTTP 201: {statuses.count(201)}")
print(f"Errores:  {statuses.count(500) + statuses.count(422)}")
print(f"IDs únicos: {len(set(ids))} / {len(ids)}")
print(f"IDs: {sorted(ids)}")
```

**Verificación final:**
```bash
# Contar tickets en la BD después del test
curl -s http://localhost:8000/tickets | python -c "import sys,json; t=json.load(sys.stdin); print(f'{len(t)} tickets totales')"
```

**Resultado esperado:** 20 HTTP 201, 20 IDs únicos, cero 500, tabla íntegra.

---

## Referencia rápida de comportamientos esperados

| Caso | Endpoint | HTTP esperado | Motivo |
|------|----------|---------------|--------|
| Title vacío | `POST /tickets` | 422 | `min_length=1` tras strip |
| Title solo espacios | `POST /tickets` | 422 | strip → vacío → `min_length=1` |
| Title 201 chars | `POST /tickets` | 422 | `max_length=200` |
| Description 5000 chars | `POST /tickets` | 201 | límite exacto permitido |
| Description 5001 chars | `POST /tickets` | 422 | supera `max_length=5000` |
| Unicode/emojis | `POST /tickets` | 201 | Python str nativo, SQLite UTF-8 |
| HTML en descripción | `POST /tickets` | 201 (sin XSS) | Jinja2 auto-escape |
| SQL injection en title | `POST /tickets` | 201 (sin efecto) | queries parametrizadas |
| LLM caído | `POST /tickets` | 201 (fallback) | `except Exception → continue` |
| Ticket duplicado | `POST /tickets` ×2 | 201+201 | sin deduplicación |
| `GET /tickets/-1` | `GET` | 404 | int válido, no existe |
| `GET /tickets/abc` | `GET` | 422 | no es int |
| `GET /tickets/99999999999` | `GET` | 404 | int válido, no existe |
| Status inválido | `PATCH /tickets/{id}` | 422 | no en `ALLOWED_STATUSES` |
| Priority inválida | `PATCH /tickets/{id}` | 422 | no en `ALLOWED_PRIORITIES` |
| 20 POSTs concurrentes | `POST /tickets` ×20 | 20×201 | SQLite serializa writes |
