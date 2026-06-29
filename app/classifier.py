import json
import os

from openai import OpenAI

from app.models import ALLOWED_CATEGORIES, ALLOWED_PRIORITIES

FALLBACK_CLASSIFICATION = {"category": "question", "priority": "P3", "tags": []}


def classify_ticket(title: str, description: str) -> dict:
    prompt = (
        "Eres un sistema de clasificación de tickets de soporte técnico. "
        "Devuelve EXCLUSIVAMENTE un JSON con tres campos: "
        "category (uno de: bug, feature_request, question, urgent), "
        "priority (uno de: P1, P2, P3), "
        "tags (lista de máx. 5 strings cortos en minúscula). "
        "No devuelvas explicaciones ni markdown. "
        "P1 = urgente, P2 = importante, P3 = normal.\n\n"
        f"Título: {title}\nDescripción: {description}"
    )
    for _ in range(2):
        try:
            client = OpenAI(
                api_key=os.environ["OPENROUTER_API_KEY"],
                base_url="https://openrouter.ai/api/v1",
            )
            resp = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": prompt}],
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
