# CLASSIFIER_PLAN.md

## Opción A — Prompt engineering avanzado

**Descripción:** Reestructurar el prompt separando roles system/user y añadir tres ejemplos few-shot reales de `seed_tickets.json`.

**Complejidad:** Baja

**Impacto esperado:** Reduce clasificaciones incorrectas al anclar el modelo con ejemplos reales del dominio; las etiquetas serán más consistentes en idioma y formato. Se mediría comparando el porcentaje de respuestas que coinciden con la clasificación esperada en un conjunto de evaluación manual sobre `seed_tickets.json`.

**Compatibilidad con los tests de aceptación:** Sí. Los tests mockean `classify_ticket` con `monkeypatch` antes de que se ejecute ninguna llamada al LLM; el prompting interno no afecta a ningún test.

**Cambios en `app/classifier.py`:**
- Extraer las instrucciones a una constante `SYSTEM_PROMPT` con role `"system"`
- Convertir el mensaje del usuario a un `user_prompt` de una sola línea con el título y descripción
- Pasar `messages=[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":user_prompt}]`
- Incluir tres ejemplos few-shot en el cuerpo del system prompt

**Código propuesto:**

```python
SYSTEM_PROMPT = """Eres un sistema de clasificación de tickets de soporte técnico.
Devuelve EXCLUSIVAMENTE un objeto JSON con exactamente estos tres campos:
- "category": uno de ["bug", "feature_request", "question", "urgent"]
- "priority": uno de ["P1", "P2", "P3"]  (P1=urgente, P2=importante, P3=normal)
- "tags": lista de máximo 5 strings en minúscula, máximo 30 caracteres cada uno

No incluyas markdown, explicaciones ni texto fuera del JSON.
Formato de salida esperado:
{"category": "bug", "priority": "P1", "tags": ["login", "error_500"]}

Si no puedes clasificar con certeza, devuelve:
{"category": "question", "priority": "P3", "tags": []}

Ejemplos:

Título: La VPN rechaza a todo el equipo de teletrabajo
Descripción: Desde primera hora ninguno de los que trabajamos en remoto podemos conectar a la VPN. Sale 'authentication failed' aunque la contraseña es correcta.
Respuesta: {"category": "urgent", "priority": "P1", "tags": ["vpn", "autenticación", "teletrabajo", "acceso-remoto"]}

Título: Añadir filtro por estado en el listado de pedidos
Descripción: Me vendría muy bien poder filtrar los pedidos por estado (pendiente, enviado, entregado) para no revisarlos todos uno a uno.
Respuesta: {"category": "feature_request", "priority": "P2", "tags": ["filtro", "pedidos", "listado", "ux"]}

Título: ¿Cómo solicito acceso de solo lectura al cuadro de mando de dirección?
Descripción: Para preparar un informe necesito consultar el panel de dirección, aunque sea solo de lectura. ¿Cómo pido ese permiso?
Respuesta: {"category": "question", "priority": "P3", "tags": ["acceso", "cuadro-de-mando", "permisos"]}"""


def classify_ticket(title: str, description: str) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return FALLBACK_CLASSIFICATION

    user_prompt = f"Título: {title}\nDescripción: {description}"

    for _ in range(2):
        try:
            client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
            )
            resp = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1024,
            )
            raw = json.loads(resp.choices[0].message.content)
            if raw.get("category") not in ALLOWED_CATEGORIES:
                return FALLBACK_CLASSIFICATION
            if raw.get("priority") not in ALLOWED_PRIORITIES:
                return FALLBACK_CLASSIFICATION
            tags = raw.get("tags", [])
            if not isinstance(tags, list):
                return FALLBACK_CLASSIFICATION
            tags = [str(t)[:30] for t in tags[:5]]
            return {"category": raw["category"], "priority": raw["priority"], "tags": tags}
        except Exception:
            continue
    return FALLBACK_CLASSIFICATION
```

