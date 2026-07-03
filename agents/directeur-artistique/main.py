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
    raise FileNotFoundError("Aucun article approuvé")


def seed_image_history_from_wordpress():
    if not HISTORY_AVAILABLE:
        return
    wp_url = os.getenv("WP_URL", "https://xn--garten-gefhl-mlb.de")
    wp_user = os.getenv("WP_USER")
    wp_password = os.getenv("WP_APP_PASSWORD", "").replace(" ", "")
    if not wp_user or not wp_password:
        return
    try:
        resp = requests.get(f"{wp_url}/wp-json/wp/v2/media", auth=(wp_user, wp_password),
                           params={"per_page": 100, "media_type": "image"}, timeout=15)
        if resp.status_code == 200:
            history = load_image_history()
            existing = set(history.get("used_urls", []))
            new = [i["source_url"] for i in resp.json() if i.get("source_url") and i["source_url"] not in existing]
            existing.update(new)
            history["used_urls"] = list(existing)
            save_image_history(history)
            if new:
                print(f"[DA] {len(new)} images WP ajoutées à l'historique")
    except Exception as e:
        print(f"[DA] ⚠️ Sync WP: {e}")


def get_image_queries(brief: dict, article: dict) -> list:
    category = brief.get("categorie_wp", "Garten Gefühl")
    return CATEGORY_IMAGE_KEYWORDS.get(category, ["garden"])[:4]


def upload_to_wordpress_media(image_path: str, alt_text: str, keyword: str) -> dict:
    wp_url = os.getenv("WP_URL", "https://xn--garten-gefhl-mlb.de")
    wp_user = os.getenv("WP_USER")
    wp_password = os.getenv("WP_APP_PASSWORD", "").replace(" ", "")
    if not wp_user or not wp_password:
        return {}
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
        filename = Path(image_path).name
        resp = requests.post(
            f"{wp_url}/wp-json/wp/v2/media",
            headers={"Content-Disposition": f'attachment; filename="{filename}"', "Content-Type": "image/webp"},
            auth=(wp_user, wp_password), data=image_data, timeout=30
        )
        if resp.status_code in (200, 201):
            media = resp.json()
            media_id = media.get("id")
            requests.post(f"{wp_url}/wp-json/wp/v2/media/{media_id}", auth=(wp_user, wp_password),
                         json={"alt_text": alt_text, "caption": f"Foto: {keyword}"}, timeout=10)
            print(f"[DA] Uploadée: ID {media_id}")
            return {"id": media_id, "url": media.get("source_url", ""), "alt_text": alt_text}
        print(f"[DA] Erreur upload: {resp.status_code}")
        return {}
    except Exception as e:
        print(f"[DA] Erreur upload: {e}")
        return {}


def inject_images_in_html(html_content: str, images: list) -> str:
    """
    Injecte les images de façon espacée dans le HTML.
    Règles :
    - Skip les 1000 premiers chars (intro + table des matières)
    - Distance minimum 500 chars entre deux images
    - Espacement régulier basé sur le nombre de </p> disponibles
    """
    if not images:
        return html_content

    p_positions = [m.end() for m in re.finditer(r"</p>", html_content, re.IGNORECASE)]
    # Filtrer les positions après les 1000 premiers chars
    valid_positions = [p for p in p_positions if p >= 1000]

    if not valid_positions:
        return html_content

    result = html_content
    offset = 0
    image_index = 0
    last_inject_pos = 0

    # Diviser les positions disponibles en N+1 segments égaux
    n_images = len(images)
    segment_size = len(valid_positions) // (n_images + 1)
    if segment_size == 0:
        segment_size = 1

    # Choisir une position par segment
    inject_positions = []
    for k in range(1, n_images + 1):
        idx = min(k * segment_size, len(valid_positions) - 1)
        pos = valid_positions[idx]
        # Vérifier distance minimum
        if not inject_positions or pos - inject_positions[-1] >= 500:
            inject_positions.append(pos)

    for pos in inject_positions:
        if image_index >= len(images):
            break

        img = images[image_index]
        img_html = (
            f'\n<figure class="wp-block-image size-large" style="margin:25px 0;">'
            f'<img src="{img.get("url", img.get("path", ""))}" '
            f'alt="{img.get("alt_text", "")}" loading="lazy" /></figure>\n'
        )

        inject_pos = pos + offset
        result = result[:inject_pos] + img_html + result[inject_pos:]
        offset += len(img_html)
        image_index += 1

    print(f"[DA] {image_index} images injectées")
    return result


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
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
        except:
            pass


def run(article_path: str = None, dry_run: bool = False):
    print("=" * 60)
    print(f"[DA] Démarrage — {datetime.now().isoformat()}")
    print("=" * 60)

    try:
        reset_article_url_cache()

        if not dry_run:
            print(f"[DA] Sync historique WP...")
            seed_image_history_from_wordpress()

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

        print(f"[DA] Keyword : {keyword} | Catégorie : {category}")

        today = date.today().isoformat()
        img_dir = Path(IMAGES_DIR) / today
        pins_dir = Path(PINS_DIR) / today
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(pins_dir, exist_ok=True)

        # ÉTAPE 2 — Sourcing images
        print(f"\n[DA] ÉTAPE 2 — Sourcing images...")
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
        print(f"\n[DA] ÉTAPE 3 — Upload WordPress...")
        wp_images = []
        featured_image_id = None

        for i, img in enumerate(images_data):
            if dry_run:
                wp_images.append({"id": 999+i, "url": img["path"], "alt_text": img["alt_text"], "source": img.get("source")})
                print(f"[DA] DRY RUN: {img['path']}")
            else:
                wp_result = upload_to_wordpress_media(img["path"], img["alt_text"], keyword)
                if wp_result:
                    wp_result["source"] = img.get("source", "unknown")
                    wp_images.append(wp_result)
                    if i == 0:
                        featured_image_id = wp_result.get("id")

        # ÉTAPE 4 — Injection images
        print(f"\n[DA] ÉTAPE 4 — Injection images...")
        article["html_content"] = inject_images_in_html(article["html_content"], wp_images)
        article["featured_image_id"] = featured_image_id
        article["images"] = wp_images

        # ÉTAPE 5 — Pins Pinterest
        print(f"\n[DA] ÉTAPE 5 — Pins Pinterest...")
        base_image = images_data[0]["path"] if images_data else None
        pins = []

        if base_image and not dry_run:
            pins = create_all_pins(base_image_path=base_image, article_title=article["seo_title"],
                                   keyword=keyword, category=category, pins_dir=str(pins_dir))
        else:
            pins = [{"account": acc, "title": article["seo_title"], "path": "DRY_RUN"}
                    for acc in ["Blumenliebe DE", "Balkon Ideen DE", "Rosenfreude DE", "Terrasse & Garten DE", "Garten Gefühl"]]
            if dry_run:
                print("[DA] DRY RUN — 5 pins simulés")

        data["article"] = article
        data["pins"] = pins
        data["status"] = "ready_to_publish"
        save_article(filepath, data, dry_run)

        print(f"\n[DA] ✅ Terminé — Images: {len(wp_images)} | Pins: {len(pins)}/5 | Featured: {featured_image_id}")

        if not dry_run:
            send_telegram(f"🎨 <b>DA</b> — {keyword}\n🖼️ {len(wp_images)} images | 📌 {len(pins)}/5 pins")

    except Exception as e:
        print(f"[DA] ❌ {str(e)}")
        send_telegram(f"❌ <b>DA Erreur</b>\n{str(e)}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--article", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(article_path=args.article, dry_run=args.dry_run)
