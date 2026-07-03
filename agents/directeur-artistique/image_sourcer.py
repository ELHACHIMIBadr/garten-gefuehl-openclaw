"""
Directeur Artistique Agent — Image Sourcer
Pexels → Pixabay → GPT-image-2 (fallback après 9 essais infructueux)
Toutes les images converties en WebP et optimisées < 200KB.
"""

import os
import io
import json
import requests
from datetime import date
from pathlib import Path
from config import (
    PEXELS_API_URL, PIXABAY_API_URL,
    ARTICLE_IMAGE_MAX_SIZE_KB, MAX_FREE_ATTEMPTS,
    GPT_IMAGE_COUNTER_FILE, GPT_IMAGE_MODEL, GPT_IMAGE_SIZE
)

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[DA] ⚠️ Pillow non installé — conversion WebP limitée")


def download_and_convert_webp(url: str, save_path: str, max_kb: int = 200) -> bool:
    """
    Télécharge une image depuis une URL et la convertit en WebP optimisé.
    Retourne True si succès, False sinon.
    """
    try:
        resp = requests.get(url, timeout=15, stream=True)
        if resp.status_code != 200:
            return False

        if PIL_AVAILABLE:
            img = Image.open(io.BytesIO(resp.content))

            # Convertir en RGB si nécessaire (pour WebP)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Sauvegarder en WebP avec compression progressive
            quality = 85
            while quality >= 50:
                output = io.BytesIO()
                img.save(output, format="WEBP", quality=quality, optimize=True)
                size_kb = output.tell() / 1024

                if size_kb <= max_kb:
                    with open(save_path, "wb") as f:
                        f.write(output.getvalue())
                    print(f"[DA] Image sauvegardée : {Path(save_path).name} ({size_kb:.0f}KB, qualité {quality}%)")
                    return True

                quality -= 10

            # Si toujours trop grande, redimensionner
            img.thumbnail((800, 800), Image.LANCZOS)
            img.save(save_path, format="WEBP", quality=75)
            print(f"[DA] Image redimensionnée et sauvegardée : {Path(save_path).name}")
            return True

        else:
            # Sans Pillow, sauvegarder tel quel
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return True

    except Exception as e:
        print(f"[DA] Erreur téléchargement {url}: {e}")
        return False


def search_pexels(query: str, per_page: int = 5) -> list:
    """
    Cherche des images sur Pexels.
    Retourne une liste de dicts {url, photographer, source}.
    """
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        print("[DA] PEXELS_API_KEY manquant")
        return []

    try:
        resp = requests.get(
            PEXELS_API_URL,
            headers={"Authorization": api_key},
            params={
                "query": query,
                "per_page": per_page,
                "orientation": "landscape"
            },
            timeout=10
        )

        if resp.status_code == 200:
            data = resp.json()
            results = []
            for photo in data.get("photos", []):
                results.append({
                    "url": photo["src"]["large"],
                    "photographer": photo.get("photographer", "Pexels"),
                    "source": "pexels",
                    "source_url": photo.get("url", "")
                })
            return results

    except Exception as e:
        print(f"[DA] Erreur Pexels: {e}")

    return []


def search_pixabay(query: str, per_page: int = 5) -> list:
    """
    Cherche des images sur Pixabay (filtre ai_generated=false).
    """
    api_key = os.getenv("PIXABAY_API_KEY")
    if not api_key:
        print("[DA] PIXABAY_API_KEY manquant")
        return []

    try:
        resp = requests.get(
            PIXABAY_API_URL,
            params={
                "key": api_key,
                "q": query,
                "image_type": "photo",
                "per_page": per_page,
                "safesearch": "true",
                "ai_generated": "false",  # Filtre anti-IA
                "orientation": "horizontal"
            },
            timeout=10
        )

        if resp.status_code == 200:
            data = resp.json()
            results = []
            for img in data.get("hits", []):
                results.append({
                    "url": img.get("largeImageURL", img.get("webformatURL")),
                    "photographer": img.get("user", "Pixabay"),
                    "source": "pixabay",
                    "source_url": img.get("pageURL", "")
                })
            return results

    except Exception as e:
        print(f"[DA] Erreur Pixabay: {e}")

    return []


def get_gpt_image_count() -> dict:
    """Lit le compteur mensuel de générations GPT-image."""
    if os.path.exists(GPT_IMAGE_COUNTER_FILE):
        with open(GPT_IMAGE_COUNTER_FILE, "r") as f:
            return json.load(f)
    return {"month": date.today().strftime("%Y-%m"), "count": 0}


def increment_gpt_image_count():
    """Incrémente le compteur mensuel."""
    counter = get_gpt_image_count()
    current_month = date.today().strftime("%Y-%m")

    if counter["month"] != current_month:
        counter = {"month": current_month, "count": 0}

    counter["count"] += 1

    with open(GPT_IMAGE_COUNTER_FILE, "w") as f:
        json.dump(counter, f)

    return counter["count"]


def generate_gpt_image(prompt: str, save_path: str) -> bool:
    """
    Génère une image via GPT-image-2 (fallback).
    Utilise le quota GPT Plus inclus.
    """
    try:
        from openai import OpenAI
        client = OpenAI()

        print(f"[DA] Génération GPT-image-2 pour: {prompt[:50]}...")

        response = client.images.generate(
            model=GPT_IMAGE_MODEL,
            prompt=prompt,
            size=GPT_IMAGE_SIZE,
            n=1
        )

        image_url = response.data[0].url
        success = download_and_convert_webp(image_url, save_path)

        if success:
            count = increment_gpt_image_count()
            print(f"[DA] GPT-image-2 générée (compteur mensuel: {count})")

        return success

    except Exception as e:
        print(f"[DA] Erreur GPT-image-2: {e}")
        return False


def fetch_image(query: str, save_path: str, attempt_num: int = 0) -> dict:
    """
    Fetch une image selon la chaîne : Pexels → Pixabay → GPT-image.
    Retourne les métadonnées de l'image.
    """
    # ÉTAPE 1 — Pexels
    pexels_results = search_pexels(query)
    for result in pexels_results:
        if download_and_convert_webp(result["url"], save_path):
            return {
                "path": save_path,
                "source": "pexels",
                "photographer": result["photographer"],
                "source_url": result["source_url"],
                "query": query
            }

    # ÉTAPE 2 — Pixabay
    pixabay_results = search_pixabay(query)
    for result in pixabay_results:
        if download_and_convert_webp(result["url"], save_path):
            return {
                "path": save_path,
                "source": "pixabay",
                "photographer": result["photographer"],
                "source_url": result["source_url"],
                "query": query
            }

    # ÉTAPE 3 — Fallback GPT-image (après 9 essais infructueux)
    if attempt_num >= MAX_FREE_ATTEMPTS:
        gpt_prompt = f"Beautiful professional garden photography: {query}. Natural light, high quality, no text."
        if generate_gpt_image(gpt_prompt, save_path):
            return {
                "path": save_path,
                "source": "gpt_image",
                "photographer": "AI Generated",
                "source_url": "",
                "query": query
            }

    print(f"[DA] ⚠️ Aucune image trouvée pour: {query}")
    return {}
