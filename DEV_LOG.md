# DEV_LOG

[2026-06-30 13:30] Frontend paso 5: crear POST /tickets/form

Solicitado: Ejecutar el paso 5 de SPEC_FRONTEND_PLAN.md: crear el endpoint
POST /tickets/form que el formulario HTMX usará para crear tickets sin recargar
la página, reutilizando la lógica de creación y validación del endpoint JSON.

Implementado:
- Extraída la lógica de creación de `create_ticket` a una función auxiliar
  `_create_ticket(body, session)` (clasificación + fallback + guardado)
- `create_ticket` (POST /tickets) ahora delega en `_create_ticket`, sin cambios en
  su firma, status_code ni response_model
- Añadido endpoint `POST /tickets/form` que acepta `title`/`description` vía
  `Form(...)`, construye un `TicketCreate(title=title, description=description)`
  para reutilizar exactamente la misma validación que el API JSON (trim + límites
  de longitud vía Pydantic), captura `ValidationError` y devuelve un fragmento
  `_tickets_table.html` con status 422 y mensaje de error si falla
- Si la validación pasa, crea el ticket vía `_create_ticket` y devuelve el tablero
  actualizado (`_tickets_table.html`) con status 200

Decisiones:
- Se reutiliza `TicketCreate` para validar en vez de reimplementar las reglas de
  longitud/trim, evitando duplicar lógica de validación entre API y formulario
- El mensaje de error se pasa al contexto del template como variable `error`;
  el renderizado visual de ese mensaje se completará en el paso 6 al tocar
  `_tickets_table.html`

Archivos tocados: SPEC_FRONTEND_PLAN.md, app/main.py, DEV_LOG.md
Tests: 10/10 ✅ (pytest -q), ruff check . ✅
Verificación manual: POST /tickets/form con datos válidos → 200 HTML; con
title/description vacíos → 422 HTML (sin 500); POST /tickets JSON sigue
devolviendo 201 con el contrato esperado

[2026-06-30 13:15] Frontend paso 4: crear GET /tickets/table

Solicitado: Ejecutar el paso 4 de SPEC_FRONTEND_PLAN.md: crear el endpoint
GET /tickets/table que HTMX usará para refrescar el tablero filtrado sin recargar
la página.

Implementado:
- Añadido endpoint `GET /tickets/table` en app/main.py, colocado entre
  `list_tickets` y `get_ticket` (antes de la ruta `/tickets/{ticket_id}` para que
  el path estático no sea capturado por el path param)
- Acepta `category`, `priority`, `status` opcionales, reutiliza `_query_tickets`
  y renderiza `templates/_tickets_table.html` como fragmento HTML
- No lleva `response_model` por devolver HTML, no JSON

Decisiones:
- Se colocó antes de `GET /tickets/{ticket_id}` deliberadamente: FastAPI resuelve
  rutas en orden de declaración, así que `/tickets/table` debía quedar antes del
  path param para no ser interpretado como `ticket_id="table"`

Archivos tocados: SPEC_FRONTEND_PLAN.md, app/main.py, DEV_LOG.md
Tests: 10/10 ✅ (pytest -q), ruff check . ✅
Verificación manual: `curl /tickets/table` → 200 HTML (tabla, sin <html>);
`curl /tickets/table?status=open` → 200 HTML filtrado; `curl /tickets` → sigue JSON

[2026-06-30 13:00] Frontend paso 3: crear GET /

Solicitado: Ejecutar el paso 3 de SPEC_FRONTEND_PLAN.md: crear el endpoint GET /
que renderiza templates/index.html con los tickets iniciales.

Implementado:
- Añadido `Request` al import de fastapi en app/main.py
- Añadido endpoint `GET /` (función `index`) que reutiliza `_query_tickets(session)`
  sin filtros y renderiza `templates/index.html` con `{"request": request, "tickets":
  tickets}` vía `templates.TemplateResponse`
- No se tocó templates/index.html ni templates/_tickets_table.html (eso son los
  pasos 6 y 7); el template aún muestra el TODO original

Decisiones:
- `GET /` se colocó como primer endpoint (antes de `/health`) por ser la página
  principal de la app
- Se reutiliza `_query_tickets` del paso 2 en vez de duplicar la query

