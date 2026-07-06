"""
Distributeur Agent — Main (Playwright)
Distribution des pins Pinterest sur 5 comptes via navigateur automatisé.

RÈGLES DE DISTRIBUTION :
  ┌─────────────────────────────────────────────────────────┐
  │  5 pins/jour par compte                                 │
  │  • 2 pins SANS lien  (contenu niche générique/archivé)  │
  │  • 3 pins AVEC lien  (articles WP de la même niche)     │
  │                                                         │
  │  CROSS-NICHE INTERDIT : chaque compte ne poste jamais   │
  │  un lien d'une autre niche (ex: jamais Rosen→Terrasse)  │
  │                                                         │
  │  Si pas d'article dans la niche : 0 pin avec lien,      │
  │  on complète avec des pins sans lien uniquement         │
  └─────────────────────────────────────────────────────────┘

PRÉREQUIS .env :
  PINTEREST_1_EMAIL / PINTEREST_1_PASSWORD   → Blumenliebe DE
  PINTEREST_2_EMAIL / PINTEREST_2_PASSWORD   → Balkon Ideen DE
  PINTEREST_3_EMAIL / PINTEREST_3_PASSWORD   → Rosenfreude DE
  PINTEREST_4_EMAIL / PINTEREST_4_PASSWORD   → Terrasse & Garten DE
  PINTEREST_5_EMAIL / PINTEREST_5_PASSWORD   → Garten Gefühl

Usage :
  python main.py              # Exécution normale
  python main.py --dry-run    # Test sans poster
  python main.py --account 1  # Un seul compte (1-5)
"""

