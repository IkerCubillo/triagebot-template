# QA_ADVERSARIAL.md — QA adversarial de TriageBot (10 escenarios)

> Ejercicio de QA adversarial repartido por el profesor: 10 escenarios de
> entrada maliciosa/límite, probados a mano contra la app real (`curl` —
> equivalente a "pulsar el botón" desde el punto de vista del backend) y
> anotados según el contrato definido en `SPEC.md` y las reglas de
> `CLAUDE.md`.
>
> **Entorno de prueba:** servidor `uvicorn` aislado con `DATABASE_URL`
> apuntando a un SQLite temporal en el scratchpad de la sesión — **no** se ha
> tocado `triagebot.db` (la base de datos real de desarrollo) en ningún
> momento.

---

## Resumen ejecutivo

| # | Escenario | Veredicto |
|---|---|---|
| 1 | Title vacío o solo espacios | ✅ Correcto |
| 2 | Title de 5000 caracteres | ✅ Correcto |
| 3 | Emojis y unicode no latino | ✅ Correcto |
| 4 | HTML/JS en la descripción (XSS) | ⚠️ Correcto en lo probado, con matiz (ver detalle) |
| 5 | Inyección SQL básica | ✅ Correcto |
| 6 | LLM caído (simulado) | ✅ Correcto |
| 7 | Mismo ticket enviado dos veces | ✅ Comportamiento esperado (no es bug) |
| 8 | IDs malformados | ✅ Correcto |
| 9 | PATCH con valores inválidos | ✅ Correcto |
| 10 | 20 POSTs concurrentes | ✅ Correcto |

**0 bugs críticos encontrados.** Un matiz documentado en el escenario 4 (no es
un bug explotable hoy, pero es una trampa potencial a futuro — ver detalle).

---

## Escenario 1 — Title vacío o solo espacios

**Comando:**
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"title":"","description":"desc valida"}' http://localhost:8200/tickets

curl -X POST -H "Content-Type: application/json" \
  -d '{"title":"     ","description":"desc valida"}' http://localhost:8200/tickets
```

**Resultado:** ambos devuelven `422` (`string_too_short`, `min_length:1`,
gracias al `strip()` en modo `before` de `TicketCreate`). `GET /tickets`
confirma 0 tickets creados.

**Veredicto:** ✅ Correcto. Cumple `SPEC.md` §3/§4 (title obligatorio, 1–200
tras trim).

---

## Escenario 2 — Title de 5000 caracteres

**Comando:** `POST /tickets` con `title` de 5000 caracteres `'A'`.

**Resultado:** `422` (`string_too_long`, `max_length: 200`). 0 tickets
creados.

**Veredicto:** ✅ Correcto. El límite real de `title` es 200 (no 5000, ese es
el límite de `description`) — la validación lo respeta y rechaza.

---

## Escenario 3 — Emojis y caracteres unicode no latinos

**Comando:**
```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "title": "🔥💥 Título con emoji y 日本語 العربية кириллица",
  "description": "Descripción con unicode: 你好世界 مرحبا بالعالم Привет мир 🚀🐛"
}' http://localhost:8200/tickets
```

**Resultado:** `201`. El ticket se crea, se persiste y `GET /tickets/{id}`
devuelve el texto íntegro (emojis y los 4 alfabetos no latinos preservados sin
corrupción, vía JSON unicode-escaped estándar).

**Veredicto:** ✅ Correcto. No hay razón de `SPEC.md` para rechazar
unicode/emojis, y no se rechazan ni se corrompen.

---

## Escenario 4 — HTML/JS en la descripción (XSS potencial)

**Comando 1** (API JSON, payload en `description`):
```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "title":"XSS test",
  "description":"<script>alert(1)</script><img src=x onerror=alert(2)>"
}' http://localhost:8200/tickets
```
→ `201`, se guarda el payload tal cual en `description` (correcto, persistir
no es el problema — el problema sería *renderizarlo sin escapar*).

**Comando 2** (formulario HTMX, payload en `title`, que sí se renderiza en el
tablero):
```bash
curl -X POST -d "title=%3Cscript%3Ealert('XSS-TITLE')%3C%2Fscript%3E&description=..." \
  http://localhost:8200/tickets/form
