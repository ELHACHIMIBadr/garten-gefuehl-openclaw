"""
Rédacteur Agent — Main
Lit le brief du Scout, génère un article en allemand natif via GPT,
et dépose l'article structuré pour le Correcteur.

Usage:
    python main.py                          # Prend le brief du jour automatiquement
    python main.py --brief path/to/brief.json  # Forcer un brief spécifique
    python main.py --dry-run               # Test sans sauvegarder

Cron recommandé (après le Scout):
    30 6 * * * cd /root/garten-gefuehl-openclaw/agents/redacteur && /usr/bin/python3 main.py
"""

import os
import sys
import json
import argparse
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv("/root/garten-gefuehl-openclaw/config/.env")

from config import MODEL, ARTICLES_DIR, BRIEFS_DIR, MIN_WORDS, MAX_WORDS
from prompt_builder import build_article_prompt
from gpt_client import call_gpt
from parser import (
    parse_gpt_output, validate_seo_title,
    validate_meta_description, validate_content
)


def get_latest_brief() -> dict:
    """
    Trouve le brief le plus récent dans /data/briefs/
    """
    today = date.today().isoformat()
    brief_dir = Path(BRIEFS_DIR) / today

    if not brief_dir.exists():
        all_brief_dirs = sorted(Path(BRIEFS_DIR).iterdir(), reverse=True)
        if not all_brief_dirs:
            raise FileNotFoundError("Aucun brief trouvé dans " + BRIEFS_DIR)
        brief_dir = all_brief_dirs[0]

    brief_files = list(brief_dir.glob("brief_*.json"))
    if not brief_files:
        raise FileNotFoundError(f"Aucun brief trouvé dans {brief_dir}")

    for brief_file in sorted(brief_files):
        with open(brief_file, "r", encoding="utf-8") as f:
            brief = json.load(f)

        article_path = Path(ARTICLES_DIR) / brief_file.stem.replace("brief", "article")
        if not article_path.exists():
            print(f"[Rédacteur] Brief chargé : {brief_file}")
            brief["_source_file"] = str(brief_file)
            return brief

    raise FileNotFoundError("Tous les briefs du jour ont déjà été traités")


def inject_newsletter_block(html_content: str) -> str:
    """
    Injecte le bloc newsletter Brevo après la section Fazit.
    """
    newsletter_block_path = "/root/garten-gefuehl-openclaw/config/newsletter-trigger.html"

    try:
        with open(newsletter_block_path, "r", encoding="utf-8") as f:
            newsletter_html = f.read()
        return html_content.replace("[NEWSLETTER_BLOCK]", newsletter_html)
    except FileNotFoundError:
        print("[Rédacteur] ⚠️ newsletter-trigger.html non trouvé, placeholder conservé")
        return html_content


def save_article(article_data: dict, brief: dict, dry_run: bool = False) -> str:
    """Sauvegarde l'article structuré en JSON pour le Correcteur."""
    today = date.today().isoformat()
    article_dir = Path(ARTICLES_DIR) / today
    os.makedirs(article_dir, exist_ok=True)

    source_file = brief.get("_source_file", "brief_01.json")
    num = Path(source_file).stem.replace("brief_", "")
    filepath = article_dir / f"article_{num}.json"

    output = {
        "date": today,
        "generated_at": datetime.now().isoformat(),
        "brief": brief,
        "article": article_data,
        "status": "pending_review"
    }

    if not dry_run:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"[Rédacteur] Article sauvegardé : {filepath}")
    else:
        print(f"[Rédacteur] DRY RUN — Article non sauvegardé")
        print(f"[Rédacteur] Titre : {article_data.get('seo_title', 'N/A')}")
        print(f"[Rédacteur] Mots : {article_data.get('word_count', 0)}")
        print(f"[Rédacteur] Erreurs de parsing : {article_data.get('parse_errors', [])}")

    return str(filepath)


def send_telegram(message: str):
    """Envoie une notification Telegram."""
    import requests
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10
            )
        except Exception as e:
            print(f"[Rédacteur] Erreur Telegram: {e}")


