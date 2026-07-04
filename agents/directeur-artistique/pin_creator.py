"""
Directeur Artistique Agent — Pin Creator v2

NOUVEAU SYSTÈME :
- 1 image unique par compte générée via GPT-image-2 (Codex CLI)
- Prompt adapté à la niche de chaque compte
- Format natif Pinterest : 1024x1536 (ratio 2:3)
- Texte overlay propre et minimal via PIL
- Fallback : image article si GPT échoue
"""

import os
import io
import json
import subprocess
import requests
import base64
from pathlib import Path
from config import PIN_WIDTH, PIN_HEIGHT, PINTEREST_ACCOUNTS

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# Prompts GPT-image-2 par niche — visuels Pinterest professionnels
NICHE_PROMPTS = {
    "Blumenliebe DE": (
        "Beautiful close-up of colorful spring flowers in a German garden, "
        "soft natural bokeh background, warm golden hour light, "
        "vibrant pink and purple blooms, professional garden photography, "
        "no text, no watermark, portrait orientation"
    ),
    "Balkon Ideen DE": (
        "Stunning German apartment balcony overflowing with spring flowers and plants, "
        "colorful flower boxes, lush greenery, cozy outdoor seating, "
        "warm morning light, professional lifestyle photography, "
        "no text, no watermark, portrait orientation"
    ),
    "Rosenfreude DE": (
        "Gorgeous climbing roses on a German garden trellis in full spring bloom, "
        "soft pink and red roses, lush green leaves, natural sunlight, "
        "romantic garden atmosphere, professional botanical photography, "
        "no text, no watermark, portrait orientation"
    ),
    "Terrasse & Garten DE": (
        "Beautiful German terrace with spring garden plants and flowers, "
        "elegant outdoor furniture, potted plants, stone paving, "
        "lush garden background, warm afternoon light, "
        "no text, no watermark, portrait orientation"
    ),
    "Garten Gefühl": (
        "Idyllic German garden in spring, colorful flower beds, "
        "lush green lawn, blooming trees, peaceful garden path, "
        "warm natural sunlight, professional garden photography, "
        "no text, no watermark, portrait orientation"
    )
}

# Textes overlay par compte (court, accrocheur, en allemand)
PIN_TEXTS = {
    "Blumenliebe DE":       "Frühlingsblumen die begeistern 🌸",
    "Balkon Ideen DE":      "Balkon-Ideen für den Frühling 🌿",
    "Rosenfreude DE":       "Rosen richtig pflanzen & pflegen 🌹",
    "Terrasse & Garten DE": "Terrasse im Frühling gestalten 🌺",
    "Garten Gefühl":        "Garten-Tipps für jeden Tag 🌱"
}


def generate_pin_image_via_codex(prompt: str, save_path: str) -> bool:
    """
    Génère une image via GPT-image-2 en appelant Codex CLI.
    Codex CLI gère l'appel à l'API OpenAI images.generate.
    """
    codex_prompt = f"""
Generate an image with this description and save it as a file.

Image description: {prompt}

Use the OpenAI images.generate API with:
- model: "gpt-image-1"  
- size: "1024x1536"
- quality: "standard"
- output_format: "webp"

Save the generated image to: {save_path}

Return only: DONE or ERROR
"""
    try:
        result = subprocess.run(
            ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox"],
            input=codex_prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120
        )
        output = result.stdout.strip().upper()
        if "DONE" in output or os.path.exists(save_path):
            print(f"[DA] GPT-image pin généré : {Path(save_path).name}")
            return True
        print(f"[DA] GPT-image résultat : {output[:100]}")
        return False
    except Exception as e:
        print(f"[DA] GPT-image erreur : {e}")
        return False