Archivos tocados: SPEC_FRONTEND_PLAN.md, app/main.py, DEV_LOG.md
Tests: 10/10 ✅ (pytest -q), ruff check . ✅
Verificación manual: `curl http://localhost:8123/` → 200 HTML con <title>TriageBot</title>;
`curl http://localhost:8123/tickets` → 200 JSON sin cambios

[2026-06-30 12:45] Frontend paso 2: extraer lógica de filtrado reutilizable

Solicitado: Ejecutar el paso 2 de SPEC_FRONTEND_PLAN.md: extraer la query de
filtrado de list_tickets a una función reutilizable para los futuros endpoints
HTMX (GET / y GET /tickets/table).

Implementado:
- Añadida función `_query_tickets(session, category, priority, status)` en
  app/main.py que encapsula el `select(Ticket)` + `.where()` condicionales +
  `.order_by(Ticket.created_at.desc())` + `.exec().all()`
- `list_tickets` ahora delega en `_query_tickets` y solo serializa el resultado
- No se cambió la firma ni el comportamiento de GET /tickets

Decisiones:
- La función se nombra con prefijo `_` por ser de uso interno del módulo, no un
  endpoint
- Se mantiene en app/main.py (no se crea un módulo nuevo) porque el spec pide no
  introducir arquitectura adicional sin necesidad clara

Archivos tocados: SPEC_FRONTEND_PLAN.md, app/main.py, DEV_LOG.md
Tests: 10/10 ✅ (pytest -q), ruff check . ✅

[2026-06-30 12:30] Frontend paso 1: configurar Jinja2Templates

Solicitado: Crear el plan de implementación del frontend HTMX (SPEC_FRONTEND.md) como
checklist en SPEC_FRONTEND_PLAN.md y ejecutar el paso 1: dar de alta Jinja2Templates
en app/main.py.

Implementado:
- Creado SPEC_FRONTEND_PLAN.md en la raíz con el checklist de 10 pasos adaptado al
  estado real del código (sustituye el pseudocódigo genérico de SPEC_FRONTEND.md)
- Añadido import `from fastapi.templating import Jinja2Templates` en app/main.py
- Añadida instancia `templates = Jinja2Templates(directory="templates")` justo
  después de `app = FastAPI(...)`
- Marcado el paso 1 como hecho en SPEC_FRONTEND_PLAN.md

Decisiones:
- No se añade todavía ningún endpoint (GET /, GET /tickets/table, POST /tickets/form)
  porque corresponden a pasos posteriores del checklist; este paso solo prepara la
  infraestructura de templates
- No se tocan los endpoints JSON existentes ni tests/test_acceptance.py

Archivos tocados: SPEC_FRONTEND_PLAN.md, app/main.py
Tests: 10/10 ✅ (pytest -q), ruff check . ✅

[2026-06-30 11:45] Guardia CI: .env no commiteado

Solicitado: Añadir comprobación en CI o en tests de que .env no se pushea al repositorio.

Implementado:
- Añadido step "Check .env not committed" en .github/workflows/ci.yml, justo después del checkout y antes de instalar Python
- El step falla con exit 1 si git ls-files detecta que .env está tracked por git
- También falla si .env no aparece en .gitignore (segunda línea de defensa)

Decisiones:
- Se añade en el workflow (no en pytest) porque es una comprobación del estado del repositorio, no del comportamiento de la app; su lugar natural es la capa CI
- Se coloca antes de Set up Python para que falle rápido sin esperar la instalación de dependencias
- grep -qF '.env' .gitignore cubre la entrada exacta que ya existe en .gitignore (línea 16)

Archivos tocados: .github/workflows/ci.yml
Tests: 10/10 ✅

[2026-06-30 10:24] Test adicional: PATCH /tickets/{id} rechaza status inválido

Solicitado: Crear un test propio que verifique que PATCH /tickets/{id} devuelve 422 cuando se envía un status fuera de ALLOWED_STATUSES.

Implementado:
- Creado tests/test_extra_validation.py con test_patch_ticket_rejects_invalid_status: crea un ticket vía POST /tickets (mockeando app.classifier.classify_ticket), luego hace PATCH con {"status": "invalid_status"} y comprueba status_code == 422.

