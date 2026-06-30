# DEV_LOG

[2026-06-30 HH:MM] Fase A — Prompt engineering: separación system/user + few-shot

Solicitado: Aplicar la Opción A de CLASSIFIER_PLAN.md: extraer instrucciones a SYSTEM_PROMPT con role system, separar el mensaje de usuario, e incluir 3 ejemplos few-shot.

Implementado:
- Añadida constante de módulo SYSTEM_PROMPT construida con f-string: las listas de valores válidos se generan dinámicamente desde ALLOWED_CATEGORIES y ALLOWED_PRIORITIES (sin duplicar los enums)
- El prompt incluye formato de salida esperado, fallback explícito y 3 ejemplos few-shot (urgent/P1, feature_request/P2, question/P3) tomados de CLASSIFIER_PLAN.md
- Dentro de classify_ticket, el prompt monolítico se reemplaza por user_prompt = f"Título: {title}\nDescripción: {description}"
- messages pasa a tener dos roles: [{"role":"system","content":SYSTEM_PROMPT}, {"role":"user","content":user_prompt}]

Decisiones:
- SYSTEM_PROMPT como f-string (no string literal) para que sorted(ALLOWED_CATEGORIES) y sorted(ALLOWED_PRIORITIES) se evalúen al importar el módulo; si los enums cambian en models.py, el prompt se actualiza automáticamente
- Las llaves literales del JSON de ejemplo se escapan como {{ }} para no colisionar con la interpolación del f-string
- sorted() en las listas de enums para orden determinista en el prompt

Archivos tocados: app/classifier.py
Tests: 5/5 ✅

[2026-06-30 HH:MM] Fase B — Parámetros de inferencia via variables de entorno

Solicitado: Aplicar la Opción B de CLASSIFIER_PLAN.md: añadir temperature, max_tokens y seed al clasificador, haciéndolos configurables via env vars.

Implementado:
- Añadidas constantes de módulo en app/classifier.py: MODEL, TEMPERATURE, MAX_TOKENS, SEED leídas desde env vars con defaults
- MODEL = os.environ.get("CLASSIFIER_MODEL", "openai/gpt-oss-120b")
- TEMPERATURE = float(os.environ.get("CLASSIFIER_TEMPERATURE", "0.0"))
- MAX_TOKENS = int(os.environ.get("CLASSIFIER_MAX_TOKENS", "150"))
- SEED = int(os.environ.get("CLASSIFIER_SEED", "42"))
- Actualizado chat.completions.create para usar las constantes en lugar de valores hardcodeados
- Documentadas las 4 nuevas variables en la tabla de Variables de entorno de CLAUDE.md

Decisiones:
- Constantes a nivel de módulo (no dentro de la función) para que el valor se resuelva una sola vez al importar el módulo, no en cada llamada
- DEFAULT temperature=0.0 para maximizar determinismo en clasificación categórica
- DEFAULT max_tokens=150 suficiente para el JSON máximo (~100 tokens con 5 tags de 30 chars); reduce coste y evita respuestas largas con texto extra
- seed=42 mejora trazabilidad aunque OpenRouter no garantiza reproducibilidad para modelos open-source

Archivos tocados: app/classifier.py, CLAUDE.md
Tests: 5/5 ✅

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
