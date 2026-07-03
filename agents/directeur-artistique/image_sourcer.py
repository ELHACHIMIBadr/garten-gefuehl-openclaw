"""
Directeur Artistique Agent — Image Sourcer
Pexels → Pixabay → GPT-image-2 (fallback après 3 rejets)
Validation visuelle via Codex CLI (-i flag) avec prompt strict.
Vérification historique global + intra-article pour éviter les doublons.
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


# Cache intra-article (réinitialisé à chaque run)
_current_article_urls = set()


def reset_article_url_cache():
    global _current_article_urls
    _current_article_urls = set()


def is_url_used_in_current_article(url: str) -> bool:
    url_key = url.split("/")[-1].split("?")[0]
    for used in _current_article_urls:
        if url_key == used.split("/")[-1].split("?")[0]:
            return True
    return False


def mark_url_used_in_article(url: str):
    _current_article_urls.add(url)


def download_and_convert_webp(url: str, save_path: str, max_kb: int = 200) -> bool:
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
    """
    Validation visuelle stricte via Codex CLI.
    Critères clairs : plantes/fleurs en premier plan = JA, tout le reste = NEIN.
    En cas de doute ou timeout → NEIN (refuser par sécurité).
    """
    prompt = (
        f"Schau dir dieses Bild genau an.\n\n"
        f"AKZEPTIERT (antworte JA) NUR wenn:\n"
        f"- Das Bild zeigt eindeutig Blumen oder Pflanzen im Vordergrund\n"
        f"- Balkonkasten mit blühenden Pflanzen sind sichtbar\n"
        f"- Topfpflanzen oder Gartenblumen sind das Hauptmotiv\n\n"
        f"ABGELEHNT (antworte NEIN) wenn:\n"
        f"- Gebäude oder Häuserfassaden sichtbar sind (auch mit kleinen Balkonen)\n"
        f"- Der Balkon leer oder fast leer ist\n"
        f"- Architektur das Hauptmotiv ist\n"
        f"- Pflanzen nur klein im Hintergrund sind\n"
        f"- Stadtlandschaft oder Straßen sichtbar sind\n"
        f"- Innenräume zu sehen sind\n\n"
        f"Antworte NUR mit JA oder NEIN. Kein weiterer Text."
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

        # Strict : doit contenir explicitement JA
        if "JA" in output and "NEIN" not in output:
            return True
        return False  # Tout ce qui n'est pas clairement JA = refusé

    except subprocess.TimeoutExpired:
        print(f"[DA] Timeout — refusée par sécurité")
        return False
    except Exception as e:
        print(f"[DA] Erreur Codex: {e} — refusée par sécurité")
        return False
    finally:
        if image_path and (image_path.startswith("/tmp/") or "Temp" in image_path):
            try:
                os.unlink(image_path)
            except:
                pass


def search_pexels(query: str, per_page: int = 10) -> list:
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


def search_pixabay(query: str, per_page: int = 10) -> list:
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
    Fetch une image avec validation stricte.
    Pexels → Pixabay → GPT-image-2 après 3 rejets.
    """
    MAX_REJECTIONS = 3
    rejected_count = 0

    all_candidates = []
    all_candidates.extend(search_pexels(query, per_page=10))
    all_candidates.extend(search_pixabay(query, per_page=10))

    print(f"[DA] {len(all_candidates)} candidats pour '{query}'")

    for i, candidate in enumerate(all_candidates):
        if rejected_count >= MAX_REJECTIONS:
            break

        url = candidate["url"]

        if HISTORY_AVAILABLE and is_image_already_used(url):
            print(f"[DA] ⏭️ Déjà utilisée (historique global)")
            continue

        if is_url_used_in_current_article(url):
            print(f"[DA] ⏭️ Déjà utilisée dans cet article")
            continue

        print(f"[DA] Candidat {i+1}/{len(all_candidates)} ({candidate['source']}) — validation...")

        temp_path = download_temp_image(url)
        if not temp_path:
            continue

        is_valid = validate_image_with_codex(temp_path, keyword, category)

        if is_valid:
            print(f"[DA] ✅ Image validée ({candidate['source']})")
            if download_and_convert_webp(url, save_path):
                if HISTORY_AVAILABLE:
                    add_image_to_history(url, keyword)
                mark_url_used_in_article(url)
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
        f"Close-up professional photo of colorful flowering plants in a balcony box. "
        f"Topic: {keyword}. Bright colors, sharp focus on flowers. "
        f"No buildings, no architecture. Natural light. No text."
    )
    if generate_gpt_image(gpt_prompt, save_path):
        mark_url_used_in_article(gpt_prompt[:50])
        return {
            "path": save_path, "source": "gpt_image",
            "photographer": "AI Generated", "source_url": "",
            "query": query, "validated": True
        }

    print(f"[DA] ⚠️ Aucune image trouvée pour: {query}")
    return {}
