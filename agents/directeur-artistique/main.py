"""
Directeur Artistique Agent — Main

CHANGELOG v4:
- Pins générés pour LES 5 NICHES à chaque exécution (pas seulement la niche de l'article).
  Chaque compte reçoit 5 pins avec son propre keyword niche.
- Fix critique v3 conservé : statut "ready_to_publish" écrit AVANT les pins.
"""

import os
import json
import argparse
import requests
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv("/root/garten-gefuehl-openclaw/config/.env")

from config import ARTICLES_DIR, IMAGES_DIR, PINS_DIR, CATEGORY_IMAGE_KEYWORDS, PINTEREST_ACCOUNTS
from image_sourcer import fetch_n_images, reset_article_cache
from pin_creator import create_pins_for_account

import sys
sys.path.insert(0, "/root/garten-gefuehl-openclaw/agents")
try:
    from history import load_image_history, save_image_history
    HISTORY_AVAILABLE = True
except ImportError:
    HISTORY_AVAILABLE = False


# ── Keyword par niche pour les pins ──────────────────────────
# Indépendant de l'article du jour — chaque compte a son propre keyword pin
NICHE_PIN_KEYWORDS = {
    "Blumenliebe DE":      ("Blumen",        "garten blumen ideen"),
    "Balkon Ideen DE":     ("Balkon",        "balkon gestalten ideen"),
    "Rosenfreude DE":      ("Rosen",         "rosen pflanzen pflegen"),
    "Terrasse & Garten DE":("Terrasse",      "terrasse gestalten tipps"),
    "Garten Gefühl":       ("Garten Gefühl", "garten inspiration ideen"),
}


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
    result = html_content
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
            result += img_html
            injected += 1
            print(f"[DA] ⚠️ {placeholder} absent — image {i} ajoutée en fin")
    for k in range(1, 6):
        orphan = f"[BILD_{k}]"
        if orphan in result:
            result = result.replace(orphan, "")
            print(f"[DA] 🧹 {orphan} orphelin supprimé")
    print(f"[DA] {injected}/{len(text_images)} images injectées")
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
        except Exception:
            pass


def generate_all_pins(pins_dir: str, article_title: str, dry_run: bool = False) -> list:
    """
    Génère 5 pins pour CHAQUE compte Pinterest (25 pins total).
    Chaque compte utilise son propre keyword niche — indépendant de l'article du jour.
    """
    all_pins = []

    for account_idx, account_name in enumerate(PINTEREST_ACCOUNTS):
        categorie, keyword = NICHE_PIN_KEYWORDS[account_name]
        account_slug = (
            account_name.replace(" ", "_").replace("&", "und")
            .replace("ü", "u").replace("Ü", "U")
        )

        print(f"\n[DA] 📌 Pins {account_name} — keyword: {keyword}")

        if dry_run:
            for v in range(5):
                all_pins.append({
                    "path": f"DRY_{account_slug}_v{v+1}",
                    "account": account_name,
                    "title": f"DRY {keyword}",
                    "variation": v + 1,
                })
            continue

        try:
            account_pins = create_pins_for_account(
                account_name=account_name,
                account_idx=account_idx,
                keyword=keyword,
                categorie=categorie,
                pins_dir=pins_dir,
                n_pins=5,
            )
            all_pins.extend(account_pins)
            print(f"[DA] ✅ {len(account_pins)}/5 pins générés — {account_name}")
        except Exception as e:
            print(f"[DA] ⚠️ Pins échoués pour {account_name} : {e}")

    return all_pins


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

        # ── ÉTAPE 2 — Sourcing images article ────────────────
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
            raise Exception(f"Pas assez d'images ({len(images_data)}/5)")

        # ── ÉTAPE 3 — Upload WordPress ────────────────────────
        print(f"\n[DA] ÉTAPE 3 — Upload WordPress...")
        wp_images = []
        featured_image_id = None

        for i, img in enumerate(images_data):
            if dry_run:
                wp_img = {"id": 999 + i, "url": img["path"], "alt_text": img["alt_text"]}
            else:
                alt = keyword if i == 0 else f"{keyword} - Bild {i + 1}"
                wp_img = upload_to_wordpress_media(img["path"], alt, keyword)
            if wp_img:
                wp_images.append(wp_img)
                if i == 0:
                    featured_image_id = wp_img.get("id")

        print(f"[DA] {len(wp_images)} images uploadées | Featured ID: {featured_image_id}")

        # ── ÉTAPE 4 — Injection placeholders ─────────────────
        print(f"\n[DA] ÉTAPE 4 — Injection images par placeholders...")
        article["html_content"] = replace_image_placeholders(article["html_content"], wp_images)
        article["featured_image_id"] = featured_image_id
        article["images"] = wp_images

        # ── ÉTAPE 4b — Écrire ready_to_publish AVANT les pins ─
        data["article"] = article
        data["pins"] = []
        data["status"] = "ready_to_publish"
        save_article(filepath, data, dry_run)
        print(f"[DA] ✅ Statut 'ready_to_publish' écrit")

        # ── ÉTAPE 5 — Pins pour LES 5 COMPTES (non bloquant) ──
        print(f"\n[DA] ÉTAPE 5 — Génération 25 pins (5 comptes × 5 variations)...")
        pins = []
        try:
            pins = generate_all_pins(pins_dir, article["seo_title"], dry_run)
            print(f"[DA] ✅ {len(pins)}/25 pins générés")
        except Exception as e:
            print(f"[DA] ⚠️ Pins échoués (non bloquant) : {e}")
            send_telegram(f"⚠️ <b>DA — Pins incomplets</b>\n{keyword}\n{str(e)[:150]}")

        if pins:
            data["pins"] = pins
            save_article(filepath, data, dry_run)

        print(f"\n[DA] ✅ Images: {len(wp_images)} | Pins: {len(pins)}/25 | Featured: {featured_image_id}")

        if not dry_run:
            send_telegram(
                f"🎨 <b>DA</b> — {keyword}\n"
                f"🖼️ {len(wp_images)} images article\n"
                f"📌 {len(pins)}/25 pins générés\n"
                f"✅ Prêt pour publication"
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