Decisiones:
- Reutilizado el mismo patrón que tests/test_acceptance.py (fixture client con DATABASE_URL temporal vía tmp_path/monkeypatch, y mock de classify_ticket) para mantener consistencia de estilo sin tocar test_acceptance.py.
- No se modificó app/main.py: el endpoint update_ticket ya valida manualmente status contra ALLOWED_STATUSES y lanza HTTPException(422), así que el comportamiento esperado ya existía.

Archivos tocados: tests/test_extra_validation.py
Tests: 6/6 ✅
[2026-06-30 11:30] Verificación CI + nuevos tests de endpoints

Solicitado: Comprobar que el workflow de CI ejecuta lint + tests en cada push/PR y añadir tests para endpoints no cubiertos en test_acceptance.py.

Implementado:
- Verificado que .github/workflows/ci.yml ya es correcto (lint + tests en push y PR a main) — sin cambios
- Añadidos 4 tests nuevos en tests/test_acceptance.py:
  - test_get_ticket_by_id: GET /tickets/{id} happy path
  - test_get_ticket_by_id_not_found: GET /tickets/99999 devuelve 404
  - test_patch_ticket_not_found: PATCH /tickets/99999 devuelve 404
  - test_post_ticket_missing_required_fields: POST sin title, sin description, cuerpo vacío devuelven 422

Decisiones:
- Se añadieron directamente en test_acceptance.py en lugar de un archivo nuevo porque el usuario lo indicó explícitamente (anula la regla del taller)
- Los tests siguen el patrón exacto del archivo: fixture client con DB temporal, monkeypatch del clasificador donde se necesita
- test_patch_ticket_not_found y test_get_ticket_by_id_not_found no necesitan monkeypatch porque no crean tickets

Archivos tocados: tests/test_acceptance.py
Tests: 9/9 ✅

[2026-06-30 07:45] Cargar OPENROUTER_API_KEY desde .env al arrancar la app

Solicitado: Investigar por qué POST /tickets siempre devolvía FALLBACK_CLASSIFICATION (category=question, priority=P3, tags=[]) en vez de la clasificación real del LLM.

Implementado:
- Diagnóstico: nada llamaba a load_dotenv(), así que OPENROUTER_API_KEY nunca llegaba a os.environ al lanzar uvicorn aunque estuviera definida en .env; classify_ticket entraba siempre en el guard `if not api_key` y devolvía el fallback.
- Añadido `from dotenv import load_dotenv` y `load_dotenv()` en app/main.py (python-dotenv ya estaba en requirements.txt pero sin usar).
- Verificado manualmente con curl contra /tickets: la respuesta ahora trae category/priority/tags reales del modelo en vez del fallback.

Decisiones:
- load_dotenv() se llama en app/main.py (punto de entrada único de la app) en vez de en classifier.py, para que cualquier otra variable de entorno futura (DATABASE_URL, etc.) también se cargue automáticamente al arrancar.

Archivos tocados: app/main.py
Tests: no se han re-ejecutado en esta tarea (cambio verificado manualmente vía curl, no afecta a tests/test_acceptance.py que mockean classify_ticket)

---

[2026-06-29 13:00] Crear CLASSIFIER_PLAN.md con análisis de mejoras del clasificador

Solicitado: Analizar app/classifier.py y documentar tres opciones de mejora (prompt engineering, parámetros de inferencia, salida estructurada) en CLASSIFIER_PLAN.md.

Implementado:
- Creado CLASSIFIER_PLAN.md en la raíz con las tres opciones evaluadas
- Opción A: separación system/user + 3 few-shot de seed_tickets.json con clasificaciones esperadas
- Opción B: evaluación de temperature=0.0, top_p, seed=42, max_tokens=150 con tabla de soporte OpenRouter
- Opción C: json_object (v1) y json_schema con schema completo (v2), análisis de impacto en except y FALLBACK_CLASSIFICATION
- Sección Recomendación: orden B → A → C(v1), justificado como aditivo y sin romper tests

Decisiones:
- Few-shot seleccionados de seed_tickets.json por cubrir las tres categorías más distintas (urgent/P1, feature_request/P2, question/P3)
- top_p excluido de la recomendación porque la API de OpenAI desaconseja combinarlo con temperature=0
- Variante 2 (json_schema) marcada experimental porque gpt-oss-120b es open-source y el soporte de structured outputs vía OpenRouter no está garantizado

