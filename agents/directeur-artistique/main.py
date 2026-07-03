"""
Directeur Artistique Agent — Main
Source les images article (Pexels → Pixabay → GPT-image),
upload dans médiathèque WordPress en WebP,
et crée les 5 visuels Pinterest 2:3.

Usage:
    python main.py                              # Prend le dernier article approuvé
    python main.py --article path/to/article.json
    python main.py --dry-run

Cron (après Correcteur):
    30 7 * * * cd /root/garten-gefuehl-openclaw/agents/directeur-artistique && /usr/bin/python3 main.py
"""

import os
import sys
import json
import re
import argparse
import requests
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv("/root/garten-gefuehl-openclaw/config/.env")

from config import (
    ARTICLES_DIR, IMAGES_DIR, PINS_DIR,
    CATEGORY_IMAGE_KEYWORDS, ARTICLE_IMAGE_MAX_SIZE_KB
)
from image_sourcer import fetch_image
from pin_creator import create_all_pins


def get_latest_approved_article() -> tuple:
    """Trouve le dernier article avec status 'approved'."""
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
        if data.get("status") == "approved":
            return filepath, data

    raise FileNotFoundError("Aucun article approuvé en attente de traitement visuel")


def get_image_queries(brief: dict, article: dict) -> list:
    """
    Génère les requêtes de recherche d'images basées sur le brief.
    """
    category = brief.get("categorie_wp", "Garten Gefühl")
    keyword = brief.get("keyword_principal", "")

    # Keywords de base par catégorie
    base_queries = CATEGORY_IMAGE_KEYWORDS.get(category, ["garden"])

    # Extraire les H2 de l'article pour des requêtes plus précises
    html_content = article.get("html_content", "")
    h2_matches = re.findall(r"<h2[^>]*>(.*?)</h2>", html_content, re.IGNORECASE | re.DOTALL)
    h2_texts = [re.sub(r"<[^>]+>", "", h).strip() for h in h2_matches[:5]]

    # Traduire les H2 en requêtes anglaises (simplification : utiliser mots-clés catégorie)
    queries = base_queries[:6]  # Max 6 images article

    return queries


def upload_to_wordpress_media(image_path: str, alt_text: str, keyword: str) -> dict:
    """
    Upload une image dans la médiathèque WordPress via REST API.
    Retourne les infos de l'image uploadée (id, url).
    """
    wp_url = os.getenv("WP_URL", "https://xn--garten-gefhl-mlb.de")
    wp_user = os.getenv("WP_USER")
    wp_password = os.getenv("WP_APP_PASSWORD", "").replace(" ", "")

    if not wp_user or not wp_password:
        print("[DA] ⚠️ Credentials WordPress manquants")
        return {}

    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        filename = Path(image_path).name

        resp = requests.post(
            f"{wp_url}/wp-json/wp/v2/media",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "image/webp"
            },
            auth=(wp_user, wp_password),
            data=image_data,
            timeout=30
        )

        if resp.status_code in (200, 201):
            media = resp.json()
            media_id = media.get("id")

            # Mettre à jour l'alt text
            requests.post(
                f"{wp_url}/wp-json/wp/v2/media/{media_id}",
                auth=(wp_user, wp_password),
                json={"alt_text": alt_text, "caption": f"Foto: {keyword}"},
                timeout=10
            )

            print(f"[DA] Image uploadée WordPress: ID {media_id}")
            return {
                "id": media_id,
                "url": media.get("source_url", ""),
                "alt_text": alt_text
            }
        else:
            print(f"[DA] Erreur upload WordPress: {resp.status_code} — {resp.text[:100]}")
            return {}

    except Exception as e:
        print(f"[DA] Erreur upload WordPress: {e}")
        return {}


def inject_images_in_html(html_content: str, images: list) -> str:
    """
    Injecte les images dans le HTML après chaque H2.
    """
    if not images:
        return html_content

    image_index = 0
    result = html_content

    # Trouver tous les H2 et injecter une image après chacun
    h2_pattern = re.compile(r"(</h2>)", re.IGNORECASE)
    parts = h2_pattern.split(result)

    new_parts = []
    for part in parts:
        new_parts.append(part)
        if part.lower() == "</h2>" and image_index < len(images):
            img = images[image_index]
            img_html = (
                f'<figure class="wp-block-image">'
                f'<img src="{img.get("url", img.get("path", ""))}" '
                f'alt="{img.get("alt_text", "")}" '
                f'loading="lazy" />'
                f'</figure>'
            )
            new_parts.append(img_html)
            image_index += 1

    return "".join(new_parts)


def save_article(filepath: Path, data: dict, dry_run: bool = False):
    """Met à jour le fichier article."""
    if not dry_run:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[DA] Article mis à jour : {filepath}")


def send_telegram(message: str):
    import requests as req
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            req.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10
            )
        except:
            pass


