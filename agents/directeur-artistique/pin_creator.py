"""
Directeur Artistique Agent — Pin Creator
Crée les 5 visuels Pinterest (format 2:3, 1000x1500px, WebP).
Texte overlay en allemand sur chaque pin.
"""

import os
import io
import requests
from pathlib import Path
from config import PIN_WIDTH, PIN_HEIGHT, PINTEREST_ACCOUNTS

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def create_pinterest_pin(
    base_image_path: str,
    title: str,
    keyword: str,
    category: str,
    save_path: str,
    account_name: str
) -> bool:
    """
    Crée un visuel Pinterest à partir d'une image de base.
    Format 2:3 (1000x1500px), texte overlay en allemand, WebP.
    """
    if not PIL_AVAILABLE:
        print("[DA] Pillow non disponible — pin non créé")
        return False

    try:
        # Charger l'image de base
        if base_image_path.startswith("http"):
            resp = requests.get(base_image_path, timeout=15)
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        else:
            img = Image.open(base_image_path).convert("RGB")

        # Redimensionner en 2:3
        img = img.resize((PIN_WIDTH, PIN_HEIGHT), Image.LANCZOS)

        # Créer overlay sombre en bas pour le texte
        draw = ImageDraw.Draw(img)

        # Gradient sombre en bas (pour lisibilité du texte)
        overlay_height = 400
        for y in range(PIN_HEIGHT - overlay_height, PIN_HEIGHT):
            alpha = int(200 * (y - (PIN_HEIGHT - overlay_height)) / overlay_height)
            draw.rectangle(
                [(0, y), (PIN_WIDTH, y + 1)],
                fill=(0, 0, 0, alpha)
            )

        # Texte principal (titre de l'article)
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
            font_tag = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
            font_tag = ImageFont.load_default()

        # Découper le titre en lignes (max 25 chars par ligne)
        words = title.split()
        lines = []
        current_line = ""
        for word in words:
            if len(current_line + " " + word) <= 25:
                current_line = (current_line + " " + word).strip()
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        # Dessiner le titre
        y_start = PIN_HEIGHT - 350
        for i, line in enumerate(lines[:4]):
            draw.text(
                (40, y_start + i * 65),
                line,
                font=font_large,
                fill=(255, 255, 255),
                stroke_width=2,
                stroke_fill=(0, 0, 0)
            )

        # Keyword tag en bas
        draw.text(
            (40, PIN_HEIGHT - 80),
            f"🌱 {keyword}",
            font=font_tag,
            fill=(144, 238, 144)  # Vert clair
        )

        # URL du site en bas à droite
        draw.text(
            (PIN_WIDTH - 300, PIN_HEIGHT - 50),
            "garten-gefühl.de",
            font=font_tag,
            fill=(200, 200, 200)
        )

        # Sauvegarder en WebP
        img.save(save_path, format="WEBP", quality=85)
        print(f"[DA] Pin créé : {Path(save_path).name}")
        return True

    except Exception as e:
        print(f"[DA] Erreur création pin: {e}")
        return False


def create_all_pins(
    base_image_path: str,
    article_title: str,
    keyword: str,
    category: str,
    pins_dir: str
) -> list:
    """
    Crée 5 pins Pinterest (1 par compte).
    Chaque pin a une légère variation de style.
    Retourne la liste des paths créés.
    """
    pins_created = []

    # Variations de texte pour chaque pin
    pin_variations = [
        article_title,
        f"✨ {article_title}",
        f"🌱 {keyword} – Tipps & Tricks",
        f"Meine besten Tipps: {keyword}",
        f"{keyword} – jetzt entdecken!"
    ]

    for i, account_name in enumerate(PINTEREST_ACCOUNTS):
        pin_title = pin_variations[i] if i < len(pin_variations) else article_title
        save_path = str(Path(pins_dir) / f"pin_{i+1:02d}_{account_name.replace(' ', '_').replace('&', 'und')}.webp")

        success = create_pinterest_pin(
            base_image_path=base_image_path,
            title=pin_title,
            keyword=keyword,
            category=category,
            save_path=save_path,
            account_name=account_name
        )

        if success:
            pins_created.append({
                "path": save_path,
                "account": account_name,
                "title": pin_title,
                "index": i + 1
            })

    print(f"[DA] {len(pins_created)}/5 pins créés")
    return pins_created
