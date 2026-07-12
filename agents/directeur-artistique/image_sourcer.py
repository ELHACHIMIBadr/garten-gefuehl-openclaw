"""
Directeur Artistique Agent — Image Sourcer

CHANGELOG v3 (Fix fond noir):
- download_and_convert_webp : fond blanc ajouté avant conversion RGBA/P → RGB.
  Évite le fond noir sur les images PNG transparentes de Pixabay/Pexels.

CHANGELOG v2 (Bug 3 corrigé):
- Prompt Codex ultra-court et binaire.
- Condition retour : output.startswith("JA").
- Timeout réduit à 30s → NEIN par défaut.
- MAX_REJECTIONS augmenté à 15.
- Anti-doublon par source_id.
"""

import os
import io
import sys
import subprocess
import tempfile
import requests
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

# IDs déjà utilisés dans l'article courant (reset entre chaque article)
_used_source_ids = set()


def reset_article_cache():
    global _used_source_ids
    _used_source_ids = set()


def download_and_convert_webp(content: bytes, save_path: str, max_kb: int = 200) -> bool:
    """Convertit les bytes image en WebP < max_kb et sauvegarde.
    Fix fond noir : fond blanc appliqué avant conversion pour les PNG transparents.
    """
    try:
        if PIL_AVAILABLE:
            img = Image.open(io.BytesIO(content))

            # Fix fond noir : composer sur fond blanc avant de convertir en RGB
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                # Utiliser le canal alpha comme masque
                alpha = img.split()[-1] if img.mode in ("RGBA", "LA") else None
                if alpha:
                    background.paste(img.convert("RGB"), mask=alpha)
                else:
                    background.paste(img.convert("RGB"))
                img = background
            elif img.mode != "RGB":
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
            # Dernier recours : resize
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
    """
    Valide qu'une image est bien une photo de plantes/fleurs via Codex CLI.
    En cas de timeout ou d'erreur → NEIN par défaut (fail-safe).
    """
    prompt = (
        "Antworte NUR mit JA oder NEIN — kein anderer Text.\n"
        "JA = Blumen oder Pflanzen sind das klare HAUPTMOTIV im Vordergrund, kein Gebäude sichtbar.\n"
        "NEIN = Gebäude, Architektur, leerer Balkon, Stadtbild, oder kein Pflanzenmotiv."
    )
    try:
        result = subprocess.run(
            ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-i", image_path],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30
        )
        output = result.stdout.strip().upper()
        first_word = output.split()[0] if output.split() else "NEIN"
        print(f"[DA] Codex validation: '{first_word}'")
        return first_word == "JA"

    except subprocess.TimeoutExpired:
        print(f"[DA] Codex timeout → NEIN (défaut)")
        return False
    except Exception as e:
        print(f"[DA] Codex erreur → NEIN (défaut) : {e}")
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
        resp = requests.get(
            PEXELS_API_URL,
            headers={"Authorization": api_key},
            params={"query": query, "per_page": per_page, "orientation": "landscape"},
            timeout=10
        )
        if resp.status_code == 200:
            return [
                {
                    "url": p["src"]["large"],
                    "source_id": f"pexels_{p['id']}",
                    "photographer": p.get("photographer", ""),
                    "source": "pexels",
                    "source_url": p.get("url", "")
                }
                for p in resp.json().get("photos", [])
            ]
    except Exception as e:
        print(f"[DA] Pexels erreur ({query}): {e}")
    return []


def search_pixabay(query: str, per_page: int = 10) -> list:
    api_key = os.getenv("PIXABAY_API_KEY")
    if not api_key:
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
            return [
                {
                    "url": img.get("largeImageURL", img.get("webformatURL")),
                    "source_id": f"pixabay_{img['id']}",
                    "photographer": img.get("user", ""),
                    "source": "pixabay",
                    "source_url": img.get("pageURL", "")
                }
                for img in resp.json().get("hits", [])
            ]
    except Exception as e:
        print(f"[DA] Pixabay erreur ({query}): {e}")
    return []


