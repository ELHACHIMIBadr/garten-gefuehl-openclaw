"""
Distributeur Agent — Main
Distribution des pins Pinterest sur 5 comptes business.

RÈGLES DE DISTRIBUTION:
- Warm-up (jours 1-4) : 2 pins/jour SANS lien, ordre aléatoire des comptes
- Mode actif : 4 pins/jour AVEC lien vers article WordPress
- Max 1 pin/jour vers la même URL (toutes comptes confondus)
- Délai aléatoire anti-ban entre chaque pin (90-240s) et entre chaque compte (120-360s)
- Rotation des boards (round-robin par compte)

PRÉREQUIS .env:
  PINTEREST_TOKEN_BLUMENLIEBE=...     + PINTEREST_BOARDS_BLUMENLIEBE=id1,id2,...
  PINTEREST_TOKEN_BALKON=...          + PINTEREST_BOARDS_BALKON=id1,id2,...
  PINTEREST_TOKEN_ROSEN=...           + PINTEREST_BOARDS_ROSEN=id1,id2,...
  PINTEREST_TOKEN_TERRASSE=...        + PINTEREST_BOARDS_TERRASSE=id1,id2,...
  PINTEREST_TOKEN_GARTENGEFUHL=...    + PINTEREST_BOARDS_GARTENGEFUHL=id1,id2,...

Usage:
  python main.py                      # Exécution normale
  python main.py --dry-run            # Test sans poster sur Pinterest
  python main.py --list-boards        # Lister les boards de tous les comptes configurés

Cron (après le Publisher, décalé de 30 min):
  30 8 * * * cd /root/garten-gefuehl-openclaw/agents/distributeur && /usr/bin/python3 main.py
"""

import os
import sys
import json
import random
import time
import argparse
import requests
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv("/root/garten-gefuehl-openclaw/config/.env")

from config import (
    PINS_DIR, ACCOUNT_CATEGORY_MAP,
    PINS_PER_DAY_WARMUP, PINS_PER_DAY_ACTIVE,
    DELAY_BETWEEN_PINS_MIN, DELAY_BETWEEN_PINS_MAX,
    DELAY_BETWEEN_ACCOUNTS_MIN, DELAY_BETWEEN_ACCOUNTS_MAX,
    MAX_PINS_PER_URL_PER_DAY,
    get_account_config
)
from pinterest_client import PinterestClient
from state_manager import (
    load_state, save_state, is_warmup, mark_first_use,
    get_next_board, is_pin_already_posted, mark_pin_as_posted,
    can_post_url_today, track_url_posted, get_warmup_days_remaining
)

sys.path.insert(0, "/root/garten-gefuehl-openclaw/agents")


def send_telegram(msg: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    cid = os.getenv("TELEGRAM_CHAT_ID")
    if token and cid:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": cid, "text": msg, "parse_mode": "HTML"},
                timeout=10
            )
        except:
            pass


def get_available_pins_for_account(account_name: str, categorie: str, state: dict) -> list:
    """
    Retourne les pins disponibles pour ce compte (non encore postés depuis ce compte).
    Scanne tous les dossiers /data/pins/ triés par date (plus récent en premier).

    Retourne une liste de dicts:
    [{
        "path": str,          # Chemin local vers le fichier WebP
        "filename": str,      # Nom du fichier (pour tracking)
        "article_url": str,   # URL WordPress de l'article (ou None si indisponible)
        "title": str,         # Titre du pin
        "date": str           # Date du dossier
    }]
    """
    pins_root = Path(PINS_DIR)
    if not pins_root.exists():
        return []

    available = []

    # Scanner tous les dossiers date, triés du plus récent
    date_dirs = sorted(pins_root.iterdir(), reverse=True)

    for date_dir in date_dirs:
        if not date_dir.is_dir():
            continue

        # Chercher les pins correspondant à ce compte dans ce dossier
        # Convention de nommage : pin_XX_AccountName.webp (ex: pin_01_Blumenliebe_DE.webp)
        account_slug = account_name.replace(" ", "_").replace("&", "und").replace("ü", "u")

        for pin_file in date_dir.glob(f"pin_*_{account_slug}.webp"):
            filename = pin_file.name

            # Déjà posté depuis ce compte ?
            if is_pin_already_posted(filename, account_name, state):
                continue

            # Chercher l'article associé (même dossier date)
            article_url = _find_article_url_for_date(date_dir.name, categorie)

            available.append({
                "path": str(pin_file),
                "filename": filename,
                "article_url": article_url,
                "title": _extract_title_from_filename(filename),
                "date": date_dir.name
            })

    return available


