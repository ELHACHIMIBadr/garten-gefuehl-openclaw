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
from image_sourcer import fetch_n_images, reset_article_cache
from pin_creator import create_all_pins

import sys
sys.path.insert(0, "/root/garten-gefuehl-openclaw/agents")
try:
    from history import load_image_history, save_image_history
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


def upload_to_wordpress_media(image_path: str, alt_text: str, keyword: str) -> dict:
    wp_url = os.getenv("WP_URL", "https://xn--garten-gefhl-mlb.de")
    wp_user = os.getenv("WP_USER")
    wp_password = os.getenv("WP_APP_PASSWORD", "").replace(" ", "")
    if not wp_user or not wp_password:
        return {}
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
        resp = requests.post(
            f"{wp_url}/wp-json/wp/v2/media",
            headers={"Content-Disposition": f'attachment; filename="{Path(image_path).name}"',
                     "Content-Type": "image/webp"},
            auth=(wp_user, wp_password), data=image_data, timeout=30
        )
        if resp.status_code in (200, 201):
            media = resp.json()
            mid = media.get("id")
            requests.post(f"{wp_url}/wp-json/wp/v2/media/{mid}", auth=(wp_user, wp_password),
                         json={"alt_text": alt_text}, timeout=10)
            print(f"[DA] Uploadée: ID {mid}")
            return {"id": mid, "url": media.get("source_url", ""), "alt_text": alt_text}
        print(f"[DA] Erreur upload: {resp.status_code}")
    except Exception as e:
        print(f"[DA] Erreur upload: {e}")
    return {}


def inject_images_in_html(html_content: str, images: list) -> str:
    """
    Injection simple et robuste :
    Divise le texte en N+1 segments égaux (par caractères).
    Insère chaque image au point </p> le plus proche du point de découpe.
    """
    if not images:
        return html_content

    n = len(images)
    total_len = len(html_content)
    segment_len = total_len // (n + 1)

    # Trouver toutes les positions </p>
    p_positions = [m.end() for m in re.finditer(r"</p>", html_content, re.IGNORECASE)]
    # Filtrer : skip les 800 premiers chars (intro + TOC)
    p_positions = [p for p in p_positions if p > 800]

    if not p_positions:
        return html_content

    # Pour chaque image, trouver le </p> le plus proche du point de découpe
    inject_points = []
    used_p_indices = set()

    for k in range(1, n + 1):
        target = k * segment_len
        # Trouver le </p> le plus proche
        best_idx = None
        best_dist = float('inf')
        for j, p in enumerate(p_positions):
            if j in used_p_indices:
                continue
            dist = abs(p - target)
            if dist < best_dist:
                best_dist = dist
                best_idx = j
        if best_idx is not None:
            inject_points.append(p_positions[best_idx])
            used_p_indices.add(best_idx)

    # Trier les points d'injection
    inject_points.sort()

    # Insérer les images (en ordre inverse pour ne pas décaler les positions)
    result = html_content
    for i in range(len(inject_points) - 1, -1, -1):
        if i >= len(images):
            continue
        img = images[i]
        img_html = (
            f'\n<figure class="wp-block-image size-large" style="margin:30px 0;">'
            f'<img src="{img.get("url", img.get("path", ""))}" '
            f'alt="{img.get("alt_text", "")}" loading="lazy" /></figure>\n'
        )
        result = result[:inject_points[i]] + img_html + result[inject_points[i]:]

    print(f"[DA] {min(len(inject_points), len(images))} images injectées (espacées)")
    return result


def save_article(filepath, data, dry_run=False):
    if not dry_run:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[DA] Article mis à jour: {filepath}")


def send_telegram(msg):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    cid = os.getenv("TELEGRAM_CHAT_ID")
    if token and cid:
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": cid, "text": msg, "parse_mode": "HTML"}, timeout=10)
        except:
            pass


def run(article_path=None, dry_run=False):
    print("=" * 60)
    print(f"[DA] Démarrage — {datetime.now().isoformat()}")
    print("=" * 60)

    try:
        reset_article_cache()

        if not dry_run:
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
        print(f"[DA] Keyword: {keyword} | Catégorie: {category}")

        today = date.today().isoformat()
        img_dir = str(Path(IMAGES_DIR) / today)
        pins_dir = str(Path(PINS_DIR) / today)
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(pins_dir, exist_ok=True)

        # ÉTAPE 2 — Sourcing images (N images uniques)
        queries = CATEGORY_IMAGE_KEYWORDS.get(category, ["garden"])[:4]
        n_images = 4

        if dry_run:
            images_data = [{"path": f"DRY_{i}", "source": "dry", "alt_text": keyword,
                           "source_id": f"dry_{i}"} for i in range(n_images)]
            print(f"[DA] DRY RUN — {n_images} images simulées")
        else:
            print(f"\n[DA] ÉTAPE 2 — Sourcing {n_images} images uniques...")
            images_data = fetch_n_images(queries, n_images, img_dir, keyword, category)

        print(f"[DA] {len(images_data)} images uniques trouvées")

        # ÉTAPE 3 — Upload WordPress
        print(f"\n[DA] ÉTAPE 3 — Upload WordPress...")
        wp_images = []
        featured_image_id = None

        for i, img in enumerate(images_data):
            if dry_run:
                wp_images.append({"id": 999+i, "url": img["path"], "alt_text": img["alt_text"]})
            else:
                wp_result = upload_to_wordpress_media(img["path"], img["alt_text"], keyword)
                if wp_result:
                    wp_images.append(wp_result)
                    if i == 0:
                        featured_image_id = wp_result.get("id")

        # ÉTAPE 4 — Injection images espacées
        print(f"\n[DA] ÉTAPE 4 — Injection images...")
        article["html_content"] = inject_images_in_html(article["html_content"], wp_images)
        article["featured_image_id"] = featured_image_id
        article["images"] = wp_images

        # ÉTAPE 5 — Pins Pinterest
        print(f"\n[DA] ÉTAPE 5 — Pins Pinterest...")
        base_image = images_data[0]["path"] if images_data and not dry_run else None
        pins = []
        if base_image:
            pins = create_all_pins(base_image, article["seo_title"], keyword, category, pins_dir)
        else:
            pins = [{"account": a, "title": article["seo_title"], "path": "DRY"}
                    for a in ["Blumenliebe DE", "Balkon Ideen DE", "Rosenfreude DE",
                              "Terrasse & Garten DE", "Garten Gefühl"]]

        data["article"] = article
        data["pins"] = pins
        data["status"] = "ready_to_publish"
        save_article(filepath, data, dry_run)

        print(f"\n[DA] ✅ Images: {len(wp_images)} | Pins: {len(pins)}/5 | Featured: {featured_image_id}")

        if not dry_run:
            send_telegram(f"🎨 <b>DA</b> — {keyword}\n🖼️ {len(wp_images)} | 📌 {len(pins)}/5")

    except Exception as e:
        print(f"[DA] ❌ {str(e)}")
        send_telegram(f"❌ <b>DA</b>\n{str(e)}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--article", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(article_path=args.article, dry_run=args.dry_run)
