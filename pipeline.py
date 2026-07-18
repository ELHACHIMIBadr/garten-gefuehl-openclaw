"""
Pipeline Orchestrateur — Garten Gefühl OpenClaw

Enchaîne tous les agents dans l'ordre :
  Scout → Rédacteur → Correcteur → Directeur Artistique → Publisher

Conçu pour être appelé 2x/jour par cron.
Rotation automatique sur 5 catégories (chaque exécution = catégorie suivante).

Usage :
    python pipeline.py                # Exécution normale (catégorie auto)
    python pipeline.py --slot 0       # Forcer slot 0 (matin) ou 1 (après-midi)
    python pipeline.py --category 2   # Forcer une catégorie (0-4)
    python pipeline.py --dry-run      # Test sans publier

Cron recommandé (2 articles/jour) :
    0  6 * * * cd /root/garten-gefuehl-openclaw && /usr/bin/python3 pipeline.py --slot 0 >> /var/log/openclaw-am.log 2>&1
    0 14 * * * cd /root/garten-gefuehl-openclaw && /usr/bin/python3 pipeline.py --slot 1 >> /var/log/openclaw-pm.log 2>&1
"""

import os
import sys
import json
import subprocess
import argparse
import traceback
from datetime import date, datetime
from pathlib import Path

# ── Config ──
PROJECT_ROOT = "/root/garten-gefuehl-openclaw"
AGENTS_DIR = f"{PROJECT_ROOT}/agents"
PYTHON = "/usr/bin/python3"
CATEGORIES_COUNT = 5

# Telegram notification (réutilise le module existant)
sys.path.insert(0, f"{AGENTS_DIR}/scout")
try:
    from telegram_notify import send_telegram
except ImportError:
    def send_telegram(msg):
        print(f"[TG] {msg}")


def get_category_index(slot: int) -> int:
    """
    Rotation 2 articles/jour sur 5 catégories.

    Logique :
    - Chaque jour a 2 slots (0=matin, 1=après-midi)
    - Index global = (jour_de_l_année * 2) + slot
    - Catégorie = index global % 5

    Cycle complet en 2.5 jours :
      Jour 1 matin  → cat 0 (Blumen/fleurs)
      Jour 1 après  → cat 1 (Balkon/balcon)
      Jour 2 matin  → cat 2 (Rosen/roses)
      Jour 2 après  → cat 3 (Terrasse)
      Jour 3 matin  → cat 4 (Garten Gefühl)
      Jour 3 après  → cat 0 (Blumen/fleurs) ← retour au début
    """
    day_of_year = date.today().timetuple().tm_yday
    global_index = (day_of_year * 2) + slot
    return global_index % CATEGORIES_COUNT


def run_agent(agent_name: str, extra_args: list = None) -> bool:
    """Lance un agent et retourne True si succès."""
    agent_dir = os.path.join(AGENTS_DIR, agent_name)
    main_py = os.path.join(agent_dir, "main.py")

    if not os.path.exists(main_py):
        print(f"[PIPELINE] ❌ Agent introuvable : {main_py}")
        return False

    cmd = [PYTHON, main_py] + (extra_args or [])
    print(f"\n{'─' * 60}")
    print(f"[PIPELINE] ▶ {agent_name.upper()} — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'─' * 60}")

    try:
        result = subprocess.run(
            cmd,
            cwd=agent_dir,
            capture_output=False,  # Afficher en temps réel dans les logs
            timeout=600,           # 10 min max par agent
        )
        if result.returncode == 0:
            print(f"[PIPELINE] ✅ {agent_name.upper()} — terminé")
            return True
        else:
            print(f"[PIPELINE] ❌ {agent_name.upper()} — code retour {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        print(f"[PIPELINE] ❌ {agent_name.upper()} — timeout 600s")
        return False
    except Exception as e:
        print(f"[PIPELINE] ❌ {agent_name.upper()} — erreur : {e}")
        return False


def run_pipeline(slot: int = 0, category_override: int = None, dry_run: bool = False):
    """Exécute le pipeline complet pour un slot."""
    start = datetime.now()

    cat_index = category_override if category_override is not None else get_category_index(slot)
    slot_label = "MATIN" if slot == 0 else "APRÈS-MIDI"

    print("=" * 60)
    print(f"[PIPELINE] 🚀 Démarrage — {start.isoformat()}")
    print(f"[PIPELINE] Slot : {slot_label} | Catégorie index : {cat_index}")
    print("=" * 60)

    dry_flag = ["--dry-run"] if dry_run else []

    # ── 1. SCOUT — recherche keyword + génère brief ──
    scout_ok = run_agent("scout", ["--category", str(cat_index)] + dry_flag)
    if not scout_ok:
        msg = f"❌ Pipeline {slot_label} échoué à l'étape SCOUT (cat {cat_index})"
        print(f"[PIPELINE] {msg}")
        send_telegram(msg)
        return False

    # ── 2. RÉDACTEUR — écrit l'article ──
    redacteur_ok = run_agent("redacteur", dry_flag)
    if not redacteur_ok:
        msg = f"❌ Pipeline {slot_label} échoué à l'étape RÉDACTEUR"
        print(f"[PIPELINE] {msg}")
        send_telegram(msg)
        return False

    # ── 3. CORRECTEUR — vérifie SEO + qualité ──
    correcteur_ok = run_agent("correcteur", dry_flag)
    if not correcteur_ok:
        msg = f"❌ Pipeline {slot_label} échoué à l'étape CORRECTEUR"
        print(f"[PIPELINE] {msg}")
        send_telegram(msg)
        return False

    # ── 4. DIRECTEUR ARTISTIQUE — images + pins ──
    da_ok = run_agent("directeur-artistique", dry_flag)
    if not da_ok:
        msg = f"⚠️ Pipeline {slot_label} — DA échoué, publication sans images"
        print(f"[PIPELINE] {msg}")
        send_telegram(msg)
        # On continue quand même — mieux publier sans images que ne pas publier

    # ── 5. PUBLISHER — publie sur WordPress ──
    if not dry_run:
        publisher_ok = run_agent("publisher")
        if not publisher_ok:
            msg = f"❌ Pipeline {slot_label} échoué à l'étape PUBLISHER"
            print(f"[PIPELINE] {msg}")
            send_telegram(msg)
            return False
    else:
        print(f"[PIPELINE] DRY RUN — publication WordPress ignorée")

    # ── Résultat ──
    elapsed = (datetime.now() - start).total_seconds()
    msg = (
        f"✅ Pipeline {slot_label} terminé en {elapsed:.0f}s\n"
        f"Catégorie : {cat_index} | Date : {date.today().isoformat()}"
    )
    print(f"\n{'=' * 60}")
    print(f"[PIPELINE] {msg}")
    print(f"{'=' * 60}")

    if not dry_run:
        send_telegram(msg)

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline OpenClaw — Garten Gefühl")
    parser.add_argument("--slot", type=int, default=0, choices=[0, 1],
                        help="Slot horaire : 0=matin, 1=après-midi")
    parser.add_argument("--category", type=int, default=None, choices=range(5),
                        help="Forcer une catégorie (0-4)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Test complet sans publier")
    args = parser.parse_args()

    success = run_pipeline(
        slot=args.slot,
        category_override=args.category,
        dry_run=args.dry_run,
    )
    sys.exit(0 if success else 1)
