"""
Scout Agent — Main
Orchestrateur principal. 1 article/jour, rotation sur 5 catégories.
Zéro intervention humaine, 100% data-driven.

Usage :
    python main.py              # Exécution normale (catégorie auto par rotation)
    python main.py --category 2 # Forcer une catégorie (0-4)
    python main.py --dry-run    # Test sans sauvegarder

Cron recommandé :
    0 6 * * * cd /root/garten-gefuehl-openclaw/agents/scout && /usr/bin/python3 main.py
"""

import os
import sys
import json
import argparse
from datetime import datetime, date

# Charger .env
from dotenv import load_dotenv
load_dotenv("/root/garten-gefuehl-openclaw/config/.env")

from config import CATEGORIES, BRIEFS_DIR, KEYWORDS_DIR, DATA_DIR, ARTICLES_PER_DAY
from scrapers import collect_all_keywords
from dataforseo import DataForSEOClient
from scorer import (
    load_history, save_history, filter_keywords,
    score_keywords, select_best_keyword
)
from telegram_notify import (
    notify_brief_ready, notify_scout_error,
    notify_scout_summary
)


def get_todays_category() -> dict:
    """
    Détermine la catégorie du jour par rotation.
    Basé sur le numéro du jour dans l'année % nombre de catégories.
    """
    day_of_year = date.today().timetuple().tm_yday
    index = day_of_year % len(CATEGORIES)
    return CATEGORIES[index]


def generate_brief(keyword_data: dict, category: dict, faq_questions: list) -> dict:
    """
    Génère le brief JSON complet pour le Rédacteur.
    """
    today = date.today().isoformat()
    
    # Déterminer l'angle recommandé basé sur le format
    keyword = keyword_data["keyword"]
    angle = _suggest_angle(keyword, faq_questions)
    
    brief = {
        "date": today,
        "keyword_principal": keyword,
        "traduction_fr": "",  # Sera rempli manuellement ou via traduction API
        "keywords_secondaires": [],  # Sera enrichi par les keywords proches
        "volume_mensuel": keyword_data["volume"],
        "cpc": keyword_data["cpc"],
        "concurrence": keyword_data["competition_level"],
        "trend": f"{keyword_data['trend']}%",
        "categorie_wp": category["name"],
        "categorie_slug": category["slug"],
        "traduction_fr_categorie": category["traduction_fr"],
        "pinterest_account": category["pinterest_account"],
        "angle_recommande": angle,
        "format": _detect_format(keyword),
        "faq_questions": faq_questions[:5],
        "score": keyword_data["score"],
        "sources": keyword_data["sources"]
    }
    
    return brief


def _suggest_angle(keyword: str, faq_questions: list) -> str:
    """
    Suggère un angle éditorial basé sur le keyword.
    """
    kw_lower = keyword.lower()
    
    # Détection du type d'article
    if any(word in kw_lower for word in ["tipps", "pflege", "pflegen"]):
        return f"Praktische Tipps: {keyword}"
    elif any(word in kw_lower for word in ["ideen", "gestalten", "deko"]):
        return f"Inspiration & Ideen: {keyword}"
    elif any(word in kw_lower for word in ["beste", "top", "schönste"]):
        return f"Listicle: Die besten {keyword}"
    elif any(word in kw_lower for word in ["wie", "anleitung", "schritt"]):
        return f"Anleitung Schritt für Schritt: {keyword}"
    elif faq_questions:
        return f"FAQ-basiert: {keyword} — Antworten auf häufige Fragen"
    else:
        return f"Ratgeber: {keyword} — Alles was du wissen musst"


def _detect_format(keyword: str) -> str:
    """Détecte le format optimal pour l'article."""
    kw_lower = keyword.lower()
    
    if any(word in kw_lower for word in ["beste", "top", "schönste", "arten", "sorten"]):
        return "listicle"
    elif any(word in kw_lower for word in ["wie", "anleitung", "schritt"]):
        return "tutorial"
    elif any(word in kw_lower for word in ["ideen", "inspiration"]):
        return "inspiration"
    else:
        return "ratgeber"


def find_secondary_keywords(all_scored: list, primary_keyword: str, max_count: int = 5) -> list:
    """
    Trouve 3-5 keywords secondaires proches du keyword principal.
    Tous validés par volume + trend (déjà enrichis par DataForSEO).
    """
    primary_words = set(primary_keyword.lower().split())
    secondary = []
    
    for kw in all_scored:
        if kw["keyword"].lower() == primary_keyword.lower():
            continue
        
        kw_words = set(kw["keyword"].lower().split())
        # Au moins 1 mot en commun avec le keyword principal
        overlap = primary_words & kw_words
        if overlap and kw["volume"] >= 30:
            secondary.append({
                "keyword": kw["keyword"],
                "volume": kw["volume"],
                "trend": kw["trend"]
            })
        
        if len(secondary) >= max_count:
            break
    
    return secondary


def save_brief(brief: dict, dry_run: bool = False) -> str:
    """Sauvegarde le brief en JSON."""
    today = date.today().isoformat()
    brief_dir = os.path.join(BRIEFS_DIR, today)
    os.makedirs(brief_dir, exist_ok=True)
    
    # Trouver le prochain numéro de brief
    existing = [f for f in os.listdir(brief_dir) if f.startswith("brief_")]
    next_num = len(existing) + 1
    
    filepath = os.path.join(brief_dir, f"brief_{next_num:02d}.json")
    
    if not dry_run:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(brief, f, ensure_ascii=False, indent=2)
        print(f"[Scout] Brief sauvegardé : {filepath}")
    else:
        print(f"[Scout] DRY RUN — Brief non sauvegardé")
        print(json.dumps(brief, ensure_ascii=False, indent=2))
    
    return filepath


