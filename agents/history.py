"""
Historique — Sujets traités et images utilisées
Évite les doublons de sujets et d'images.

CHANGELOG v2 (Fix déduplication images):
- Séparation used_source_urls (Pexels/Pixabay) et used_wp_urls (WordPress).
  Avant : seed_WP écrasait les URLs source → is_image_already_used() ne matchait jamais.
  Maintenant : is_image_already_used() vérifie UNIQUEMENT used_source_urls.
  seed_image_history_from_wordpress() écrit dans used_wp_urls (référence uniquement).
- Migration automatique : used_urls existant détecté et réparti au premier chargement.
"""

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

DATA_DIR = "/root/garten-gefuehl-openclaw/data"
HISTORY_FILE = f"{DATA_DIR}/keywords/history.json"
IMAGE_HISTORY_FILE = f"{DATA_DIR}/images/image_history.json"

MIN_DAYS_BEFORE_SIMILAR_TOPIC = 60


# ============================================================
# HISTORIQUE DES SUJETS
# ============================================================

def load_topic_history() -> dict:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed_keywords": []}


def save_topic_history(history: dict):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def add_topic_to_history(keyword: str, category: str, post_url: str = ""):
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
    history = load_topic_history()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    keyword_words = set(keyword.lower().split())
    for entry in history.get("processed_keywords", []):
        if entry["date"] >= cutoff[:10]:
            entry_words = set(entry["keyword_lower"].split())
            overlap = keyword_words & entry_words
            similarity = len(overlap) / max(len(keyword_words), 1)
            if similarity >= 0.6:
                print(f"[Historique] ⚠️ Sujet trop récent : '{entry['keyword']}' traité le {entry['date']}")
                return True
    return False


# ============================================================
# HISTORIQUE DES IMAGES
# ============================================================

def load_image_history() -> dict:
    """Charge l'historique. Migration auto si ancienne structure détectée."""
    if not os.path.exists(IMAGE_HISTORY_FILE):
        return {"used_source_urls": [], "used_wp_urls": []}

    with open(IMAGE_HISTORY_FILE, "r", encoding="utf-8") as f:
        h = json.load(f)

    # Migration : ancienne structure avec used_urls mélangées
    if "used_urls" in h and "used_source_urls" not in h:
        source_urls = []
        wp_urls = []
        for url in h.get("used_urls", []):
            if any(k in url for k in ["pexels.com", "pixabay.com", "images.pexels", "cdn.pixabay"]):
                source_urls.append(url)
            else:
                wp_urls.append(url)
        h["used_source_urls"] = source_urls
        h["used_wp_urls"] = wp_urls
        del h["used_urls"]
        save_image_history(h)
        print(f"[Historique] Migration : {len(source_urls)} URLs source, {len(wp_urls)} URLs WP")

    return h


def save_image_history(history: dict):
    os.makedirs(os.path.dirname(IMAGE_HISTORY_FILE), exist_ok=True)
    with open(IMAGE_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def is_image_already_used(image_url: str) -> bool:
    """
    Vérifie si une URL source (Pexels/Pixabay) a déjà été utilisée.
    Vérifie UNIQUEMENT used_source_urls — jamais les URLs WordPress.
    """
    history = load_image_history()
    url_end = image_url.split("/")[-1].split("?")[0]

    for used in history.get("used_source_urls", []):
        used_end = used.split("/")[-1].split("?")[0]
        if url_end == used_end or image_url == used:
            return True
    return False


def add_image_to_history(image_url: str, keyword: str):
    """Ajoute une URL source (Pexels/Pixabay) à used_source_urls."""
    history = load_image_history()
    if image_url not in history.get("used_source_urls", []):
        history.setdefault("used_source_urls", []).append(image_url)
        # Garder max 1000 URLs source
        if len(history["used_source_urls"]) > 1000:
            history["used_source_urls"] = history["used_source_urls"][-1000:]
        save_image_history(history)


def add_wp_url_to_history(wp_url: str):
    """Ajoute une URL WordPress à used_wp_urls (référence, pas déduplication)."""
    history = load_image_history()
    if wp_url not in history.get("used_wp_urls", []):
        history.setdefault("used_wp_urls", []).append(wp_url)
        if len(history["used_wp_urls"]) > 1000:
            history["used_wp_urls"] = history["used_wp_urls"][-1000:]
        save_image_history(history)
