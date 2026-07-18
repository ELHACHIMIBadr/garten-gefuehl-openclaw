"""
Distributeur Agent — Main (Playwright) — Mode Round-Robin

MODE ROUND-ROBIN :
  Round 1 (16:00) : 1 pin compte 1 → 1 pin compte 2 → ... → 1 pin compte 5
  Attente 30 min
  Round 2 (16:30) : 1 pin compte 1 → ... → 1 pin compte 5
  ...
  Round 5 (18:00) : dernier pin pour chaque compte

  Total : 25 pins en ~2h, 30 min entre chaque round.

RÈGLES :
  - 3 pins avec lien + 2 pins sans lien par compte/jour
  - Cross-niche interdit
  - Si pas d'article dans la niche : 0 pin avec lien

Usage :
  python main.py              # Exécution normale (5 rounds × 5 comptes)
  python main.py --dry-run    # Test sans poster
  python main.py --round 1    # Un seul round (1-5)
  python main.py --account 1  # Un seul compte tous rounds
"""

import os
import json
import random
import time
import argparse
from datetime import date, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
load_dotenv("/root/garten-gefuehl-openclaw/config/.env")

from config import (
    PINS_DIR, ARTICLES_DIR, ACCOUNT_CONFIG,
    PINS_NO_LINK, PINS_WITH_LINK, PINS_PER_ACCOUNT,
    DELAY_BETWEEN_ACCOUNTS_MIN, DELAY_BETWEEN_ACCOUNTS_MAX,
    DELAY_BETWEEN_ROUNDS,
)
from playwright_poster import post_pin_with_retry, build_description
from state_manager import (
    load_state, save_state,
    get_next_board_name,
    is_pin_already_posted, mark_pin_as_posted,
    can_post_url_today, track_url_posted,
    record_daily_result,
    get_daily_pin_count, increment_daily_pin_count,
)


# ── Telegram ──────────────────────────────────────────────────

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
        except Exception:
            pass


# ── Ressources ─────────────────────────────────────────────────

