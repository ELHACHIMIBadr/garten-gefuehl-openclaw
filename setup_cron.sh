#!/bin/bash
# ============================================================
# Setup cron pour le pipeline OpenClaw — 2 articles/jour
#
# Exécuter une seule fois sur le VPS :
#   bash setup_cron.sh
#
# Résultat :
#   06:00 → pipeline.py --slot 0  (article matin)
#   14:00 → pipeline.py --slot 1  (article après-midi)
#
# Rotation : 5 catégories, cycle complet en 2.5 jours
#   Jour 1 : Blumen (fleurs) + Balkon (balcon)
#   Jour 2 : Rosen (roses) + Terrasse
#   Jour 3 : Garten Gefühl + Blumen...
#
# Logs : /var/log/openclaw-am.log et /var/log/openclaw-pm.log
# ============================================================

set -e

PROJECT="/root/garten-gefuehl-openclaw"
PYTHON="/usr/bin/python3"
LOG_AM="/var/log/openclaw-am.log"
LOG_PM="/var/log/openclaw-pm.log"

# Créer les fichiers de log
touch "$LOG_AM" "$LOG_PM"

# Sauvegarder le cron existant
crontab -l > /tmp/cron_backup_$(date +%Y%m%d).txt 2>/dev/null || true

# Construire le nouveau cron (sans supprimer les jobs existants non-openclaw)
(
    # Garder les jobs existants qui ne sont PAS openclaw
    crontab -l 2>/dev/null | grep -v "pipeline.py" | grep -v "openclaw" || true

    # Ajouter les 2 jobs pipeline
    echo ""
    echo "# === OpenClaw Pipeline — 2 articles/jour ==="
    echo "0  6 * * * cd $PROJECT && $PYTHON pipeline.py --slot 0 >> $LOG_AM 2>&1"
    echo "0 14 * * * cd $PROJECT && $PYTHON pipeline.py --slot 1 >> $LOG_PM 2>&1"
    echo "# === Fin OpenClaw ==="
) | crontab -

echo "✅ Cron installé :"
crontab -l | grep -A2 "OpenClaw"

echo ""
echo "Pour tester maintenant (dry-run) :"
echo "  cd $PROJECT && python3 pipeline.py --slot 0 --dry-run"
echo ""
echo "Logs :"
echo "  tail -f $LOG_AM    # matin"
echo "  tail -f $LOG_PM    # après-midi"
