# DEV_LOG

[2026-07-01 01:00] Corrección de bugs detectados en code review (deadline/overdue)

Solicitado: Revisar y corregir los bugs encontrados en el code review de la feature de deadline y filtro "Solo vencidos".

Implementado:
- `app/main.py`: helper `_now_naive()` que centraliza `datetime.now(UTC).replace(tzinfo=None)`; elimina 5 duplicaciones del patrón en los handlers
- `app/main.py` `_seed_from_file`: `status_since=created_at.replace(tzinfo=None)` — los timestamps Z-suffix del seed file se almacenaban como tz-aware (CONFIRMADO: seed usa `"2026-03-27T09:42:23Z"`)
- `app/main.py` `_create_ticket`: `now = _now_naive()` en lugar de `datetime.now(UTC)` — `status_since` y `deadline` ahora ambos naive en memoria y en DB
- `app/main.py` `update_ticket`: `ticket.status_since = _now_naive()` y `ticket.updated_at = _now_naive()` — consistente con el resto de escrituras
- `app/main.py` `tickets_table`: `int(technician_id)` envuelto en try/except con `HTTPException(422)` — la old anotación `int | None` de FastAPI validaba automáticamente; la nueva `str | None` no lo hace
- `app/main.py` `tickets_table`: `now = _now_naive()` capturado una vez y pasado a `_query_tickets(now=now)` y al contexto de template — elimina el skew entre el filtro SQL y el rendering de badges "Vencido"
- `app/main.py` `_query_tickets`: acepta parámetro `now: datetime | None` opcional; `~Ticket.status.in_(["closed"])` → `Ticket.status != "closed"`
- `app/db.py` `_get_engine`: `_engine_url = url` ahora se asigna DESPUÉS de `_engine = create_engine(...)` — evita race condition donde un segundo hilo veía la URL asignada pero engine aún None y retornaba None

Decisiones:
- `_now_naive()` centraliza la lógica de timezone-stripping: un único sitio a cambiar si la estrategia evoluciona (p.ej., migrar a comparaciones tz-aware)
- NULL deadline en el filtro overdue es correcto per spec: tickets sin deadline no están vencidos
- `raise ... from exc` en el except para cumplir con ruff B904

Archivos tocados: app/main.py, app/db.py
Tests: 10/10 ✅

[2026-07-01 00:00] Deadline automático por prioridad + status_since

Solicitado: Añadir fecha límite calculada a partir de la prioridad (P1=hoy, P2=mañana, P3=+2 días) y campo status_since que registra cuándo cambió de estado el ticket; filtro "Solo vencidos" en el tablero.

Implementado:
- `app/models.py`: campos `deadline: datetime | None` y `status_since: datetime | None` en `Ticket`; ambos expuestos en `TicketResponse`
- `app/db.py`: función `_migrate_columns` que añade las columnas mediante `ALTER TABLE` en DBs existentes (detecta columnas ausentes vía `PRAGMA table_info`); se llama desde `_get_engine` tras `create_all`
- `app/main.py`: helper `_calculate_deadline(priority, base)` (P1=0d, P2=1d, P3=2d, end-of-day UTC); `_create_ticket` y `_seed_from_file` ahora poblando `deadline` y `status_since`; `update_ticket` recalcula `deadline` si cambia `priority` y actualiza `status_since` solo si `status` cambia realmente; `_query_tickets` acepta `overdue: str | None` (filtra `deadline < now AND status != closed`); endpoints `/tickets/table`, `/tickets/form` y `/` reciben `now=datetime.now(UTC)` para el template
- `templates/_tickets_table.html`: nueva columna "Fecha límite" (9 columnas, colspan actualizado de 8 a 9); fila en `bg-red-50` y badge "Vencido" para tickets vencidos; sublínea "desde {fecha}" en celda de estado usando `status_since`
- `templates/index.html`: nuevo filtro "Vencimiento" (select Todos / Solo vencidos) que envía `overdue=true` a `GET /tickets/table`
- `SPEC.md` y `SPEC_FRONTEND.md`: actualizados con los nuevos campos y comportamientos

