#!/bin/bash
# Installation playwright-stealth sur le VPS Hetzner
# Usage : bash agents/distributeur/install_stealth.sh

echo "=== Installation playwright-stealth ==="
pip install playwright-stealth --break-system-packages

echo ""
echo "=== Vérification ==="
python3 -c "from playwright_stealth import Stealth; print('✅ playwright-stealth OK')"

echo ""
echo "=== Création répertoires profils Chrome ==="
mkdir -p /root/garten-gefuehl-openclaw/data/pinterest_profiles
mkdir -p /root/garten-gefuehl-openclaw/data/pinterest_sessions
echo "✅ Répertoires créés"

echo ""
echo "=== Terminé — tu peux tester avec --dry-run ==="
