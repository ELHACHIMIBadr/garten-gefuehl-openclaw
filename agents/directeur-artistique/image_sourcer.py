"""
Directeur Artistique Agent — Image Sourcer
Pexels → Pixabay → GPT-image-2 (fallback après 3 rejets)
Validation visuelle via Codex CLI (-i flag).
Vérification historique pour éviter les images dupliquées.
Toutes les images converties en WebP et optimisées < 200KB.
"""

import os
import io
import json
import sys
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

# Import historique
sys.path.insert(0, "/root/garten-gefuehl-openclaw/agents")
try:
    from history import is_image_already_used, add_image_to_history
    HISTORY_AVAILABLE = True
except ImportError:
    HISTORY_AVAILABLE = False
    print("[DA] ⚠️ Module history non disponible")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def download_and_convert_webp(url: str, save_path: str, max_kb: int = 200) -> bool:
    """Télécharge et convertit en WebP optimisé."""
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
                    print(f"[DA] Image sauvegardée : {Path(save_path).name} ({size_kb:.0f}KB)")
                    return True
                quality -= 10

            img.thumbnail((800, 800), Image.LANCZOS)
            img.save(save_path, format="WEBP", quality=75)
            return True
        else:
            with open(save_path, "wb") as f:
                f.write(requests.get(url, timeout=15).content)
            return True

    except Exception as e:
        print(f"[DA] Erreur téléchargement: {e}")
        return False


def download_temp_image(url: str) -> str:
    """Télécharge temporairement pour validation Codex."""
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return ""
        content_type = resp.headers.get("Content-Type", "image/jpeg")
        ext = ".png" if "png" in content_type else ".jpg"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(resp.content)
            return f.name
    except Exception as e:
        print(f"[DA] Erreur download temp: {e}")
        return ""


def validate_image_with_codex(image_path: str, keyword: str, category: str) -> bool:
    """Valide visuellement une image via Codex CLI (-i flag)."""
    prompt = (
        f"Schau dir dieses Bild an. Ist es geeignet als Illustration für einen deutschen "
        f"Gartenblog-Artikel über '{keyword}' in der Kategorie '{category}'? "
        f"Antworte NUR mit JA oder NEIN."
    )

    try:
        result = subprocess.run(
            ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-i", image_path],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60
        )
        output = result.stdout.strip().upper()
        print(f"[DA] Validation Codex : {output[:20]}")

        if "NEIN" in output or "NO" in output:
            return False
        return True  # JA ou ambigü → accepter

    except subprocess.TimeoutExpired:
        print(f"[DA] Timeout — acceptée par défaut")
        return True
    except Exception as e:
        print(f"[DA] Erreur Codex: {e} — acceptée par défaut")
        return True
    finally:
        if image_path.startswith("/tmp/") or "Temp" in image_path:
            try:
                os.unlink(image_path)
            except:
                pass


def search_pexels(query: str, per_page: int = 8) -> list:
    """Cherche des images sur Pexels."""
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        return []
    try:
        resp = requests.get(
            PEXELS_API_URL,
            headers={"Authorization": api_key},
            params={"query": query, "per_page": per_page, "orientation": "landscape"},
            timeout=10
        )
        if resp.status_code == 200:
            results = [
                {"url": p["src"]["large"], "photographer": p.get("photographer", "Pexels"),
                 "source": "pexels", "source_url": p.get("url", "")}
                for p in resp.json().get("photos", [])
            ]
            print(f"[DA] Pexels: {len(results)} résultats pour '{query}'")
            return results
    except Exception as e:
        print(f"[DA] Erreur Pexels: {e}")
    return []