Decisiones:
- `_migrate_columns` se llama dentro de `_get_engine` (no en `lifespan`) para que los tests con DB temporal también reciban la migración antes de cualquier petición
- `status_since` solo se actualiza si el valor de `status` realmente cambia, evitando sobrescribir la fecha cuando PATCH no modifica el estado
- `deadline` se recalcula desde `ticket.created_at` (no desde `now`) cuando cambia la prioridad, para preservar el origen temporal del ticket
- El filtro overdue usa `str | None` en lugar de `bool` para compatibilidad con HTMX (que envía valores de select como strings vacíos, no como falsy booleans)
- Filas vencidas usan `bg-red-50` en lugar de `bg-red-100` para no opacar el contraste del resto de badges

Archivos tocados: app/models.py, app/db.py, app/main.py, templates/_tickets_table.html, templates/index.html, SPEC.md, SPEC_FRONTEND.md
Tests: 10/10 ✅

[2026-06-30 15:00] Seed automático de tickets desde seed_tickets.json

Solicitado: Cargar todos los tickets de seed_tickets.json al arrancar la app,
siguiendo SPEC.md, SPEC_FRONTEND.md y las convenciones de CLAUDE.md.

Implementado:
- `app/db.py`: añadida función pública `get_engine()` que devuelve el engine
  SQLite ya inicializado (necesario para obtener una sesión fuera de la inyección
  de dependencias de FastAPI)
- `app/main.py`: añadida función `_seed_from_file(session)` que comprueba si la
  DB está vacía y, si lo está, carga los 100 tickets de seed_tickets.json
  llamando a `classify_ticket` por cada uno (con fallback si no hay API key)
  y preservando el `created_at` original del JSON
- `app/main.py`: actualizado `lifespan` para abrir una sesión y llamar a
  `_seed_from_file` justo después de `init_db()`

Decisiones:
- Idempotente: si ya hay tickets en la DB, la función retorna inmediatamente
  sin tocar nada
- Se reutiliza `classify_ticket` (con su fallback integrado) en lugar de
  insertar datos sin clasificar, para que los tickets de demo sean realistas
  cuando hay `OPENROUTER_API_KEY` y aceptables (question/P3) cuando no la hay
- En tests la DB temporal está vacía al crear el TestClient, así que el seed
  se ejecuta con FALLBACK (sin API key); los tests siguen pasando porque
  ningún ticket de seed coincide con los filtros específicos que usan los tests

Archivos tocados: app/db.py, app/main.py
[2026-06-30 17:30] Nuevo endpoint GET /tickets/stats

Solicitado: Añadir endpoint JSON que devuelva conteos de tickets por categoría, prioridad y estado.

Implementado:
- Añadido modelo `TicketStats` (Pydantic) en `app/models.py` con tres campos `dict[str, int]`
- Importados `ALLOWED_CATEGORIES` y `TicketStats` en `app/main.py`
- Registrado `GET /tickets/stats` antes de `GET /tickets/{ticket_id}` para que la ruta estática no sea capturada por el parámetro dinámico
- Los conteos se inicializan a 0 para todos los valores de cada enum, garantizando respuesta estable aunque no haya tickets de algún tipo

Decisiones:
- El endpoint se coloca ANTES de `GET /tickets/{ticket_id}` porque FastAPI resuelve rutas por orden de registro y "stats" sería interpretado como un ticket_id (int) en caso contrario
- Se inicializan todos los enum-values a 0 para que la forma de la respuesta sea siempre predecible

Archivos tocados: app/models.py, app/main.py
Tests: 10/10 ✅

[2026-06-30 16:00] Añadir técnicos/responsables a tickets

Solicitado: Ampliar el modelo de datos con técnicos (uno o varios por ticket), filtrado por técnico en el tablero, selector de técnico activo en el header, gestión de técnicos desde la UI y endpoints de API.

