"""
Scout Agent — Scorer
Score et sélection des meilleurs keywords.
Formule : Score = (volume × CPC) / concurrence + bonus/pénalités
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


def filter_keywords(keywords_data: dict, volumes_data: dict, history: dict) -> List[dict]:
    """
    Filtre les keywords :
    - Supprime ceux sans volume suffisant
    - Supprime ceux déjà traités récemment (60 jours)
    - Supprime ceux trop courts (< 2 mots)
    - Supprime ceux hors niche jardin (garden_terms)
    - Supprime ceux avec mots exclus (non_garden_terms)
    - Supprime les requêtes locales/commerciales (magasins, marques)
    """
    filtered = []

    # Mots qui indiquent un keyword jardin
    garden_terms = [
        "garten", "blumen", "balkon", "rosen", "terrasse", "pflanzen",
        "blüte", "blüten", "beet", "beete", "erde", "dünger", "düngen",
        "schneiden", "pflege", "pflegen", "pflanzen", "saat", "säen",
        "topf", "töpfe", "kräuter", "gemüse", "hecke", "rasen",
        "strauch", "sträucher", "stauden", "zwiebel", "samen",
        "hochbeet", "kompost", "bewässerung", "schädling", "mulch",
        "sichtschutz", "gartengestaltung", "gartenideen", "gartendeko",
        "blumenkasten", "blumentopf", "blumenbeet", "blumenzwiebeln",
        "rosenpflege", "rosenstrauch", "kletterrosen", "beetrosen",
        "balkonpflanzen", "balkonblumen", "hängepflanzen",
        "frühling", "frühjahr", "herbst", "winter", "sommer",
        "sonnig", "schattig", "mehrjährig", "einjährig",
        "tipps", "ideen", "gestalten", "anlegen", "pflanzen",
        "wachsen", "blühen", "schnitt", "anleitung"
    ]

    # Mots qui EXCLUENT un keyword — hors sujet jardin
    non_garden_terms = [
        # Commerce / local
        "geöffnet", "öffnungszeiten", "lieferung", "bestellen", "kaufen",
        "online", "shop", "preis", "günstig", "angebot", "rabatt",
        "liefern", "versand", "expresslieferung",
        # Magasins spécifiques
        "müller", "aldi", "lidl", "rewe", "edeka", "penny", "obi",
        "hornbach", "bauhaus", "ikea", "amazon",
        # Hors niche
        "tattoo", "tätowierung", "hochzeit", "braut", "strauß hochzeit",
        "foto", "fotografie", "bilder", "tapete", "clipart",
        "basteln", "häkeln", "stricken",
        # Requêtes info commerciale
        "jetzt geöffnet", "in der nähe", "nächste", "adresse",
        "telefon", "bewertung", "erfahrung",
    ]

    # Minimum de mots jardin actifs dans le keyword (contrôle qualité)
    GARDEN_CONTEXT_TERMS = [
        "garten", "pflanz", "blum", "rose", "balkon", "terrasse",
        "beet", "topf", "erde", "dünger", "schneid", "pflege",
        "hochbeet", "sichtschutz", "kräuter", "gemüse", "rasen",
        "strauch", "staude", "zwiebel", "samen", "kompost"
    ]

    for kw_lower, kw_info in keywords_data.items():
        volume_info = volumes_data.get(kw_lower, {})
        volume = volume_info.get("volume", 0)

        if volume < 50:
            continue

        if is_recently_processed(kw_lower, history):
            continue

        if len(kw_lower.split()) < 2:
            continue

        # Exclure les keywords hors niche
        has_exclusion = any(excl in kw_lower for excl in non_garden_terms)
        if has_exclusion:
            continue

        # Vérifier pertinence jardin (présence d'un terme contexte jardin)
        has_garden_context = any(term in kw_lower for term in GARDEN_CONTEXT_TERMS)
        if not has_garden_context:
            continue

        filtered.append({
            "keyword": kw_info["original"],
            "keyword_lower": kw_lower,
            "volume": volume,
            "cpc": volume_info.get("cpc", 0),
            "competition": volume_info.get("competition", 0),
            "competition_level": volume_info.get("competition_level", "UNKNOWN"),
            "trend": volume_info.get("trend", 0),
            "sources": kw_info["sources"],
            "faq": kw_info.get("faq", [])
        })

    print(f"[Scout] Keywords après filtrage : {len(filtered)}")
    return filtered


def score_keywords(keywords: List[dict]) -> List[dict]:
    """
    Score chaque keyword.
    Avec volumes synthétiques, on différencie par :
    - Nombre de mots (long-tail = meilleur)
    - Présence de FAQ (intention réelle)
    - Sources multiples (google + pinterest)
    - Mots à forte intention SEO (tipps, anleitung, ideen, pflege...)
    """
    HIGH_INTENT_WORDS = [
        "tipps", "anleitung", "ideen", "pflege", "pflanzen", "gestalten",
        "richtig", "schneiden", "düngen", "gießen", "anlegen", "schritt",
        "wann", "wie", "beste", "schönste", "einfach", "richtig"
    ]

    for kw in keywords:
        volume = kw["volume"]
        cpc = max(kw["cpc"], 0.01)
        competition = max(kw["competition"], 0.01)

        base_score = (volume * cpc * SCORING["cpc_weight"]) / (competition * SCORING["competition_penalty"])

        # Bonus trend
        if kw["trend"] > 0:
            base_score *= (1 + SCORING["trend_bonus"])

        # Bonus dual source
        if "google" in kw["sources"] and "pinterest" in kw["sources"]:
            base_score *= (1 + SCORING["dual_source_bonus"])

        # Bonus FAQ
        if len(kw.get("faq", [])) > 0:
            base_score *= (1 + SCORING["faq_bonus"])

        # Pénalité concurrence élevée
        if kw["competition_level"] == "HIGH":
            base_score *= 0.5

        # Bonus long-tail : plus de mots = plus spécifique
        word_count = len(kw["keyword_lower"].split())
        if word_count >= 3:
            base_score *= 1.3
        if word_count >= 4:
            base_score *= 1.2

        # Bonus intention SEO forte
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

    # Priorité : keyword qui matche la catégorie ET a une intention forte
    for kw in scored_keywords[:20]:
        if category_lower in kw["keyword_lower"]:
            return kw

    return scored_keywords[0]
