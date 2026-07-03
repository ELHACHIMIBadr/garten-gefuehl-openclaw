"""
Publisher Agent — Configuration
"""

# Chemins
DATA_DIR = "/root/garten-gefuehl-openclaw/data"
ARTICLES_DIR = f"{DATA_DIR}/articles"

# WordPress
WP_URL = "https://xn--garten-gefhl-mlb.de"
WP_API = f"{WP_URL}/wp-json/wp/v2"

# Heure de publication fixe (heure DE = UTC+2 en été)
PUBLISH_TIME = "08:00:00"

# Catégories WordPress IDs (vérifiés via API)
WP_CATEGORY_IDS = {
    "Blumen": 3,
    "Balkon": 4,
    "Rosen": 5,
    "Terrasse": 6,
    "Garten Gefühl": 7
}

# Statut de publication
PUBLISH_STATUS = "publish"

# Nombre de liens internes à injecter
MIN_INTERNAL_LINKS = 2

# Ping Google Indexing API après publication
PING_GOOGLE = True