```
→ HTML de respuesta contiene:
```html
<td class="...">&lt;script&gt;alert(&#39;XSS-TITLE&#39;)&lt;/script&gt;</td>
```
Escapado correctamente por el autoescape de Jinja2. **No** aparece como
`<script>` ejecutable.

**Matiz importante:** `templates/_tickets_table.html` **nunca muestra el
campo `description`** (solo id, title, category, priority, tags, status,
responsables, created_at). Por tanto, hoy el XSS vía `description` no tiene
ninguna superficie de ataque real en la UI — no porque esté protegido
explícitamente, sino porque ese campo simplemente no se imprime en ningún
template. Si en el futuro se añade una vista de detalle que sí muestre
`description`, hay que asegurarse de que siga usando `{{ description }}` de
Jinja2 (autoescape) y no `{{ description | safe }}` ni inserción vía
`innerHTML` en JS.

**Veredicto:** ⚠️ Correcto en todo lo probado (title escapado, JS no se
ejecuta). No es un bug, pero se documenta el matiz de `description` como nota
para vigilar en futuros cambios de UI.

---

## Escenario 5 — Inyección SQL básica

**Comando:**
```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "title": "Robert'\''); DROP TABLE ticket;--",
  "description": "'\'' OR '\''1'\''='\''1'\'' -- SQLi test"
}' http://localhost:8200/tickets
```

**Resultado:** `201`. El payload se guarda como texto literal:
```
id=5 | title = Robert'); DROP TABLE ticket;--
```
Verificado directamente en SQLite (`sqlite3 qa_test.db ".schema ticket"` y
`SELECT id, title FROM ticket`): la tabla `ticket` sigue existiendo con su
esquema intacto, y las 5 filas anteriores (incluida la del intento de
inyección) están presentes sin alteración. `GET /tickets` sigue funcionando
con normalidad tras el intento.

**Veredicto:** ✅ Correcto. SQLModel/SQLAlchemy usa queries parametrizadas en
todo `app/main.py` (`Ticket.category == category`, `session.add(...)`, etc.) —
no hay concatenación de SQL crudo en ningún punto, así que la inyección se
trata como dato, no como código.

---

## Escenario 6 — LLM caído (simulado)

**Cómo se simuló:** instancia `uvicorn` aparte (puerto 8201, DB temporal
distinta) levantada con `OPENROUTER_API_KEY=""`. Según
`app/classifier.py:12-14`, si la key no está presente el clasificador
devuelve `FALLBACK_CLASSIFICATION` de forma inmediata y determinista, sin
intentar llamar al SDK.

**Comando:**
```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "title":"Ticket sin LLM disponible",
  "description":"Probando comportamiento cuando el LLM esta caido"
}' http://localhost:8201/tickets
```

**Resultado:** `201` con
`{"category":"question","priority":"P3","tags":[]}` — exactamente el
fallback documentado en `SPEC.md` §5.

**Veredicto:** ✅ Correcto. Cumple la regla no negociable de §5/§9: "el
`POST /tickets` nunca devuelve 5xx por un fallo del LLM".

---

## Escenario 7 — Mismo ticket enviado dos veces seguidas

**Comando:** mismo payload JSON enviado dos veces consecutivas por
`POST /tickets`.

**Resultado:** dos respuestas `201` con `id=6` e `id=7` respectivamente,
mismo `title`/`description`, `created_at` distintos (4 segundos de
diferencia real entre comandos). `GET /tickets` confirma 2 tickets
independientes con el mismo título.

**Veredicto:** ✅ Comportamiento esperado, **no es un bug**: `SPEC.md` no
exige idempotencia ni deduplicación en `POST /tickets`, así que crear dos
tickets idénticos es el comportamiento correcto dado el contrato actual. Si
el equipo quisiera evitar duplicados accidentales (doble clic del usuario en
"Crear ticket"), sería una mejora de producto a discutir, no un fallo de la
spec actual.

---

## Escenario 8 — IDs malformados

| Comando | Resultado | Esperado | Veredicto |
|---|---|---|---|
| `GET /tickets/-1` | `404 Ticket not found` | 404 (válido pero no existe) | ✅ |
| `GET /tickets/abc` | `422 int_parsing` | 422 (FastAPI valida el tipo del path param) | ✅ |
| `GET /tickets/99999999999` | `404 Ticket not found` | 404 (entero válido, no existe, sin overflow) | ✅ |
| `PATCH /tickets/-1` | `404 Ticket not found` | 404 | ✅ |
| `PATCH /tickets/abc` | `422 int_parsing` | 422 | ✅ |
| `PATCH /tickets/99999999999` | `404 Ticket not found` | 404 | ✅ |

**Veredicto:** ✅ Correcto en los 6 casos. Ningún `500`, ningún overflow de
SQLite con el entero de 11 dígitos, ningún id negativo tratado como válido.

---

## Escenario 9 — PATCH con valores inválidos

**Comando 1:** `PATCH /tickets/1` con `{"status": "inventado"}` → `422
Invalid status: inventado`.

**Comando 2:** `PATCH /tickets/1` con `{"priority": "P9"}` → `422 Invalid
priority: P9`.

**Verificación post-intento:** `GET /tickets/1` confirma `status=open,
priority=P3` — **sin cambios**, ninguno de los dos intentos inválidos alteró
el ticket.

**Veredicto:** ✅ Correcto. Coincide con `test_patch_ticket_rejects_invalid_status`
de `tests/test_extra_validation.py`, y se confirma también para `priority`
(no cubierto explícitamente por ese test, pero el código usa el mismo patrón
de validación contra `ALLOWED_PRIORITIES`).

---

## Escenario 10 — 20 POSTs concurrentes

**Comando:** 20 procesos `curl -X POST /tickets` lanzados en paralelo
(`& ... wait` en bash) contra el mismo servidor.

**Resultado:**
- Códigos de respuesta: **20/20 → `201`** (ninguno `500`, ninguno colgado).
- Conteo de tickets antes/después: 7 → 27 (exactamente +20, sin pérdidas de
  escritura).
- IDs asignados: `8, 9, 10, ..., 27` — **20 IDs consecutivos sin colisión ni
  duplicados**.

**Veredicto:** ✅ Correcto. A pesar de que SQLite tiene fama de tener
problemas de locking bajo escritura concurrente, en esta prueba con 20
peticiones simultáneas no se observó ningún error ni pérdida de datos — la
combinación de `Session` por request de SQLModel y el `check_same_thread:
False` de `app/db.py` se comportó correctamente en esta carga. (Nota: con
volúmenes mucho mayores de concurrencia esto podría degradar, pero eso entra
en territorio de rendimiento/DoS, fuera del alcance de este ejercicio.)

---

## Conclusión

De los 10 escenarios de QA adversarial, **ninguno reveló un bug** según la
definición de la tarea (¿error 500? ¿app caída? ¿ticket basura persistido
tras un rechazo? ¿JS ejecutado en el navegador? ¿inyección que modificó
datos?). El único hallazgo a documentar (no a corregir) es el matiz del
escenario 4: `description` no se renderiza en ningún template hoy, así que
ese campo no es un vector de XSS actual — pero si se añade una vista de
detalle en el futuro, debe seguir las mismas reglas de autoescape de Jinja2
que ya protegen `title` correctamente.
