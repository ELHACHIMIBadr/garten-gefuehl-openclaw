"""
Directeur Artistique Agent — Configuration
"""

# Chemins
DATA_DIR = "/root/garten-gefuehl-openclaw/data"
ARTICLES_DIR = f"{DATA_DIR}/articles"
IMAGES_DIR = f"{DATA_DIR}/images"
PINS_DIR = f"{DATA_DIR}/pins"

# APIs Images
PEXELS_API_URL = "https://api.pexels.com/v1/search"
PIXABAY_API_URL = "https://pixabay.com/api/"

# Format images article
ARTICLE_IMAGE_MAX_SIZE_KB = 200   # Max 200KB par image
ARTICLE_IMAGE_FORMAT = "webp"

# Format pins Pinterest
PIN_WIDTH = 1000
PIN_HEIGHT = 1500  # Format 2:3
PIN_FORMAT = "webp"
PINS_PER_ARTICLE = 5  # 1 pin par compte Pinterest

# Chaîne de sourcing (ordre de priorité)
IMAGE_SOURCES = ["pexels", "pixabay", "gpt_image"]

# Nombre d'essais avant fallback GPT-image
MAX_FREE_ATTEMPTS = 9

# Compteur mensuel GPT-image (fichier de suivi)
GPT_IMAGE_COUNTER_FILE = f"{DATA_DIR}/gpt_image_counter.json"

# Mots-clés de recherche image par catégorie (en anglais pour les APIs)
CATEGORY_IMAGE_KEYWORDS = {
    "Blumen": ["garden flowers", "colorful flowers", "flower garden", "blooming flowers"],
    "Balkon": ["balcony flowers", "balcony garden", "balcony plants", "balcony decoration"],
    "Rosen": ["roses garden", "rose flowers", "red roses", "rose bush"],
    "Terrasse": ["terrace garden", "patio garden", "outdoor terrace", "garden terrace"],
    "Garten Gefühl": ["garden", "natural garden", "green garden", "garden design"]
}

# Comptes Pinterest (ordre = index de 0 à 4)
PINTEREST_ACCOUNTS = [
    "Blumenliebe DE",
    "Balkon Ideen DE",
    "Rosenfreude DE",
    "Terrasse & Garten DE",
    "Garten Gefühl"
]

# Modèle GPT pour génération image fallback
GPT_IMAGE_MODEL = "gpt-image-2"
GPT_IMAGE_SIZE = "1024x1536"  # Proche du 2:3