def add_text_overlay(image_path: str, text: str, site_url: str = "garten-gefühl.de") -> bool:
    """
    Ajoute un texte overlay propre et minimal sur le pin.
    Style : texte en haut avec fond semi-transparent, URL en bas.
    """
    if not PIL_AVAILABLE:
        return True  # Pas d'overlay si PIL absent

    try:
        img = Image.open(image_path).convert("RGBA")
        w, h = img.size

        # Créer un layer transparent pour l'overlay
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # --- Bandeau haut (texte principal) ---
        band_height = int(h * 0.16)
        # Fond dégradé vert foncé semi-transparent
        for y in range(band_height):
            alpha = int(200 * (1 - y / band_height * 0.3))
            draw.rectangle([(0, y), (w, y + 1)], fill=(30, 80, 40, alpha))

        # --- Bandeau bas (URL) ---
        bottom_band = int(h * 0.07)
        for y in range(h - bottom_band, h):
            draw.rectangle([(0, y), (w, y + 1)], fill=(0, 0, 0, 160))

        # Fusionner overlay avec image
        img = Image.alpha_composite(img, overlay).convert("RGB")
        draw_final = ImageDraw.Draw(img)

        # Charger polices
        try:
            font_main = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(h * 0.038))
            font_url = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(h * 0.022))
        except:
            font_main = ImageFont.load_default()
            font_url = ImageFont.load_default()

        # Texte principal (wrapper automatique)
        words = text.split()
        lines = []
        current = ""
        max_chars = 28
        for word in words:
            if len(current + " " + word) <= max_chars:
                current = (current + " " + word).strip()
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        # Dessiner texte principal (centré verticalement dans le bandeau)
        line_h = int(h * 0.045)
        total_text_h = len(lines) * line_h
        y_start = (band_height - total_text_h) // 2

        for i, line in enumerate(lines[:3]):
            draw_final.text(
                (int(w * 0.05), y_start + i * line_h),
                line,
                font=font_main,
                fill=(255, 255, 255)
            )

        # URL en bas
        draw_final.text(
            (int(w * 0.05), h - int(h * 0.055)),
            site_url,
            font=font_url,
            fill=(200, 200, 200)
        )

        # Sauvegarder
        img.save(image_path, format="WEBP", quality=88)
        return True

    except Exception as e:
        print(f"[DA] Overlay erreur : {e}")
        return True  # Ne pas bloquer si overlay échoue


def create_pin_from_article_image(
    article_image_path: str,
    text: str,
    save_path: str,
    account_name: str
) -> bool:
    """
    Fallback : crée un pin à partir d'une image d'article existante.
    Recadrage intelligent centre (pas de stretch) + overlay.
    """
    if not PIL_AVAILABLE:
        return False

    try:
        img = Image.open(article_image_path).convert("RGB")
        orig_w, orig_h = img.size

        # Recadrage intelligent : crop au centre pour ratio 2:3
        target_ratio = PIN_WIDTH / PIN_HEIGHT  # 2:3
        orig_ratio = orig_w / orig_h

        if orig_ratio > target_ratio:
            # Image trop large → crop horizontal
            new_w = int(orig_h * target_ratio)
            left = (orig_w - new_w) // 2
            img = img.crop((left, 0, left + new_w, orig_h))
        else:
            # Image trop haute → crop vertical (garder le haut)
            new_h = int(orig_w / target_ratio)
            img = img.crop((0, 0, orig_w, new_h))

        # Redimensionner
        img = img.resize((PIN_WIDTH, PIN_HEIGHT), Image.LANCZOS)
        img.save(save_path, format="WEBP", quality=88)

        # Ajouter overlay texte
        add_text_overlay(save_path, text)

        print(f"[DA] Pin fallback créé : {Path(save_path).name}")
        return True

    except Exception as e:
        print(f"[DA] Erreur pin fallback : {e}")
        return False


def create_all_pins(
    base_image_path: str,
    article_title: str,
    keyword: str,
    category: str,
    pins_dir: str
) -> list:
    """
    Crée 5 pins Pinterest uniques — 1 par compte, adapté à sa niche.

    Flux :
    1. Tente GPT-image-2 via Codex (image unique générée par niche)
    2. Fallback : image d'article recadrée proprement
    3. Ajoute overlay texte minimal sur chaque pin
    """
    os.makedirs(pins_dir, exist_ok=True)
    pins_created = []

    for i, account_name in enumerate(PINTEREST_ACCOUNTS):
        account_slug = account_name.replace(" ", "_").replace("&", "und").replace("ü", "u")
        save_path = str(Path(pins_dir) / f"pin_{i+1:02d}_{account_slug}.webp")

        pin_text = PIN_TEXTS.get(account_name, article_title)
        prompt = NICHE_PROMPTS.get(account_name, f"Beautiful German garden spring photography, {keyword}")

        print(f"[DA] Génération pin {i+1}/5 — {account_name}...")

        # Tentative GPT-image-2
        success = generate_pin_image_via_codex(prompt, save_path)

        # Fallback si GPT échoue
        if not success or not os.path.exists(save_path):
            print(f"[DA] GPT échoué → fallback image article")
            success = create_pin_from_article_image(base_image_path, pin_text, save_path, account_name)
        else:
            # Ajouter overlay sur l'image GPT
            add_text_overlay(save_path, pin_text)

        if success and os.path.exists(save_path):
            pins_created.append({
                "path": save_path,
                "account": account_name,
                "title": pin_text,
                "index": i + 1
            })
            print(f"[DA] ✅ Pin {i+1}/5 — {account_name}")
        else:
            print(f"[DA] ❌ Pin {i+1}/5 échoué — {account_name}")

    print(f"[DA] {len(pins_created)}/5 pins créés")
    return pins_created
