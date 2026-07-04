"""
Directeur Artistique Agent — Main

CHANGELOG v2:
- Bug 1 + 2 corrigés : injection par placeholders [BILD_X] au lieu d'injection par position.
  Plus d'images dupliquées ni d'images empilées — GPT place les placeholders aux bons endroits.
- n_images = 5 : 1 featured image + 4 images texte ([BILD_1] à [BILD_4]).
- Bug 3 : validation Codex plus stricte (voir image_sourcer.py).
- Bug 4 : featured_image_id correctement transmis au Publisher.
  ⚠️ Côté WordPress : activer dans GeneratePress → Personnaliser → Blog →
    Article unique → "Image mise en avant" pour l'afficher en haut de l'article.
"""

import os
import json
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


def replace_image_placeholders(html_content: str, images: list) -> str:
    """
    Remplace les placeholders [BILD_1] à [BILD_N] par les balises <figure> correspondantes.

    Logique :
    - images[0] = featured image (déjà assignée via featured_media WP) → PAS de placeholder
    - images[1] → [BILD_1], images[2] → [BILD_2], images[3] → [BILD_3], images[4] → [BILD_4]

    Si un placeholder est absent (GPT a oublié), l'image est ajoutée en fin de contenu (fallback).
    Si un placeholder est présent mais plus d'images disponibles, il est supprimé proprement.
    """
    result = html_content

    # images[0] = featured only → on commence à images[1] pour les placeholders texte
    text_images = images[1:] if len(images) > 1 else []

    injected = 0
    for i, img in enumerate(text_images, 1):
        placeholder = f"[BILD_{i}]"
        img_url = img.get("url") or img.get("path", "")
        alt = img.get("alt_text", "")

        img_html = (
            f'\n<figure class="wp-block-image size-large" style="margin:30px 0 30px 0;">'
            f'<img src="{img_url}" alt="{alt}" loading="lazy" /></figure>\n'
        )

        if placeholder in result:
            result = result.replace(placeholder, img_html, 1)
            injected += 1
            print(f"[DA] ✅ {placeholder} → image {i} injectée")
        else:
            # Fallback : GPT n'a pas placé ce placeholder → append en fin de contenu
            result += img_html
            injected += 1
            print(f"[DA] ⚠️ {placeholder} absent — image {i} ajoutée en fin de contenu (fallback)")

    # Nettoyer les placeholders orphelins restants (GPT en a trop mis)
    for k in range(1, 6):
        orphan = f"[BILD_{k}]"
        if orphan in result:
            result = result.replace(orphan, "")
            print(f"[DA] 🧹 {orphan} orphelin supprimé")

    print(f"[DA] {injected}/{len(text_images)} images injectées via placeholders")
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

        # ÉTAPE 2 — Sourcing images
        # 5 images : index 0 = featured image, index 1-4 = [BILD_1] à [BILD_4] dans le texte
        queries = CATEGORY_IMAGE_KEYWORDS.get(category, ["garden"])[:4]
        n_images = 5

        if dry_run:
            images_data = [{"path": f"DRY_{i}", "source": "dry", "alt_text": keyword,
                           "source_id": f"dry_{i}"} for i in range(n_images)]
            print(f"[DA] DRY RUN — {n_images} images simulées")
        else:
            print(f"\n[DA] ÉTAPE 2 — Sourcing {n_images} images uniques...")
            images_data = fetch_n_images(queries, n_images, img_dir, keyword, category)

        print(f"[DA] {len(images_data)} images uniques trouvées")

        if len(images_data) < 2:
            raise Exception(f"Pas assez d'images ({len(images_data)}/5) — pipeline arrêté")

        # ÉTAPE 3 — Upload WordPress
        print(f"\n[DA] ÉTAPE 3 — Upload WordPress...")
        wp_images = []
        featured_image_id = None

        for i, img in enumerate(images_data):
            if dry_run:
                wp_img = {"id": 999 + i, "url": img["path"], "alt_text": img["alt_text"]}
            else:
                # Image 0 : alt_text = keyword exact (requis par Rank Math)
                alt = keyword if i == 0 else f"{keyword} - Bild {i + 1}"
                wp_img = upload_to_wordpress_media(img["path"], alt, keyword)

            if wp_img:
                wp_images.append(wp_img)
                if i == 0:
                    featured_image_id = wp_img.get("id")

        print(f"[DA] {len(wp_images)} images uploadées | Featured ID: {featured_image_id}")

        # ÉTAPE 4 — Remplacement placeholders [BILD_1] à [BILD_4]
        print(f"\n[DA] ÉTAPE 4 — Injection images par placeholders...")
        article["html_content"] = replace_image_placeholders(article["html_content"], wp_images)
        article["featured_image_id"] = featured_image_id
        article["images"] = wp_images

        # ÉTAPE 5 — Pins Pinterest (basé sur l'image featured = index 0)
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
            send_telegram(
                f"🎨 <b>DA</b> — {keyword}\n"
                f"🖼️ {len(wp_images)} images | 📌 {len(pins)}/5 pins\n"
                f"🏷️ Featured ID: {featured_image_id}"
            )

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
