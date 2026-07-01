"""
Scout Agent — Configuration
Constantes et paramètres du Scout.
"""

# Catégories WordPress + comptes Pinterest associés
CATEGORIES = [
    {
        "name": "Blumen",
        "slug": "blumen",
        "traduction_fr": "fleurs",
        "pinterest_account": "Blumenliebe DE",
        "seed_keywords": ["Blumen", "Blumen Garten", "Blumen pflanzen", "Blumenarten", "Blumen Balkon"]
    },
    {
        "name": "Balkon",
        "slug": "balkon",
        "traduction_fr": "balcon",
        "pinterest_account": "Balkon Ideen DE",
        "seed_keywords": ["Balkon", "Balkon gestalten", "Balkon Pflanzen", "Balkon Ideen", "Balkon Deko"]
    },
    {
        "name": "Rosen",
        "slug": "rosen",
        "traduction_fr": "roses",
        "pinterest_account": "Rosenfreude DE",
        "seed_keywords": ["Rosen", "Rosen pflegen", "Rosen schneiden", "Rosensorten", "Rosen pflanzen"]
    },
    {
        "name": "Terrasse",
        "slug": "terrasse",
        "traduction_fr": "terrasse",
        "pinterest_account": "Terrasse & Garten DE",
        "seed_keywords": ["Terrasse", "Terrasse gestalten", "Terrasse Ideen", "Terrasse Deko", "Terrasse Pflanzen"]
    },
    {
        "name": "Garten Gefühl",
        "slug": "garten-gefuehl",
        "traduction_fr": "sensation jardin",
        "pinterest_account": "Garten Gefühl",
        "seed_keywords": ["Garten", "Garten gestalten", "Garten Ideen", "Naturgarten", "Garten Tipps"]
    }
]

# Scoring weights
SCORING = {
    "volume_weight": 1.0,
    "cpc_weight": 2.0,
    "competition_penalty": 1.5,
    "trend_bonus": 0.2,          # +20% si trend en hausse
    "dual_source_bonus": 0.15,   # +15% si trouvé sur Pinterest ET Google
    "recency_penalty": 0.5,      # -50% si sujet traité dans les 30 derniers jours
    "faq_bonus": 0.1             # +10% si des questions FAQ existent
}

# DataForSEO
DATAFORSEO_LOCATION = 2276  # Germany
DATAFORSEO_LANGUAGE = "de"

# Chemins fichiers
DATA_DIR = "/root/garten-gefuehl-openclaw/data"
BRIEFS_DIR = f"{DATA_DIR}/briefs"
KEYWORDS_DIR = f"{DATA_DIR}/keywords"
HISTORY_FILE = f"{KEYWORDS_DIR}/history.json"

# Rotation : 1 article/jour, cycle sur 5 catégories
ARTICLES_PER_DAY = 1
