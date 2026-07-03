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
PUBLISH_TIME = "08:00:00"  # 08h00 heure DE

# Catégories WordPress IDs (à confirmer sur ton WP)
WP_CATEGORY_IDS = {
    "Blumen": 2,
    "Balkon": 3,
    "Rosen": 4,
    "Terrasse": 5,
    "Garten Gefühl": 6
}

# Statut de publication
PUBLISH_STATUS = "publish"  # publish = immédiatement visible

# Nombre de liens internes à injecter
MIN_INTERNAL_LINKS = 2

# Ping Google Indexing API après publication
PING_GOOGLE = True
