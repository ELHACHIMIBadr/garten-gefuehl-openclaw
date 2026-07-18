"""
Directeur Artistique Agent — Pin Creator v3.3

v3.3 — 5 pins par compte (25 total) :
- Chaque compte reçoit 5 images GPT distinctes avec prompt varié
- Naming : pin_01_Blumenliebe_DE_v1.webp … pin_01_Blumenliebe_DE_v5.webp
- Fallback Pexels/Pixabay si GPT échoue
- Déduplication MD5 par compte

v3.2 — Fix Codex image gen (inchangé)
"""

import os
import io
import json
import hashlib
import subprocess
import random
import time
import requests
from pathlib import Path
from config import PIN_WIDTH, PIN_HEIGHT, PINTEREST_ACCOUNTS

from dotenv import load_dotenv
load_dotenv("/root/garten-gefuehl-openclaw/config/.env")

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ============================================================
# PROMPTS GPT-IMAGE — 5 variations par compte
# ============================================================

# Chaque compte a une liste de 5 angles différents
NICHE_PROMPT_VARIATIONS = {
    "Blumenliebe DE": [
        "Professional Pinterest photo: close-up of beautiful {keyword} flowers in a German garden, soft bokeh background, warm golden hour light, vibrant natural colors, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: wide shot of a colorful German flower garden featuring {keyword}, lush green borders, morning mist, natural light, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: hands planting {keyword} flowers in garden soil, close-up, shallow depth of field, warm daylight, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: bouquet of {keyword} flowers in a rustic vase on a garden table, soft natural light, blurred garden background, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: garden path lined with {keyword} flowers in full bloom, German cottage garden style, golden afternoon light, portrait 2:3. No text, no watermark.",
    ],
    "Balkon Ideen DE": [
        "Professional Pinterest photo: cozy German apartment balcony with {keyword}, colorful flower boxes, lush greenery, warm morning light, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: small urban balcony transformed with {keyword}, hanging plants, fairy lights, evening ambiance, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: balcony garden close-up showing {keyword} in terracotta pots, sunlight, brick wall background, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: aerial view of a German apartment balcony with {keyword}, wooden furniture, cushions, green plants, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: balcony herb garden featuring {keyword}, wooden crates, morning dew, soft natural light, portrait 2:3. No text, no watermark.",
    ],
    "Rosenfreude DE": [
        "Professional Pinterest photo: gorgeous roses in a German garden related to {keyword}, soft pink and red blooms, lush green foliage, natural sunlight, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: climbing roses on a garden arch featuring {keyword}, romantic garden scene, warm light, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: close-up of a single perfect rose bloom related to {keyword}, water droplets, blurred garden background, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: rose garden path with {keyword}, mixed colors, stone pathway, cottage garden style, golden hour, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: hands holding freshly cut roses from a garden, {keyword}, rustic garden setting, warm light, portrait 2:3. No text, no watermark.",
    ],
    "Terrasse & Garten DE": [
        "Professional Pinterest photo: elegant German terrace garden with {keyword}, outdoor furniture, potted plants, stone paving, warm afternoon light, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: cozy terrace dining area surrounded by {keyword}, string lights, summer evening ambiance, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: modern terrace with {keyword}, minimalist design, concrete planters, lush greenery, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: rustic wooden terrace decorated with {keyword}, lanterns, wildflower pots, countryside view, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: terrace corner lounge area featuring {keyword}, comfortable chairs, side table, garden backdrop, portrait 2:3. No text, no watermark.",
    ],
    "Garten Gefühl": [
        "Professional Pinterest photo: idyllic German garden scene featuring {keyword}, colorful flower beds, lush lawn, blooming trees, warm natural light, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: peaceful garden reading nook surrounded by {keyword}, hammock, lush greenery, dappled sunlight, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: vegetable and flower garden with {keyword}, raised beds, garden path, morning light, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: garden pond area with {keyword}, water plants, stones, reflections, soft natural light, portrait 2:3. No text, no watermark.",
        "Professional Pinterest photo: spring garden awakening with {keyword}, fresh sprouts, garden tools, rich soil, warm light, portrait 2:3. No text, no watermark.",
    ],
}

