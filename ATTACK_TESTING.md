# TriageBot — Guía de pruebas de robustez (casos de ataque y bugs)

Guía manual de QA/pentest informal para verificar cómo se comporta TriageBot
ante inputs maliciosos o mal formados. No reemplaza `tests/test_acceptance.py`
(que se mockean y no pegan al LLM real ni al servidor vivo): esto se ejecuta
manualmente contra un servidor en local (`uvicorn app.main:app --reload`),
idealmente con una base de datos de prueba, no `triagebot.db` con datos reales.

Acompaña a este documento el script `attack_tests.py`, que automatiza los
puntos 1, 2, 3, 4, 5, 8, 9 y 10.

---

## 1. Title vacío o solo espacios

```bash
curl -X POST localhost:8000/tickets -H "Content-Type: application/json" \
  -d '{"title": "", "description": "algo"}'

curl -X POST localhost:8000/tickets -H "Content-Type: application/json" \
  -d '{"title": "   ", "description": "algo"}'
```

SPEC.md exige "longitud 1–200 tras trim". El caso vacío debe dar `422`
obviamente. El interesante es el de solo espacios: si la validación Pydantic
mide `len(title)` sin hacer antes `.strip()`, "   " pasaría como válido
(longitud 3) y crearía un ticket con título en blanco — ese es el bug a cazar.

Repite la misma prueba contra `POST /tickets/form` (el endpoint HTMX), porque
es fácil que la validación esté duplicada de forma inconsistente entre el
JSON y el form.

**Esperado:** `422` en ambos casos, en ambos endpoints.

---

## 2. Title de 5000 caracteres (límites de longitud)

El límite real de `title` es 200, el de `description` es 5000 (SPEC.md §3).
Prueba el límite exacto y el +1 en ambos campos:

```bash
python3 -c "print('a'*201)"  # title justo por encima del límite -> 422
python3 -c "print('a'*200)"  # title en el límite -> 201
python3 -c "print('a'*5001)" # description por encima del límite -> 422
```

Si envías un `description` de 5000 caracteres con emojis o saltos de línea
mezclados, comprueba que el conteo de longitud se hace sobre caracteres
Python (`len(str)`) y no sobre bytes. Si en algún punto se mide en bytes, un
texto con tildes o emojis fallará el límite de forma inconsistente con lo que
ve el usuario en el textarea.

**Esperado:** `201` en el límite exacto, `422` un carácter por encima.

---

## 3. Emojis y caracteres unicode no latinos

```json
{"title": "🔥 urgente 紧急情况 مرحبا", "description": "prueba RTL y CJK"}
```

Comprobar:

- Que SQLite lo guarda y devuelve sin corromper (no mojibake al recargar
  `GET /tickets`).
- Que el tablero HTML lo renderiza bien.
- Que el clasificador no revienta al construir el prompt con caracteres
  no-ASCII (si peta, debería caer en el fallback, nunca en un `500`).

También merece la pena probar un null byte (`"título\x00malicioso"`), porque
algunos drivers de BD fallan de forma fea con esto en vez de simplemente
rechazarlo.

**Esperado:** se guarda y se recupera idéntico; nunca `500`.

---

## 4. HTML/JS en la descripción (XSS potencial)

```
<script>alert(document.cookie)</script>
<img src=x onerror=alert(1)>
"><svg/onload=alert(1)>
```

La verificación correcta no es mirar con DevTools (eso ya muestra el DOM
parseado y escapado), sino hacer "ver código fuente" de la página después de
crear el ticket y confirmar que aparece `&lt;script&gt;` en vez de
`<script>`. Jinja2 autoescapa por defecto en `TemplateResponse`, así que si
esto falla, busca en los templates algún `|safe` puesto sin querer, o algún
sitio donde se construya HTML con f-strings en vez de Jinja2.

Prueba el mismo payload también en `title`. Si quieres ser exhaustivo, simula
que el LLM devuelve un tag malicioso (`tags: ["<script>x</script>"]`)
monkeypatcheando `classify_ticket` — los tags no son input directo del
usuario, pero sí contenido no confiable que acaba renderizado.

**Esperado:** el payload aparece siempre escapado en el HTML servido; nunca
ejecutable.

---

## 5. Inyección SQL básica

```bash
curl -X POST localhost:8000/tickets -H "Content-Type: application/json" \
  -d '{"title": "x", "description": "y'"'"'; DROP TABLE ticket; --"}'

curl "localhost:8000/tickets/board?category=bug' OR '1'='1"
```