def save_raw_keywords(keywords_data: dict):
    """Sauvegarde le dump brut des keywords collectés."""
    today = date.today().isoformat()
    os.makedirs(KEYWORDS_DIR, exist_ok=True)
    filepath = os.path.join(KEYWORDS_DIR, f"raw_{today}.json")
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(keywords_data, f, ensure_ascii=False, indent=2)
    print(f"[Scout] Raw keywords sauvegardés : {filepath}")


def run(category_override: int = None, dry_run: bool = False):
    """
    Exécution principale du Scout.
    """
    print("=" * 60)
    print(f"[Scout] Démarrage — {datetime.now().isoformat()}")
    print("=" * 60)
    
    # ÉTAPE 0 — Déterminer la catégorie du jour
    if category_override is not None:
        category = CATEGORIES[category_override]
        print(f"[Scout] Catégorie forcée : {category['name']} ({category['traduction_fr']})")
    else:
        category = get_todays_category()
        print(f"[Scout] Catégorie du jour : {category['name']} ({category['traduction_fr']})")
    
    try:
        # ÉTAPE 1 — Collecte keywords (Google + Pinterest + FAQ)
        print(f"\n[Scout] ÉTAPE 1 — Collecte des keywords...")
        keywords_data = collect_all_keywords(category["seed_keywords"])
        total_collected = len(keywords_data)
        
        if total_collected == 0:
            notify_scout_error(f"Aucun keyword collecté pour {category['name']}")
            return
        
        # Sauvegarder dump brut
        if not dry_run:
            save_raw_keywords(keywords_data)
        
        # ÉTAPE 2 — Dédoublonnage & filtrage
        print(f"\n[Scout] ÉTAPE 2 — Filtrage...")
        history = load_history()
        
        # ÉTAPE 3 — Enrichissement volumes via DataForSEO
        print(f"\n[Scout] ÉTAPE 3 — Enrichissement DataForSEO...")
        dfs_client = DataForSEOClient(
            login=os.getenv("DATAFORSEO_LOGIN"),
            password=os.getenv("DATAFORSEO_PASSWORD")
        )
        
        # Vérifier le solde
        balance = dfs_client.get_balance()
        print(f"[Scout] Solde DataForSEO : ${balance:.2f}")
        
        keyword_list = [kw_info["original"] for kw_info in keywords_data.values()]
        volumes_data = dfs_client.get_keyword_volumes(keyword_list)
        print(f"[Scout] Volumes récupérés pour {len(volumes_data)} keywords")
        
        # ÉTAPE 4 — Filtrage + scoring
        print(f"\n[Scout] ÉTAPE 4 — Scoring...")
        filtered = filter_keywords(keywords_data, volumes_data, history)
        
        if not filtered:
            notify_scout_error(
                f"Aucun keyword valide après filtrage pour {category['name']}. "
                f"Collectés: {total_collected}, tous filtrés."
            )
            return
        
        scored = score_keywords(filtered)
        
        # ÉTAPE 5 — Sélection du meilleur keyword
        print(f"\n[Scout] ÉTAPE 5 — Sélection...")
        best = select_best_keyword(scored, category["name"])
        
        if not best:
            notify_scout_error(f"Impossible de sélectionner un keyword pour {category['name']}")
            return
        
        print(f"[Scout] Meilleur keyword : {best['keyword']} (score: {best['score']})")
        
        # Trouver keywords secondaires (validés par volume + trend)
        secondary = find_secondary_keywords(scored, best["keyword"])
        
        # ÉTAPE 6 — Générer le brief
        print(f"\n[Scout] ÉTAPE 6 — Génération du brief...")
        brief = generate_brief(best, category, best.get("faq", []))
        brief["keywords_secondaires"] = secondary
        
        # Sauvegarder
        filepath = save_brief(brief, dry_run)
        
        # Mettre à jour l'historique
        if not dry_run:
            history["processed_keywords"].append({
                "keyword": best["keyword"],
                "category": category["name"],
                "date": date.today().isoformat(),
                "score": best["score"]
            })
            save_history(history)
        
        # Notifications Telegram
        if not dry_run:
            notify_scout_summary(total_collected, len(filtered), best["keyword"])
            notify_brief_ready(brief)
        
        print(f"\n[Scout] ✅ Terminé — Brief prêt pour le Rédacteur")
        print(f"[Scout] Top 5 keywords :")
        for i, kw in enumerate(scored[:5], 1):
            print(f"  {i}. {kw['keyword']} — vol:{kw['volume']} cpc:{kw['cpc']} score:{kw['score']}")
    
    except Exception as e:
        error_msg = f"Erreur Scout : {str(e)}"
        print(f"[Scout] ❌ {error_msg}")
        notify_scout_error(error_msg)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scout Agent — Garten Gefühl")
    parser.add_argument("--category", type=int, help="Forcer une catégorie (0-4)", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Test sans sauvegarder")
    args = parser.parse_args()
    
    run(category_override=args.category, dry_run=args.dry_run)
