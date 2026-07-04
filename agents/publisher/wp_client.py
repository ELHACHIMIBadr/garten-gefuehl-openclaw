"""
Publisher Agent — WordPress Client
Publication via REST API WordPress.

CHANGELOG v2:
- clean_content() : ajout nettoyage des placeholders [BILD_X] résiduels
  au cas où le DA n'aurait pas pu remplacer tous les placeholders GPT.
"""

import os
import re
import requests
from config import WP_API, WP_CATEGORY_IDS, PUBLISH_STATUS


def get_wp_credentials():
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
    cat_id = WP_CATEGORY_IDS.get(category_name)
    if cat_id:
        return cat_id

    user, password = get_wp_credentials()
    try:
        resp = requests.get(
            f"{WP_API}/categories",
            auth=(user, password),
            params={"search": category_name, "per_page": 10},
            timeout=10
        )
        if resp.status_code == 200:
            categories = resp.json()
            for cat in categories:
                if cat["name"].lower() == category_name.lower():
                    print(f"[Publisher] Catégorie '{category_name}' trouvée via API: ID {cat['id']}")
                    return cat["id"]
    except Exception as e:
        print(f"[Publisher] Erreur récupération catégorie: {e}")

    print(f"[Publisher] ⚠️ Catégorie '{category_name}' non trouvée — utilisation Uncategorized")
    return 1


def clean_content(html_content: str, keyword: str) -> str:
    """
    Nettoie le contenu HTML avant publication :
    1. Supprime les H1 résiduels (WordPress génère le H1 automatiquement)
    2. Supprime la première image si elle précède le contenu (WordPress affiche la featured image)
    3. Supprime les placeholders [INTERNER LINK: xxx]
    4. Supprime les blocs ```html ... ``` résiduels de GPT
    5. Supprime les placeholders [BILD_X] résiduels (si DA n'a pas pu remplacer)
    6. Nettoie les espaces multiples
    """
    content = html_content

    # 1. Supprimer tous les H1
    content = re.sub(r"<h1[^>]*>.*?</h1>", "", content, flags=re.IGNORECASE | re.DOTALL)

    # 2. Supprimer la première image si elle est dans les 500 premiers caractères
    first_500 = content[:500]
    if "<img" in first_500 or "<figure" in first_500:
        content = re.sub(
            r"^(\s*<figure[^>]*>.*?</figure>\s*)",
            "",
            content,
            count=1,
            flags=re.IGNORECASE | re.DOTALL
        )
        content = re.sub(
            r"^(\s*<img[^>]*/>\s*)",
            "",
            content,
            count=1,
            flags=re.IGNORECASE | re.DOTALL
        )

    # 3. Supprimer les placeholders [INTERNER LINK: xxx]
    content = re.sub(r"\[INTERNER LINK:[^\]]*\]", "", content)
    content = re.sub(r"\[INTERNAL LINK:[^\]]*\]", "", content)

    # 4. Nettoyer les balises markdown résiduelles de GPT
    content = re.sub(r"```html?\s*", "", content)
    content = re.sub(r"```\s*", "", content)

    # 5. Supprimer les placeholders [BILD_X] résiduels
    # (sécurité : si le DA n'a pas pu remplacer certains placeholders GPT)
    residual_bilder = re.findall(r"\[BILD_\d+\]", content)
    if residual_bilder:
        print(f"[Publisher] 🧹 {len(residual_bilder)} placeholder(s) [BILD_X] résiduels supprimés: {residual_bilder}")
        content = re.sub(r"\[BILD_\d+\]", "", content)

    # 6. Nettoyer les espaces multiples
    content = re.sub(r"\n{3,}", "\n\n", content)

    return content.strip()


def publish_post(article: dict, brief: dict) -> dict:
    """Publie l'article sur WordPress via REST API."""
    user, password = get_wp_credentials()

    if not user or not password:
        raise Exception("Credentials WordPress manquants dans .env")

    # Vérifier si slug déjà utilisé
    existing = get_existing_posts(article["slug"])
    if existing:
        raise Exception(f"Article avec slug '{article['slug']}' déjà publié (ID: {existing[0]['id']})")

    # Récupérer l'ID de catégorie
    category_id = get_category_id(brief["categorie_wp"])
    print(f"[Publisher] Catégorie : {brief['categorie_wp']} → ID {category_id}")

    # Nettoyer le contenu
    keyword = brief["keyword_principal"]
    clean_html = clean_content(article["html_content"], keyword)
    print(f"[Publisher] Contenu nettoyé ({len(clean_html)} caractères)")

    # Construire le payload WordPress
    payload = {
        "title": article["seo_title"],
        "content": clean_html,
        "slug": article["slug"],
        "status": PUBLISH_STATUS,
        "categories": [category_id],
        "excerpt": article["meta_description"],
        "meta": {
            "rank_math_focus_keyword": article.get("focus_keyword", keyword),
            "rank_math_description": article["meta_description"],
        }
    }

    # Ajouter l'image à la une
    # ⚠️ IMPORTANT : pour que la featured image s'affiche dans l'article,
    # activer dans WordPress → Apparence → Personnaliser → Blog →
    # Article unique → cocher "Image mise en avant"
    featured_image_id = article.get("featured_image_id")
    if featured_image_id:
        payload["featured_media"] = featured_image_id
        print(f"[Publisher] Image à la une : ID {featured_image_id}")
    else:
        print(f"[Publisher] ⚠️ Pas d'image à la une (featured_image_id manquant)")

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

        _update_rank_math_meta(post_id, article, user, password)

        return {
            "post_id": post_id,
            "url": post_url,
            "slug": article["slug"],
            "title": article["seo_title"],
            "published_at": __import__('datetime').datetime.now().isoformat()
        }
    else:
        raise Exception(f"Erreur WordPress {resp.status_code}: {resp.text[:200]}")


def _update_rank_math_meta(post_id: int, article: dict, user: str, password: str):
    """Met à jour les métadonnées Rank Math SEO."""
    try:
        meta_updates = {
            "rank_math_focus_keyword": article.get("focus_keyword", ""),
            "rank_math_description": article.get("meta_description", ""),
        }
        resp = requests.post(
            f"{WP_API}/posts/{post_id}",
            auth=(user, password),
            json={"meta": meta_updates},
            timeout=10
        )
        if resp.status_code in (200, 201):
            print(f"[Publisher] Rank Math meta mis à jour")
    except Exception as e:
        print(f"[Publisher] ⚠️ Erreur Rank Math meta: {e}")


def ping_google_indexing(url: str):
    """Ping Google Search Console pour indexation."""
    try:
        ping_url = f"https://www.google.com/ping?sitemap=https://xn--garten-gefhl-mlb.de/sitemap_index.xml"
        resp = requests.get(ping_url, timeout=10)
        print(f"[Publisher] Ping Google: {resp.status_code}")
    except Exception as e:
        print(f"[Publisher] ⚠️ Erreur ping Google: {e}")


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
            return [
                {
                    "url": p.get("link", ""),
                    "title": p.get("title", {}).get("rendered", ""),
                    "slug": p.get("slug", "")
                }
                for p in posts
            ]
    except Exception as e:
        print(f"[Publisher] Erreur récupération posts: {e}")
    return []
