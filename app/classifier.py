import json
import os

from openai import OpenAI

from app.models import ALLOWED_CATEGORIES, ALLOWED_PRIORITIES

FALLBACK_CLASSIFICATION = {"category": "question", "priority": "P3", "tags": []}

MODEL       = os.environ.get("CLASSIFIER_MODEL",       "openai/gpt-oss-120b")
TEMPERATURE = float(os.environ.get("CLASSIFIER_TEMPERATURE", "0.1"))
MAX_TOKENS  = int(os.environ.get("CLASSIFIER_MAX_TOKENS",    "500"))
SEED        = int(os.environ.get("CLASSIFIER_SEED",          "42"))

SYSTEM_PROMPT = f"""Eres un sistema de clasificación de tickets de soporte técnico.
Devuelve EXCLUSIVAMENTE un objeto JSON con exactamente estos tres campos:
- "category": uno de {sorted(ALLOWED_CATEGORIES)}
- "priority": uno de {sorted(ALLOWED_PRIORITIES)}  (P1=urgente, P2=importante, P3=normal)
- "tags": lista de máximo 5 strings en minúscula, máximo 30 caracteres cada uno

No incluyas markdown, explicaciones ni texto fuera del JSON.
Formato de salida esperado:
{{"category": "bug", "priority": "P1", "tags": ["login", "error_500"]}}

Si no puedes clasificar con certeza, devuelve:
{{"category": "question", "priority": "P3", "tags": []}}

Ejemplos:

Título: La VPN rechaza a todo el equipo de teletrabajo
Descripción: Desde primera hora ninguno de los que trabajamos en remoto podemos conectar a la VPN. Sale 'authentication failed' aunque la contraseña es correcta.
Respuesta: {{"category": "urgent", "priority": "P1", "tags": ["vpn", "autenticación", "teletrabajo", "acceso-remoto"]}}

Título: Añadir filtro por estado en el listado de pedidos
Descripción: Me vendría muy bien poder filtrar los pedidos por estado (pendiente, enviado, entregado) para no revisarlos todos uno a uno.
Respuesta: {{"category": "feature_request", "priority": "P2", "tags": ["filtro", "pedidos", "listado", "ux"]}}

Título: ¿Cómo solicito acceso de solo lectura al cuadro de mando de dirección?
Descripción: Para preparar un informe necesito consultar el panel de dirección, aunque sea solo de lectura. ¿Cómo pido ese permiso?
Respuesta: {{"category": "question", "priority": "P3", "tags": ["acceso", "cuadro-de-mando", "permisos"]}}"""


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
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                seed=SEED,
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
