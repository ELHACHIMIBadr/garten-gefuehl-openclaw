"""
Correcteur Agent — Configuration
"""

# Chemins
DATA_DIR = "/root/garten-gefuehl-openclaw/data"
ARTICLES_DIR = f"{DATA_DIR}/articles"

# Modèle pour corrections GPT
MODEL = "gpt-5.5"

# Nombre maximum d'allers-retours Rédacteur ↔ Correcteur
MAX_RETRIES = 2

# ============================================================
# RÈGLES SEO RANK MATH — 20 POINTS OBLIGATOIRES
# ============================================================

# Règles de base (6 points)
SEO_BASIC_RULES = [
    "keyword_in_seo_title",
    "keyword_in_meta_description",
    "keyword_in_slug",
    "keyword_in_first_10pct",
    "keyword_in_content",
    "min_word_count_800",
]

# Règles supplémentaires (7 points)
SEO_EXTRA_RULES = [
    "keyword_in_h2_or_h3",
    "image_has_keyword_alt_text",
    "keyword_density_ok",
    "url_under_75_chars",
    "has_external_links",
    "has_internal_links",
    "keyword_not_used_before",
]

# Règles lisibilité titre (3 points)
SEO_TITLE_RULES = [
    "keyword_at_start_of_title",
    "title_has_power_word",
    "title_has_number",
]

# Règles lisibilité contenu (3 points)
SEO_CONTENT_RULES = [
    "has_table_of_contents",
    "has_short_paragraphs",
    "has_images_in_content",
]

# Règle critique titre — JAMAIS de ponctuation collée après keyword
TITLE_FORBIDDEN_PATTERNS = [
    ":",   # Ex: "Rosen pflegen:" → INTERDIT
    ";",   # Ex: "Rosen pflegen;" → INTERDIT
]

# Longueur titre SEO
TITLE_MIN_CHARS = 30
TITLE_MAX_CHARS = 65

# Longueur meta description
META_MIN_CHARS = 120
META_MAX_CHARS = 160

# Longueur URL/slug
SLUG_MAX_CHARS = 75

# Densité keyword
KEYWORD_DENSITY_MIN = 0.8   # 0.8%
KEYWORD_DENSITY_MAX = 1.5   # 1.5%

# Nombre minimum de mots
MIN_WORDS = 800  # Minimum absolu
TARGET_WORDS = 1500  # Cible

# Power words allemands
POWER_WORDS = [
    "einfach", "schnell", "günstig", "schön", "perfekt", "traumhaft",
    "wunderschön", "unglaublich", "erstaunlich", "sofort", "beliebt",
    "bewährt", "natürlich", "geheimnis", "zauber", "traumhafter",
    "zauberhafte", "beste", "top", "ultimativ", "effektiv"
]

# Phrases IA interdites
FORBIDDEN_AI_PHRASES = [
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
    "Als KI",
    "Als Sprachmodell",
    "Als AI",
    "Als künstliche Intelligenz",
    "Ich bin ein KI"
]

# Structure minimum requise
MIN_H2_COUNT = 3
MIN_H3_COUNT = 1
REQUIRED_SECTIONS = ["fazit"]  # Sections obligatoires (en minuscules)

# Outils de vérification plagiat (gratuits)
PLAGIAT_CHECK_ENABLED = True
