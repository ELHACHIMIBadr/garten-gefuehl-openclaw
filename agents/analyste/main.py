"""
Analyste + Stratège Agent — Main
Collecte les données de performance et génère des rapports Telegram.

RAPPORTS PRODUITS :
1. Rapport quotidien (chaque nuit à 23:30) : GA4 + Search Console + Pinterest KPIs
2. Rapport hebdomadaire (lundi à 23:30) : tendances + recommandations stratégiques

PRÉREQUIS :
- Service account Google configuré (voir config.py pour les instructions)
- Tokens Pinterest dans .env (réutilisés depuis le Distributeur)

Usage:
  python main.py                    # Rapport quotidien
  python main.py --weekly           # Forcer le rapport hebdomadaire
  python main.py --dry-run          # Test sans envoyer sur Telegram

Cron :
  30 23 * * * cd /root/garten-gefuehl-openclaw/agents/analyste && /usr/bin/python3 main.py
  30 23 * * 0 cd /root/garten-gefuehl-openclaw/agents/analyste && /usr/bin/python3 main.py --weekly
"""

import os
import sys
import json
import argparse
import requests
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv("/root/garten-gefuehl-openclaw/config/.env")

from config import WEEKLY_REPORT_DAY, ANALYTICS_DIR
from ga4_collector import collect_daily_metrics as ga4_daily, collect_weekly_metrics as ga4_weekly
from search_console_collector import collect_daily_metrics as sc_daily, collect_weekly_metrics as sc_weekly
from pinterest_collector import collect_all_accounts_metrics
from report_builder import (
    build_daily_telegram_report,
    build_weekly_telegram_report,
    save_report
)


def send_telegram(msg: str, split_at: int = 4096):
    """
    Envoie un message Telegram.
    Telegram limite les messages à 4096 chars → découpe si nécessaire.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    cid = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not cid:
        print("[Analyste] ⚠️ Telegram non configuré")
        return

    # Découper si nécessaire
    chunks = [msg[i:i+split_at] for i in range(0, len(msg), split_at)]

    for chunk in chunks:
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": cid, "text": chunk, "parse_mode": "HTML"},
                timeout=10
            )
            if resp.status_code != 200:
                print(f"[Analyste] Telegram erreur: {resp.status_code}")
        except Exception as e:
            print(f"[Analyste] Telegram exception: {e}")


def count_published_articles() -> int:
    """Compte le nombre total d'articles publiés (statut 'published' dans les JSONs)."""
    count = 0
    articles_root = Path("/root/garten-gefuehl-openclaw/data/articles")
    if not articles_root.exists():
        return 0

    for article_file in articles_root.rglob("article_*.json"):
        try:
            with open(article_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("status") == "published":
                count += 1
        except:
            continue
    return count


def save_analytics_snapshot(ga4: dict, sc: dict, pinterest: dict):
    """Sauvegarde un snapshot des données analytics du jour."""
    os.makedirs(ANALYTICS_DIR, exist_ok=True)
    today = date.today().isoformat()
    filepath = Path(ANALYTICS_DIR) / f"{today}_snapshot.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "date": today,
            "generated_at": datetime.now().isoformat(),
            "ga4": ga4,
            "search_console": sc,
            "pinterest": pinterest
        }, f, ensure_ascii=False, indent=2)

    print(f"[Analyste] Snapshot sauvegardé : {filepath}")


def run_daily(dry_run: bool = False):
    """Exécution du rapport quotidien."""
    print("=" * 60)
    print(f"[Analyste] Rapport quotidien — {datetime.now().isoformat()}")
    print("=" * 60)

    # Collecter les données
    print("\n[Analyste] Collecte GA4...")
    ga4 = ga4_daily(days_ago=1)

    print("\n[Analyste] Collecte Search Console...")
    sc = sc_daily(days_ago=3)  # SC a 2-3j de délai

    print("\n[Analyste] Collecte Pinterest Analytics...")
    pinterest = collect_all_accounts_metrics(days_ago=2)

    # Compter les articles
    articles_count = count_published_articles()
    print(f"[Analyste] Articles publiés: {articles_count}")

    # Sauvegarder le snapshot
    save_analytics_snapshot(ga4, sc, pinterest)

    # Construire le rapport
    report = build_daily_telegram_report(ga4, sc, pinterest, articles_count)

    # Afficher en console
    print("\n" + "=" * 60)
    print("RAPPORT QUOTIDIEN:")
    print("=" * 60)
    print(report)
    print("=" * 60)

    # Envoyer sur Telegram
    if not dry_run:
        send_telegram(report)
        print("[Analyste] ✅ Rapport envoyé sur Telegram")
    else:
        print("[Analyste] DRY RUN — Rapport non envoyé")

    # Sauvegarder
    save_report("daily", {
        "ga4": ga4,
        "search_console": sc,
        "pinterest": pinterest,
        "articles_count": articles_count
    })


def run_weekly(dry_run: bool = False):
    """Exécution du rapport hebdomadaire stratégique."""
    print("=" * 60)
    print(f"[Analyste] Rapport hebdomadaire — {datetime.now().isoformat()}")
    print("=" * 60)

    # Collecter les données hebdomadaires
    print("\n[Analyste] Collecte GA4 hebdo...")
    ga4_w = ga4_weekly()

    print("\n[Analyste] Collecte Search Console hebdo...")
    sc_w = sc_weekly()

    # Construire le rapport hebdomadaire
    report = build_weekly_telegram_report(ga4_w, sc_w)

    print("\n" + "=" * 60)
    print("RAPPORT HEBDOMADAIRE:")
    print("=" * 60)
    print(report)
    print("=" * 60)

    if not dry_run:
        send_telegram(report)
        print("[Analyste] ✅ Rapport hebdo envoyé sur Telegram")
    else:
        print("[Analyste] DRY RUN — Rapport non envoyé")

    save_report("weekly", {
        "ga4_weekly": ga4_w,
        "search_console_weekly": sc_w
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyste Agent — Garten Gefühl")
    parser.add_argument("--weekly", action="store_true", help="Forcer le rapport hebdomadaire")
    parser.add_argument("--dry-run", action="store_true", help="Test sans envoyer Telegram")
    args = parser.parse_args()

    if args.weekly:
        run_weekly(dry_run=args.dry_run)
    else:
        # Rapport quotidien toujours + hebdomadaire automatiquement le lundi
        run_daily(dry_run=args.dry_run)
        if date.today().weekday() == WEEKLY_REPORT_DAY and not args.dry_run:
            print("\n[Analyste] Lundi → ajout du rapport stratégique hebdomadaire")
            run_weekly(dry_run=False)
