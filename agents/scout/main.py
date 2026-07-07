"""
Scout Agent — Main
Orchestrateur principal. 2 articles/jour, rotation sur 5 catégories.
Zéro intervention humaine, 100% data-driven.

Usage :
    python main.py              # Exécution normale
    python main.py --category 2 # Forcer une catégorie (0-4)
    python main.py --dry-run    # Test sans sauvegarder
    python main.py --slot 0     # Slot matin (0) ou après-midi (1)
"""

import os
import sys
import json
import argparse
from datetime import datetime, date

from dotenv import load_dotenv
load_dotenv("/root/garten-gefuehl-openclaw/config/.env")

from config import CATEGORIES, BRIEFS_DIR, KEYWORDS_DIR, DATA_DIR, ARTICLES_PER_DAY
from scrapers import collect_all_keywords
from scorer import (
    load_history, save_history, filter_keywords,
    score_keywords, select_best_keyword
)
from telegram_notify import (
    notify_brief_ready, notify_scout_error,
    notify_scout_summary
)

# Base locale des slugs/keywords publiés
try:
    sys.path.insert(0, "/root/garten-gefuehl-openclaw/agents/publisher")
    from published_slugs import (
        sync_from_wordpress, is_keyword_published,
        is_slug_published, get_all_published_keywords
    )
    SLUGS_DB_AVAILABLE = True
except ImportError:
    SLUGS_DB_AVAILABLE = False

# WordStream scraper pour volumes réels
try:
    from wordstream_scraper import get_volumes_for_keywords
    WORDSTREAM_AVAILABLE = True
except ImportError:
    WORDSTREAM_AVAILABLE = False


def get_todays_category(slot: int = 0) -> dict:
    day_of_year = date.today().timetuple().tm_yday
    index = (day_of_year * 2 + slot) % len(CATEGORIES)
    return CATEGORIES[index]


def build_synthetic_volumes(keywords_data: dict) -> dict:
    """Volumes synthétiques basés sur fréquence multi-sources."""
    synthetic = {}
    for kw_lower, kw_info in keywords_data.items():
        source_count = len(kw_info.get("sources", set()))
        volume = max(source_count * 100, 50)
        if kw_info.get("faq"):
            volume += 50
        synthetic[kw_lower] = {
            "volume": volume,
            "cpc": 0.5,
            "competition": 0.3,
            "competition_level": "MEDIUM",
            "trend": 10
        }
    return synthetic


def filter_published_keywords(keywords_data: dict) -> dict:
    """
    Supprime les keywords déjà publiés de la liste.
    Vérifie à la fois la base locale et génère le slug pour vérification.
    """
    if not SLUGS_DB_AVAILABLE:
        return keywords_data

    published_keywords = get_all_published_keywords()
    published_set = set(k.lower().strip() for k in published_keywords)

    filtered = {}
    removed = 0
    for kw_lower, kw_info in keywords_data.items():
        # Vérifier le keyword exact
        if kw_lower in published_set:
            removed += 1
            continue
        # Vérifier si un keyword très similaire a été publié
        kw_words = set(kw_lower.split())
        too_similar = False
        for published_kw in published_set:
            pub_words = set(published_kw.split())
            # Si 80%+ des mots sont communs → trop similaire
            if len(kw_words) > 0 and len(pub_words) > 0:
                overlap = len(kw_words & pub_words) / max(len(kw_words), len(pub_words))
                if overlap >= 0.8:
                    too_similar = True
                    break
        if too_similar:
            removed += 1
            continue
        filtered[kw_lower] = kw_info

    if removed > 0:
        print(f"[Scout] 🚫 {removed} keywords déjà publiés exclus")
    return filtered


