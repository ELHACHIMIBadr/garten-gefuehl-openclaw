"""
Rédacteur Agent — Configuration
"""

# Longueur cible de l'article
MIN_WORDS = 1500
MAX_WORDS = 2000

# Nombre de keywords secondaires à intégrer
MAX_SECONDARY_KEYWORDS = 5

# Nombre d'images par article (1 par H2 + 1 featured)
IMAGES_PER_SECTION = 1

# Chemins fichiers
DATA_DIR = "/root/garten-gefuehl-openclaw/data"
BRIEFS_DIR = f"{DATA_DIR}/briefs"
ARTICLES_DIR = f"{DATA_DIR}/articles"

# Modèle OpenAI via Codex OAuth
MODEL = "gpt-5.5"

# Phrases interdites (détection IA)
FORBIDDEN_PHRASES = [
    "In diesem Artikel",
    "Es ist wichtig zu beachten",
    "Zusammenfassend lässt sich sagen",
    "Es ist erwähnenswert",
    "Ich hoffe, dieser Artikel",
    "Abschließend möchte ich",
    "In der heutigen Zeit",
    "Es versteht sich von selbst",
    "Es sei darauf hingewiesen",
    "Es ist zu beachten",
    "In Bezug auf",
    "Heutzutage",
    "Als KI",
    "Als Sprachmodell",
    "Als AI"
]

# Mots forts pour les titres (power words)
POWER_WORDS = [
    "einfach", "schnell", "günstig", "schön", "perfekt",
    "geheimnis", "bewährt", "natürlich", "traumhaft", "wunderschön",
    "unglaublich", "erstaunlich", "sofort", "kostenlos", "beliebt"
]

# Structure minimum attendue
REQUIRED_STRUCTURE = {
    "min_h2": 4,
    "min_h3": 2,
    "has_intro": True,
    "has_fazit": True,
    "has_table_of_contents": True
}

# Catégories WP → IDs (à confirmer sur ton WordPress)
WP_CATEGORY_IDS = {
    "Blumen": 2,
    "Balkon": 3,
    "Rosen": 4,
    "Terrasse": 5,
    "Garten Gefühl": 6
}