def collect_unique_candidates(queries: list) -> list:
    """Collecte candidats depuis toutes les requêtes, dédupliqués par source_id."""
    seen_ids = set()
    unique = []
    for query in queries:
        for candidate in search_pexels(query, 10) + search_pixabay(query, 10):
            sid = candidate["source_id"]
            if sid not in seen_ids:
                seen_ids.add(sid)
                unique.append(candidate)
    print(f"[DA] {len(unique)} candidats uniques collectés ({len(queries)} requêtes)")
    return unique


def fetch_n_images(queries: list, n: int, img_dir: str, keyword: str, category: str) -> list:
    """Collecte exactement N images uniques, validées visuellement par Codex."""
    MAX_REJECTIONS = max(15, n * 3)
    rejected_count = 0
    images = []

    candidates = collect_unique_candidates(queries)

    for candidate in candidates:
        if len(images) >= n:
            break
        if rejected_count >= MAX_REJECTIONS:
            print(f"[DA] MAX_REJECTIONS ({MAX_REJECTIONS}) atteint — passage au fallback GPT")
            break

        sid = candidate["source_id"]
        url = candidate["url"]

        if sid in _used_source_ids:
            continue
        if HISTORY_AVAILABLE and is_image_already_used(url):
            print(f"[DA] ⏭️ {sid} — déjà utilisé (historique)")
            continue

        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            content = resp.content
        except Exception as e:
            print(f"[DA] Erreur téléchargement {sid}: {e}")
            continue

        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(content)
                temp_path = f.name
        except Exception as e:
            print(f"[DA] Erreur fichier temp: {e}")
            continue

        print(f"[DA] Validation {sid} ({candidate['source']})...")
        if validate_image_with_codex(temp_path, keyword, category):
            img_num = len(images) + 1
            save_path = str(Path(img_dir) / f"article_img_{img_num:02d}.webp")

            if download_and_convert_webp(content, save_path):
                _used_source_ids.add(sid)
                if HISTORY_AVAILABLE:
                    add_image_to_history(url, keyword)

                alt_text = keyword if img_num == 1 else f"{keyword} - Bild {img_num}"
                images.append({
                    "path": save_path,
                    "source": candidate["source"],
                    "photographer": candidate["photographer"],
                    "source_url": candidate["source_url"],
                    "source_id": sid,
                    "alt_text": alt_text
                })
                print(f"[DA] ✅ Image {img_num}/{n} validée ({candidate['source']})")
        else:
            rejected_count += 1
            print(f"[DA] ❌ Rejetée {sid} ({rejected_count}/{MAX_REJECTIONS})")

    # Fallback GPT-image si pas assez d'images libres
    gpt_attempt = 0
    while len(images) < n:
        img_num = len(images) + 1
        gpt_attempt += 1
        save_path = str(Path(img_dir) / f"article_img_{img_num:02d}.webp")
        print(f"[DA] 🔄 GPT-image fallback — image {img_num} (tentative {gpt_attempt})")

        try:
            from openai import OpenAI
            client = OpenAI()
            gpt_prompt = (
                f"Close-up of beautiful {category.lower()} plants and flowers, "
                f"lush green leaves, natural daylight, no buildings or architecture visible, "
                f"garden photography style, photo {gpt_attempt}"
            )
            r = client.images.generate(
                model=GPT_IMAGE_MODEL,
                prompt=gpt_prompt,
                size=GPT_IMAGE_SIZE,
                n=1
            )
            img_resp = requests.get(r.data[0].url, timeout=15)
            if img_resp.status_code == 200 and download_and_convert_webp(img_resp.content, save_path):
                alt_text = keyword if img_num == 1 else f"{keyword} - Bild {img_num}"
                images.append({
                    "path": save_path,
                    "source": "gpt_image",
                    "photographer": "AI Generated",
                    "source_url": "",
                    "source_id": f"gpt_{img_num}_{gpt_attempt}",
                    "alt_text": alt_text
                })
                print(f"[DA] ✅ GPT-image {img_num}/{n}")
            else:
                print(f"[DA] GPT-image échec — arrêt")
                break
        except Exception as e:
            print(f"[DA] GPT-image erreur: {e}")
            break

    return images
