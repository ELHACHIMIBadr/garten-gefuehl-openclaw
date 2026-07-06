"""
Distributeur Agent — Configuration (Playwright)

Boards vérifiés live sur chaque compte Pinterest (juillet 2026).
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
