"""
Distributeur Agent — State Manager

Gère l'état de chaque compte Pinterest :
- Date de première utilisation (pour calcul warm-up)
- Historique des pins postés (évite les doublons)
- Historique des URLs postées par jour (max 1 pin/URL/jour)
- Board actif en rotation
"""

import json
import os
from datetime import date, datetime
from pathlib import Path
from config import STATE_FILE, WARMUP_DAYS, ACCOUNT_CATEGORY_MAP


def load_state() -> dict:
    """Charge l'état depuis le fichier JSON."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Distributeur] Erreur chargement état: {e}")

    # État initial
    return {
        "accounts": {
            account: {
                "first_use_date": None,
                "posted_pins": [],        # Liste des noms de fichiers pins déjà postés
                "board_index": 0,         # Index du prochain board à utiliser
                "total_pins_posted": 0
            }
            for account in ACCOUNT_CATEGORY_MAP.keys()
        },
        "daily_url_tracking": {}  # {date: {url: count}}
    }


def save_state(state: dict):
    """Sauvegarde l'état dans le fichier JSON."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def is_warmup(account_name: str, state: dict) -> bool:
    """Retourne True si le compte est encore en phase de warm-up."""
    acc = state["accounts"].get(account_name, {})
    first_use = acc.get("first_use_date")

    if not first_use:
        return True  # Jamais utilisé = warm-up

    try:
        first_date = date.fromisoformat(first_use)
        days_active = (date.today() - first_date).days
        return days_active < WARMUP_DAYS
    except:
        return True


def mark_first_use(account_name: str, state: dict):
    """Marque la première utilisation d'un compte (début warm-up)."""
    acc = state["accounts"].setdefault(account_name, {
        "first_use_date": None,
        "posted_pins": [],
        "board_index": 0,
        "total_pins_posted": 0
    })
    if not acc.get("first_use_date"):
        acc["first_use_date"] = date.today().isoformat()
        print(f"[Distributeur] 🆕 {account_name} — warm-up démarré")


def get_next_board(account_name: str, boards: list, state: dict) -> str:
    """
    Rotation des boards : retourne le prochain board_id à utiliser.
    Incrémente l'index pour le prochain appel.
    """
    if not boards:
        return None

    acc = state["accounts"].get(account_name, {})
    idx = acc.get("board_index", 0) % len(boards)
    board_id = boards[idx]

    # Incrémenter pour le prochain pin
    acc["board_index"] = (idx + 1) % len(boards)
    state["accounts"][account_name] = acc

    return board_id


def is_pin_already_posted(pin_filename: str, account_name: str, state: dict) -> bool:
    """Vérifie si un pin a déjà été posté depuis ce compte."""
    acc = state["accounts"].get(account_name, {})
    return pin_filename in acc.get("posted_pins", [])


def mark_pin_as_posted(pin_filename: str, account_name: str, state: dict):
    """Marque un pin comme posté pour ce compte."""
    acc = state["accounts"].setdefault(account_name, {
        "first_use_date": None, "posted_pins": [], "board_index": 0, "total_pins_posted": 0
    })
    if pin_filename not in acc.get("posted_pins", []):
        acc.setdefault("posted_pins", []).append(pin_filename)
        acc["total_pins_posted"] = acc.get("total_pins_posted", 0) + 1


def can_post_url_today(url: str, state: dict, max_per_day: int = 1) -> bool:
    """
    Vérifie si une URL peut encore être postée aujourd'hui.
    Règle : max 1 pin/URL/jour (toutes comptes confondus).
    """
    if not url:
        return True  # Pin sans lien → toujours autorisé

    today = date.today().isoformat()
    daily = state.setdefault("daily_url_tracking", {})
    today_urls = daily.get(today, {})
    count = today_urls.get(url, 0)
    return count < max_per_day


def track_url_posted(url: str, state: dict):
    """Enregistre qu'une URL a été postée aujourd'hui."""
    if not url:
        return

    today = date.today().isoformat()
    daily = state.setdefault("daily_url_tracking", {})
    today_urls = daily.setdefault(today, {})
    today_urls[url] = today_urls.get(url, 0) + 1

    # Nettoyer les dates > 7 jours
    to_delete = [d for d in daily if d < date.today().replace(day=max(1, date.today().day - 7)).isoformat()]
    for d in to_delete:
        del daily[d]


def get_warmup_days_remaining(account_name: str, state: dict) -> int:
    """Retourne le nombre de jours de warm-up restants (0 si terminé)."""
    acc = state["accounts"].get(account_name, {})
    first_use = acc.get("first_use_date")
    if not first_use:
        return WARMUP_DAYS

    try:
        first_date = date.fromisoformat(first_use)
        days_active = (date.today() - first_date).days
        return max(0, WARMUP_DAYS - days_active)
    except:
        return WARMUP_DAYS
