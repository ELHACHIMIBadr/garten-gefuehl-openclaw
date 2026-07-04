"""
Analyste Agent — Configuration

PRÉREQUIS :
Les APIs Google nécessitent un Service Account JSON avec les rôles suivants :
  - Google Analytics 4 : "Lecteur" sur la propriété GA4
  - Search Console : "Propriétaire délégué" ou "Lecteur" sur le site

ÉTAPES DE CONFIGURATION :
1. Google Cloud Console → APIs & Services → Créer un projet (ou réutiliser existant)
2. Activer : Google Analytics Data API + Google Search Console API
3. IAM & Admin → Comptes de service → Créer → Télécharger JSON de clé
4. GA4 Admin → Gestion des accès → Ajouter le service account email (lecteur)
5. Search Console → Paramètres → Utilisateurs et autorisations → Ajouter service account email
6. Copier le JSON sur le VPS : /root/garten-gefuehl-openclaw/config/google-service-account.json
7. Ajouter dans .env :
     GA4_PROPERTY_ID=123456789       # Trouvé dans GA4 → Admin → Propriété → ID de propriété
     SEARCH_CONSOLE_SITE=https://xn--garten-gefhl-mlb.de/
     GOOGLE_SERVICE_ACCOUNT_JSON=/root/garten-gefuehl-openclaw/config/google-service-account.json

Pour Pinterest Analytics, les access tokens des comptes sont réutilisés depuis .env :
  PINTEREST_TOKEN_BLUMENLIEBE, PINTEREST_TOKEN_BALKON, etc.
"""

import os

# Chemins
DATA_DIR = "/root/garten-gefuehl-openclaw/data"
ANALYTICS_DIR = f"{DATA_DIR}/analytics"
REPORTS_DIR = f"{DATA_DIR}/reports"

# Google
GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "")
SEARCH_CONSOLE_SITE = os.getenv("SEARCH_CONSOLE_SITE", "https://xn--garten-gefhl-mlb.de/")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "/root/garten-gefuehl-openclaw/config/google-service-account.json"
)

# Pinterest (5 comptes)
PINTEREST_ACCOUNTS_TOKENS = {
    "Blumenliebe DE":       os.getenv("PINTEREST_TOKEN_BLUMENLIEBE", ""),
    "Balkon Ideen DE":      os.getenv("PINTEREST_TOKEN_BALKON", ""),
    "Rosenfreude DE":       os.getenv("PINTEREST_TOKEN_ROSEN", ""),
    "Terrasse & Garten DE": os.getenv("PINTEREST_TOKEN_TERRASSE", ""),
    "Garten Gefühl":        os.getenv("PINTEREST_TOKEN_GARTENGEFUHL", ""),
}

# Seuils d'alerte Telegram
ALERT_THRESHOLDS = {
    "min_daily_sessions": 10,          # Alerte si < 10 sessions/jour
    "min_monthly_revenue_eur": 0.5,    # Alerte si < 0.50€ AdSense/mois (quand activé)
    "min_pinterest_impressions": 100,  # Alerte si < 100 impressions/jour sur Pinterest
    "ctr_warning_threshold": 0.02,     # Alerte si CTR Search Console < 2%
}

# Rapport hebdomadaire (quel jour ?)
WEEKLY_REPORT_DAY = 0  # 0=lundi, 6=dimanche

# Nombre de jours de données à inclure dans les rapports
DAILY_REPORT_DAYS = 1   # Données d'hier
WEEKLY_REPORT_DAYS = 7  # 7 derniers jours