def generate_slug(keyword: str) -> str:
    """Génère le slug WordPress depuis un keyword."""
    import re
    slug = keyword.lower().strip()
    slug = slug.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def generate_brief(keyword_data: dict, category: dict, faq_questions: list) -> dict:
    today = date.today().isoformat()
    keyword = keyword_data["keyword"]
    angle = _suggest_angle(keyword, faq_questions)

    brief = {
        "date": today,
        "keyword_principal": keyword,
        "traduction_fr": "",
        "keywords_secondaires": [],
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
    kw_lower = keyword.lower()
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
    primary_words = set(primary_keyword.lower().split())
    secondary = []
    for kw in all_scored:
        if kw["keyword"].lower() == primary_keyword.lower():
            continue
        kw_words = set(kw["keyword"].lower().split())
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
    today = date.today().isoformat()
    brief_dir = os.path.join(BRIEFS_DIR, today)
    os.makedirs(brief_dir, exist_ok=True)
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
    today = date.today().isoformat()
    os.makedirs(KEYWORDS_DIR, exist_ok=True)
    filepath = os.path.join(KEYWORDS_DIR, f"raw_{today}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(keywords_data, f, ensure_ascii=False, indent=2)
    print(f"[Scout] Raw keywords sauvegardés : {filepath}")


def run(category_override: int = None, dry_run: bool = False, slot: int = 0):
    print("=" * 60)
    print(f"[Scout] Démarrage — {datetime.now().isoformat()}")
    print("=" * 60)

    if category_override is not None:
        category = CATEGORIES[category_override]
        print(f"[Scout] Catégorie forcée : {category['name']}")
    else:
        category = get_todays_category(slot)
        print(f"[Scout] Catégorie du jour (slot {slot}) : {category['name']}")

    try:
        # ÉTAPE 0 — Synchroniser la base des articles publiés depuis WP
        if SLUGS_DB_AVAILABLE and not dry_run:
            print(f"\n[Scout] ÉTAPE 0 — Sync articles publiés...")
            sync_from_wordpress()

        # ÉTAPE 1 — Collecte keywords
        print(f"\n[Scout] ÉTAPE 1 — Collecte des keywords...")
        keywords_data = collect_all_keywords(category["seed_keywords"])
        total_collected = len(keywords_data)

        if total_collected == 0:
            notify_scout_error(f"Aucun keyword collecté pour {category['name']}")
            return

        if not dry_run:
            save_raw_keywords(keywords_data)

        # ÉTAPE 2 — Filtrer les keywords déjà publiés
        print(f"\n[Scout] ÉTAPE 2 — Filtrage keywords publiés...")
        keywords_data = filter_published_keywords(keywords_data)

        if not keywords_data:
            notify_scout_error(
                f"Tous les keywords sont déjà publiés pour {category['name']}. "
                f"Collectés: {total_collected}, tous filtrés."
            )
            return

        # ÉTAPE 3 — Historique
        print(f"\n[Scout] ÉTAPE 3 — Historique...")
        history = load_history()

        # ÉTAPE 4 — Volumes
        print(f"\n[Scout] ÉTAPE 4 — Volumes SEO...")
        volumes_data = {}

        # Essayer WordStream (Playwright)
        if WORDSTREAM_AVAILABLE:
            try:
                keyword_list = [kw_info.get("original", kw) for kw, kw_info in list(keywords_data.items())[:5]]
                volumes_data = get_volumes_for_keywords(keyword_list)
                print(f"[Scout] ✅ WordStream — {len(volumes_data)} volumes récupérés")
            except Exception as e:
                print(f"[Scout] ⚠️ WordStream erreur: {e} — fallback synthétique")
                volumes_data = {}

        if not volumes_data:
            print(f"[Scout] ℹ️ Volumes synthétiques (WordStream indisponible)")
            volumes_data = build_synthetic_volumes(keywords_data)

        # ÉTAPE 5 — Filtrage + scoring
        print(f"\n[Scout] ÉTAPE 5 — Scoring...")
        filtered = filter_keywords(keywords_data, volumes_data, history)

        if not filtered:
            notify_scout_error(
                f"Aucun keyword valide après filtrage pour {category['name']}."
            )
            return

        scored = score_keywords(filtered)

        # ÉTAPE 6 — Sélection (en vérifiant le slug)
        print(f"\n[Scout] ÉTAPE 6 — Sélection...")
        best = None
        for candidate in scored:
            kw = candidate["keyword"]
            slug = generate_slug(kw)
            if SLUGS_DB_AVAILABLE and is_slug_published(slug):
                print(f"[Scout] ⏭️ Slug déjà publié : {slug} — skip")
                continue
            if SLUGS_DB_AVAILABLE and is_keyword_published(kw):
                print(f"[Scout] ⏭️ Keyword déjà publié : {kw} — skip")
                continue
            best = candidate
            break

        if not best:
            # Fallback : select_best_keyword sans vérification slug
            best = select_best_keyword(scored, category["name"])

        if not best:
            notify_scout_error(f"Impossible de sélectionner un keyword pour {category['name']}")
            return

        print(f"[Scout] ✅ Meilleur keyword : {best['keyword']} (score: {best['score']})")

        secondary = find_secondary_keywords(scored, best["keyword"])

        # ÉTAPE 7 — Brief
        print(f"\n[Scout] ÉTAPE 7 — Génération du brief...")
        brief = generate_brief(best, category, best.get("faq", []))
        brief["keywords_secondaires"] = secondary

        filepath = save_brief(brief, dry_run)

        if not dry_run:
            history["processed_keywords"].append({
                "keyword": best["keyword"],
                "category": category["name"],
                "date": date.today().isoformat(),
                "score": best["score"]
            })
            save_history(history)
            notify_scout_summary(total_collected, len(filtered), best["keyword"])
            notify_brief_ready(brief)

        print(f"\n[Scout] ✅ Terminé — Brief prêt pour le Rédacteur")
        print(f"[Scout] Top 5 keywords :")
        for i, kw in enumerate(scored[:5], 1):
            print(f"  {i}. {kw['keyword']} — vol:{kw['volume']} score:{kw['score']}")

    except Exception as e:
        error_msg = f"Erreur Scout : {str(e)}"
        print(f"[Scout] ❌ {error_msg}")
        notify_scout_error(error_msg)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scout Agent — Garten Gefühl")
    parser.add_argument("--category", type=int, help="Forcer une catégorie (0-4)", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--slot", type=int, default=0, help="Slot 0=matin, 1=après-midi")
    args = parser.parse_args()
    run(category_override=args.category, dry_run=args.dry_run, slot=args.slot)