Con SQLModel/SQLAlchemy usando queries parametrizadas esto debería ser
inofensivo (se trata como literal de string). Lo que hay que auditar es el
código: busca cualquier `session.exec(text(...))` o construcción del filtro
con f-strings/`.format()` en lugar de los métodos del ORM
(`.where(Ticket.category == category)`). Si encuentras eso, hay riesgo real.

**Esperado:** la tabla `ticket` sigue intacta después del intento; el `GET
/tickets` posterior sigue devolviendo `200`.

---

## 6. LLM caído (simulación)

Tres formas de simularlo, de menor a mayor realismo:

1. **Sin key.** `unset OPENROUTER_API_KEY` antes de levantar `uvicorn` → según
   DEV_LOG, `classify_ticket` debería hacer early exit y devolver el fallback
   sin reintentos.
2. **Key inválida.** `OPENROUTER_API_KEY=invalida` → falla la autenticación
   real, debe reintentar una vez y luego caer al fallback.
3. **Sin red.** Cambia temporalmente `base_url` a algo que no resuelve
   (`http://localhost:1/`) para simular timeout/conexión rechazada.

En los tres casos, `POST /tickets` debe devolver siempre `201` con
`{"category": "question", "priority": "P3", "tags": []}`, nunca un `5xx`.
Revisa los logs para confirmar que el reintento ocurre exactamente una vez
antes del fallback, ni cero ni dos.

**Esperado:** siempre `201` con fallback exacto; un único reintento visible
en logs.

---

## 7. Mismo ticket enviado dos veces seguidas

No hay idempotencia en la spec, así que lo esperable es que se creen dos
tickets con IDs distintos — no es un bug en sí. Lo que sí hay que comprobar
es el comportamiento de la UI: doble click rápido en "Crear ticket", ¿el
botón se deshabilita mientras la petición está en vuelo o se puede disparar
dos veces sin querer?

Si quieres mitigarlo, un `hx-disabled-elt="this"` en el botón es la solución
típica con HTMX.

**Esperado:** dos tickets distintos creados correctamente; sin estado de UI
colgado ni formulario duplicado.

---

## 8. IDs malformados (-1, abc, 99999999999...)

```bash
curl localhost:8000/tickets/-1                          # int válido negativo -> 404
curl localhost:8000/tickets/abc                          # tipo inválido -> 422 automático de FastAPI
curl localhost:8000/tickets/99999999999999999999999999   # int gigante -> 404/422, nunca 500
```

`GET /tickets/abc` debería ser rechazado por FastAPI antes de llegar a tu
código, gracias al tipado `int` del path param. Repite el mismo patrón contra
`PATCH /tickets/{id}` con esos mismos IDs.

**Esperado:** `404` para IDs válidos pero inexistentes, `422` para IDs no
convertibles a `int`; nunca `500`.

---

## 9. PATCH con valores inválidos

```json
{"status": "inventado"}
{"priority": "P9"}
{"status": "OPEN"}
{"status": ""}
```

Todos deben dar `422`. El caso de `"OPEN"` en mayúsculas es el más fácil de
pasar por alto: SPEC.md es explícito en que los enums son case-sensitive, así
que si la validación hace algo como `.lower()` antes de comparar, este caso
pasaría incorrectamente.

**Esperado:** `422` en los cuatro casos.

---

## 10. 20 POSTs concurrentes

Con SQLite solo hay un writer a la vez, así que cierta serialización/latencia
es normal y esperable bajo 20 peticiones simultáneas. Lo que **no** es
aceptable es ver excepciones tipo `database is locked` sin manejar, IDs
duplicados, o cualquier `500`.

Si aparece eso, la solución típica es activar WAL mode en SQLite o subir el
`timeout` del engine de SQLAlchemy.

**Esperado:** 20/20 respuestas `201`, sin colisión de IDs.

---

## Cómo ejecutar la suite automatizada

```bash
pip install requests --break-system-packages
uvicorn app.main:app --reload      # en otra terminal, idealmente con DB de prueba
python3 attack_tests.py
```

El script cubre los puntos 1, 2, 3, 4, 5, 8, 9 y 10. Los puntos 6 (LLM caído)
y 7 (doble envío) se hacen manualmente: el 6 requiere manipular el entorno
antes de levantar el servidor, y el 7 es comportamiento de UI, no algo
verificable solo con peticiones HTTP.