# Textes overlay par compte — 5 variations
PIN_OVERLAY_TEXTS = {
    "Blumenliebe DE": [
        "Frühlingsblumen die begeistern",
        "Blumen für den Garten",
        "Blumenideen für zuhause",
        "Garten voller Blüten",
        "Blumen richtig pflanzen",
    ],
    "Balkon Ideen DE": [
        "Balkon-Ideen für den Frühling",
        "Balkon bepflanzen leicht gemacht",
        "Kleiner Balkon große Wirkung",
        "Balkon gestalten mit Pflanzen",
        "Balkon Deko Ideen",
    ],
    "Rosenfreude DE": [
        "Rosen richtig pflanzen und pflegen",
        "Rosengarten anlegen",
        "Schöne Rosen im Garten",
        "Rosen für Anfänger",
        "Kletterrosen am Haus",
    ],
    "Terrasse & Garten DE": [
        "Terrasse im Frühling gestalten",
        "Terrasse gemütlich einrichten",
        "Terrassenideen für jeden Stil",
        "Terrasse bepflanzen",
        "Schöne Terrasse gestalten",
    ],
    "Garten Gefühl": [
        "Garten-Tipps für jeden Tag",
        "Traumgarten anlegen",
        "Garten neu gestalten",
        "Naturgarten Ideen",
        "Garten mit Liebe gestalten",
    ],
}

NICHE_FALLBACK_QUERIES = {
    "Blumenliebe DE":       ["spring garden flowers", "colorful blooming flowers", "flower garden close up"],
    "Balkon Ideen DE":      ["balcony garden plants", "apartment balcony flowers", "urban balcony greenery"],
    "Rosenfreude DE":       ["rose garden bloom", "pink roses bush", "climbing roses trellis"],
    "Terrasse & Garten DE": ["terrace garden patio", "outdoor terrace plants", "garden terrace furniture"],
    "Garten Gefühl":        ["beautiful garden landscape", "garden path flowers", "lush green garden"],
}

PINS_PER_ACCOUNT = 5  # 5 pins par compte = 25 total


# ============================================================
# UTILS
# ============================================================

def _file_hash(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""


def _is_valid_image(path: str, min_kb: int = 5) -> bool:
    if not os.path.exists(path):
        return False
    if os.path.getsize(path) / 1024 < min_kb:
        return False
    if PIL_AVAILABLE:
        try:
            img = Image.open(path)
            img.verify()
            return True
        except Exception:
            return False
    return True


def _compress_to_max_kb(image_path: str, max_kb: int = 200):
    if not PIL_AVAILABLE or not os.path.exists(image_path):
        return
    if os.path.getsize(image_path) / 1024 <= max_kb:
        return
    try:
        img = Image.open(image_path).convert("RGB")
        quality = 80
        while quality >= 30:
            img.save(image_path, format="WEBP", quality=quality)
            if os.path.getsize(image_path) / 1024 <= max_kb:
                break
            quality -= 10
        print(f"[PIN] Compressé à {os.path.getsize(image_path)/1024:.0f}KB (q={quality})")
    except Exception as e:
        print(f"[PIN] Compression erreur : {e}")


def _ensure_pin_dimensions(image_path: str):
    if not PIL_AVAILABLE:
        return
    try:
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        if w == PIN_WIDTH and h == PIN_HEIGHT:
            return
        target_ratio = PIN_WIDTH / PIN_HEIGHT
        orig_ratio = w / h
        if abs(orig_ratio - target_ratio) > 0.02:
            if orig_ratio > target_ratio:
                new_w = int(h * target_ratio)
                left = (w - new_w) // 2
                img = img.crop((left, 0, left + new_w, h))
            else:
                new_h = int(w / target_ratio)
                img = img.crop((0, 0, w, min(new_h, h)))
        img = img.resize((PIN_WIDTH, PIN_HEIGHT), Image.LANCZOS)
        img.save(image_path, format="WEBP", quality=85)
    except Exception as e:
        print(f"[PIN] Resize erreur : {e}")


# ============================================================
# GPT-IMAGE VIA CODEX CLI
# ============================================================

def generate_pin_image_via_codex(prompt: str, save_path: str) -> bool:
    if os.path.exists(save_path):
        os.remove(save_path)

    safe_path = save_path.replace("\\", "/")
    codex_prompt = f"""Generate a photo-realistic image with this description:

{prompt}

Save the generated image to this exact file path: {safe_path}

The image must be:
- 1024x1536 pixels (portrait orientation)
- Saved as a file on disk at the path above

After saving, verify the file exists and print: IMAGE_SAVED_OK
"""
    try:
        result = subprocess.run(
            ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox"],
            input=codex_prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180
        )
        if _is_valid_image(save_path):
            print(f"[PIN] ✅ GPT-image généré : {Path(save_path).name}")
            return True
        print(f"[PIN] ❌ GPT-image échoué — {result.stdout[:150]}")
        return False
    except subprocess.TimeoutExpired:
        print(f"[PIN] ❌ GPT-image timeout")
        return False
    except Exception as e:
        print(f"[PIN] ❌ GPT-image erreur : {e}")
        return False


# ============================================================
# FALLBACK — PEXELS / PIXABAY
# ============================================================

def _process_and_save_pin_image(image_bytes: bytes, save_path: str) -> bool:
    if not PIL_AVAILABLE:
        with open(save_path, "wb") as f:
            f.write(image_bytes)
        return True
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        orig_w, orig_h = img.size
        target_ratio = PIN_WIDTH / PIN_HEIGHT
        orig_ratio = orig_w / orig_h
        if orig_ratio > target_ratio:
            new_w = int(orig_h * target_ratio)
            left = (orig_w - new_w) // 2
            img = img.crop((left, 0, left + new_w, orig_h))
        else:
            new_h = int(orig_w / target_ratio)
            img = img.crop((0, 0, orig_w, min(new_h, orig_h)))
        img = img.resize((PIN_WIDTH, PIN_HEIGHT), Image.LANCZOS)
        quality = 82
        img.save(save_path, format="WEBP", quality=quality)
        while os.path.getsize(save_path) / 1024 > 195 and quality >= 40:
            quality -= 8
            img.save(save_path, format="WEBP", quality=quality)
        return True
    except Exception as e:
        print(f"[PIN] Erreur traitement image : {e}")
        return False


def _fetch_from_pexels(query: str, save_path: str) -> bool:
    api_key = os.getenv("PEXELS_API_KEY", "")
    if not api_key:
        return False
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": api_key},
            params={"query": query, "orientation": "portrait", "per_page": 15, "page": random.randint(1, 3)},
            timeout=15,
        )
        if resp.status_code != 200:
            return False
        photos = resp.json().get("photos", [])
        if not photos:
            return False
        photo = random.choice(photos)
        img_url = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("original", "")
        if not img_url:
            return False
        img_resp = requests.get(img_url, timeout=30)
        return _process_and_save_pin_image(img_resp.content, save_path)
    except Exception:
        return False