Implementado:
- `app/models.py`: nuevos modelos `Technician` (tabla SQLite), `TicketTechnician` (tabla de enlace many-to-many), `TechnicianCreate`, `TechnicianResponse`; `TicketCreate` acepta `technician_ids: list[int] = []` (opcional, retrocompatible); `TicketResponse` incluye `technician_ids: list[int] = []`.
- `app/main.py`: helpers `_get_technician_ids`, `_set_technicians`, `_build_ticket_technicians`, `_ticket_to_response`; `_create_ticket` asigna técnicos tras el commit; `_query_tickets` acepta `technician_id` con join a `TicketTechnician`; `TicketUpdate` acepta `technician_ids`; endpoints JSON actualizados a `_ticket_to_response`; nuevos endpoints `POST /technicians` (JSON), `GET /technicians` (JSON), `POST /technicians/form` (HTMX).
- `templates/index.html`: selector "Técnico activo" en header top-right (incluido en `#ticket-filters`, filtra tabla al cambiar); multi-select de responsables en formulario de creación; card "Gestión de técnicos" con formulario HTMX para añadir técnicos y lista en vivo.
- `templates/_tickets_table.html`: columna "Responsables" con chips indigo por técnico asignado; colspan 7→8.
- `templates/_technicians_list.html`: nuevo partial para lista de técnicos (usado por HTMX en la sección de gestión).

Decisiones:
- Many-to-many via tabla enlace (`TicketTechnician`) en lugar de JSON array en el ticket, para mantener integridad referencial.
- `technician_ids` opcional con default `[]` en `TicketCreate` y `TicketResponse` para no romper ningún test existente.
- `_build_ticket_technicians` usa exactamente 2 queries para cualquier número de tickets (eficiencia).
- Selector de técnico vinculado al formulario `#ticket-filters` con `form="ticket-filters"` para que `hx-include="#ticket-filters"` lo capture automáticamente sin duplicar lógica HTMX.

Archivos tocados: app/models.py, app/main.py, templates/index.html, templates/_tickets_table.html, templates/_technicians_list.html (nuevo)
Tests: 10/10 ✅

[2026-06-30 14:10] Frontend paso 8: accesibilidad mínima (auditoría)

Solicitado: Ejecutar el paso 8 de SPEC_FRONTEND_PLAN.md: verificar accesibilidad
mínima (labels, name correctos, badges con texto visible).

Implementado:
- Auditoría de templates/index.html y templates/_tickets_table.html contra los 6
  puntos de SPEC_FRONTEND.md §10. Resultado: los 6 puntos ya se cumplían gracias
  al trabajo de los pasos 6 y 7 (labels enlazados por for/id, name correctos en
  inputs/selects, badges con texto + color, encabezados de tabla claros)
- No se modificó ningún archivo de código/template, este paso es de verificación

Decisiones:
- No se introdujeron cambios "por si acaso" (p. ej. scope="col" en los <th>) ya
  que no son requisito explícito del spec y el principio del proyecto es no añadir
  alcance no solicitado

Archivos tocados: SPEC_FRONTEND_PLAN.md, DEV_LOG.md
Tests: no aplica (sin cambios de código); el estado verde ya estaba confirmado
desde el paso 7

[2026-06-30 14:00] Frontend paso 7: completar templates/index.html

Solicitado: Ejecutar el paso 7 de SPEC_FRONTEND_PLAN.md: completar index.html con
el formulario de creación, los filtros y el contenedor que incluye la tabla,
conectando todo lo construido en los pasos 1-6.

Implementado:
- Reescrito templates/index.html: card "Crear ticket" (title + description +
  botón) con hx-post="/tickets/form", bloque de filtros (3 selects category/
  priority/status) con hx-get="/tickets/table", botón "Limpiar filtros", indicador
  de carga simple (.htmx-indicator), y `<div id="tickets-table">` con
  `{% include "_tickets_table.html" %}`
