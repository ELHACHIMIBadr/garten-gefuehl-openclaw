"""
Distributeur Agent — State Manager (Playwright)

CHANGELOG v2 (Fix permanent déduplication pins):
- posted_pins stocke désormais "YYYY-MM-DD::filename" au lieu de juste "filename"
- is_pin_already_posted vérifie uniquement les pins de la même date
- Migration automatique des anciens formats (filename seul → ignorés)
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
                "posted_pins":  [],
                "board_index":  0,
                "total_posted": 0,
            }
            for cfg in ACCOUNT_CONFIG
        },
        "daily_url_tracking": {},
        "daily_results":      {},
        "daily_plan":         {},
        "daily_pin_counts":   {},
    }


def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ── Boards ───────────────────────────────────────────────────

def get_next_board_name(account_name: str, boards: list, state: dict) -> str:
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

def _pin_key(pin_filename: str, for_date: str = None) -> str:
    """Clé unique : YYYY-MM-DD::filename"""
    d = for_date or date.today().isoformat()
    return f"{d}::{pin_filename}"


def is_pin_already_posted(pin_filename: str, account_name: str, state: dict) -> bool:
    """Vérifie uniquement les pins de la date du jour."""
    acc = state["accounts"].get(account_name, {})
    today_key = _pin_key(pin_filename)
    return today_key in acc.get("posted_pins", [])


def mark_pin_as_posted(pin_filename: str, account_name: str, state: dict):
    """Enregistre le pin avec sa date pour éviter les collisions inter-jours."""
    acc = state["accounts"].setdefault(account_name, {
        "posted_pins": [], "board_index": 0, "total_posted": 0
    })
    posted = acc.setdefault("posted_pins", [])
    key = _pin_key(pin_filename)
    if key not in posted:
        posted.append(key)
        acc["total_posted"] = acc.get("total_posted", 0) + 1
    # Garder max 60 jours d'historique (5 pins/jour × 60 = 300 entrées max)
    if len(posted) > 300:
        posted[:] = posted[-300:]


# ── Tracking URLs journalier ─────────────────────────────────

def can_post_url_today(url: str, state: dict, max_per_day: int = 2) -> bool:
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
    cutoff = date.today().replace(day=max(1, date.today().day - 7)).isoformat()
    for d in list(daily.keys()):
        if d < cutoff:
            del daily[d]


# ── Compteurs journaliers par compte ─────────────────────────

def get_daily_pin_count(account_name: str, state: dict) -> int:
    today = date.today().isoformat()
    return state.setdefault("daily_pin_counts", {}).get(today, {}).get(account_name, 0)


def increment_daily_pin_count(account_name: str, state: dict):
    today = date.today().isoformat()
    counts = state.setdefault("daily_pin_counts", {})
    today_counts = counts.setdefault(today, {})
    today_counts[account_name] = today_counts.get(account_name, 0) + 1


# ── Historique journalier ─────────────────────────────────────

def record_daily_result(state: dict, results: list):
    today = date.today().isoformat()
    state.setdefault("daily_results", {})[today] = results