def _fetch_from_pixabay(query: str, save_path: str) -> bool:
    api_key = os.getenv("PIXABAY_API_KEY", "")
    if not api_key:
        return False
    try:
        resp = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": api_key, "q": query, "orientation": "vertical",
                "image_type": "photo", "per_page": 15,
                "page": random.randint(1, 3), "safesearch": "true",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return False
        hits = resp.json().get("hits", [])
        if not hits:
            return False
        hit = random.choice(hits)
        img_url = hit.get("largeImageURL", "")
        if not img_url:
            return False
        img_resp = requests.get(img_url, timeout=30)
        return _process_and_save_pin_image(img_resp.content, save_path)
    except Exception:
        return False


def fetch_fallback_image(account_name: str, keyword: str, save_path: str) -> bool:
    queries = NICHE_FALLBACK_QUERIES.get(account_name, ["garden flowers"])
    keyword_en = keyword.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    all_queries = queries + [keyword_en]
    for query in all_queries:
        if _fetch_from_pexels(query, save_path):
            return True
        if _fetch_from_pixabay(query, save_path):
            return True
    return False


# ============================================================
# OVERLAY TEXTE
# ============================================================

def _draw_text_with_shadow(draw, position, text, font, fill, shadow_color=(0, 0, 0), shadow_offset=2):
    x, y = position
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill)