def search_pixabay(query: str, per_page: int = 8) -> list:
    """Cherche des images sur Pixabay (sans IA)."""
    api_key = os.getenv("PIXABAY_API_KEY")
    if not api_key:
        return []
    try:
        resp = requests.get(
            PIXABAY_API_URL,
            params={
                "key": api_key, "q": query, "image_type": "photo",
                "per_page": per_page, "safesearch": "true",
                "ai_generated": "false", "orientation": "horizontal"
            },
            timeout=10
        )
        if resp.status_code == 200:
            results = [
                {"url": img.get("largeImageURL", img.get("webformatURL")),
                 "photographer": img.get("user", "Pixabay"),
                 "source": "pixabay", "source_url": img.get("pageURL", "")}
                for img in resp.json().get("hits", [])
            ]
            print(f"[DA] Pixabay: {len(results)} résultats pour '{query}'")
            return results
    except Exception as e:
        print(f"[DA] Erreur Pixabay: {e}")
    return []


def get_gpt_image_count() -> dict:
    if os.path.exists(GPT_IMAGE_COUNTER_FILE):
        with open(GPT_IMAGE_COUNTER_FILE, "r") as f:
            return json.load(f)
    return {"month": date.today().strftime("%Y-%m"), "count": 0}


def increment_gpt_image_count():
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
    """Génère une image via GPT-image-2 (fallback)."""
    try:
        from openai import OpenAI
        client = OpenAI()
        print(f"[DA] Génération GPT-image-2...")
        response = client.images.generate(model=GPT_IMAGE_MODEL, prompt=prompt, size=GPT_IMAGE_SIZE, n=1)
        image_url = response.data[0].url
        success = download_and_convert_webp(image_url, save_path)
        if success:
            count = increment_gpt_image_count()
            print(f"[DA] GPT-image-2 générée (compteur: {count})")
        return success
    except Exception as e:
        print(f"[DA] Erreur GPT-image-2: {e}")
        return False


def fetch_image(query: str, save_path: str, keyword: str, category: str) -> dict:
    """
    Fetch une image avec :
    1. Vérification historique (pas de doublon)
    2. Validation visuelle Codex
    3. Fallback GPT-image après 3 rejets
    """
    MAX_REJECTIONS = 3
    rejected_count = 0

    all_candidates = []
    all_candidates.extend(search_pexels(query, per_page=6))
    all_candidates.extend(search_pixabay(query, per_page=6))

    print(f"[DA] {len(all_candidates)} candidats pour '{query}'")

    for i, candidate in enumerate(all_candidates):
        if rejected_count >= MAX_REJECTIONS:
            break

        url = candidate["url"]

        # Vérifier historique (doublon)
        if HISTORY_AVAILABLE and is_image_already_used(url):
            print(f"[DA] ⏭️ Image déjà utilisée — ignorée")
            continue

        print(f"[DA] Candidat {i+1}/{len(all_candidates)} ({candidate['source']}) — validation...")

        # Télécharger temporairement + validation Codex
        temp_path = download_temp_image(url)
        if not temp_path:
            continue

        is_valid = validate_image_with_codex(temp_path, keyword, category)

        if is_valid:
            print(f"[DA] ✅ Image validée ({candidate['source']})")
            if download_and_convert_webp(url, save_path):
                # Ajouter à l'historique
                if HISTORY_AVAILABLE:
                    add_image_to_history(url, keyword)
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
            print(f"[DA] ❌ Rejetée ({rejected_count}/{MAX_REJECTIONS})")

    # Fallback GPT-image-2
    print(f"[DA] 🔄 Fallback GPT-image-2")
    gpt_prompt = (
        f"Professional garden photography for a German gardening blog. "
        f"Topic: '{keyword}'. Category: {category}. "
        f"Beautiful, colorful, realistic. Natural light. No text. No watermarks."
    )
    if generate_gpt_image(gpt_prompt, save_path):
        return {
            "path": save_path, "source": "gpt_image",
            "photographer": "AI Generated", "source_url": "",
            "query": query, "validated": True
        }

    print(f"[DA] ⚠️ Aucune image trouvée pour: {query}")
    return {}
