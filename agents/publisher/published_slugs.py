"""
Published Slugs Manager — Base de données locale des articles publiés.

Centralise tous les slugs/keywords/URLs publiés pour éviter les doublons.
Utilisé par le Scout (avant de proposer un keyword) et le Publisher (après publication).

Fichier : data/published_articles.json
Format :
{
  "slugs": ["balkon-bepflanzen-fruehling", ...],
  "keywords": ["balkon bepflanzen frühling", ...],
  "articles": [
    {
      "slug": "...",
      "keyword": "...",
      "url": "...",
      "categorie": "...",
      "date": "2026-07-06",
      "post_id": 145
    }
  ]
}
"""

import json
import os
import requests
from datetime import datetime
from pathlib import Path

DB_FILE = "/root/garten-gefuehl-openclaw/data/published_articles.json"


def load_db() -> dict:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"slugs": [], "keywords": [], "articles": []}


def save_db(db: dict):
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def is_slug_published(slug: str) -> bool:
    """Vérifie si un slug est déjà publié (base locale)."""
    db = load_db()
    return slug.lower().strip() in [s.lower().strip() for s in db.get("slugs", [])]


def is_keyword_published(keyword: str) -> bool:
    """Vérifie si un keyword a déjà été publié (base locale)."""
    db = load_db()
    return keyword.lower().strip() in [k.lower().strip() for k in db.get("keywords", [])]


def add_published_article(slug: str, keyword: str, url: str,
                           categorie: str, post_id: int = None):
    """Ajoute un article publié à la base locale."""
    db = load_db()

    # Éviter les doublons
    if slug not in db["slugs"]:
        db["slugs"].append(slug)
    if keyword.lower() not in [k.lower() for k in db["keywords"]]:
        db["keywords"].append(keyword)

    # Ajouter l'entrée complète
    existing_slugs = [a["slug"] for a in db.get("articles", [])]
    if slug not in existing_slugs:
        db["articles"].append({
            "slug": slug,
            "keyword": keyword,
            "url": url,
            "categorie": categorie,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "post_id": post_id,
        })

    save_db(db)
    print(f"[PublishedDB] ✅ Ajouté : {slug} ({keyword})")


def sync_from_wordpress():
    """
    Synchronise la base locale depuis WordPress REST API.
    À appeler au démarrage du Scout pour être toujours à jour.
    """
    from dotenv import load_dotenv
    import os
    load_dotenv("/root/garten-gefuehl-openclaw/config/.env")

    wp_url = os.getenv("WP_URL", "https://xn--garten-gefhl-mlb.de")
    wp_user = os.getenv("WP_USER")
    wp_password = os.getenv("WP_APP_PASSWORD", "").replace(" ", "")

    if not wp_user or not wp_password:
        print("[PublishedDB] ⚠️ Credentials WP manquants — sync ignorée")
        return

    db = load_db()
    existing_slugs = set(db.get("slugs", []))
    new_count = 0

    try:
        page = 1
        while True:
            resp = requests.get(
                f"{wp_url}/wp-json/wp/v2/posts",
                auth=(wp_user, wp_password),
                params={"per_page": 100, "page": page, "status": "publish"},
                timeout=15
            )
            if resp.status_code != 200:
                break
            posts = resp.json()
            if not posts:
                break

            for post in posts:
                slug = post.get("slug", "")
                if slug and slug not in existing_slugs:
                    title = post.get("title", {}).get("rendered", "")
                    url = post.get("link", "")
                    post_id = post.get("id")
                    # Extraire keyword depuis le titre (approximation)
                    keyword = title.lower().strip()

                    db["slugs"].append(slug)
                    if keyword not in [k.lower() for k in db["keywords"]]:
                        db["keywords"].append(keyword)
                    db["articles"].append({
                        "slug": slug,
                        "keyword": keyword,
                        "url": url,
                        "categorie": "",
                        "date": post.get("date", "")[:10],
                        "post_id": post_id,
                    })
                    existing_slugs.add(slug)
                    new_count += 1

            if len(posts) < 100:
                break
            page += 1

    except Exception as e:
        print(f"[PublishedDB] ⚠️ Erreur sync WP: {e}")

    if new_count > 0:
        save_db(db)
        print(f"[PublishedDB] ✅ Sync WP : {new_count} nouveaux articles ajoutés")
    else:
        print(f"[PublishedDB] ✅ Base à jour ({len(existing_slugs)} articles)")


def get_all_published_slugs() -> list:
    return load_db().get("slugs", [])


def get_all_published_keywords() -> list:
    return load_db().get("keywords", [])