- Detectados y corregidos dos bugs de integración al conectar HTML real con HTMX:
  1. `tickets_table` (app/main.py): los `<select>` con opción "Todas..." envían
     `category=""` (no ausente), y `_query_tickets` solo trataba `None` como "sin
     filtro". Se normaliza `category or None` / `priority or None` / `status or
     None` en la llamada
  2. `create_ticket_form` (app/main.py): el fragmento de error devolvía
     `status_code=422`, pero HTMX por defecto no hace swap del DOM en respuestas
     no-2xx (solo dispara `htmx:responseError`), así que el mensaje de error nunca
     se vería en el navegador real. Se quitó el `status_code=422` (queda 200)

Decisiones:
- El botón "Limpiar filtros" es `type="reset"` + `hx-get="/tickets/table"` SIN
  `hx-include`, para no depender del orden entre el reset nativo del navegador y
  la lectura de valores por HTMX
- `hx-on::after-request="this.reset()"` limpia el formulario de creación tras
  cualquier respuesta; los atributos `required`/`maxlength` HTML ya bloquean en
  el navegador el envío de campos vacíos antes de llegar al servidor
- No se tocó `GET /tickets`, `POST /tickets` ni el resto de endpoints JSON

Archivos tocados: SPEC_FRONTEND_PLAN.md, templates/index.html, app/main.py,
DEV_LOG.md
Tests: 10/10 ✅ (pytest -q), ruff check . ✅
Verificación manual: GET /tickets/table?category= devuelve todos los tickets (no
vacío); POST /tickets/form con datos vacíos → 200 con mensaje de error visible;
crear ticket vía form → aparece en el tablero; GET / devuelve página completa con
formulario y filtros conectados a HTMX

[2026-06-30 13:45] Frontend paso 6: completar templates/_tickets_table.html

Solicitado: Ejecutar el paso 6 de SPEC_FRONTEND_PLAN.md: completar el renderizado
real de la tabla de tickets con Jinja2, badges, chips de tags y estado vacío.

Implementado:
- Reescrito templates/_tickets_table.html completo: loop Jinja2 sobre `tickets` en
  el `<tbody>`, sustituyendo el TODO
- Diccionarios Jinja2 (`{% set %}`) para traducir category/priority/status a texto
  en español y aplicar clases Tailwind de color (badge)
- P1 destaca visualmente con fondo rojo, anillo y negrita frente a P2 (ámbar) y P3
  (gris)
- Chips individuales para cada tag de `ticket.tags`
- Estado vacío ("Todavía no hay tickets. Crea el primer ticket para empezar.")
  cuando `tickets` está vacío
- Renderizado del mensaje de `error` (pasado desde POST /tickets/form en el paso 5)
  en un `<div>` visible antes de la tabla

Decisiones:
- Los badges siempre muestran texto además del color, para no depender solo del
  color (requisito de accesibilidad del spec)
- Se usan dict.get(...) en Jinja2 con un fallback al valor crudo del enum, para que
  un valor inesperado no rompa el render
- `ticket.created_at.strftime(...)` funciona porque `_query_tickets` devuelve
  objetos `Ticket` (SQLModel) reales, no JSON serializado

Archivos tocados: SPEC_FRONTEND_PLAN.md, templates/_tickets_table.html, DEV_LOG.md
Tests: 10/10 ✅ (pytest -q), ruff check . ✅
Verificación manual: GET /tickets/table renderiza filas reales con badges/chips;
filtro status=closed sigue funcionando; POST /tickets/form con datos vacíos
muestra el mensaje de error visible en el fragmento (422)

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

[2026-06-30 12:30] FASE 1 spec — catálogo de tests existentes en SPEC.md

Solicitado: Añadir sección "## 10. Tests" en SPEC.md con los tests ya existentes organizados por caso de uso (nombre, qué cubre, qué bug detectaría). Sin inventar tests nuevos.

Implementado:
- Añadida sección `## 10. Tests` al final de `SPEC.md` via Write (el archivo no tenía newline final, lo que hacía fallar Edit)
- Documentados los 10 tests existentes en 4 casos de uso: UC-1 POST /tickets (4 tests), UC-2 GET /tickets (2 tests), UC-3 GET /tickets/{id} (2 tests), UC-4 PATCH /tickets/{id} (3 tests)
- Cada entrada incluye archivo fuente, qué comportamiento cubre y qué regresión detectaría

Decisiones:
- `test_update_ticket_and_filter_by_status_priority_category` aparece en UC-2 y UC-4 porque el test cubre ambos endpoints en un solo flujo
- Write en lugar de Edit porque el archivo terminaba sin `\n` y el anchor del Edit no encontraba el texto final

Archivos tocados: SPEC.md
Tests: N/A (fase spec, sin ejecución de código)

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
