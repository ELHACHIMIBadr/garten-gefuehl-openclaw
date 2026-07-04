"""
Utilitaire — Obtenir les access tokens Pinterest pour les 5 comptes

Ce script guide le flux OAuth 2.0 pour chaque compte Pinterest.
Lancer une fois par compte, depuis un navigateur sur ton PC Windows
(pas depuis le VPS).

PRÉREQUIS :
1. Créer une app Pinterest sur https://developers.pinterest.com/apps/
   → Récupérer App ID + App Secret
   → Ajouter en Redirect URI : https://localhost/callback
   → Scopes requis : boards:read, pins:write, user_accounts:read
2. pip install requests (sur ton PC Windows)
3. Lancer : python setup_pinterest_tokens.py

Usage :
  python setup_pinterest_tokens.py
  → Te demande App ID + App Secret
  → Ouvre l'URL d'autorisation Pinterest (à ouvrir dans le profil Chrome du compte)
  → Tu colles l'URL de redirection (avec le code OAuth)
  → Affiche le access_token à copier dans .env
"""

import sys
import json
import urllib.parse
import webbrowser

try:
    import requests
except ImportError:
    print("Installer requests : pip install requests")
    sys.exit(1)


ACCOUNTS = [
    ("Blumenliebe DE",       "PINTEREST_TOKEN_BLUMENLIEBE",    "PINTEREST_BOARDS_BLUMENLIEBE"),
    ("Balkon Ideen DE",      "PINTEREST_TOKEN_BALKON",          "PINTEREST_BOARDS_BALKON"),
    ("Rosenfreude DE",       "PINTEREST_TOKEN_ROSEN",           "PINTEREST_BOARDS_ROSEN"),
    ("Terrasse & Garten DE", "PINTEREST_TOKEN_TERRASSE",        "PINTEREST_BOARDS_TERRASSE"),
    ("Garten Gefühl",        "PINTEREST_TOKEN_GARTENGEFUHL",    "PINTEREST_BOARDS_GARTENGEFUHL"),
]

PINTEREST_AUTH_URL = "https://www.pinterest.com/oauth/"
PINTEREST_TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"
PINTEREST_BOARDS_URL = "https://api.pinterest.com/v5/boards"
REDIRECT_URI = "https://localhost/callback"
SCOPES = "boards:read,pins:write,user_accounts:read"


def get_token_for_account(app_id: str, app_secret: str, account_name: str) -> tuple:
    """
    Obtient un access_token pour un compte Pinterest.
    Retourne (access_token, board_ids_list).
    """
    print(f"\n{'='*60}")
    print(f"Compte : {account_name}")
    print(f"{'='*60}")

    # Construire l'URL d'autorisation
    params = {
        "client_id": app_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": account_name.replace(" ", "_")
    }
    auth_url = PINTEREST_AUTH_URL + "?" + urllib.parse.urlencode(params)

    print(f"\n1. Ouvrir l'URL suivante dans le profil Chrome de '{account_name}' :")
    print(f"\n   {auth_url}\n")
    print(f"2. Autoriser l'app Pinterest")
    print(f"3. Tu seras redirigé vers https://localhost/callback?code=XXXX")
    print(f"   (Erreur de connexion normale — copier l'URL complète)")

    callback_url = input(f"\nColler l'URL de redirection complète : ").strip()

    # Extraire le code OAuth
    parsed = urllib.parse.urlparse(callback_url)
    query_params = urllib.parse.parse_qs(parsed.query)
    code = query_params.get("code", [None])[0]

    if not code:
        print(f"❌ Code OAuth non trouvé dans l'URL")
        return None, []

    # Échanger le code contre un access token
    resp = requests.post(
        PINTEREST_TOKEN_URL,
        auth=(app_id, app_secret),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI
        },
        timeout=15
    )

    if resp.status_code not in (200, 201):
        print(f"❌ Erreur token ({resp.status_code}): {resp.text}")
        return None, []

    token_data = resp.json()
    access_token = token_data.get("access_token")

    if not access_token:
        print(f"❌ access_token manquant dans la réponse: {token_data}")
        return None, []

    print(f"\n✅ Token obtenu !")

    # Récupérer les boards du compte
    boards_resp = requests.get(
        PINTEREST_BOARDS_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        params={"page_size": 25},
        timeout=15
    )

    board_ids = []
    if boards_resp.status_code == 200:
        boards = boards_resp.json().get("items", [])
        print(f"\nBoards trouvés ({len(boards)}) :")
        for b in boards:
            print(f"  ID: {b['id']} | Nom: {b['name']}")
            board_ids.append(b["id"])
    else:
        print(f"⚠️ Impossible de récupérer les boards ({boards_resp.status_code})")

    return access_token, board_ids


def main():
    print("=" * 60)
    print("SETUP TOKENS PINTEREST — GARTEN GEFÜHL")
    print("=" * 60)
    print("\nCe script obtient les access tokens OAuth pour tes 5 comptes.")
    print("Lancer une fois par compte dans le bon profil Chrome.\n")

    app_id = input("App ID Pinterest (depuis developers.pinterest.com) : ").strip()
    app_secret = input("App Secret Pinterest : ").strip()

    if not app_id or not app_secret:
        print("❌ App ID et App Secret requis")
        sys.exit(1)

    env_lines = []
    print("\n" + "="*60)
    print("Lancer pour chaque compte ? (ou appuyer sur Entrée pour sauter)")
    print("="*60)

    for account_name, token_key, boards_key in ACCOUNTS:
        do_it = input(f"\n→ Configurer '{account_name}' ? [O/n] : ").strip().lower()
        if do_it == "n":
            print(f"  Skipped.")
            continue

        token, board_ids = get_token_for_account(app_id, app_secret, account_name)

        if token:
            env_lines.append(f"{token_key}={token}")
            env_lines.append(f"{boards_key}={','.join(board_ids)}")
            print(f"\n✅ {account_name} configuré ({len(board_ids)} boards)")

    # Afficher le résumé à copier dans .env
    if env_lines:
        print("\n" + "="*60)
        print("COPIER CES LIGNES DANS config/.env :")
        print("="*60)
        for line in env_lines:
            print(line)
        print("="*60)

        # Sauvegarder dans un fichier temporaire
        with open("pinterest_tokens_temp.txt", "w") as f:
            f.write("\n".join(env_lines))
        print(f"\n✅ Sauvegardé dans pinterest_tokens_temp.txt")
        print("⚠️  Supprimer ce fichier après avoir copié dans .env !")
    else:
        print("\nAucun token obtenu.")


if __name__ == "__main__":
    main()
