"""
Directeur Artistique Agent — Main
"""

import os
import json
import re
import argparse
import requests
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv("/root/garten-gefuehl-openclaw/config/.env")

from config import ARTICLES_DIR, IMAGES_DIR, PINS_DIR, CATEGORY_IMAGE_KEYWORDS
from image_sourcer import fetch_image, reset_article_url_cache
from pin_creator import create_all_pins

import sys
sys.path.insert(0, "/root/garten-gefuehl-openclaw/agents")
try:
    from history import add_image_to_history, load_image_history, save_image_history
    HISTORY_AVAILABLE = True
except ImportError:
    HISTORY_AVAILABLE = False


def get_latest_approved_article() -> tuple:
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


def seed_image_history_from_wordpress():
    """
    Récupère les images déjà uploadées sur WordPress et les ajoute à l'historique.
    Évite les doublons avec les articles précédents.
    """
    if not HISTORY_AVAILABLE:
        return

    wp_url = os.getenv("WP_URL", "https://xn--garten-gefhl-mlb.de")
    wp_user = os.getenv("WP_USER")
    wp_password = os.getenv("WP_APP_PASSWORD", "").replace(" ", "")

    if not wp_user or not wp_password:
        return

    try:
        resp = requests.get(
            f"{wp_url}/wp-json/wp/v2/media",
            auth=(wp_user, wp_password),
            params={"per_page": 100, "media_type": "image"},
            timeout=15
        )
        if resp.status_code == 200:
            media_items = resp.json()
            history = load_image_history()
            existing_urls = set(history.get("used_urls", []))
            new_count = 0

            for item in media_items:
                source_url = item.get("source_url", "")
                if source_url and source_url not in existing_urls:
                    existing_urls.add(source_url)
                    new_count += 1

            history["used_urls"] = list(existing_urls)
            save_image_history(history)
            if new_count > 0:
                print(f"[DA] {new_count} images WP ajoutées à l'historique")
    except Exception as e:
        print(f"[DA] ⚠️ Erreur sync historique WP: {e}")


def get_image_queries(brief: dict, article: dict) -> list:
    category = brief.get("categorie_wp", "Garten Gefühl")
    base_queries = CATEGORY_IMAGE_KEYWORDS.get(category, ["garden"])
    return base_queries[:4]


def upload_to_wordpress_media(image_path: str, alt_text: str, keyword: str) -> dict:
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
            requests.post(
                f"{wp_url}/wp-json/wp/v2/media/{media_id}",
                auth=(wp_user, wp_password),
                json={"alt_text": alt_text, "caption": f"Foto: {keyword}"},
                timeout=10
            )
            print(f"[DA] Image uploadée WordPress: ID {media_id}")
            return {"id": media_id, "url": media.get("source_url", ""), "alt_text": alt_text}
        else:
            print(f"[DA] Erreur upload WordPress: {resp.status_code}")
            return {}

    except Exception as e:
        print(f"[DA] Erreur upload WordPress: {e}")
        return {}


def inject_images_in_html(html_content: str, images: list) -> str:
    if not images:
        return html_content

    image_index = 0
    h2_pattern = re.compile(r"(</h2>)", re.IGNORECASE)
    parts = h2_pattern.split(html_content)

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
    if not dry_run:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[DA] Article mis à jour : {filepath}")


def send_telegram(message: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10
            )
        except:
            pass


def run(article_path: str = None, dry_run: bool = False):
    print("=" * 60)
    print(f"[DA] Démarrage — {datetime.now().isoformat()}")
    print("=" * 60)

    try:
        # Réinitialiser le cache intra-article
        reset_article_url_cache()

        # Synchroniser l'historique avec les images WordPress existantes
        if not dry_run:
            print(f"[DA] Sync historique images WordPress...")
            seed_image_history_from_wordpress()

        # ÉTAPE 1 — Charger l'article
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

        today = date.today().isoformat()
        img_dir = Path(IMAGES_DIR) / today
        pins_dir = Path(PINS_DIR) / today
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(pins_dir, exist_ok=True)

        # ÉTAPE 2 — Sourcing images
        print(f"\n[DA] ÉTAPE 2 — Sourcing images avec validation Codex...")
        queries = get_image_queries(brief, article)
        images_data = []

        for i, query in enumerate(queries):
            img_path = str(img_dir / f"article_img_{i+1:02d}.webp")
            alt_text = keyword if i == 0 else f"{keyword} - {query}"

            print(f"\n[DA] Image {i+1}/{len(queries)} : '{query}'")
            result = fetch_image(query=query, save_path=img_path, keyword=keyword, category=category)

            if result:
                result["alt_text"] = alt_text
                images_data.append(result)

        print(f"\n[DA] {len(images_data)}/{len(queries)} images sourcées")

        # ÉTAPE 3 — Upload WordPress
        print(f"\n[DA] ÉTAPE 3 — Upload médiathèque WordPress...")
        wp_images = []
        featured_image_id = None

        for i, img in enumerate(images_data):
            if dry_run:
                print(f"[DA] DRY RUN — Upload simulé: {img['path']} ({img.get('source', '?')})")
                wp_images.append({"id": 999+i, "url": img["path"], "alt_text": img["alt_text"], "source": img.get("source")})
            else:
                wp_result = upload_to_wordpress_media(img["path"], img["alt_text"], keyword)
                if wp_result:
                    wp_result["source"] = img.get("source", "unknown")
                    wp_images.append(wp_result)
                    if i == 0:
                        featured_image_id = wp_result.get("id")

        # ÉTAPE 4 — Injection images HTML
        print(f"\n[DA] ÉTAPE 4 — Injection images dans l'article...")
        updated_html = inject_images_in_html(article["html_content"], wp_images)
        article["html_content"] = updated_html
        article["featured_image_id"] = featured_image_id
        article["images"] = wp_images

        # ÉTAPE 5 — Pins Pinterest
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

        data["article"] = article
        data["pins"] = pins
        data["status"] = "ready_to_publish"
        save_article(filepath, data, dry_run)

        print(f"\n[DA] ✅ Directeur Artistique terminé")
        print(f"  Images article : {len(wp_images)}")
        print(f"  Pins Pinterest : {len(pins)}/5")
        print(f"  Featured image ID : {featured_image_id}")

        if not dry_run:
            send_telegram(
                f"🎨 <b>Directeur Artistique — Terminé</b>\n\n"
                f"🔑 {keyword}\n"
                f"🖼️ Images : {len(wp_images)}\n"
                f"📌 Pins : {len(pins)}/5\n"
                f"➡️ Prêt pour le Publisher"
            )

    except Exception as e:
        print(f"[DA] ❌ Erreur: {str(e)}")
        send_telegram(f"❌ <b>DA — Erreur</b>\n\n{str(e)}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Directeur Artistique — Garten Gefühl")
    parser.add_argument("--article", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run(article_path=args.article, dry_run=args.dry_run)
