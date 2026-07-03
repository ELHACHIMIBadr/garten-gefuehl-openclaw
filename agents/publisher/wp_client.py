"""
Publisher Agent — WordPress Client
Publication via REST API WordPress.
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from config import WP_API, WP_CATEGORY_IDS, PUBLISH_STATUS


def get_wp_credentials():
    """Retourne les credentials WordPress."""
    user = os.getenv("WP_USER")
    password = os.getenv("WP_APP_PASSWORD", "").replace(" ", "")
    return user, password


def get_existing_posts(slug: str) -> list:
    """Vérifie si un article avec ce slug existe déjà."""
    user, password = get_wp_credentials()
    try:
        resp = requests.get(
            f"{WP_API}/posts",
            auth=(user, password),
            params={"slug": slug},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[Publisher] Erreur vérification slug: {e}")
    return []


def get_category_id(category_name: str) -> int:
    """Retourne l'ID de catégorie WordPress."""
    # D'abord chercher dans le mapping local
    cat_id = WP_CATEGORY_IDS.get(category_name)
    if cat_id:
        return cat_id

    # Sinon chercher via l'API
    user, password = get_wp_credentials()
    try:
        resp = requests.get(
            f"{WP_API}/categories",
            auth=(user, password),
            params={"search": category_name, "per_page": 5},
            timeout=10
        )
        if resp.status_code == 200:
            categories = resp.json()
            for cat in categories:
                if cat["name"].lower() == category_name.lower():
                    return cat["id"]
    except Exception as e:
        print(f"[Publisher] Erreur récupération catégorie: {e}")

    return 1  # Catégorie par défaut (Uncategorized)


def publish_post(article: dict, brief: dict) -> dict:
    """
    Publie l'article sur WordPress via REST API.
    Retourne les infos de l'article publié.
    """
    user, password = get_wp_credentials()

    if not user or not password:
        raise Exception("Credentials WordPress manquants dans .env")

    # Vérifier si slug déjà utilisé
    existing = get_existing_posts(article["slug"])
    if existing:
        raise Exception(f"Article avec slug '{article['slug']}' déjà publié (ID: {existing[0]['id']})")

    # Récupérer l'ID de catégorie
    category_id = get_category_id(brief["categorie_wp"])

    # Construire le payload WordPress
    payload = {
        "title": article["seo_title"],
        "content": article["html_content"],
        "slug": article["slug"],
        "status": PUBLISH_STATUS,
        "categories": [category_id],
        "meta": {
            "rank_math_focus_keyword": article.get("focus_keyword", brief["keyword_principal"]),
            "rank_math_description": article["meta_description"],
        },
        "excerpt": article["meta_description"],
    }

    # Ajouter l'image à la une si disponible
    featured_image_id = article.get("featured_image_id")
    if featured_image_id:
        payload["featured_media"] = featured_image_id

    # Publier
    print(f"[Publisher] Publication WordPress...")
    resp = requests.post(
        f"{WP_API}/posts",
        auth=(user, password),
        json=payload,
        timeout=30
    )

    if resp.status_code in (200, 201):
        post = resp.json()
        post_id = post.get("id")
        post_url = post.get("link", "")

        print(f"[Publisher] ✅ Article publié — ID: {post_id}")
        print(f"[Publisher] URL: {post_url}")

        # Mettre à jour les métadonnées Rank Math via meta
        _update_rank_math_meta(post_id, article, user, password)

        return {
            "post_id": post_id,
            "url": post_url,
            "slug": article["slug"],
            "title": article["seo_title"],
            "published_at": datetime.now().isoformat()
        }
    else:
        raise Exception(f"Erreur WordPress {resp.status_code}: {resp.text[:200]}")


def _update_rank_math_meta(post_id: int, article: dict, user: str, password: str):
    """Met à jour les métadonnées Rank Math SEO après publication."""
    try:
        # Rank Math utilise des meta custom
        meta_updates = {
            "rank_math_focus_keyword": article.get("focus_keyword", ""),
            "rank_math_description": article.get("meta_description", ""),
            "_yoast_wpseo_metadesc": article.get("meta_description", ""),  # Compatibilité Yoast
        }

        resp = requests.post(
            f"{WP_API}/posts/{post_id}",
            auth=(user, password),
            json={"meta": meta_updates},
            timeout=10
        )

        if resp.status_code in (200, 201):
            print(f"[Publisher] Rank Math meta mis à jour")
        else:
            print(f"[Publisher] ⚠️ Rank Math meta: {resp.status_code}")

    except Exception as e:
        print(f"[Publisher] ⚠️ Erreur Rank Math meta: {e}")


def ping_google_indexing(url: str):
    """
    Ping Google pour indexation rapide via Search Console API.
    Utilise le endpoint ping simple (pas besoin d'auth).
    """
    try:
        ping_url = f"https://www.google.com/ping?sitemap=https://xn--garten-gefhl-mlb.de/sitemap_index.xml"
        resp = requests.get(ping_url, timeout=10)
        if resp.status_code == 200:
            print(f"[Publisher] Google pingé pour indexation")
        else:
            print(f"[Publisher] ⚠️ Ping Google: {resp.status_code}")
    except Exception as e:
        print(f"[Publisher] ⚠️ Erreur ping Google: {e}")


def inject_internal_links(html_content: str, published_posts: list, keyword: str) -> str:
    """
    Injecte 2-3 liens internes vers d'autres articles du blog.
    published_posts = liste des articles déjà publiés (url + titre).
    """
    if not published_posts:
        return html_content

    links_injected = 0
    max_links = 3

    for post in published_posts[:max_links]:
        post_url = post.get("url", "")
        post_title = post.get("title", "")

        if not post_url or not post_title:
            continue

        # Chercher un endroit naturel pour insérer le lien
        # Injecter avant le premier </p> dans le contenu
        link_html = f'<a href="{post_url}" title="{post_title}">{post_title}</a>'

        # Remplacer la première occurrence du titre dans le texte
        if post_title.lower() in html_content.lower():
            import re
            pattern = re.compile(re.escape(post_title), re.IGNORECASE)
            html_content = pattern.sub(link_html, html_content, count=1)
            links_injected += 1

    print(f"[Publisher] {links_injected} liens internes injectés")
    return html_content


def get_published_posts() -> list:
    """Récupère la liste des articles publiés sur le blog."""
    user, password = get_wp_credentials()
    try:
        resp = requests.get(
            f"{WP_API}/posts",
            auth=(user, password),
            params={"per_page": 20, "status": "publish"},
            timeout=10
        )
        if resp.status_code == 200:
            posts = resp.json()
            return [{"url": p.get("link", ""), "title": p.get("title", {}).get("rendered", "")} for p in posts]
    except Exception as e:
        print(f"[Publisher] Erreur récupération posts: {e}")
    return []
