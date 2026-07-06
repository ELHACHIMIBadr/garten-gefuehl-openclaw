"""
Distributeur Agent — Configuration (Playwright)

Boards vérifiés live sur chaque compte Pinterest (juillet 2026).

MODE ROUND-ROBIN :
  Chaque round poste 1 pin par compte (5 pins simultanés).
  30 minutes entre chaque round.
  5 rounds = 25 pins en 2h.
"""

import os

DATA_DIR     = "/root/garten-gefuehl-openclaw/data"
PINS_DIR     = f"{DATA_DIR}/pins"
ARTICLES_DIR = f"{DATA_DIR}/articles"
STATE_FILE   = f"{DATA_DIR}/distributeur_state.json"

PINS_WITH_LINK  = 3
PINS_NO_LINK    = 2
PINS_PER_ACCOUNT = 5  # 5 rounds total

# Délai entre pins du MÊME round (anti-ban inter-comptes, secondes)
DELAY_BETWEEN_ACCOUNTS_MIN = 30
DELAY_BETWEEN_ACCOUNTS_MAX = 60

# Délai entre rounds (secondes) — 30 minutes
DELAY_BETWEEN_ROUNDS = 30 * 60  # 1800s

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
            "Balkon Deko",
            "Balkon gemütlich gestalten",
            "Balkon Sichtschutz",
            "Balkonpflanzen",
            "Kleiner Balkon Ideen",
            "Kräuter auf dem Balkon",
        ],
    },
    {
        "name":         "Rosenfreude DE",
        "categorie":    "Rosen",
        "email_env":    "PINTEREST_3_EMAIL",
        "password_env": "PINTEREST_3_PASSWORD",
        "boards": [
            "Alte Rosensorten",
            "Beetrosen",
            "Kletterrosen",
            "Rosen Arrangement",
            "Rosen im Garten",
            "Rosen Pflege Tipps",
        ],
    },
    {
        "name":         "Terrasse & Garten DE",
        "categorie":    "Terrasse",
        "email_env":    "PINTEREST_4_EMAIL",
        "password_env": "PINTEREST_4_PASSWORD",
        "boards": [
            "Terrasse aus Holz",
            "Terrasse Beleuchtung",
            "Terrasse Deko",
            "Terrasse gemütlich einrichten",
            "Terrassenmöbel Ideen",
            "Überdachte Terrasse",
        ],
    },
    {
        "name":         "Garten Gefühl",
        "categorie":    "Garten Gefühl",
        "email_env":    "PINTEREST_5_EMAIL",
        "password_env": "PINTEREST_5_PASSWORD",
        "boards": [
            "Garten Deko",
            "Garten Gestaltung",
            "Garten Inspiration",
            "Gartenideen",
            "Gartenpflanzen",
            "Naturgarten",
        ],
    },
]
