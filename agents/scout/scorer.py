"""
Scout Agent — Scorer
Score et sélection des meilleurs keywords.
Formule : Score = (volume × CPC) / concurrence + bonus/pénalités

CHANGELOG v2:
- Fix critique : competition normalisé en float partout
  (WordStream retourne "HIGH"/"MEDIUM"/"LOW" → max(str, float) plantait)
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from config import SCORING, HISTORY_FILE


def load_history() -> dict:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {"processed_keywords": []}


def save_history(history: dict):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def is_recently_processed(keyword: str, history: dict, days: int = 60) -> bool:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    for entry in history.get("processed_keywords", []):
        if entry["keyword"].lower() == keyword.lower() and entry["date"] >= cutoff:
            return True
    return False


def _normalize_competition(raw) -> float:
    """Normalise competition en float — supporte str et float."""
    if isinstance(raw, str):
        comp_map = {"HIGH": 0.8, "MEDIUM": 0.5, "LOW": 0.2, "UNKNOWN": 0.3}
        return comp_map.get(raw.upper(), 0.3)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.3


def filter_keywords(keywords_data: dict, volumes_data: dict, history: dict) -> List[dict]:
    filtered = []

    non_garden_terms = [
        "geöffnet", "öffnungszeiten", "lieferung", "bestellen", "kaufen",
        "online", "shop", "preis", "günstig", "angebot", "rabatt",
        "liefern", "versand", "expresslieferung",
        "müller", "aldi", "lidl", "rewe", "edeka", "penny", "obi",
        "hornbach", "bauhaus", "ikea", "amazon", "ambiente",
        "berlin", "münchen", "hamburg", "köln", "frankfurt",
        "wien", "wienhausen", "zürich", "animal crossing",
        "tattoo", "tätowierung", "hochzeit", "braut", "strauß hochzeit",
        "foto", "fotografie", "bilder", "tapete", "clipart",
        "basteln", "häkeln", "stricken",
        "jetzt geöffnet", "in der nähe", "nächste", "adresse",
        "telefon", "bewertung", "erfahrung",
    ]

    GARDEN_CONTEXT_TERMS = [
        "garten", "pflanz", "blum", "rose", "balkon", "terrasse",
        "beet", "topf", "erde", "dünger", "schneid", "pflege",
        "hochbeet", "sichtschutz", "kräuter", "gemüse", "rasen",
        "strauch", "staude", "zwiebel", "samen", "kompost"
    ]

    for kw_lower, kw_info in keywords_data.items():
        volume_info = volumes_data.get(kw_lower, {})

        # Cast défensif — les sources peuvent retourner des strings
        try:
            volume = float(volume_info.get("volume", 0) or 0)
        except (TypeError, ValueError):
            volume = 0

        if volume < 50:
            continue
        if is_recently_processed(kw_lower, history):
            continue
        if len(kw_lower.split()) < 2:
            continue

        has_exclusion = any(excl in kw_lower for excl in non_garden_terms)
        if has_exclusion:
            continue

        has_garden_context = any(term in kw_lower for term in GARDEN_CONTEXT_TERMS)
        if not has_garden_context:
            continue

        filtered.append({
            "keyword": kw_info["original"],
            "keyword_lower": kw_lower,
            "volume": int(volume_info.get("volume", 0) or 0),
            "cpc": float(volume_info.get("cpc", 0) or 0),
            "competition": _normalize_competition(volume_info.get("competition", 0)),
            "competition_level": volume_info.get("competition_level", "UNKNOWN"),
            "trend": float(volume_info.get("trend", 0) or 0),
            "sources": kw_info["sources"],
            "faq": kw_info.get("faq", [])
        })

    print(f"[Scout] Keywords après filtrage : {len(filtered)}")
    return filtered


def score_keywords(keywords: List[dict]) -> List[dict]:
    HIGH_INTENT_WORDS = [
        "tipps", "anleitung", "ideen", "pflege", "pflanzen", "gestalten",
        "richtig", "schneiden", "düngen", "gießen", "anlegen", "schritt",
        "wann", "wie", "beste", "schönste", "einfach", "richtig"
    ]

    for kw in keywords:
        try:
            volume = int(float(kw.get("volume", 0) or 0))
        except (TypeError, ValueError):
            volume = 0
        try:
            cpc = max(float(kw.get("cpc", 0) or 0), 0.01)
        except (TypeError, ValueError):
            cpc = 0.01
        competition = max(_normalize_competition(kw.get("competition", 0)), 0.01)

        base_score = (volume * cpc * SCORING["cpc_weight"]) / (competition * SCORING["competition_penalty"])

        try:
            trend_val = float(kw.get("trend", 0) or 0)
        except (TypeError, ValueError):
            trend_val = 0
        if trend_val > 0:
            base_score *= (1 + SCORING["trend_bonus"])

        sources = kw.get("sources", [])
        if "google" in sources and "pinterest" in sources:
            base_score *= (1 + SCORING["dual_source_bonus"])

        if len(kw.get("faq", [])) > 0:
            base_score *= (1 + SCORING["faq_bonus"])

        if kw["competition_level"] == "HIGH":
            base_score *= 0.5

        word_count = len(kw["keyword_lower"].split())
        if word_count >= 3:
            base_score *= 1.3
        if word_count >= 4:
            base_score *= 1.2

        has_intent = any(word in kw["keyword_lower"] for word in HIGH_INTENT_WORDS)
        if has_intent:
            base_score *= 1.5

        kw["score"] = round(base_score, 2)

    keywords.sort(key=lambda x: x["score"], reverse=True)
    return keywords


def select_best_keyword(scored_keywords: List[dict], category_name: str) -> dict:
    if not scored_keywords:
        return None

    category_lower = category_name.lower()
    INTENT_WORDS = [
        "tipps", "ideen", "pflege", "anleitung", "gestalten",
        "pflanzen", "schneiden", "düngen", "anlegen", "richtig",
        "beste", "schönste", "einfach", "wann", "wie", "wenig",
        "mehrjährig", "winterhart", "schnellwachsend", "deko"
    ]

    for kw in scored_keywords[:50]:
        has_intent = any(w in kw["keyword_lower"] for w in INTENT_WORDS)
        has_category = category_lower in kw["keyword_lower"]
        if has_intent and has_category:
            return kw

    for kw in scored_keywords[:50]:
        has_intent = any(w in kw["keyword_lower"] for w in INTENT_WORDS)
        if has_intent:
            return kw

    return scored_keywords[0]
