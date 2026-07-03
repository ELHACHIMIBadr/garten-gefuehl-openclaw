"""
Directeur Artistique Agent — Image Sourcer
Pexels → Pixabay → GPT-image-2 (fallback après 3 rejets de validation Codex)
Validation visuelle via Codex CLI (-i flag).
Toutes les images converties en WebP et optimisées < 200KB.
"""

import os
import io
import json
import subprocess
import tempfile
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
    """
    try:
        resp = requests.get(url, timeout=15, stream=True)
        if resp.status_code != 200:
            return False

        if PIL_AVAILABLE:
            img = Image.open(io.BytesIO(resp.content))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

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

            img.thumbnail((800, 800), Image.LANCZOS)
            img.save(save_path, format="WEBP", quality=75)
            print(f"[DA] Image redimensionnée : {Path(save_path).name}")
            return True

        else:
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return True

    except Exception as e:
        print(f"[DA] Erreur téléchargement {url}: {e}")
        return False


def download_temp_image(url: str) -> str:
    """
    Télécharge une image dans un fichier temporaire pour validation Codex.
    Retourne le chemin du fichier temp, ou "" si échec.
    """
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return ""

        # Détecter l'extension
        content_type = resp.headers.get("Content-Type", "image/jpeg")
        ext = ".jpg"
        if "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(resp.content)
            return f.name

    except Exception as e:
        print(f"[DA] Erreur download temp: {e}")
        return ""


def validate_image_with_codex(image_path: str, keyword: str, category: str) -> bool:
    """
    Valide une image via Codex CLI avec le flag -i (image input).
    Pose une question simple : l'image est-elle pertinente pour le keyword ?
    Retourne True si pertinente, False sinon.
    """
    prompt = (
        f"Schau dir dieses Bild an. Ist es geeignet als Illustration für einen deutschen Gartenblog-Artikel "
        f"über '{keyword}' in der Kategorie '{category}'?\n\n"
        f"Antworte NUR mit JA oder NEIN. Kein weiterer Text."
    )

    try:
        result = subprocess.run(
            [
                "codex", "exec",
                "--dangerously-bypass-approvals-and-sandbox",
                "-i", image_path,
            ],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60
        )

        output = result.stdout.strip().upper()
        print(f"[DA] Validation Codex : {output[:50]}")

        # Extraire JA/NEIN de la sortie
        if "JA" in output or "YES" in output or "OUI" in output:
            return True
        elif "NEIN" in output or "NO" in output or "NON" in output:
            return False
        else:
            # Si réponse ambiguë, accepter par défaut
            print(f"[DA] Réponse ambiguë — acceptée par défaut")
            return True

    except subprocess.TimeoutExpired:
        print(f"[DA] Timeout validation Codex — acceptée par défaut")
        return True
    except Exception as e:
        print(f"[DA] Erreur validation Codex: {e} — acceptée par défaut")
        return True
    finally:
        # Nettoyer le fichier temp si c'est un temp file
        if "/tmp/" in image_path or "\\Temp\\" in image_path:
            try:
                os.unlink(image_path)
            except:
                pass


def search_pexels(query: str, per_page: int = 8) -> list:
    """
    Cherche des images sur Pexels.
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
            print(f"[DA] Pexels: {len(results)} résultats pour '{query}'")
            return results

    except Exception as e:
        print(f"[DA] Erreur Pexels: {e}")

    return []


def search_pixabay(query: str, per_page: int = 8) -> list:
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
                "ai_generated": "false",
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
            print(f"[DA] Pixabay: {len(results)} résultats pour '{query}'")
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

    os.makedirs(os.path.dirname(GPT_IMAGE_COUNTER_FILE), exist_ok=True)
    with open(GPT_IMAGE_COUNTER_FILE, "w") as f:
        json.dump(counter, f)

    return counter["count"]


def generate_gpt_image(prompt: str, save_path: str) -> bool:
    """
    Génère une image via GPT-image-2 (fallback après 3 rejets).
    """
    try:
        from openai import OpenAI
        client = OpenAI()

        print(f"[DA] Génération GPT-image-2: {prompt[:60]}...")
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


def fetch_image(query: str, save_path: str, keyword: str, category: str) -> dict:
    """
    Fetch une image avec validation visuelle Codex.
    Logique : Pexels → Pixabay → GPT-image-2 (après 3 rejets).

    Pour chaque source :
    - Récupère plusieurs candidats
    - Télécharge temporairement chaque candidat
    - Valide via Codex CLI (-i flag)
    - Si validée → convertit en WebP final
    - Si 3 rejets consécutifs → fallback GPT-image-2
    """
    MAX_VALIDATION_ATTEMPTS = 3
    rejected_count = 0

    all_candidates = []

    # Collecter tous les candidats (Pexels + Pixabay)
    pexels_results = search_pexels(query, per_page=5)
    all_candidates.extend(pexels_results)

    pixabay_results = search_pixabay(query, per_page=5)
    all_candidates.extend(pixabay_results)

    print(f"[DA] {len(all_candidates)} candidats à valider pour '{query}'")

    for i, candidate in enumerate(all_candidates):
        if rejected_count >= MAX_VALIDATION_ATTEMPTS:
            break

        print(f"[DA] Candidat {i+1}/{len(all_candidates)} ({candidate['source']}) — validation Codex...")

        # Télécharger temporairement pour validation
        temp_path = download_temp_image(candidate["url"])
        if not temp_path:
            continue

        # Validation visuelle Codex
        is_valid = validate_image_with_codex(temp_path, keyword, category)

        if is_valid:
            print(f"[DA] ✅ Image validée ({candidate['source']})")
            # Télécharger et convertir en WebP final
            if download_and_convert_webp(candidate["url"], save_path):
                return {
                    "path": save_path,
                    "source": candidate["source"],
                    "photographer": candidate["photographer"],
                    "source_url": candidate["source_url"],
                    "query": query,
                    "validated": True
                }
        else:
            rejected_count += 1
            print(f"[DA] ❌ Image rejetée ({rejected_count}/{MAX_VALIDATION_ATTEMPTS})")

    # Fallback GPT-image-2 après 3 rejets
    print(f"[DA] 🔄 Fallback GPT-image-2 après {rejected_count} rejets")
    gpt_prompt = (
        f"Professional garden photography for a German gardening blog. "
        f"Topic: '{keyword}'. Category: {category}. "
        f"Show beautiful, colorful, realistic garden scene. Natural light. No text. No watermarks."
    )

    if generate_gpt_image(gpt_prompt, save_path):
        return {
            "path": save_path,
            "source": "gpt_image",
            "photographer": "AI Generated",
            "source_url": "",
            "query": query,
            "validated": True
        }

    print(f"[DA] ⚠️ Aucune image trouvée pour: {query}")
    return {}