def add_text_overlay(image_path: str, text: str, site_url: str = "") -> bool:
    if not PIL_AVAILABLE:
        return True
    try:
        img = Image.open(image_path).convert("RGBA")
        w, h = img.size
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        band_h = int(h * 0.18)
        for y in range(band_h):
            alpha = int(180 * (1 - y / band_h) ** 1.5)
            draw_overlay.rectangle([(0, y), (w, y + 1)], fill=(0, 0, 0, alpha))
        bottom_h = int(h * 0.08)
        for y in range(h - bottom_h, h):
            alpha = int(160 * ((y - (h - bottom_h)) / bottom_h) ** 1.3)
            draw_overlay.rectangle([(0, y), (w, y + 1)], fill=(0, 0, 0, alpha))
        img = Image.alpha_composite(img, overlay).convert("RGB")
        draw = ImageDraw.Draw(img)
        try:
            font_main = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(h * 0.036))
            font_url = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(h * 0.020))
        except Exception:
            font_main = ImageFont.load_default()
            font_url = ImageFont.load_default()
        words = text.split()
        lines, current = [], ""
        for word in words:
            test = (current + " " + word).strip()
            if len(test) <= 26:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        lines = lines[:3]
        line_height = int(h * 0.048)
        total_h = len(lines) * line_height
        y_start = max(int(h * 0.02), (band_h - total_h) // 2)
        for i, line in enumerate(lines):
            _draw_text_with_shadow(draw, (int(w * 0.06), y_start + i * line_height),
                                   line, font=font_main, fill=(255, 255, 255))
        # URL watermark supprimé — Pinterest pénalise les URLs sur l'image
        img.save(image_path, format="WEBP", quality=88)
        return True
    except Exception as e:
        print(f"[PIN] Overlay erreur : {e}")
        return True


# ============================================================
# POINT D'ENTRÉE — create_all_pins
# ============================================================

def create_all_pins(
    base_image_path: str,
    article_title: str,
    keyword: str,
    category: str,
    pins_dir: str,
) -> list:
    """
    Crée 5 pins par compte = 25 pins total.
    Naming : pin_01_Blumenliebe_DE_v1.webp … pin_01_Blumenliebe_DE_v5.webp
    """
    os.makedirs(pins_dir, exist_ok=True)
    pins_created = []

    for account_idx, account_name in enumerate(PINTEREST_ACCOUNTS):
        account_slug = (
            account_name.replace(" ", "_").replace("&", "und").replace("ü", "u")
        )
        prompts = NICHE_PROMPT_VARIATIONS.get(account_name, [
            f"Professional Pinterest photo: beautiful German garden, {keyword}, portrait 2:3. No text."
        ] * 5)
        overlay_texts = PIN_OVERLAY_TEXTS.get(account_name, [article_title] * 5)

        seen_hashes_account = set()
        account_pins = []

        print(f"\n[PIN] ══ Compte {account_idx + 1}/5 — {account_name} ══")

        for v in range(PINS_PER_ACCOUNT):
            save_path = str(Path(pins_dir) / f"pin_{account_idx + 1:02d}_{account_slug}_v{v + 1}.webp")
            prompt = prompts[v % len(prompts)].format(keyword=keyword)
            overlay_text = overlay_texts[v % len(overlay_texts)]

            print(f"[PIN] ── Variation {v + 1}/{PINS_PER_ACCOUNT} ──")
            success = False

            # Étape 1 : GPT-image
            print(f"[PIN] GPT-image...")
            if generate_pin_image_via_codex(prompt, save_path):
                h = _file_hash(save_path)
                if h and h not in seen_hashes_account:
                    seen_hashes_account.add(h)
                    success = True
                    print(f"[PIN] ✅ GPT-image unique")
                else:
                    print(f"[PIN] ⚠️ GPT doublon → fallback")
                    if os.path.exists(save_path):
                        os.remove(save_path)

            # Étape 2 : Fallback Pexels/Pixabay
            if not success:
                print(f"[PIN] Fallback stock photo...")
                if fetch_fallback_image(account_name, keyword, save_path):
                    h = _file_hash(save_path)
                    if h and h not in seen_hashes_account:
                        seen_hashes_account.add(h)
                    success = True

            # Étape 3 : Dernier recours — base image
            if not success and base_image_path and os.path.exists(base_image_path):
                print(f"[PIN] Dernier recours : base image")
                try:
                    with open(base_image_path, "rb") as f:
                        img_bytes = f.read()
                    if _process_and_save_pin_image(img_bytes, save_path):
                        success = True
                except Exception:
                    pass

            # Étape 4 : Finalisation
            if success and os.path.exists(save_path):
                _ensure_pin_dimensions(save_path)
                add_text_overlay(save_path, overlay_text)
                _compress_to_max_kb(save_path, max_kb=200)
                account_pins.append({
                    "path": save_path,
                    "account": account_name,
                    "title": overlay_text,
                    "index": account_idx + 1,
                    "variation": v + 1,
                })
                print(f"[PIN] ✅ Variation {v + 1} TERMINÉE")
            else:
                print(f"[PIN] ❌ Variation {v + 1} ÉCHOUÉE")

            time.sleep(2)

        print(f"[PIN] ✅ {len(account_pins)}/{PINS_PER_ACCOUNT} pins — {account_name}")
        pins_created.extend(account_pins)

    print(f"\n[PIN] ══ Total : {len(pins_created)}/25 pins créés ══")
    return pins_created