**Riesgos:**
- El system prompt añade ~130 tokens a cada llamada (coste marginal por petición)
- Algunos backends de OpenRouter combinan system+user en modelos que no soportan el rol `"system"` nativamente; en ese caso el comportamiento es equivalente al actual pero no peor

---

## Opción B — Parámetros de inferencia

**Descripción:** Añadir `temperature=0.0` y ajustar `max_tokens` al `chat.completions.create` para maximizar determinismo y reducir respuestas con formato incorrecto.

**Complejidad:** Baja

**Impacto esperado:** Reduce la variabilidad en el formato de salida (JSON con markdown envuelto, texto extra después del cierre `}`). Con `temperature=0` el modelo siempre elige el token de mayor probabilidad. Se mediría por la tasa de activaciones de `FALLBACK_CLASSIFICATION` en producción.

**Compatibilidad con los tests de aceptación:** Sí. Los tests mockean `classify_ticket` completamente; los parámetros de inferencia no llegan a ejecutarse.

**Parámetros evaluados:**

| Parámetro | Valor recomendado | Justificación | Soporte OpenRouter |
|-----------|-------------------|---------------|--------------------|
| `temperature` | `0.0` | Determinismo máximo; la clasificación es categórica, no creativa | ✅ Universal |
| `top_p` | no aplicar | Con `temperature=0`, `top_p` es redundante; la API de OpenAI desaconseja combinarlos | — |
| `seed` | `42` | Intenta reproducibilidad entre llamadas idénticas | ⚠️ No garantizado para `gpt-oss-120b` vía OpenRouter; el campo se acepta pero puede ignorarse |
| `max_tokens` | `150` | El JSON máximo es ~100 tokens (5 tags × 30 chars); reducir de 1024 ahorra coste y evita respuestas largas con texto adicional | ✅ Universal |

**Cambios en `app/classifier.py`:**
- Añadir `temperature=0.0` al `chat.completions.create`
- Cambiar `max_tokens=1024` a `max_tokens=150`
- Opcionalmente añadir `seed=42` (mejora trazabilidad aunque el efecto sea no garantizado)

**Código propuesto:**

```python
resp = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=150,
    temperature=0.0,
    seed=42,
)
```

**Riesgos:**
- `max_tokens=150` puede truncar respuestas con tags muy largos si el modelo genera más de 5 (mitigado por la validación posterior `tags[:5]` y `str(t)[:30]`)
- `seed` no está especificado en el contrato de OpenRouter para modelos open-source; no depender de él para reproducibilidad garantizada
- `temperature=0` con ciertos modelos cuantizados puede aumentar la probabilidad de loops de token en respuestas muy largas (no aplica con `max_tokens=150`)

---

## Opción C — Salida estructurada (JSON garantizado)

**Descripción:** Usar el parámetro `response_format` del SDK de OpenAI para forzar que la respuesta sea JSON válido, eliminando fallos de `json.loads`.

**Complejidad:** Media

**Impacto esperado:** Elimina casi por completo los `JSONDecodeError` (actualmente la causa más frecuente de activar `FALLBACK_CLASSIFICATION`). Se mediría por la reducción de errores de parseo en logs de producción.

**Compatibilidad con los tests de aceptación:** Sí para variante 1 (`json_object`). Parcial para variante 2 (`json_schema`): si OpenRouter no lo soporta para el modelo actual, lanzaría HTTP 400 en producción, que el `except Exception` capturaría activando el fallback; los tests no se ven afectados porque mockean `classify_ticket`.

### Variante 1 — `response_format={"type": "json_object"}` (JSON mode)

Garantiza JSON válido sintácticamente pero **no garantiza el schema** (pueden faltar campos o tener tipos incorrectos). La validación posterior en `classifier.py` sigue siendo necesaria.

**Soporte para `openai/gpt-oss-120b` vía OpenRouter:** ✅ Compatible — `json_object` es la variante más ampliamente soportada por OpenRouter para modelos de la familia GPT.

### Variante 2 — `response_format={"type": "json_schema", ...}` (Structured Outputs)

