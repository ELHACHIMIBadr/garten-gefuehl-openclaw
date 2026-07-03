"""
Correcteur Agent — Main
Vérifie l'article du Rédacteur sur 25 points SEO + plagiat + qualité allemande.
Corrige via GPT si nécessaire (max 2 allers-retours).
Approuve ou rejette l'article.

Usage:
    python main.py                              # Prend le dernier article non validé
    python main.py --article path/to/article.json
    python main.py --dry-run

Cron (après Rédacteur):
    0 7 * * * cd /root/garten-gefuehl-openclaw/agents/correcteur && /usr/bin/python3 main.py
"""

import os
import json
import argparse
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv("/root/garten-gefuehl-openclaw/config/.env")

from config import ARTICLES_DIR, MAX_RETRIES
from seo_checker import check_all_seo_rules, check_ai_detection, check_german_quality
from plagiat_checker import check_plagiat
from gpt_fixer import fix_article_with_gpt
from sys import path as syspath
syspath.insert(0, "/root/garten-gefuehl-openclaw/agents/redacteur")
from parser import parse_gpt_output


def get_latest_article() -> tuple:
    """Trouve le dernier article avec status 'pending_review'."""
    today = date.today().isoformat()
    article_dir = Path(ARTICLES_DIR) / today

    if not article_dir.exists():
        all_dirs = sorted(Path(ARTICLES_DIR).iterdir(), reverse=True)
        if not all_dirs:
            raise FileNotFoundError("Aucun article trouvé")
        article_dir = all_dirs[0]

    for filepath in sorted(article_dir.glob("article_*.json")):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("status") == "pending_review":
            return filepath, data

    raise FileNotFoundError("Aucun article en attente de vérification")


def save_article(filepath: Path, data: dict, dry_run: bool = False):
    """Met à jour le fichier article."""
    if not dry_run:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[Correcteur] Article mis à jour : {filepath}")


def send_telegram(message: str):
    import requests
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10
            )
        except Exception as e:
            print(f"[Correcteur] Erreur Telegram: {e}")


def print_seo_report(seo_result: dict):
    """Affiche le rapport SEO complet."""
    print(f"\n{'='*50}")
    print(f"RAPPORT SEO — {seo_result['score']}/{seo_result['total']} points")
    print(f"{'='*50}")

    if seo_result["errors"]:
        print(f"\n🔴 ERREURS ({len(seo_result['errors'])}) :")
        for e in seo_result["errors"]:
            print(f"  {e}")

    if seo_result["warnings"]:
        print(f"\n🟡 AVERTISSEMENTS ({len(seo_result['warnings'])}) :")
        for w in seo_result["warnings"]:
            print(f"  {w}")

    if seo_result["passed"]:
        print(f"\n🟢 VALIDÉ ({len(seo_result['passed'])}) :")
        for p in seo_result["passed"]:
            print(f"  {p}")

    print(f"{'='*50}\n")


