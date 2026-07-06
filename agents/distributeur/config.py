"""
Distributeur Agent — Configuration (Playwright)

CREDENTIALS dans config/.env :
  PINTEREST_1_EMAIL=blumenliebe@example.com
  PINTEREST_1_PASSWORD=motdepasse123
  PINTEREST_2_EMAIL=...
  PINTEREST_2_PASSWORD=...
  PINTEREST_3_EMAIL=...
  PINTEREST_3_PASSWORD=...
  PINTEREST_4_EMAIL=...
  PINTEREST_4_PASSWORD=...
  PINTEREST_5_EMAIL=...
  PINTEREST_5_PASSWORD=...

BOARDS : noms exacts des boards Pinterest (tels qu'affichés sur le profil).
         Le bot cherchera le board par nom dans le dropdown.
         Si non trouvé → sélection du premier board disponible.
"""

import os

# ── Chemins ──────────────────────────────────────────────────
DATA_DIR     = "/root/garten-gefuehl-openclaw/data"
PINS_DIR     = f"{DATA_DIR}/pins"
ARTICLES_DIR = f"{DATA_DIR}/articles"
STATE_FILE   = f"{DATA_DIR}/distributeur_state.json"

# ── Règles de distribution ───────────────────────────────────
PINS_WITH_LINK  = 3   # Pins avec lien vers article WP (par compte/jour)
PINS_NO_LINK    = 2   # Pins sans lien (par compte/jour)

# ── Anti-ban : délais en secondes ────────────────────────────
DELAY_BETWEEN_PINS_MIN     = 45   # Entre 2 pins du même compte
DELAY_BETWEEN_PINS_MAX     = 120
DELAY_BETWEEN_ACCOUNTS_MIN = 90   # Entre 2 comptes
DELAY_BETWEEN_ACCOUNTS_MAX = 240

# ── Configuration des 5 comptes ──────────────────────────────
# ORDRE IMPORTANT : correspond aux numéros 1-5 dans .env
# CROSS-NICHE STRICTEMENT INTERDIT :
#   chaque compte ne poste QUE des liens de sa propre categorie_wp
ACCOUNT_CONFIG = [
    {
        "name":         "Blumenliebe DE",
        "categorie":    "Blumen",
        "email_env":    "PINTEREST_1_EMAIL",
        "password_env": "PINTEREST_1_PASSWORD",
        "boards": [
            "Blumen Ideen",
            "Gartenblumen",
            "Frühlingsblumen",
            "Balkonblumen",
            "Wildblumen & Naturblumen",
            "Schnittblumen & Sträuße",
        ],
    },
    {
        "name":         "Balkon Ideen DE",
        "categorie":    "Balkon",
        "email_env":    "PINTEREST_2_EMAIL",
        "password_env": "PINTEREST_2_PASSWORD",
        "boards": [
            "Balkon Ideen",
            "Balkonpflanzen",
            "Balkon Deko",
            "Kleiner Balkon",
            "Balkon Sommer",
            "Balkon Gemüse & Kräuter",
        ],
    },
    {
        "name":         "Rosenfreude DE",
        "categorie":    "Rosen",
        "email_env":    "PINTEREST_3_EMAIL",
        "password_env": "PINTEREST_3_PASSWORD",
        "boards": [
            "Rosen Ideen",
            "Rosenpflege",
            "Kletterrosen",
            "Rosensorten",
            "Rosengarten Gestaltung",
            "Rosen & Romantik",
        ],
    },
    {
        "name":         "Terrasse & Garten DE",
        "categorie":    "Terrasse",
        "email_env":    "PINTEREST_4_EMAIL",
        "password_env": "PINTEREST_4_PASSWORD",
        "boards": [
            "Terrasse Ideen",
            "Terrassengestaltung",
            "Gartenmöbel",
            "Sichtschutz Terrasse",
            "Terrasse Bepflanzung",
            "Terrasse & Outdoor Living",
        ],
    },
    {
        "name":         "Garten Gefühl",
        "categorie":    "Garten Gefühl",
        "email_env":    "PINTEREST_5_EMAIL",
        "password_env": "PINTEREST_5_PASSWORD",
        "boards": [
            "Garten Inspiration",
            "Gartengestaltung",
            "Naturgarten",
            "Garten DIY",
            "Gartenpflege Tipps",
            "Traumgarten",
        ],
    },
]
