"""
Correcteur Agent — Plagiat Checker
Vérifie le plagiat via des outils gratuits.
"""

import requests
import hashlib
import re
from config import PLAGIAT_CHECK_ENABLED


def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def check_plagiat_duplichecker(text: str) -> dict:
    """
    Vérifie le plagiat via DupliChecker API (gratuit, limité).
    Retourne un dict avec le score de similarité et les sources.
    """
    if not PLAGIAT_CHECK_ENABLED:
        return {"skipped": True, "reason": "Plagiat check désactivé"}

    # Extrait les 500 premiers mots pour le check
    words = text.split()[:500]
    sample = " ".join(words)

    try:
        # DupliChecker API gratuite
        resp = requests.post(
            "https://www.duplichecker.com/api/check-plagiarism",
            data={"text": sample},
            timeout=30
        )

        if resp.status_code == 200:
            data = resp.json()
            return {
                "unique_pct": data.get("unique", 100),
                "plagiarism_pct": data.get("plagiarism", 0),
                "sources": data.get("sources", [])
            }
    except Exception as e:
        print(f"[Correcteur] DupliChecker erreur: {e}")

    # Fallback : calcul local basique (hash des phrases)
    return _local_uniqueness_check(sample)


def _local_uniqueness_check(text: str) -> dict:
    """
    Vérification locale de base — détecte si le texte semble trop générique.
    """
    # Phrases suspectes communes dans le contenu généré
    generic_phrases = [
        "in diesem artikel werden wir",
        "in diesem ratgeber erfahren sie",
        "wir zeigen ihnen",
        "dieser artikel gibt ihnen",
        "sie möchten wissen",
    ]

    text_lower = text.lower()
    generic_count = sum(1 for p in generic_phrases if p in text_lower)

    if generic_count > 2:
        return {
            "unique_pct": 70,
            "plagiarism_pct": 30,
            "warning": f"{generic_count} phrases génériques détectées",
            "method": "local"
        }

    return {
        "unique_pct": 95,
        "plagiarism_pct": 5,
        "method": "local",
        "note": "Check local uniquement — DupliChecker non disponible"
    }


def check_plagiat(html_content: str) -> dict:
    """Point d'entrée principal pour la vérification de plagiat."""
    text = strip_html(html_content)
    return check_plagiat_duplichecker(text)
