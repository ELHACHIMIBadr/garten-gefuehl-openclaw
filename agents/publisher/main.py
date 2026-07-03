"""
Publisher Agent — Main
Publie l'article approuvé sur WordPress + ping Google + historique sujets.

Usage:
    python main.py                              # Prend le dernier article ready_to_publish
    python main.py --article path/to/article.json
    python main.py --dry-run

Cron:
    0 8 * * * cd /root/garten-gefuehl-openclaw/agents/publisher && /usr/bin/python3 main.py
"""

import os
import sys
import json
import argparse
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv("/root/garten-gefuehl-openclaw/config/.env")

sys.path.insert(0, "/root/garten-gefuehl-openclaw/agents")

from config import ARTICLES_DIR, PING_GOOGLE
from wp_client import (
    publish_post, ping_google_indexing, get_published_posts
)

try:
    from history import add_topic_to_history
    HISTORY_AVAILABLE = True
except ImportError:
    HISTORY_AVAILABLE = False


def get_latest_ready_article() -> tuple:
    """Trouve le dernier article avec status 'ready_to_publish'."""
    today = date.today().isoformat()
    article_dir = Path(ARTICLES_DIR) / today

    if not article_dir.exists():
        all_dirs = sorted(Path(ARTICLES_DIR).iterdir(), reverse=True)
        if not all_dirs:
            raise FileNotFoundError("Aucun article trouvé")
        article_dir = all_dirs[0]

    for filepath in sorted(article_dir.glob("article_*.json")):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("status") == "ready_to_publish":
            return filepath, data

    raise FileNotFoundError("Aucun article prêt à publier")


def save_article(filepath: Path, data: dict):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[Publisher] Article mis à jour : {filepath}")


def send_telegram(message: str):
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
            print(f"[Publisher] Erreur Telegram: {e}")


def run(article_path: str = None, dry_run: bool = False):
    """Exécution principale du Publisher."""
    print("=" * 60)
    print(f"[Publisher] Démarrage — {datetime.now().isoformat()}")
    print("=" * 60)

    try:
        # ÉTAPE 1 — Charger l'article
        if article_path:
            filepath = Path(article_path)
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            filepath, data = get_latest_ready_article()

        article = data["article"]
        brief = data["brief"]
        keyword = brief["keyword_principal"]
        category = brief["categorie_wp"]

        print(f"[Publisher] Titre    : {article['seo_title']}")
        print(f"[Publisher] Keyword  : {keyword}")
        print(f"[Publisher] Slug     : {article['slug']}")
        print(f"[Publisher] Catégorie: {category}")

        # ÉTAPE 2 — Vérifier articles existants (pour liens internes)
        print(f"\n[Publisher] ÉTAPE 2 — Articles existants...")
        published_posts = get_published_posts()
        print(f"[Publisher] {len(published_posts)} articles existants")

        # ÉTAPE 3 — Publication WordPress
        print(f"\n[Publisher] ÉTAPE 3 — Publication WordPress...")

        if dry_run:
            print(f"[Publisher] DRY RUN — Publication simulée")
            print(f"  Titre    : {article['seo_title']}")
            print(f"  Slug     : {article['slug']}")
            print(f"  Catégorie: {category}")
            print(f"  Mots     : {article.get('word_count', '?')}")
            print(f"  Images   : {len(article.get('images', []))}")

            data["status"] = "published"
            data["publish_result"] = {
                "post_id": "DRY_RUN",
                "url": f"https://xn--garten-gefhl-mlb.de/{article['slug']}/",
                "published_at": datetime.now().isoformat()
            }
        else:
            publish_result = publish_post(article, brief)
            data["status"] = "published"
            data["publish_result"] = publish_result

            # ÉTAPE 4 — Ping Google
            if PING_GOOGLE:
                print(f"\n[Publisher] ÉTAPE 4 — Ping Google...")
                ping_google_indexing(publish_result["url"])

            # ÉTAPE 5 — Ajouter à l'historique des sujets
            if HISTORY_AVAILABLE:
                add_topic_to_history(keyword, category, publish_result["url"])
                print(f"[Publisher] Sujet ajouté à l'historique")

        save_article(filepath, data)

        post_url = data["publish_result"].get("url", "N/A")
        print(f"\n[Publisher] ✅ Article publié !")
        print(f"  URL : {post_url}")

        if not dry_run:
            send_telegram(
                f"🚀 <b>Article publié !</b>\n\n"
                f"📝 {article['seo_title']}\n"
                f"🔑 {keyword}\n"
                f"🔗 {post_url}\n"
                f"📊 {article.get('word_count', '?')} mots\n"
                f"🖼️ {len(article.get('images', []))} images\n"
                f"➡️ Distributeur Pinterest"
            )

    except Exception as e:
        error_msg = f"❌ Erreur Publisher : {str(e)}"
        print(f"[Publisher] {error_msg}")
        send_telegram(f"❌ <b>Publisher — Erreur</b>\n\n{str(e)}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publisher Agent — Garten Gefühl")
    parser.add_argument("--article", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run(article_path=args.article, dry_run=args.dry_run)
