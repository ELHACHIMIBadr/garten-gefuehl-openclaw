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
    """Charge l'historique des keywords déjà traités."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {"processed_keywords": []}


def save_history(history: dict):
    """Sauvegarde l'historique."""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def is_recently_processed(keyword: str, history: dict, days: int = 30) -> bool:
    """Vérifie si un keyword a été traité dans les X derniers jours."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    for entry in history.get("processed_keywords", []):
        if entry["keyword"].lower() == keyword.lower() and entry["date"] >= cutoff:
            return True
    return False


def filter_keywords(keywords_data: dict, volumes_data: dict, history: dict) -> List[dict]:
    """
    Filtre les keywords :
    - Supprime ceux sans volume (0 ou absent)
    - Supprime ceux déjà traités récemment
    - Supprime ceux trop courts (< 2 mots) — on veut du long-tail
    - Supprime ceux hors niche jardin
    """
    filtered = []
    
    garden_terms = [
        "garten", "blumen", "balkon", "rosen", "terrasse", "pflanzen",
        "blüte", "beet", "erde", "dünger", "schneiden", "pflege",
        "sommer", "frühling", "herbst", "winter", "saat", "topf",
        "kräuter", "gemüse", "hecke", "rasen", "baum", "strauch",
        "deko", "gestalten", "ideen", "tipps", "sichtschutz",
        "hochbeet", "kompost", "bewässerung", "schädling", "mulch"
    ]
    
    for kw_lower, kw_info in keywords_data.items():
        # Vérifier volume disponible
        volume_info = volumes_data.get(kw_lower, {})
        volume = volume_info.get("volume", 0)
        
        if volume < 50:  # Minimum 50 recherches/mois
            continue
        
        # Vérifier si déjà traité
        if is_recently_processed(kw_lower, history):
            continue
        
        # Vérifier minimum 2 mots (long-tail)
        if len(kw_lower.split()) < 2:
            continue
        
        # Vérifier pertinence jardin
        is_garden = any(term in kw_lower for term in garden_terms)
        if not is_garden:
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
    Score chaque keyword avec la formule :
    Score = (volume × CPC_weight) / (competition_penalty + 0.01) × bonus/pénalités
    """
    for kw in keywords:
        volume = kw["volume"]
        cpc = max(kw["cpc"], 0.01)  # Minimum CPC pour éviter score 0
        competition = max(kw["competition"], 0.01)  # Éviter division par 0
        
        # Score de base
        base_score = (volume * cpc * SCORING["cpc_weight"]) / (competition * SCORING["competition_penalty"])
        
        # Bonus : trend en hausse
        if kw["trend"] > 0:
            base_score *= (1 + SCORING["trend_bonus"])
        
        # Bonus : trouvé sur Google ET Pinterest
        if "google" in kw["sources"] and "pinterest" in kw["sources"]:
            base_score *= (1 + SCORING["dual_source_bonus"])
        
        # Bonus : questions FAQ disponibles
        if len(kw.get("faq", [])) > 0:
            base_score *= (1 + SCORING["faq_bonus"])
        
        # Pénalité : concurrence élevée
        if kw["competition_level"] == "HIGH":
            base_score *= 0.5
        
        kw["score"] = round(base_score, 2)
    
    # Tri par score décroissant
    keywords.sort(key=lambda x: x["score"], reverse=True)
    
    return keywords


def select_best_keyword(scored_keywords: List[dict], category_name: str) -> dict:
    """
    Sélectionne le meilleur keyword pour la catégorie du jour.
    Privilégie les keywords dont le contenu matche la catégorie.
    """
    if not scored_keywords:
        return None
    
    category_lower = category_name.lower()
    
    # D'abord, chercher un keyword qui matche la catégorie
    for kw in scored_keywords:
        if category_lower in kw["keyword_lower"]:
            return kw
    
    # Sinon, prendre le meilleur score global
    return scored_keywords[0]
