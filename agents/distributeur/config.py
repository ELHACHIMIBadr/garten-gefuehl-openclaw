"""
Distributeur Agent — Configuration (Playwright)

CREDENTIALS dans config/.env :
  PINTEREST_1_EMAIL / PINTEREST_1_PASSWORD   → Blumenliebe DE
  PINTEREST_2_EMAIL / PINTEREST_2_PASSWORD   → Balkon Ideen DE
  PINTEREST_3_EMAIL / PINTEREST_3_PASSWORD   → Rosenfreude DE
  PINTEREST_4_EMAIL / PINTEREST_4_PASSWORD   → Terrasse & Garten DE
  PINTEREST_5_EMAIL / PINTEREST_5_PASSWORD   → Garten Gefühl

BOARDS : noms exacts tels qu'ils apparaissent sur Pinterest.
"""

import os

DATA_DIR     = "/root/garten-gefuehl-openclaw/data"
PINS_DIR     = f"{DATA_DIR}/pins"
ARTICLES_DIR = f"{DATA_DIR}/articles"
STATE_FILE   = f"{DATA_DIR}/distributeur_state.json"

PINS_WITH_LINK  = 3
PINS_NO_LINK    = 2

DELAY_BETWEEN_PINS_MIN     = 45
DELAY_BETWEEN_PINS_MAX     = 120
DELAY_BETWEEN_ACCOUNTS_MIN = 90
DELAY_BETWEEN_ACCOUNTS_MAX = 240

# Boards vérifiés live sur chaque compte Pinterest
ACCOUNT_CONFIG = [
    {
        "name":         "Blumenliebe DE",
        "categorie":    "Blumen",
        "email_env":    "PINTEREST_1_EMAIL",
        "password_env": "PINTEREST_1_PASSWORD",
        "boards": [
            "Balkonblumen",
            "Blumenbeet Ideen",
            "Blumenstrauß Ideen",
            "Frühlingsblumen",
            "Sommerblumen",
            "Trockenblumen",
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
