"""
Distributeur Agent — Client API Pinterest v5

Gère la création de pins via Pinterest API v5 (OAuth 2.0).
Upload image via base64 (pas de serveur externe requis).
"""

import base64
import requests
from config import PINTEREST_API_BASE


class PinterestClient:
    def __init__(self, access_token: str):
        self.token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    def test_connection(self) -> bool:
        """Vérifie que le token est valide."""
        try:
            resp = requests.get(
                f"{PINTEREST_API_BASE}/user_account",
                headers=self.headers,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                print(f"[Distributeur] ✅ Connecté en tant que : {data.get('username', '?')}")
                return True
            print(f"[Distributeur] ❌ Token invalide ({resp.status_code}): {resp.text[:100]}")
            return False
        except Exception as e:
            print(f"[Distributeur] Erreur connexion Pinterest: {e}")
            return False

    def get_boards(self) -> list:
        """
        Récupère la liste des boards du compte.
        Retourne une liste de dicts : [{id, name, description}, ...]
        """
        boards = []
        bookmark = None

        while True:
            params = {"page_size": 25}
            if bookmark:
                params["bookmark"] = bookmark

            try:
                resp = requests.get(
                    f"{PINTEREST_API_BASE}/boards",
                    headers=self.headers,
                    params=params,
                    timeout=15
                )
                if resp.status_code != 200:
                    print(f"[Distributeur] Erreur boards ({resp.status_code})")
                    break

                data = resp.json()
                boards.extend(data.get("items", []))
                bookmark = data.get("bookmark")
                if not bookmark:
                    break

            except Exception as e:
                print(f"[Distributeur] Erreur récupération boards: {e}")
                break

        return boards

    def create_pin(
        self,
        board_id: str,
        title: str,
        description: str,
        image_path: str,
        link: str = None
    ) -> dict:
        """
        Crée un pin Pinterest.

        Args:
            board_id: ID du board Pinterest
            title: Titre du pin (max 100 chars)
            description: Description (max 500 chars)
            image_path: Chemin local vers l'image WebP
            link: URL destination (None pendant le warm-up)

        Returns:
            dict avec {id, link} si succès, {} si erreur
        """
        # Encoder l'image en base64
        try:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            print(f"[Distributeur] Erreur lecture image {image_path}: {e}")
            return {}

        payload = {
            "board_id": board_id,
            "title": title[:100],
            "description": description[:500],
            "media_source": {
                "source_type": "image_base64",
                "content_type": "image/webp",
                "data": image_b64
            }
        }

        if link:
            payload["link"] = link

        try:
            resp = requests.post(
                f"{PINTEREST_API_BASE}/pins",
                headers=self.headers,
                json=payload,
                timeout=60  # Upload image peut prendre du temps
            )

            if resp.status_code in (200, 201):
                pin = resp.json()
                print(f"[Distributeur] ✅ Pin créé : {pin.get('id', '?')}")
                return {"id": pin.get("id"), "link": pin.get("link", ""), "board_id": board_id}
            else:
                print(f"[Distributeur] ❌ Erreur création pin ({resp.status_code}): {resp.text[:200]}")
                return {}

        except Exception as e:
            print(f"[Distributeur] Erreur création pin: {e}")
            return {}