Garantiza JSON válido Y conforme al schema definido. Requiere soporte explícito del modelo para "Structured Outputs" (introducido en GPT-4o, agosto 2024). `openai/gpt-oss-120b` es un modelo open-source ruteado por OpenRouter — el soporte de schema validation depende del backend subyacente y no está garantizado.

**Soporte para `openai/gpt-oss-120b` vía OpenRouter:** ⚠️ Incierto — OpenRouter puede aceptar el parámetro sin validarlo, o rechazarlo con HTTP 400.

**JSON Schema completo para variante 2:**

```json
{
  "name": "ticket_classification",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "category": {
        "type": "string",
        "enum": ["bug", "feature_request", "question", "urgent"]
      },
      "priority": {
        "type": "string",
        "enum": ["P1", "P2", "P3"]
      },
      "tags": {
        "type": "array",
        "items": {
          "type": "string",
          "maxLength": 30
        },
        "maxItems": 5
      }
    },
    "required": ["category", "priority", "tags"],
    "additionalProperties": false
  }
}
```

**Impacto en el bloque `except` y `FALLBACK_CLASSIFICATION`:**
- **Variante 1:** `json.loads` sigue siendo necesario pero nunca lanzará `JSONDecodeError`. El bloque `except` sigue protegiendo contra errores de red, auth y campos fuera de enum.
- **Variante 2 (si funciona):** `json.loads` sigue siendo necesario; las validaciones de enum se vuelven redundantes pero son defensivas y deben mantenerse. El bloque `except` captura el caso donde OpenRouter no soporte el schema (HTTP 400).
- **`FALLBACK_CLASSIFICATION`** sigue siendo necesario en ambas variantes para errores de red y autenticación.

**Cambios en `app/classifier.py`:**
- Añadir `response_format={"type": "json_object"}` al `chat.completions.create` (variante 1)
- Para variante 2: extraer `RESPONSE_SCHEMA` como constante de módulo y pasarla como `response_format`
- Mantener `json.loads`, las validaciones de campos, el bloque `except` y `FALLBACK_CLASSIFICATION`

**Código propuesto (variante 1 — recomendada):**

```python
resp = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=150,
    temperature=0.0,
    response_format={"type": "json_object"},
)
```

**Código propuesto (variante 2 — experimental):**

```python
RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "ticket_classification",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["bug", "feature_request", "question", "urgent"]},
                "priority": {"type": "string", "enum": ["P1", "P2", "P3"]},
                "tags": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 30},
                    "maxItems": 5,
                },
            },
            "required": ["category", "priority", "tags"],
            "additionalProperties": False,
        },
    },
}

resp = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=150,
    temperature=0.0,
    response_format=RESPONSE_SCHEMA,
)
```

**Riesgos:**
- `json_object` no garantiza que los campos requeridos estén presentes; la validación posterior sigue siendo crítica
- `json_schema` con `strict=True` puede rechazar schemas con `maxLength` en items de array (no todos los proveedores lo implementan completamente)
- Si OpenRouter no soporta `response_format` para `gpt-oss-120b`, ambas variantes lanzarán HTTP 400, que `except Exception` capturará activando el retry y el fallback — comportamiento degradado pero seguro

---

## Recomendación

Implementar las tres opciones en este orden:

1. **Opción B primero** (parámetros de inferencia): cambio de dos líneas, riesgo cero para los tests y la firma pública, impacto inmediato en determinismo. Añadir `temperature=0.0`, bajar `max_tokens` a `150` y `seed=42`.

2. **Opción A segundo** (prompt engineering): separar system/user e incorporar los tres few-shot. Complementa a B porque el modelo con temperatura 0 extrae más señal de los ejemplos.

3. **Opción C variante 1** (json_object): añadir `response_format={"type": "json_object"}` como capa de seguridad adicional. No implementar variante 2 hasta confirmar soporte de OpenRouter para `gpt-oss-120b` mediante una prueba empírica.

La combinación B+A+C(v1) es aditiva: cada capa refuerza a la anterior sin modificar la firma pública de `classify_ticket(title, description) -> dict` ni romper ningún test de aceptación.
