"""
Historique — Sujets traités et images utilisées
Évite les doublons de sujets et d'images.
"""

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

DATA_DIR = "/root/garten-gefuehl-openclaw/data"
HISTORY_FILE = f"{DATA_DIR}/keywords/history.json"
IMAGE_HISTORY_FILE = f"{DATA_DIR}/images/image_history.json"

# Délai minimum avant de re-traiter un sujet similaire (jours)
MIN_DAYS_BEFORE_SIMILAR_TOPIC = 60


def load_topic_history() -> dict:
    """Charge l'historique des sujets traités."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed_keywords": []}


def save_topic_history(history: dict):
    """Sauvegarde l'historique des sujets."""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def add_topic_to_history(keyword: str, category: str, post_url: str = ""):
    """Ajoute un sujet traité à l'historique."""
    history = load_topic_history()
    history["processed_keywords"].append({
        "keyword": keyword,
        "keyword_lower": keyword.lower(),
        "category": category,
        "date": date.today().isoformat(),
        "post_url": post_url
    })
    save_topic_history(history)
    print(f"[Historique] Sujet ajouté : '{keyword}' ({category})")


def is_topic_too_recent(keyword: str, days: int = MIN_DAYS_BEFORE_SIMILAR_TOPIC) -> bool:
    """Vérifie si un sujet similaire a été traité récemment."""
    history = load_topic_history()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    keyword_words = set(keyword.lower().split())

    for entry in history.get("processed_keywords", []):
        if entry["date"] >= cutoff[:10]:
            # Vérifier similarité (mots en commun)
            entry_words = set(entry["keyword_lower"].split())
            overlap = keyword_words & entry_words
            similarity = len(overlap) / max(len(keyword_words), 1)

            if similarity >= 0.6:  # 60% de mots en commun = trop similaire
                print(f"[Historique] ⚠️ Sujet trop récent : '{entry['keyword']}' traité le {entry['date']}")
                return True

    return False


# ============================================================
# HISTORIQUE DES IMAGES
# ============================================================

def load_image_history() -> dict:
    """Charge l'historique des URLs d'images utilisées."""
    if os.path.exists(IMAGE_HISTORY_FILE):
        with open(IMAGE_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"used_urls": []}


def save_image_history(history: dict):
    """Sauvegarde l'historique des images."""
    os.makedirs(os.path.dirname(IMAGE_HISTORY_FILE), exist_ok=True)
    with open(IMAGE_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def is_image_already_used(image_url: str) -> bool:
    """Vérifie si une image a déjà été utilisée."""
    history = load_image_history()
    # Comparer les URLs (ou les derniers segments pour robustesse)
    url_end = image_url.split("/")[-1].split("?")[0]  # Nom du fichier sans params

    for used in history.get("used_urls", []):
        used_end = used.split("/")[-1].split("?")[0]
        if url_end == used_end or image_url == used:
            return True
    return False


def add_image_to_history(image_url: str, keyword: str):
    """Ajoute une URL d'image à l'historique."""
    history = load_image_history()
    history["used_urls"].append(image_url)
    # Garder max 500 URLs
    if len(history["used_urls"]) > 500:
        history["used_urls"] = history["used_urls"][-500:]
    save_image_history(history)
