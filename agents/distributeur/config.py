"""
Distributeur Agent — Configuration Pinterest

CONFIGURATION REQUISE dans .env :
Pour chaque compte Pinterest (5 au total), ajouter dans config/.env :

  PINTEREST_TOKEN_BLUMENLIEBE=your_access_token
  PINTEREST_BOARDS_BLUMENLIEBE=board_id1,board_id2,board_id3,board_id4,board_id5,board_id6

  PINTEREST_TOKEN_BALKON=your_access_token
  PINTEREST_BOARDS_BALKON=board_id1,board_id2,...

  PINTEREST_TOKEN_ROSEN=your_access_token
  PINTEREST_BOARDS_ROSEN=board_id1,...

  PINTEREST_TOKEN_TERRASSE=your_access_token
  PINTEREST_BOARDS_TERRASSE=board_id1,...

  PINTEREST_TOKEN_GARTENGEFUHL=your_access_token
  PINTEREST_BOARDS_GARTENGEFUHL=board_id1,...

COMMENT OBTENIR UN ACCESS TOKEN PINTEREST :
1. Aller sur https://developers.pinterest.com/apps/
2. Créer une app → récupérer App ID + App Secret
3. Utiliser le script setup_pinterest_tokens.py fourni
4. Ou : https://developers.pinterest.com/tools/oauth-token-generator/ (OAuth 2.0 PKCE)
5. Scopes requis : boards:read, pins:write, user_accounts:read

COMMENT OBTENIR LES BOARD IDs :
1. Lancer : python distributeur/main.py --list-boards
   → Affiche les board IDs de tous les comptes configurés
   Ou manuellement via : GET https://api.pinterest.com/v5/boards
"""

import os

# Chemins données
DATA_DIR = "/root/garten-gefuehl-openclaw/data"
PINS_DIR = f"{DATA_DIR}/pins"
STATE_FILE = f"{DATA_DIR}/distributeur_state.json"

# API Pinterest
PINTEREST_API_BASE = "https://api.pinterest.com/v5"

# Mapping compte → catégorie WP
ACCOUNT_CATEGORY_MAP = {
    "Blumenliebe DE":      {"env_token": "PINTEREST_TOKEN_BLUMENLIEBE",    "env_boards": "PINTEREST_BOARDS_BLUMENLIEBE",    "categorie": "Blumen"},
    "Balkon Ideen DE":     {"env_token": "PINTEREST_TOKEN_BALKON",          "env_boards": "PINTEREST_BOARDS_BALKON",          "categorie": "Balkon"},
    "Rosenfreude DE":      {"env_token": "PINTEREST_TOKEN_ROSEN",           "env_boards": "PINTEREST_BOARDS_ROSEN",           "categorie": "Rosen"},
    "Terrasse & Garten DE":{"env_token": "PINTEREST_TOKEN_TERRASSE",        "env_boards": "PINTEREST_BOARDS_TERRASSE",        "categorie": "Terrasse"},
    "Garten Gefühl":       {"env_token": "PINTEREST_TOKEN_GARTENGEFUHL",    "env_boards": "PINTEREST_BOARDS_GARTENGEFUHL",    "categorie": "Garten Gefühl"},
}

# Règles de distribution
WARMUP_DAYS = 4            # Nombre de jours de warm-up par compte
PINS_PER_DAY_WARMUP = 2   # Pins/jour pendant le warm-up (sans lien)
PINS_PER_DAY_ACTIVE = 4   # Pins/jour en mode actif (avec lien)

# Anti-ban : délais en secondes entre actions
DELAY_BETWEEN_PINS_MIN = 90   # Délai min entre 2 pins du même compte
DELAY_BETWEEN_PINS_MAX = 240  # Délai max entre 2 pins du même compte
DELAY_BETWEEN_ACCOUNTS_MIN = 120  # Délai min entre comptes
DELAY_BETWEEN_ACCOUNTS_MAX = 360  # Délai max entre comptes

# Gestion liens intelligente
MAX_PINS_PER_URL_PER_DAY = 1  # Max 1 pin/jour vers la même URL article


def get_account_config(account_name: str) -> dict:
    """Retourne la configuration (token + boards) pour un compte."""
    cfg = ACCOUNT_CATEGORY_MAP.get(account_name, {})
    if not cfg:
        return {}

    token = os.getenv(cfg["env_token"], "")
    boards_raw = os.getenv(cfg["env_boards"], "")
    boards = [b.strip() for b in boards_raw.split(",") if b.strip()] if boards_raw else []

    return {
        "account_name": account_name,
        "token": token,
        "boards": boards,
        "categorie": cfg["categorie"],
        "configured": bool(token and boards)
    }
