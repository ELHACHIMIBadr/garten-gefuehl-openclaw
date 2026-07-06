"""
Distributeur Agent — State Manager (Playwright)

État persistant par compte :
  - Pins déjà postés (évite doublons)
  - Rotation des boards (round-robin)
  - Tracking URLs postées par jour (évite de poster le même lien 2x/jour)
  - Historique journalier pour rapports
"""

import json
import os
from datetime import date
from pathlib import Path
from config import STATE_FILE, ACCOUNT_CONFIG


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[State] Erreur chargement: {e}")

    return _initial_state()


def _initial_state() -> dict:
    return {
        "accounts": {
            cfg["name"]: {
                "posted_pins":  [],   # Noms de fichiers déjà postés depuis ce compte
                "board_index":  0,    # Index rotation boards
                "total_posted": 0,
            }
            for cfg in ACCOUNT_CONFIG
        },
        "daily_url_tracking": {},     # {date_iso: {url: count}}
        "daily_results":      {},     # {date_iso: [...résultats]}
    }


def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ── Boards ───────────────────────────────────────────────────

def get_next_board_name(account_name: str, boards: list, state: dict) -> str:
    """Rotation round-robin sur la liste des boards."""
    if not boards:
        return ""
    acc = state["accounts"].setdefault(account_name, {
        "posted_pins": [], "board_index": 0, "total_posted": 0
    })
    idx = acc.get("board_index", 0) % len(boards)
    board = boards[idx]
    acc["board_index"] = (idx + 1) % len(boards)
    return board


# ── Déduplication pins ───────────────────────────────────────

def is_pin_already_posted(pin_filename: str, account_name: str, state: dict) -> bool:
    acc = state["accounts"].get(account_name, {})
    return pin_filename in acc.get("posted_pins", [])


def mark_pin_as_posted(pin_filename: str, account_name: str, state: dict):
    acc = state["accounts"].setdefault(account_name, {
        "posted_pins": [], "board_index": 0, "total_posted": 0
    })
    posted = acc.setdefault("posted_pins", [])
    if pin_filename not in posted:
        posted.append(pin_filename)
        acc["total_posted"] = acc.get("total_posted", 0) + 1


# ── Tracking URLs journalier ─────────────────────────────────

def can_post_url_today(url: str, state: dict, max_per_day: int = 2) -> bool:
    """
    Max 2 pins/URL/jour (tous comptes confondus).
    Permet de poster le même article sur 2 comptes différents max.
    """
    if not url:
        return True
    today = date.today().isoformat()
    daily = state.setdefault("daily_url_tracking", {})
    count = daily.get(today, {}).get(url, 0)
    return count < max_per_day


def track_url_posted(url: str, state: dict):
    if not url:
        return
    today = date.today().isoformat()
    daily = state.setdefault("daily_url_tracking", {})
    today_urls = daily.setdefault(today, {})
    today_urls[url] = today_urls.get(url, 0) + 1

    # Nettoyer les entrées > 7 jours
    cutoff = date.today().replace(day=max(1, date.today().day - 7)).isoformat()
    for d in list(daily.keys()):
        if d < cutoff:
            del daily[d]


# ── Historique journalier ─────────────────────────────────────

def record_daily_result(state: dict, results: list):
    today = date.today().isoformat()
    state.setdefault("daily_results", {})[today] = [
        {
            "account":          r["account"],
            "posted_with_link": r["posted_with_link"],
            "posted_no_link":   r["posted_no_link"],
            "skipped":          r["skipped"],
            "errors":           r["errors"],
        }
        for r in results
    ]
