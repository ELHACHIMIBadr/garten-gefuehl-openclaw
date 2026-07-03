"""
Directeur Artistique Agent — Image Sourcer
Fix: hash MD5 marqué IMMÉDIATEMENT pour éviter doublons inter-requêtes.
"""

import os
import io
import json
import sys
import hashlib
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

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# Cache intra-article par hash MD5
_current_article_hashes = set()


def reset_article_url_cache():
    global _current_article_hashes
    _current_article_hashes = set()


def is_hash_used_in_current_article(h: str) -> bool:
    return h in _current_article_hashes


def mark_hash_used_in_article(h: str):
    _current_article_hashes.add(h)


def download_and_convert_webp(content: bytes, save_path: str, max_kb: int = 200) -> bool:
    try:
        if PIL_AVAILABLE:
            img = Image.open(io.BytesIO(content))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            quality = 85
            while quality >= 50:
                output = io.BytesIO()
                img.save(output, format="WEBP", quality=quality, optimize=True)
                if output.tell() / 1024 <= max_kb:
                    with open(save_path, "wb") as f:
                        f.write(output.getvalue())
                    print(f"[DA] Sauvegardée : {Path(save_path).name} ({output.tell()//1024}KB)")
                    return True
                quality -= 10
            img.thumbnail((800, 800), Image.LANCZOS)
            img.save(save_path, format="WEBP", quality=75)
            return True
        else:
            with open(save_path, "wb") as f:
                f.write(content)
            return True
    except Exception as e:
        print(f"[DA] Erreur WebP: {e}")
        return False


def validate_image_with_codex(image_path: str, keyword: str, category: str) -> bool:
    prompt = (
        f"Schau dir dieses Bild genau an.\n\n"
        f"AKZEPTIERT (JA) NUR wenn Blumen/Pflanzen das HAUPTMOTIV sind.\n"
        f"ABGELEHNT (NEIN) wenn Gebäude, Fassaden, Architektur oder leere Balkone.\n\n"
        f"Antworte NUR: JA oder NEIN."
    )
    try:
        result = subprocess.run(
            ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-i", image_path],
            input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=60
        )
        output = result.stdout.strip().upper()
        print(f"[DA] Codex: {output[:15]}")
        return "JA" in output and "NEIN" not in output
    except:
        return False
    finally:
        try:
            os.unlink(image_path)
        except:
            pass


def search_pexels(query: str, per_page: int = 10) -> list:
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        return []
    try:
        resp = requests.get(PEXELS_API_URL, headers={"Authorization": api_key},
                           params={"query": query, "per_page": per_page, "orientation": "landscape"}, timeout=10)
        if resp.status_code == 200:
            results = [{"url": p["src"]["large"], "photographer": p.get("photographer", "Pexels"),
                        "source": "pexels", "source_url": p.get("url", "")}
                       for p in resp.json().get("photos", [])]
            print(f"[DA] Pexels: {len(results)} pour '{query}'")
            return results
    except Exception as e:
        print(f"[DA] Pexels erreur: {e}")
    return []


def search_pixabay(query: str, per_page: int = 10) -> list:
    api_key = os.getenv("PIXABAY_API_KEY")
    if not api_key:
        return []
    try:
        resp = requests.get(PIXABAY_API_URL, params={
            "key": api_key, "q": query, "image_type": "photo", "per_page": per_page,
            "safesearch": "true", "ai_generated": "false", "orientation": "horizontal"
        }, timeout=10)
        if resp.status_code == 200:
            results = [{"url": img.get("largeImageURL", img.get("webformatURL")),
                        "photographer": img.get("user", "Pixabay"),
                        "source": "pixabay", "source_url": img.get("pageURL", "")}
                       for img in resp.json().get("hits", [])]
            print(f"[DA] Pixabay: {len(results)} pour '{query}'")
            return results
    except Exception as e:
        print(f"[DA] Pixabay erreur: {e}")
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


def fetch_image(query: str, save_path: str, keyword: str, category: str) -> dict:
    """
    Fetch image avec anti-doublon MD5 fiable.
    Hash marqué IMMÉDIATEMENT après téléchargement — avant validation.
    Garantit zéro doublon même entre requêtes différentes.
    """
    MAX_REJECTIONS = 3
    rejected_count = 0

    candidates = search_pexels(query, 10) + search_pixabay(query, 10)
    print(f"[DA] {len(candidates)} candidats pour '{query}'")

    for i, candidate in enumerate(candidates):
        if rejected_count >= MAX_REJECTIONS:
            break

        url = candidate["url"]

        # Vérifier historique global
        if HISTORY_AVAILABLE and is_image_already_used(url):
            print(f"[DA] ⏭️ URL connue")
            continue

        # Télécharger UNE SEULE FOIS
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            content = resp.content
        except:
            continue

        # Hash MD5 — marquer IMMÉDIATEMENT
        h = hashlib.md5(content).hexdigest()
        if is_hash_used_in_current_article(h):
            print(f"[DA] ⏭️ Photo identique déjà utilisée (MD5)")
            continue
        mark_hash_used_in_article(h)  # ← Immédiat, avant validation

        # Validation Codex
        print(f"[DA] Candidat {i+1} ({candidate['source']})...")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(content)
            temp_path = f.name

        if validate_image_with_codex(temp_path, keyword, category):
            print(f"[DA] ✅ Validée ({candidate['source']})")
            if download_and_convert_webp(content, save_path):
                if HISTORY_AVAILABLE:
                    add_image_to_history(url, keyword)
                return {"path": save_path, "source": candidate["source"],
                        "photographer": candidate["photographer"],
                        "source_url": candidate["source_url"], "query": query}
        else:
            rejected_count += 1
            print(f"[DA] ❌ Rejetée ({rejected_count}/{MAX_REJECTIONS})")

    # Fallback GPT-image-2
    print(f"[DA] 🔄 GPT-image-2 fallback")
    try:
        from openai import OpenAI
        client = OpenAI()
        r = client.images.generate(
            model=GPT_IMAGE_MODEL,
            prompt=f"Close-up colorful spring flowers balcony box, no buildings, natural light",
            size=GPT_IMAGE_SIZE, n=1
        )
        img_resp = requests.get(r.data[0].url, timeout=15)
        if img_resp.status_code == 200 and download_and_convert_webp(img_resp.content, save_path):
            print(f"[DA] GPT-image-2 générée (compteur: {increment_gpt_image_count()})")
            return {"path": save_path, "source": "gpt_image", "photographer": "AI",
                    "source_url": "", "query": query}
    except Exception as e:
        print(f"[DA] GPT-image-2 erreur: {e}")

    return {}
