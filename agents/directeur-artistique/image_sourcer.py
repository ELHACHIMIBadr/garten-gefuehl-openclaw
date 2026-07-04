"""
Directeur Artistique Agent — Image Sourcer

CHANGELOG v2 (Bug 3 corrigé):
- Prompt Codex ultra-court et binaire (Blumen/Pflanzen = JA, Gebäude = NEIN).
- Condition de retour : output.startswith("JA") au lieu de "JA" in output.
  Évite les faux-positifs ("VIELLEICHT JA", "ICH GLAUBE JA...").
- Timeout réduit à 30s → NEIN par défaut en cas d'erreur/timeout.
- MAX_REJECTIONS augmenté à 15 (pool de ~80 candidats disponibles).
- Anti-doublon par source_id conservé (pool unifié par collect_unique_candidates).
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
    """Convertit les bytes image en WebP < max_kb et sauvegarde."""
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
            # Dernier recours : resize
            img.thumbnail((800, 800), Image.LANCZOS)
            img.save(save_path, format="WEBP", quality=75)
            return True
        else:
            # PIL non disponible — sauvegarde brute
            with open(save_path, "wb") as f:
                f.write(content)
            return True
    except Exception as e:
        print(f"[DA] Erreur WebP: {e}")
        return False


def validate_image_with_codex(image_path: str, keyword: str, category: str) -> bool:
    """
    Valide qu'une image est bien une photo de plantes/fleurs via Codex CLI.

    Règles strictes :
    - JA  = Plantes/fleurs CLAIREMENT en premier plan, pas de bâtiment visible
    - NEIN = Bâtiment, architecture, balcon vide, paysage urbain, ou incertain

    En cas de timeout ou d'erreur → NEIN par défaut (fail-safe).
    La condition de retour vérifie que la réponse COMMENCE par "JA" (anti-faux-positif).
    """
    # Prompt ultra-court et binaire — Codex doit répondre JA ou NEIN, rien d'autre
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
            timeout=30  # Réduit à 30s — timeout → NEIN
        )
        # Nettoyer la réponse : prendre le 1er mot uniquement
        output = result.stdout.strip().upper()
        first_word = output.split()[0] if output.split() else "NEIN"
        print(f"[DA] Codex validation: '{first_word}'")

        # Condition stricte : doit commencer par "JA" exactement
        return first_word == "JA"

    except subprocess.TimeoutExpired:
        print(f"[DA] Codex timeout → NEIN (défaut)")
        return False
    except Exception as e:
        print(f"[DA] Codex erreur → NEIN (défaut) : {e}")
        return False
    finally:
        # Supprimer le fichier temporaire dans tous les cas
        try:
            os.unlink(image_path)
        except:
            pass


def search_pexels(query: str, per_page: int = 10) -> list:
    """Recherche des images sur Pexels."""
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
    """Recherche des images sur Pixabay."""
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
    """
    Collecte des candidats depuis TOUTES les requêtes (Pexels + Pixabay).
    Déduplique par source_id — élimine les photos populaires qui reviennent
    dans plusieurs requêtes différentes (cause principale du Bug 1).
    """
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
    """
    Collecte exactement N images uniques, validées visuellement par Codex.

    Ordre de priorité : Pexels → Pixabay → GPT-image fallback.
    Anti-doublon : source_id par article (cache local) + historique global.
    Validation : chaque image passée à Codex CLI — plantes/fleurs uniquement.
    """
    # MAX_REJECTIONS augmenté : pool de ~80 candidats disponibles
    MAX_REJECTIONS = max(15, n * 3)
    rejected_count = 0
    images = []

    # Étape 1 : collecter tous les candidats uniques depuis toutes les requêtes
    candidates = collect_unique_candidates(queries)

    for candidate in candidates:
        if len(images) >= n:
            break
        if rejected_count >= MAX_REJECTIONS:
            print(f"[DA] MAX_REJECTIONS ({MAX_REJECTIONS}) atteint — passage au fallback GPT")
            break

        sid = candidate["source_id"]
        url = candidate["url"]

        # Filtre 1 : déjà utilisé dans cet article ?
        if sid in _used_source_ids:
            continue

        # Filtre 2 : historique global (inter-articles)
        if HISTORY_AVAILABLE and is_image_already_used(url):
            print(f"[DA] ⏭️ {sid} — déjà utilisé (historique)")
            continue

        # Télécharger l'image
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            content = resp.content
        except Exception as e:
            print(f"[DA] Erreur téléchargement {sid}: {e}")
            continue

        # Écrire dans un fichier temp pour Codex
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(content)
                temp_path = f.name
        except Exception as e:
            print(f"[DA] Erreur fichier temp: {e}")
            continue

        # Validation Codex (supprime temp_path dans le finally)
        print(f"[DA] Validation {sid} ({candidate['source']})...")
        if validate_image_with_codex(temp_path, keyword, category):
            img_num = len(images) + 1
            save_path = str(Path(img_dir) / f"article_img_{img_num:02d}.webp")

            if download_and_convert_webp(content, save_path):
                _used_source_ids.add(sid)
                if HISTORY_AVAILABLE:
                    add_image_to_history(url, keyword)

                # Alt text : keyword exact pour l'image 1 (featured), descriptif pour les autres
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
            # Prompt spécifique à la catégorie pour meilleure pertinence
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
