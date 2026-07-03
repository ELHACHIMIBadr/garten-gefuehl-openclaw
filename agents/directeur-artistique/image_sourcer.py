"""
Directeur Artistique Agent — Image Sourcer
Anti-doublon par ID source (pexels_id / pixabay_id).
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

# IDs déjà utilisés dans l'article courant
_used_source_ids = set()


def reset_article_cache():
    global _used_source_ids
    _used_source_ids = set()


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
                    print(f"[DA] Sauvegardée: {Path(save_path).name} ({output.tell()//1024}KB)")
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
        "Schau dir dieses Bild an.\n"
        "JA nur wenn: Blumen/Pflanzen sind HAUPTMOTIV im Vordergrund.\n"
        "NEIN wenn: Gebäude, Fassaden, Architektur, leere Balkone, Stadtlandschaft.\n"
        "Antworte NUR: JA oder NEIN."
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
            return [{"url": p["src"]["large"], "source_id": f"pexels_{p['id']}",
                     "photographer": p.get("photographer", ""), "source": "pexels",
                     "source_url": p.get("url", "")}
                    for p in resp.json().get("photos", [])]
    except:
        pass
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
            return [{"url": img.get("largeImageURL", img.get("webformatURL")),
                     "source_id": f"pixabay_{img['id']}",
                     "photographer": img.get("user", ""), "source": "pixabay",
                     "source_url": img.get("pageURL", "")}
                    for img in resp.json().get("hits", [])]
    except:
        pass
    return []


def collect_unique_candidates(queries: list) -> list:
    """
    Collecte des candidats de TOUTES les requêtes et déduplique par source_id.
    Retourne une liste unique de candidats.
    """
    seen_ids = set()
    unique = []

    for query in queries:
        for candidate in search_pexels(query, 10) + search_pixabay(query, 10):
            sid = candidate["source_id"]
            if sid not in seen_ids:
                seen_ids.add(sid)
                unique.append(candidate)

    print(f"[DA] {len(unique)} candidats uniques collectés")
    return unique


def fetch_n_images(queries: list, n: int, img_dir: str, keyword: str, category: str) -> list:
    """
    Collecte N images uniques et validées.
    1. Pool unique de toutes les requêtes (dédupliqué par source_id)
    2. Filtre par historique global
    3. Filtre par IDs déjà utilisés dans l'article
    4. Validation Codex
    5. Fallback GPT-image si pas assez d'images
    """
    MAX_REJECTIONS = 5
    rejected_count = 0
    images = []

    # Collecter tous les candidats uniques
    candidates = collect_unique_candidates(queries)

    for i, candidate in enumerate(candidates):
        if len(images) >= n:
            break
        if rejected_count >= MAX_REJECTIONS:
            break

        sid = candidate["source_id"]
        url = candidate["url"]

        # Déjà utilisé dans cet article ?
        if sid in _used_source_ids:
            continue

        # Historique global
        if HISTORY_AVAILABLE and is_image_already_used(url):
            print(f"[DA] ⏭️ {sid} — historique global")
            continue

        # Télécharger
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            content = resp.content
        except:
            continue

        # Validation Codex
        print(f"[DA] Candidat {sid} — validation...")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(content)
            temp_path = f.name

        if validate_image_with_codex(temp_path, keyword, category):
            img_num = len(images) + 1
            save_path = str(Path(img_dir) / f"article_img_{img_num:02d}.webp")
            if download_and_convert_webp(content, save_path):
                _used_source_ids.add(sid)
                if HISTORY_AVAILABLE:
                    add_image_to_history(url, keyword)
                alt_text = keyword if img_num == 1 else f"{keyword} - Bild {img_num}"
                images.append({
                    "path": save_path, "source": candidate["source"],
                    "photographer": candidate["photographer"],
                    "source_url": candidate["source_url"],
                    "source_id": sid, "alt_text": alt_text
                })
                print(f"[DA] ✅ Image {img_num}/{n} ({candidate['source']})")
        else:
            rejected_count += 1
            print(f"[DA] ❌ Rejetée ({rejected_count}/{MAX_REJECTIONS})")

    # Fallback GPT-image si pas assez
    while len(images) < n:
        img_num = len(images) + 1
        save_path = str(Path(img_dir) / f"article_img_{img_num:02d}.webp")
        print(f"[DA] 🔄 GPT-image fallback pour image {img_num}")
        try:
            from openai import OpenAI
            client = OpenAI()
            r = client.images.generate(
                model=GPT_IMAGE_MODEL,
                prompt=f"Close-up colorful spring flowers balcony, no buildings, natural light, photo {img_num}",
                size=GPT_IMAGE_SIZE, n=1
            )
            img_resp = requests.get(r.data[0].url, timeout=15)
            if img_resp.status_code == 200 and download_and_convert_webp(img_resp.content, save_path):
                images.append({
                    "path": save_path, "source": "gpt_image", "photographer": "AI",
                    "source_url": "", "source_id": f"gpt_{img_num}",
                    "alt_text": f"{keyword} - Bild {img_num}"
                })
                print(f"[DA] ✅ GPT image {img_num}")
            else:
                break
        except Exception as e:
            print(f"[DA] GPT erreur: {e}")
            break

    return images