def run(article_path: str = None, dry_run: bool = False):
    """Exécution principale du Correcteur."""
    print("=" * 60)
    print(f"[Correcteur] Démarrage — {datetime.now().isoformat()}")
    print("=" * 60)

    try:
        # ÉTAPE 1 — Charger l'article
        if article_path:
            filepath = Path(article_path)
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            filepath, data = get_latest_article()

        article = data["article"]
        brief = data["brief"]
        keyword = brief["keyword_principal"]

        print(f"[Correcteur] Article : {filepath.name}")
        print(f"[Correcteur] Keyword : {keyword}")

        attempt = 0
        final_status = "rejected"

        while attempt < MAX_RETRIES:
            attempt += 1
            print(f"\n[Correcteur] === Vérification — Tentative {attempt}/{MAX_RETRIES} ===")

            # ÉTAPE 2 — Vérification SEO complète (25 points)
            print(f"\n[Correcteur] ÉTAPE 2 — Vérification SEO (25 points)...")
            seo_result = check_all_seo_rules(article, brief)
            print_seo_report(seo_result)

            # ÉTAPE 3 — Détection IA
            print(f"[Correcteur] ÉTAPE 3 — Détection IA...")
            ai_issues = check_ai_detection(article.get("html_content", ""))
            if ai_issues:
                print(f"  ⚠️ Phrases IA détectées : {ai_issues}")
            else:
                print(f"  ✅ Aucune phrase IA détectée")

            # ÉTAPE 4 — Qualité allemande
            print(f"[Correcteur] ÉTAPE 4 — Qualité allemande...")
            german_issues = check_german_quality(article.get("html_content", ""))
            if german_issues:
                print(f"  ⚠️ {german_issues}")
            else:
                print(f"  ✅ Qualité allemande OK")

            # ÉTAPE 5 — Vérification plagiat
            print(f"[Correcteur] ÉTAPE 5 — Vérification plagiat...")
            plagiat_result = check_plagiat(article.get("html_content", ""))
            unique_pct = plagiat_result.get("unique_pct", 100)
            print(f"  Unicité : {unique_pct}%")
            if unique_pct < 80:
                seo_result["errors"].append(f"❌ Plagiat détecté — unicité {unique_pct}% (min 80%)")

            # DÉCISION
            blocking_errors = seo_result["errors"] + [f"❌ {i}" for i in ai_issues]

            if not blocking_errors:
                # ✅ APPROUVÉ
                final_status = "approved"
                print(f"\n[Correcteur] ✅ Article APPROUVÉ")
                break
            else:
                print(f"\n[Correcteur] ⚠️ {len(blocking_errors)} erreur(s) bloquante(s)")

                if attempt < MAX_RETRIES:
                    # Correction via GPT
                    print(f"[Correcteur] 🔄 Correction via GPT (tentative {attempt})...")
                    raw_fixed = fix_article_with_gpt(
                        article,
                        seo_result["errors"],
                        seo_result["warnings"],
                        brief
                    )

                    # Parser l'article corrigé
                    fixed_data = parse_gpt_output(raw_fixed)
                    if not fixed_data["parse_errors"]:
                        article.update(fixed_data)
                        data["article"] = article
                        print(f"[Correcteur] Article corrigé, nouvelle vérification...")
                    else:
                        print(f"[Correcteur] ❌ Parsing de la correction échoué")
                        break
                else:
                    # Max retries atteint
                    final_status = "rejected"
                    print(f"\n[Correcteur] ❌ Article REJETÉ après {MAX_RETRIES} tentatives")

        # Mise à jour du statut
        data["status"] = final_status
        data["correcteur_report"] = {
            "checked_at": datetime.now().isoformat(),
            "attempts": attempt,
            "seo_score": seo_result["score"],
            "seo_total": seo_result["total"],
            "errors": seo_result["errors"],
            "warnings": seo_result["warnings"],
            "ai_issues": ai_issues,
            "plagiat_unique_pct": unique_pct
        }

        save_article(filepath, data, dry_run)

        # Rapport final
        emoji = "✅" if final_status == "approved" else "❌"
        summary = (
            f"{emoji} <b>Correcteur — Article {final_status.upper()}</b>\n\n"
            f"🔑 Keyword : {keyword}\n"
            f"📊 Score SEO : {seo_result['score']}/{seo_result['total']}\n"
            f"🔴 Erreurs : {len(seo_result['errors'])}\n"
            f"🟡 Avertissements : {len(seo_result['warnings'])}\n"
            f"🤖 Phrases IA : {len(ai_issues)}\n"
            f"📋 Plagiat : {unique_pct}% unique\n"
            f"🔄 Tentatives : {attempt}/{MAX_RETRIES}"
        )

        print(f"\n[Correcteur] {emoji} Statut final : {final_status.upper()}")

        if not dry_run:
            send_telegram(summary)

    except Exception as e:
        error_msg = f"❌ Erreur Correcteur : {str(e)}"
        print(f"[Correcteur] {error_msg}")
        send_telegram(f"❌ <b>Correcteur — Erreur</b>\n\n{str(e)}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Correcteur Agent — Garten Gefühl")
    parser.add_argument("--article", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run(article_path=args.article, dry_run=args.dry_run)