def _find_article_url_for_date(date_str: str, categorie: str) -> str:
    """
    Cherche l'URL WordPress de l'article publié à cette date pour cette catégorie.
    Lit le fichier article JSON correspondant.
    """
    articles_dir = Path("/root/garten-gefuehl-openclaw/data/articles") / date_str

    if not articles_dir.exists():
        return None

    for article_file in articles_dir.glob("article_*.json"):
        try:
            with open(article_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            brief = data.get("brief", {})
            if brief.get("categorie_wp") != categorie:
                continue

            # Récupérer l'URL de publication
            publish_result = data.get("publish_result", {})
            url = publish_result.get("url")
            if url and data.get("status") == "published":
                return url

        except:
            continue

    return None


def _extract_title_from_filename(filename: str) -> str:
    """Extrait un titre lisible du nom de fichier (fallback si pas de données JSON)."""
    # pin_01_Blumenliebe_DE.webp → Blumenliebe DE
    parts = filename.replace(".webp", "").split("_")
    if len(parts) > 2:
        return " ".join(parts[2:]).replace("_", " ")
    return filename


def list_boards_all_accounts():
    """
    Commande utilitaire : affiche les boards de tous les comptes configurés.
    Usage: python main.py --list-boards
    """
    print("\n" + "=" * 60)
    print("BOARDS PAR COMPTE PINTEREST")
    print("=" * 60)

    for account_name in ACCOUNT_CATEGORY_MAP:
        cfg = get_account_config(account_name)
        if not cfg.get("token"):
            print(f"\n❌ {account_name} — Token manquant dans .env")
            continue

        print(f"\n📌 {account_name} (catégorie: {cfg['categorie']})")
        client = PinterestClient(cfg["token"])
        if not client.test_connection():
            continue

        boards = client.get_boards()
        if boards:
            for b in boards:
                print(f"   ID: {b.get('id')} | Nom: {b.get('name')}")
            print(f"   → Copier ces IDs dans .env sous PINTEREST_BOARDS_{account_name.upper().replace(' ', '_').replace('&', 'UND')}")
        else:
            print(f"   Aucun board trouvé")

    print("\n" + "=" * 60)


def run_account(account_name: str, cfg: dict, state: dict, dry_run: bool = False) -> dict:
    """
    Exécute la distribution pour UN compte Pinterest.

    Retourne un dict résultat : {account, pins_posted, pins_skipped, mode, errors}
    """
    result = {
        "account": account_name,
        "mode": "",
        "pins_posted": 0,
        "pins_skipped": 0,
        "errors": []
    }

    if not cfg.get("configured"):
        msg = f"Compte non configuré (token ou boards manquants)"
        print(f"[Distributeur] ⚠️ {account_name} — {msg}")
        result["errors"].append(msg)
        return result

    # Déterminer le mode
    warmup = is_warmup(account_name, state)
    pins_target = PINS_PER_DAY_WARMUP if warmup else PINS_PER_DAY_ACTIVE
    warmup_remaining = get_warmup_days_remaining(account_name, state)
    result["mode"] = f"warm-up (J-{warmup_remaining} restants)" if warmup else "actif"

    print(f"\n[Distributeur] {'🌱' if warmup else '🚀'} {account_name} — Mode {result['mode']} — Cible: {pins_target} pins")

    # Connexion Pinterest
    client = PinterestClient(cfg["token"])
    if not dry_run and not client.test_connection():
        result["errors"].append("Connexion Pinterest échouée")
        return result

    # Pins disponibles pour ce compte
    available_pins = get_available_pins_for_account(account_name, cfg["categorie"], state)
    print(f"[Distributeur] Pins disponibles: {len(available_pins)}")

    if not available_pins:
        print(f"[Distributeur] ⚠️ Aucun pin disponible pour {account_name}")
        result["pins_skipped"] = pins_target
        return result

    # Marquer première utilisation si nécessaire
    if not dry_run:
        mark_first_use(account_name, state)

    # Poster les pins
    posted_count = 0
    for pin_data in available_pins:
        if posted_count >= pins_target:
            break

        pin_path = pin_data["path"]
        pin_filename = pin_data["filename"]
        article_url = pin_data["article_url"]

        # Déterminer si on poste avec ou sans lien
        link = None
        if not warmup and article_url:
            if can_post_url_today(article_url, state, MAX_PINS_PER_URL_PER_DAY):
                link = article_url
            else:
                print(f"[Distributeur] ⏭️ URL déjà postée aujourd'hui : {article_url}")
                result["pins_skipped"] += 1
                continue

        # Choisir un board (rotation)
        board_id = get_next_board(account_name, cfg["boards"], state)
        if not board_id:
            print(f"[Distributeur] ❌ Pas de board_id pour {account_name}")
            result["errors"].append("Pas de board_id configuré")
            break

        # Description du pin (générique mais engageante)
        description = (
            f"Entdecke unsere besten Tipps rund um {cfg['categorie']} auf garten-gefühl.de 🌱 "
            f"#Garten #{''.join(cfg['categorie'].split())} #Gartenideen #Pflanzen"
        )

        print(f"[Distributeur] → Posting pin {posted_count + 1}/{pins_target} "
              f"| Board: {board_id[:8]}... | Link: {'✓' if link else '✗ (warm-up)'}")

        if dry_run:
            print(f"[Distributeur] DRY RUN — Pin simulé: {pin_filename}")
            success = True
            pin_result = {"id": f"dry_{posted_count}"}
        else:
            # Délai anti-ban avant chaque pin (sauf le premier)
            if posted_count > 0:
                delay = random.randint(DELAY_BETWEEN_PINS_MIN, DELAY_BETWEEN_PINS_MAX)
                print(f"[Distributeur] ⏱️ Délai anti-ban: {delay}s...")
                time.sleep(delay)

            pin_result = client.create_pin(
                board_id=board_id,
                title=_extract_title_from_filename(pin_filename)[:100],
                description=description,
                image_path=pin_path,
                link=link
            )
            success = bool(pin_result.get("id"))

        if success:
            if not dry_run:
                mark_pin_as_posted(pin_filename, account_name, state)
                if link:
                    track_url_posted(link, state)
            posted_count += 1
            result["pins_posted"] += 1
            print(f"[Distributeur] ✅ Pin posté ({posted_count}/{pins_target})")
        else:
            result["errors"].append(f"Échec pin {pin_filename}")
            result["pins_skipped"] += 1

    return result


def run(dry_run: bool = False):
    print("=" * 60)
    print(f"[Distributeur] Démarrage — {datetime.now().isoformat()}")
    print("=" * 60)

    state = load_state()
    all_results = []

    # Ordre aléatoire des comptes (anti-ban)
    account_names = list(ACCOUNT_CATEGORY_MAP.keys())
    random.shuffle(account_names)
    print(f"[Distributeur] Ordre aujourd'hui: {' → '.join(account_names)}")

    for i, account_name in enumerate(account_names):
        cfg = get_account_config(account_name)
        result = run_account(account_name, cfg, state, dry_run)
        all_results.append(result)

        # Sauvegarder l'état après chaque compte (sécurité)
        if not dry_run:
            save_state(state)

        # Délai entre comptes (sauf après le dernier)
        if i < len(account_names) - 1 and not dry_run:
            delay = random.randint(DELAY_BETWEEN_ACCOUNTS_MIN, DELAY_BETWEEN_ACCOUNTS_MAX)
            print(f"\n[Distributeur] ⏱️ Pause entre comptes: {delay}s...")
            time.sleep(delay)

    # Rapport final
    total_posted = sum(r["pins_posted"] for r in all_results)
    total_errors = sum(len(r["errors"]) for r in all_results)

    print(f"\n[Distributeur] " + "=" * 40)
    print(f"[Distributeur] RÉSUMÉ : {total_posted} pins postés | {total_errors} erreurs")
    for r in all_results:
        status = "✅" if r["pins_posted"] > 0 else "⚠️"
        print(f"[Distributeur] {status} {r['account']} — {r['pins_posted']} pins | {r['mode']}")
    print(f"[Distributeur] " + "=" * 40)

    # Rapport Telegram
    if not dry_run:
        lines = [f"📌 <b>Distributeur</b> — {date.today().isoformat()}"]
        lines.append(f"Total : <b>{total_posted} pins</b> postés")
        lines.append("")
        for r in all_results:
            icon = "✅" if r["pins_posted"] > 0 else ("⚠️" if r["pins_skipped"] > 0 else "❌")
            lines.append(f"{icon} {r['account']} : {r['pins_posted']} pins | {r['mode']}")
        if total_errors > 0:
            lines.append(f"\n⚠️ {total_errors} erreur(s) — vérifier logs VPS")

        send_telegram("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Distributeur Agent — Garten Gefühl")
    parser.add_argument("--dry-run", action="store_true", help="Test sans poster sur Pinterest")
    parser.add_argument("--list-boards", action="store_true", help="Lister les boards de tous les comptes")
    args = parser.parse_args()

    if args.list_boards:
        list_boards_all_accounts()
    else:
        run(dry_run=args.dry_run)