Archivos tocados: CLASSIFIER_PLAN.md
Tests: 5/5 ✅

[2026-06-29 12:30] Añadir GET /tickets/{id} y reorganizar app/main.py

Solicitado: Implementar el endpoint GET /tickets/{id} y reorganizar clases/endpoints en app/main.py.

Implementado:
- Añadido GET /tickets/{ticket_id}: devuelve 200 con el ticket o 404 si no existe
- Movida la clase TicketUpdate al inicio del archivo (antes de cualquier endpoint)
- Endpoints reordenados: POST /tickets → GET /tickets → GET /tickets/{id} → PATCH /tickets/{id}

Decisiones:
- TicketUpdate se mantiene en main.py (no en models.py) por ser específica del endpoint PATCH; solo se sube al bloque de schemas al inicio del archivo
- Se reutiliza el patrón session.get(Ticket, ticket_id) ya presente en update_ticket

Archivos tocados: app/main.py
Tests: 5/5 ✅

[2026-06-29 12:00] Mejoras en app/classifier.py

Solicitado: Implementar/revisar el módulo clasificador según SPEC.md §5 y añadir max_tokens=1024.

Implementado:
- Early exit cuando OPENROUTER_API_KEY no está definida (evita dos reintentos innecesarios)
- Añadido max_tokens=1024 a client.chat.completions.create(...)

Decisiones:
- La clave se lee con os.environ.get() fuera del bucle de reintentos; si es None se retorna FALLBACK_CLASSIFICATION inmediatamente en lugar de dejar que KeyError se propague y consuma los dos intentos
- max_tokens=1024 es suficiente para el JSON de clasificación y previene completions desbordadas

Archivos tocados: app/classifier.py
Tests: 5/5 ✅

[2026-06-29 11:30] Implementar GET /tickets/{id} y PATCH /tickets/{id}

Solicitado: Añadir los endpoints GET /tickets/{id} y PATCH /tickets/{id} en app/main.py siguiendo SPEC.md §4.

Implementado:
- Añadido `TicketUpdate` (BaseModel Pydantic) con campos opcionales `status` y `priority`
- Importados `HTTPException` y `ALLOWED_PRIORITIES`, `ALLOWED_STATUSES` de models.py
- Implementado `GET /tickets/{ticket_id}`: busca por id, devuelve 404 si no existe
- Implementado `PATCH /tickets/{ticket_id}`: valida enums, actualiza solo `status`/`priority`, actualiza `updated_at`, devuelve 404 si no existe y 422 si el valor no pertenece al enum

Decisiones:
- La validación de enum en PATCH devuelve 422 explícito via HTTPException antes de abrir la sesión DB, para no generar ruido innecesario
- `updated_at` se actualiza solo cuando hay un cambio efectivo en PATCH, conforme a la spec

Archivos tocados: app/main.py

Tests: 0/5 ❌ (esperado: todos los tests dependen de POST /tickets que aún no está implementado)

---

[2026-06-29 HH:MM] Implementar GET /tickets

Solicitado: Crear el endpoint GET /tickets en app/main.py siguiendo SPEC.md §4, usando el modelo Ticket de §3.

Implementado:
- Definido modelo `Ticket` como tabla SQLModel con todos los campos de SPEC.md §3 (id, title, description, category, priority, tags JSON, status, created_at, updated_at)
- Configurado engine SQLite leyendo `DATABASE_URL` desde entorno (con fallback a `triagebot.db`)
- Añadido `lifespan` handler (asynccontextmanager) que crea la tabla en startup
- Implementado `GET /tickets` con query params opcionales y combinables: `category`, `priority`, `status`
- Resultados ordenados por `created_at DESC`
- Instalados paquetes faltantes: `sqlmodel==0.0.38` y `SQLAlchemy==2.0.50`

Decisiones:
- Se usó `lifespan` en lugar del deprecado `@app.on_event("startup")` para compatibilidad con FastAPI moderno
- `tags` se almacena como columna JSON (`sa_column=Column(JSON)`) porque SQLite no tiene tipo array nativo
- Solo se tocó `app/main.py` según instrucción explícita del usuario

Archivos tocados: app/main.py

Tests: 0/5 ❌ (esperado: todos los tests dependen de POST /tickets que aún no está implementado; además hay un error de permisos en el directorio temp de pytest en esta máquina)