import os
import sys
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
    PINS_NO_LINK, PINS_WITH_LINK,
    DELAY_BETWEEN_PINS_MIN, DELAY_BETWEEN_PINS_MAX,
    DELAY_BETWEEN_ACCOUNTS_MIN, DELAY_BETWEEN_ACCOUNTS_MAX,
)
from playwright_poster import post_pin_with_retry, build_description
from state_manager import (
    load_state, save_state,
    get_next_board_name,
    is_pin_already_posted, mark_pin_as_posted,
    can_post_url_today, track_url_posted,
    record_daily_result,
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


# ── Collecte des ressources disponibles ───────────────────────

def get_published_articles(categorie: str) -> list:
    """
    Retourne tous les articles publiés dans une catégorie WP donnée.
    Triés du plus récent au plus ancien.
    Chaque article = {"url": str, "title": str, "date": str}
    """
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
                brief = data.get("brief", {})
                if brief.get("categorie_wp") != categorie:
                    continue
                publish = data.get("publish_result", {})
                url = publish.get("url")
                title = data.get("article", {}).get("seo_title", "")
                if url:
                    found.append({
                        "url": url,
                        "title": title,
                        "date": date_dir.name
                    })
            except Exception:
                continue

    return found


def get_pins_for_account(account_name: str, categorie: str, state: dict) -> list:
    """
    Retourne les pins disponibles (non encore postés depuis ce compte).
    Scanne tous les dossiers /data/pins/ par date décroissante.
    """
    pins_root = Path(PINS_DIR)
    if not pins_root.exists():
        return []

    account_slug = (
        account_name
        .replace(" ", "_")
        .replace("&", "und")
        .replace("ü", "u")
        .replace("Ü", "U")
    )

    available = []
    for date_dir in sorted(pins_root.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for pin_file in date_dir.glob(f"pin_*_{account_slug}.webp"):
            filename = pin_file.name
            if is_pin_already_posted(filename, account_name, state):
                continue
            article_url = _find_article_url(date_dir.name, categorie)
            available.append({
                "path": str(pin_file),
                "filename": filename,
                "article_url": article_url,
                "date": date_dir.name,
            })

    return available


def _find_article_url(date_str: str, categorie: str):
    """Trouve l'URL de l'article publié à cette date pour cette catégorie."""
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


# ── Logique principale par compte ─────────────────────────────

def run_account(account_idx: int, state: dict, dry_run: bool = False) -> dict:
    """
    Exécute les 5 pins pour un compte.
    Retourne un résumé {account, posted_no_link, posted_with_link, skipped, errors}.
    """
    cfg          = ACCOUNT_CONFIG[account_idx]
    account_name = cfg["name"]
    categorie    = cfg["categorie"]
    email        = os.getenv(cfg["email_env"], "")
    password     = os.getenv(cfg["password_env"], "")

    result = {
        "account":          account_name,
        "categorie":        categorie,
        "posted_no_link":   0,
        "posted_with_link": 0,
        "skipped":          0,
        "errors":           [],
    }

    print(f"\n{'─'*60}")
    print(f"[Distributeur] 📌 {account_name} (niche: {categorie})")
    print(f"{'─'*60}")

    if not email or not password:
        msg = f"Credentials manquants ({cfg['email_env']} / {cfg['password_env']})"
        print(f"[Distributeur] ❌ {msg}")
        result["errors"].append(msg)
        return result

    # ── Ressources disponibles ────────────────────────────────
    available_pins     = get_pins_for_account(account_name, categorie, state)
    published_articles = get_published_articles(categorie)

    print(f"[Distributeur] Pins disponibles : {len(available_pins)}")
    print(f"[Distributeur] Articles {categorie} publiés : {len(published_articles)}")

    # ── Plan : 3 avec lien + 2 sans lien ─────────────────────
    pins_with_link_target = PINS_WITH_LINK if published_articles else 0
    pins_no_link_target   = PINS_NO_LINK + (PINS_WITH_LINK - pins_with_link_target)

    print(f"[Distributeur] Plan : {pins_with_link_target} avec lien + {pins_no_link_target} sans lien")

    # File des articles (max 2 pins/URL/jour tous comptes confondus)
    article_queue = []
    for art in published_articles:
        if can_post_url_today(art["url"], state):
            article_queue.append(art)
        if len(article_queue) >= pins_with_link_target:
            break

    actual_with_link = len(article_queue)
    actual_no_link   = pins_no_link_target + (pins_with_link_target - actual_with_link)

    random.shuffle(available_pins)
    pin_pool   = available_pins.copy()
    pin_cursor = 0

    # ── Plan d'exécution ─────────────────────────────────────
    execution_plan = []

    for art in article_queue:
        if pin_cursor >= len(pin_pool):
            print(f"[Distributeur] ⚠️ Pins épuisés pour {account_name}")
            break
        pin   = pin_pool[pin_cursor]; pin_cursor += 1
        board = get_next_board_name(account_name, cfg["boards"], state)
        execution_plan.append({
            "pin":   pin,
            "link":  art["url"],
            "title": art["title"] or f"Garten Tipps – {categorie}",
            "board": board,
        })

    for _ in range(actual_no_link):
        if pin_cursor >= len(pin_pool):
            break
        pin   = pin_pool[pin_cursor]; pin_cursor += 1
        board = get_next_board_name(account_name, cfg["boards"], state)
        execution_plan.append({
            "pin":   pin,
            "link":  None,
            "title": f"Garten Inspiration – {categorie}",
            "board": board,
        })

    random.shuffle(execution_plan)
    print(f"[Distributeur] Plan final : {len(execution_plan)} pins à poster")

    # ── Exécution ─────────────────────────────────────────────
    for i, item in enumerate(execution_plan):
        pin   = item["pin"]
        link  = item["link"]
        board = item["board"]
        title = item["title"][:100]
        desc  = build_description(categorie, title)

        link_label = f"🔗 {link[:50]}..." if link else "🚫 sans lien"
        print(f"\n[Distributeur] Pin {i+1}/{len(execution_plan)} | {link_label}")
        print(f"[Distributeur] Image : {pin['filename']} | Board : {board}")

        if dry_run:
            print(f"[Distributeur] DRY RUN — simulé ✅")
            if link:
                result["posted_with_link"] += 1
            else:
                result["posted_no_link"] += 1
            continue

        if i > 0:
            delay = random.randint(DELAY_BETWEEN_PINS_MIN, DELAY_BETWEEN_PINS_MAX)
            print(f"[Distributeur] ⏱️ Anti-ban : {delay}s...")
            time.sleep(delay)

        post_result = post_pin_with_retry(
            account_name=account_name,
            email=email,
            password=password,
            image_path=pin["path"],
            title=title,
            description=desc,
            board_name=board,
            categorie=categorie,
            link=link,
            max_retries=3,
            headless=True,
        )

        if post_result["success"]:
            mark_pin_as_posted(pin["filename"], account_name, state)
            if link:
                track_url_posted(link, state)
                result["posted_with_link"] += 1
            else:
                result["posted_no_link"] += 1
            save_state(state)
        else:
            err = post_result.get("error", "erreur inconnue")
            result["errors"].append(f"Pin {i+1}: {err}")
            result["skipped"] += 1
            print(f"[Distributeur] ⚠️ Pin skippé : {err}")

    return result


# ── Orchestrateur ─────────────────────────────────────────────

def run(dry_run: bool = False, only_account: int = None):
    print("=" * 60)
    print(f"[Distributeur] 🚀 Démarrage — {datetime.now().isoformat()}")
    print(f"[Distributeur] Mode : {'DRY RUN' if dry_run else 'PRODUCTION'}")
    print("=" * 60)

    state   = load_state()
    indices = list(range(len(ACCOUNT_CONFIG)))

    if only_account is not None:
        indices = [only_account - 1]
    else:
        random.shuffle(indices)

    print(f"[Distributeur] Ordre : {[ACCOUNT_CONFIG[i]['name'] for i in indices]}")

    all_results = []
    for pos, idx in enumerate(indices):
        result = run_account(idx, state, dry_run)
        all_results.append(result)

        if pos < len(indices) - 1 and not dry_run:
            delay = random.randint(DELAY_BETWEEN_ACCOUNTS_MIN, DELAY_BETWEEN_ACCOUNTS_MAX)
            print(f"\n[Distributeur] ⏱️ Pause inter-compte : {delay}s...")
            time.sleep(delay)

    total_with = sum(r["posted_with_link"] for r in all_results)
    total_no   = sum(r["posted_no_link"]   for r in all_results)
    total_err  = sum(len(r["errors"])      for r in all_results)

    print(f"\n{'='*60}")
    print(f"[Distributeur] RÉSUMÉ")
    print(f"  🔗 Pins avec lien  : {total_with}")
    print(f"  📷 Pins sans lien  : {total_no}")
    print(f"  ❌ Erreurs         : {total_err}")
    for r in all_results:
        ok = "✅" if (r["posted_with_link"] + r["posted_no_link"]) > 0 else "⚠️"
        print(f"  {ok} {r['account']} : {r['posted_with_link']}🔗 + {r['posted_no_link']}📷")
    print(f"{'='*60}")

    if not dry_run:
        record_daily_result(state, all_results)
        save_state(state)

        lines = [f"📌 <b>Distributeur Pinterest</b> — {date.today().isoformat()}"]
        lines.append(f"🔗 Avec lien : <b>{total_with}</b> pins")
        lines.append(f"📷 Sans lien : <b>{total_no}</b> pins")
        lines.append("")
        for r in all_results:
            icon = "✅" if (r["posted_with_link"] + r["posted_no_link"]) > 0 else "⚠️"
            lines.append(f"{icon} {r['account']} : {r['posted_with_link']}🔗 + {r['posted_no_link']}📷")
        if total_err > 0:
            lines.append(f"\n⚠️ {total_err} erreur(s) — logs VPS")

        send_telegram("\n".join(lines))


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Distributeur Pinterest — Playwright")
    parser.add_argument("--dry-run", action="store_true", help="Test sans poster")
    parser.add_argument("--account", type=int, choices=range(1, 6),
                        help="Exécuter un seul compte (1=Blumenliebe … 5=Garten Gefühl)")
    args = parser.parse_args()

    run(dry_run=args.dry_run, only_account=args.account)
