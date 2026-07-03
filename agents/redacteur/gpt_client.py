"""
Rédacteur Agent — GPT Client
Appelle GPT via OpenClaw Gateway (Codex OAuth) — pas de clé API pay-per-use.
"""

import os
import requests
from config import MODEL


def call_gpt(prompt: str) -> str:
    """
    Appelle GPT via OpenClaw Gateway local (port 18789).
    Utilise le quota Codex inclus dans GPT Plus — zéro coût supplémentaire.
    """
    gateway_url = os.getenv("OPENCLAW_GATEWAY_URL", "http://127.0.0.1:18789")
    gateway_token = os.getenv("OPENCLAW_GATEWAY_TOKEN", "")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {gateway_token}"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Du bist ein erfahrener deutscher Gartenredakteur. Du schreibst präzise, natürliche und SEO-optimierte Artikel auf Deutsch. Du folgst immer exakt dem vorgegebenen Format."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 4000,
        "temperature": 0.7
    }

    print(f"[Rédacteur] Appel GPT via OpenClaw Gateway ({MODEL})...")

    try:
        resp = requests.post(
            f"{gateway_url}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=120
        )

        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        else:
            raise Exception(f"OpenClaw Gateway erreur {resp.status_code}: {resp.text[:200]}")

    except requests.exceptions.ConnectionError:
        raise Exception(
            "Impossible de se connecter au OpenClaw Gateway. "
            "Vérifiez que le tunnel SSH est actif et que OpenClaw tourne sur le VPS."
        )