def run(brief_path: str = None, dry_run: bool = False, max_retries: int = 2):
    """Exécution principale du Rédacteur."""
    print("=" * 60)
    print(f"[Rédacteur] Démarrage — {datetime.now().isoformat()}")
    print("=" * 60)

    try:
        # ÉTAPE 1 — Charger le brief
        if brief_path:
            with open(brief_path, "r", encoding="utf-8") as f:
                brief = json.load(f)
            brief["_source_file"] = brief_path
        else:
            brief = get_latest_brief()

        keyword = brief["keyword_principal"]
        print(f"[Rédacteur] Keyword : {keyword}")
        print(f"[Rédacteur] Catégorie : {brief['categorie_wp']} ({brief.get('traduction_fr_categorie', '')})")

        # ÉTAPE 2 — Construire le prompt
        print(f"\n[Rédacteur] ÉTAPE 2 — Construction du prompt...")
        prompt = build_article_prompt(brief)

        # ÉTAPE 3 — Appel GPT via OpenClaw Gateway
        article_data = None
        for attempt in range(1, max_retries + 1):
            print(f"\n[Rédacteur] ÉTAPE 3 — Génération article (tentative {attempt}/{max_retries})...")

            raw_output = call_gpt(prompt)

            # ÉTAPE 4 — Parser la sortie
            print(f"[Rédacteur] ÉTAPE 4 — Parsing...")
            article_data = parse_gpt_output(raw_output)

            if article_data["parse_errors"]:
                print(f"[Rédacteur] ⚠️ Erreurs de parsing : {article_data['parse_errors']}")
                if attempt < max_retries:
                    print(f"[Rédacteur] Nouvelle tentative...")
                    continue

            if article_data["word_count"] < MIN_WORDS:
                print(f"[Rédacteur] ⚠️ Article trop court ({article_data['word_count']} mots)")
                if attempt < max_retries:
                    print(f"[Rédacteur] Nouvelle tentative...")
                    continue

            break

        # ÉTAPE 5 — Validations SEO
        print(f"\n[Rédacteur] ÉTAPE 5 — Validations SEO...")
        seo_errors = []
        seo_errors += validate_seo_title(article_data["seo_title"], keyword)
        seo_errors += validate_meta_description(article_data["meta_description"], keyword)
        seo_errors += validate_content(article_data["html_content"], keyword, MIN_WORDS)

        if seo_errors:
            print(f"[Rédacteur] ⚠️ Erreurs SEO ({len(seo_errors)}) :")
            for err in seo_errors:
                print(f"  - {err}")
            article_data["seo_errors"] = seo_errors
        else:
            print(f"[Rédacteur] ✅ Toutes les validations SEO passées")
            article_data["seo_errors"] = []

        # ÉTAPE 6 — Injecter le bloc newsletter
        print(f"\n[Rédacteur] ÉTAPE 6 — Injection newsletter...")
        article_data["html_content"] = inject_newsletter_block(article_data["html_content"])

        # ÉTAPE 7 — Sauvegarder
        print(f"\n[Rédacteur] ÉTAPE 7 — Sauvegarde...")
        filepath = save_article(article_data, brief, dry_run)

        print(f"\n[Rédacteur] ✅ Article généré avec succès")
        print(f"  Titre    : {article_data['seo_title']}")
        print(f"  Mots     : {article_data['word_count']}")
        print(f"  Slug     : {article_data['slug']}")
        print(f"  Erreurs  : {len(article_data.get('seo_errors', []))}")

        if not dry_run:
            status = "✅" if not article_data.get("seo_errors") else "⚠️"
            send_telegram(
                f"{status} <b>Rédacteur — Article généré</b>\n\n"
                f"📝 Titre : {article_data['seo_title']}\n"
                f"🔑 Keyword : {keyword}\n"
                f"📊 Mots : {article_data['word_count']}\n"
                f"⚠️ Erreurs SEO : {len(article_data.get('seo_errors', []))}\n"
                f"➡️ Passé au Correcteur"
            )

    except Exception as e:
        error_msg = f"❌ Erreur Rédacteur : {str(e)}"
        print(f"[Rédacteur] {error_msg}")
        send_telegram(f"❌ <b>Rédacteur — Erreur</b>\n\n{str(e)}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rédacteur Agent — Garten Gefühl")
    parser.add_argument("--brief", type=str, help="Chemin vers un brief JSON spécifique", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Test sans sauvegarder")
    args = parser.parse_args()

    run(brief_path=args.brief, dry_run=args.dry_run)