def run(article_path: str = None, dry_run: bool = False):
    """Exécution principale du Directeur Artistique."""
    print("=" * 60)
    print(f"[DA] Démarrage — {datetime.now().isoformat()}")
    print("=" * 60)

    try:
        # ÉTAPE 1 — Charger l'article approuvé
        if article_path:
            filepath = Path(article_path)
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            filepath, data = get_latest_approved_article()

        article = data["article"]
        brief = data["brief"]
        keyword = brief["keyword_principal"]
        category = brief["categorie_wp"]

        print(f"[DA] Article : {filepath.name}")
        print(f"[DA] Keyword : {keyword}")
        print(f"[DA] Catégorie : {category}")

        # Créer dossiers images
        today = date.today().isoformat()
        img_dir = Path(IMAGES_DIR) / today
        pins_dir = Path(PINS_DIR) / today
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(pins_dir, exist_ok=True)

        # ÉTAPE 2 — Sourcer les images article
        print(f"\n[DA] ÉTAPE 2 — Sourcing images article...")
        queries = get_image_queries(brief, article)
        images_data = []
        attempt_count = 0

        for i, query in enumerate(queries):
            img_path = str(img_dir / f"article_img_{i+1:02d}.webp")
            alt_text = keyword if i == 0 else f"{keyword} - {query}"

            print(f"[DA] Image {i+1}/{len(queries)} : '{query}'")
            result = fetch_image(query, img_path, attempt_count)

            if result:
                result["alt_text"] = alt_text
                images_data.append(result)
                attempt_count = 0
            else:
                attempt_count += 1

        print(f"[DA] {len(images_data)}/{len(queries)} images sourcées")

        # ÉTAPE 3 — Upload WordPress (sauf dry-run)
        print(f"\n[DA] ÉTAPE 3 — Upload médiathèque WordPress...")
        wp_images = []
        featured_image_id = None

        for i, img in enumerate(images_data):
            if dry_run:
                print(f"[DA] DRY RUN — Upload simulé: {img['path']}")
                wp_images.append({
                    "id": 999 + i,
                    "url": img["path"],
                    "alt_text": img["alt_text"],
                    "source": img.get("source", "unknown")
                })
            else:
                wp_result = upload_to_wordpress_media(
                    img["path"],
                    img["alt_text"],
                    keyword
                )
                if wp_result:
                    wp_result["source"] = img.get("source", "unknown")
                    wp_images.append(wp_result)
                    if i == 0:
                        featured_image_id = wp_result.get("id")

        # ÉTAPE 4 — Injecter images dans le HTML
        print(f"\n[DA] ÉTAPE 4 — Injection images dans l'article...")
        updated_html = inject_images_in_html(article["html_content"], wp_images)
        article["html_content"] = updated_html
        article["featured_image_id"] = featured_image_id
        article["images"] = wp_images

        # ÉTAPE 5 — Créer les 5 pins Pinterest
        print(f"\n[DA] ÉTAPE 5 — Création pins Pinterest...")
        base_image = images_data[0]["path"] if images_data else None

        pins = []
        if base_image and not dry_run:
            pins = create_all_pins(
                base_image_path=base_image,
                article_title=article["seo_title"],
                keyword=keyword,
                category=category,
                pins_dir=str(pins_dir)
            )
        elif dry_run:
            print(f"[DA] DRY RUN — 5 pins simulés")
            pins = [{"account": acc, "title": article["seo_title"], "path": "DRY_RUN"} 
                   for acc in ["Blumenliebe DE", "Balkon Ideen DE", "Rosenfreude DE", "Terrasse & Garten DE", "Garten Gefühl"]]

        # ÉTAPE 6 — Mettre à jour l'article
        data["article"] = article
        data["pins"] = pins
        data["status"] = "ready_to_publish"
        save_article(filepath, data, dry_run)

        # Résumé
        print(f"\n[DA] ✅ Directeur Artistique terminé")
        print(f"  Images article : {len(wp_images)}")
        print(f"  Pins Pinterest : {len(pins)}/5")
        print(f"  Featured image ID : {featured_image_id}")

        if not dry_run:
            send_telegram(
                f"🎨 <b>Directeur Artistique — Terminé</b>\n\n"
                f"🔑 Keyword : {keyword}\n"
                f"🖼️ Images article : {len(wp_images)}\n"
                f"📌 Pins Pinterest : {len(pins)}/5\n"
                f"➡️ Prêt pour le Publisher"
            )

    except Exception as e:
        error_msg = f"❌ Erreur Directeur Artistique : {str(e)}"
        print(f"[DA] {error_msg}")
        send_telegram(f"❌ <b>DA — Erreur</b>\n\n{str(e)}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Directeur Artistique — Garten Gefühl")
    parser.add_argument("--article", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run(article_path=args.article, dry_run=args.dry_run)