def get_published_articles(categorie: str) -> list:
    articles_root = Path(ARTICLES_DIR)
    found = []
    if not articles_root.exists():
        return found
    for date_dir in sorted(articles_root.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for article_file in date_dir.glob("article_*.json"):
            try:
                with open(article_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("status") != "published":
                    continue
                if data.get("brief", {}).get("categorie_wp") != categorie:
                    continue
                url = data.get("publish_result", {}).get("url")
                title = data.get("article", {}).get("seo_title", "")
                if url:
                    found.append({"url": url, "title": title, "date": date_dir.name})
            except Exception:
                continue
    return found


def _load_pin_titles_for_date(date_str: str) -> dict:
    """Charge les titres des pins depuis les article JSON d'une date."""
    mapping = {}
    article_dir = Path(ARTICLES_DIR) / date_str
    if not article_dir.exists():
        return mapping
    for f in article_dir.glob("article_*.json"):
        try:
            data = json.load(open(f, encoding="utf-8"))
            for pin in data.get("pins", []):
                pin_path = pin.get("path", "")
                title = pin.get("title", "")
                if pin_path and title:
                    mapping[Path(pin_path).name] = title
        except Exception:
            continue
    return mapping


def get_pins_for_account(account_name: str, state: dict) -> list:
    """Retourne les pins non encore postés pour ce compte, triés par date desc."""
    pins_root = Path(PINS_DIR)
    if not pins_root.exists():
        return []

    account_slug = (
        account_name.replace(" ", "_").replace("&", "und")
        .replace("ü", "u").replace("Ü", "U")
    )

    available = []
    for date_dir in sorted(pins_root.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        pin_titles = _load_pin_titles_for_date(date_dir.name)
        for pin_file in sorted(date_dir.glob(f"pin_*_{account_slug}*.webp")):
            filename = pin_file.name
            if is_pin_already_posted(filename, account_name, state):
                continue
            available.append({
                "path": str(pin_file),
                "filename": filename,
                "date": date_dir.name,
                "title": pin_titles.get(filename, ""),
            })
    return available


def _find_article_url(date_str: str, categorie: str):
    article_dir = Path(ARTICLES_DIR) / date_str
    if not article_dir.exists():
        return None
    for f in article_dir.glob("article_*.json"):
        try:
            data = json.load(open(f, encoding="utf-8"))
            if data.get("status") != "published":
                continue
            if data.get("brief", {}).get("categorie_wp") != categorie:
                continue
            return data.get("publish_result", {}).get("url")
        except Exception:
            continue
    return None


# ── Préparer le plan journalier ────────────────────────────────

def build_daily_plan(state: dict) -> dict:
    """
    Construit le plan de la journée : pour chaque compte, liste ordonnée
    de 5 pins avec/sans lien.
    Stocké dans state["daily_plan"] pour persistance entre rounds.
    """
    today = date.today().isoformat()

    # Si plan déjà construit aujourd'hui → le réutiliser
    existing = state.get("daily_plan", {})
    if existing.get("date") == today:
        return existing

    plan = {"date": today, "accounts": {}}

    for cfg in ACCOUNT_CONFIG:
        account_name = cfg["name"]
        categorie = cfg["categorie"]

        pins_available = get_pins_for_account(account_name, state)
        articles = get_published_articles(categorie)

        # Déterminer combien de pins avec/sans lien
        with_link_target = PINS_WITH_LINK if articles else 0
        no_link_target = PINS_NO_LINK + (PINS_WITH_LINK - with_link_target)

        # File d'articles (max 2 fois le même URL/jour)
        article_queue = []
        for art in articles:
            if can_post_url_today(art["url"], state):
                article_queue.append(art)
            if len(article_queue) >= with_link_target:
                break

        actual_with_link = len(article_queue)
        actual_no_link = no_link_target + (with_link_target - actual_with_link)

        # Assigner pins aux slots
        random.shuffle(pins_available)
        pin_cursor = 0
        slots = []

        for art in article_queue:
            if pin_cursor >= len(pins_available):
                break
            pin = pins_available[pin_cursor]; pin_cursor += 1
            board = get_next_board_name(account_name, cfg["boards"], state)
            slots.append({
                "pin_path": pin["path"],
                "pin_filename": pin["filename"],
                "link": art["url"],
                "title": art["title"] or f"Garten Tipps – {categorie}",
                "board": board,
                "posted": False,
            })

        for _ in range(actual_no_link):
            if pin_cursor >= len(pins_available):
                break
            pin = pins_available[pin_cursor]; pin_cursor += 1
            board = get_next_board_name(account_name, cfg["boards"], state)
            # Titre = overlay texte du pin (unique) ou fallback keyword
            pin_title = pin.get("title", "") or f"{categorie} Tipps & Ideen"
            slots.append({
                "pin_path": pin["path"],
                "pin_filename": pin["filename"],
                "link": None,
                "title": pin_title,
                "board": board,
                "posted": False,
            })

        # Mélanger pour entremêler avec/sans lien
        random.shuffle(slots)
        plan["accounts"][account_name] = slots

    state["daily_plan"] = plan
    save_state(state)
    return plan


# ── Exécuter un round ──────────────────────────────────────────

def run_round(round_num: int, state: dict, dry_run: bool = False,
              only_account_idx: int = None) -> dict:
    """
    Exécute le round N : poste 1 pin par compte.
    round_num : 0-based (0 = round 1)
    """
    plan = build_daily_plan(state)
    round_results = {"round": round_num + 1, "posted": 0, "skipped": 0, "errors": []}

    print(f"\n{'='*60}")
    print(f"[Distributeur] 🔄 ROUND {round_num + 1}/{PINS_PER_ACCOUNT} — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    account_indices = list(range(len(ACCOUNT_CONFIG)))
    if only_account_idx is not None:
        account_indices = [only_account_idx]
    else:
        random.shuffle(account_indices)

    for pos, idx in enumerate(account_indices):
        cfg = ACCOUNT_CONFIG[idx]
        account_name = cfg["name"]
        categorie = cfg["categorie"]
        email = os.getenv(cfg["email_env"], "")
        password = os.getenv(cfg["password_env"], "")

        account_slots = plan["accounts"].get(account_name, [])

        # Trouver le prochain slot non posté
        slot = None
        slot_idx = None
        not_posted = [(i, s) for i, s in enumerate(account_slots) if not s.get("posted")]
        if not not_posted:
            print(f"[Distributeur] ⏭️ {account_name} — plus de pins à poster")
            continue
        slot_idx, slot = not_posted[0]

        print(f"\n[Distributeur] 📌 {account_name}")
        link_label = f"🔗 {slot['link'][:50]}..." if slot["link"] else "🚫 sans lien"
        print(f"[Distributeur] {link_label} | Board : {slot['board']}")
        print(f"[Distributeur] Image : {slot['pin_filename']}")

        if dry_run:
            print(f"[Distributeur] DRY RUN ✅")
            plan["accounts"][account_name][slot_idx]["posted"] = True
            round_results["posted"] += 1
            continue

        if not email or not password:
            print(f"[Distributeur] ❌ Credentials manquants")
            round_results["errors"].append(f"{account_name}: credentials manquants")
            continue

        desc = build_description(categorie, slot["title"])

        post_result = post_pin_with_retry(
            account_name=account_name,
            email=email,
            password=password,
            image_path=slot["pin_path"],
            title=slot["title"][:100],
            description=desc,
            board_name=slot["board"],
            categorie=categorie,
            link=slot["link"],
            max_retries=3,
            headless=True,
        )

        if post_result["success"]:
            plan["accounts"][account_name][slot_idx]["posted"] = True
            mark_pin_as_posted(slot["pin_filename"], account_name, state)
            if slot["link"]:
                track_url_posted(slot["link"], state)
            state["daily_plan"] = plan
            save_state(state)
            round_results["posted"] += 1
            print(f"[Distributeur] ✅ Pin posté")
        else:
            err = post_result.get("error", "erreur inconnue")
            round_results["errors"].append(f"{account_name}: {err}")
            round_results["skipped"] += 1
            print(f"[Distributeur] ⚠️ Skippé : {err}")

        # Délai anti-ban entre comptes
        if pos < len(account_indices) - 1 and not dry_run:
            delay = random.randint(DELAY_BETWEEN_ACCOUNTS_MIN, DELAY_BETWEEN_ACCOUNTS_MAX)
            print(f"[Distributeur] ⏱️ {delay}s avant prochain compte...")
            time.sleep(delay)

    return round_results


# ── Orchestrateur principal ────────────────────────────────────

def run(dry_run: bool = False, only_account: int = None, only_round: int = None):
    print("=" * 60)
    print(f"[Distributeur] 🚀 Démarrage — {datetime.now().isoformat()}")
    print(f"[Distributeur] Mode : {'DRY RUN' if dry_run else 'PRODUCTION'}")
    print("=" * 60)

    state = load_state()
    only_account_idx = (only_account - 1) if only_account is not None else None

    # Déterminer les rounds à exécuter
    if only_round is not None:
        rounds_to_run = [only_round - 1]  # --round 1 → index 0
    else:
        rounds_to_run = list(range(PINS_PER_ACCOUNT))

    all_results = []

    for r_idx, round_num in enumerate(rounds_to_run):
        result = run_round(round_num, state, dry_run, only_account_idx)
        all_results.append(result)

        # Rapport Telegram par round
        if not dry_run and len(rounds_to_run) > 1:
            send_telegram(
                f"🔄 <b>Round {round_num + 1}/{PINS_PER_ACCOUNT}</b>\n"
                f"✅ {result['posted']} pins postés\n"
                f"⚠️ {result['skipped']} skippés"
            )

        # Attendre 30 min avant le prochain round (sauf le dernier)
        if r_idx < len(rounds_to_run) - 1 and not dry_run:
            next_time = datetime.fromtimestamp(time.time() + DELAY_BETWEEN_ROUNDS)
            print(f"\n[Distributeur] ⏳ Prochain round à {next_time.strftime('%H:%M:%S')} (30 min)...")
            time.sleep(DELAY_BETWEEN_ROUNDS)

    # Résumé final
    total_posted = sum(r["posted"] for r in all_results)
    total_skipped = sum(r["skipped"] for r in all_results)
    total_errors = sum(len(r["errors"]) for r in all_results)

    print(f"\n{'='*60}")
    print(f"[Distributeur] RÉSUMÉ FINAL")
    print(f"  ✅ Postés  : {total_posted}")
    print(f"  ⚠️ Skippés : {total_skipped}")
    print(f"  ❌ Erreurs : {total_errors}")
    print(f"{'='*60}")

    if not dry_run:
        record_daily_result(state, all_results)
        save_state(state)
        send_telegram(
            f"📌 <b>Distributeur Pinterest — Terminé</b>\n"
            f"📅 {date.today().isoformat()}\n"
            f"✅ {total_posted}/25 pins postés\n"
            f"⚠️ {total_skipped} skippés"
        )


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Distributeur Pinterest — Round-Robin")
    parser.add_argument("--dry-run", action="store_true", help="Test sans poster")
    parser.add_argument("--account", type=int, choices=range(1, 6),
                        help="Un seul compte (1-5)")
    parser.add_argument("--round", type=int, choices=range(1, 6),
                        help="Un seul round (1-5)")
    args = parser.parse_args()

    run(dry_run=args.dry_run, only_account=args.account,
        only_round=getattr(args, "round", None))
