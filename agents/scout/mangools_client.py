"""
Scout Agent — Mangools KWFinder API Client

Endpoint : POST /v3/kwfinder/keyword-imports
- Jusqu'à 700 keywords par requête = 1 seul lookup
- Plan gratuit : 5 lookups / 24h = 3 500 keywords/jour
- Requêtes identiques < 24h : pas recomptées

Params Allemagne :
  location_id = 2276  (Germany)
  language_id = 1001  (German)
"""

import os
import requests

API_BASE = "https://api.mangools.com/v3"
LOCATION_ID = 2276   # Germany
LANGUAGE_ID = 1001   # German
MAX_KEYWORDS_PER_REQUEST = 700


def _get_api_key() -> str:
    key = os.getenv("MANGOOLS_API_KEY", "")
    if not key:
        raise ValueError("[Mangools] MANGOOLS_API_KEY manquant dans .env")
    return key


def get_keyword_volumes(keywords: list) -> dict:
    """
    Appelle Mangools keyword-imports pour obtenir volumes réels.
    
    Args:
        keywords: liste de strings (max 700)
    
    Returns:
        dict {keyword_lower: {volume, cpc, competition, competition_level, trend}}
    """
    if not keywords:
        return {}

    api_key = _get_api_key()
    
    # Dédupliquer et limiter
    unique_kws = list(dict.fromkeys(kw.strip() for kw in keywords if kw.strip()))

    # Plan gratuit : max ~200 keywords par requête (700 = plans payants)
    batch_size = 200
    unique_kws = unique_kws[:batch_size]

    print(f"[Mangools] Requête keyword-imports : {len(unique_kws)} keywords | DE/de")

    try:
        resp = requests.post(
            f"{API_BASE}/kwfinder/keyword-imports",
            headers={
                "x-access-token": api_key,
                "Content-Type": "application/json",
            },
            json={
                "keywords": unique_kws,
                "location_id": LOCATION_ID,
                "language_id": LANGUAGE_ID,
            },
            timeout=60,
        )

        if resp.status_code == 401:
            print("[Mangools] ❌ Clé API invalide ou expirée")
            return {}
        if resp.status_code == 429:
            print("[Mangools] ❌ Limite lookups atteinte (5/jour plan gratuit)")
            return {}
        if resp.status_code != 200:
            print(f"[Mangools] ❌ HTTP {resp.status_code} : {resp.text[:200]}")
            return {}

        data = resp.json()
        kw_list = data.get("keywords", [])

        results = {}
        for kw_data in kw_list:
            kw_text = kw_data.get("kw", "").lower().strip()
            if not kw_text:
                continue

            # sv = average monthly search volume (12 mois)
            sv = kw_data.get("sv", 0)
            try:
                sv = int(sv) if sv is not None else 0
            except (TypeError, ValueError):
                sv = 0

            # cpc
            cpc_raw = kw_data.get("cpc", 0)
            try:
                cpc = float(cpc_raw) if cpc_raw is not None else 0
            except (TypeError, ValueError):
                cpc = 0

            # ppc competition (0-100 → normalisé 0-1)
            ppc_raw = kw_data.get("ppc", 0)
            try:
                ppc = float(ppc_raw) if ppc_raw is not None else 0
                competition = ppc / 100.0 if ppc > 1 else ppc
            except (TypeError, ValueError):
                competition = 0.3

            # Keyword difficulty (seo score, peut être null)
            seo_raw = kw_data.get("seo", None)
            if seo_raw is not None:
                try:
                    kd = int(seo_raw)
                except (TypeError, ValueError):
                    kd = 50
            else:
                kd = None

            # Competition level basé sur PPC
            if competition >= 0.7:
                comp_level = "HIGH"
            elif competition >= 0.3:
                comp_level = "MEDIUM"
            else:
                comp_level = "LOW"

            # Trend : calculé depuis msv (monthly search volumes)
            trend = 0
            msv = kw_data.get("msv", [])
            if msv and isinstance(msv, list) and len(msv) >= 6:
                try:
                    # msv peut être flat [year,month,vol,...] ou nested [[year,month,vol],...]
                    if isinstance(msv[0], list):
                        volumes = [entry[2] for entry in msv if isinstance(entry, list) and len(entry) >= 3]
                    else:
                        volumes = [msv[i] for i in range(2, len(msv), 3) if i < len(msv) and isinstance(msv[i], (int, float))]
                    if len(volumes) >= 4:
                        recent = sum(volumes[:3]) / 3
                        older = sum(volumes[-3:]) / 3
                        if older > 0:
                            trend = round(((recent - older) / older) * 100, 1)
                except Exception:
                    trend = 0

            results[kw_text] = {
                "volume": sv,
                "cpc": cpc,
                "competition": competition,
                "competition_level": comp_level,
                "trend": trend,
                "kd": kd,
            }

        print(f"[Mangools] ✅ {len(results)} keywords avec volumes")
        
        # Stats rapides
        with_volume = sum(1 for v in results.values() if v["volume"] > 0)
        print(f"[Mangools] 📊 {with_volume}/{len(results)} ont un volume > 0")

        return results

    except requests.exceptions.Timeout:
        print("[Mangools] ❌ Timeout (60s)")
        return {}
    except requests.exceptions.ConnectionError:
        print("[Mangools] ❌ Erreur connexion")
        return {}
    except Exception as e:
        print(f"[Mangools] ❌ Erreur : {e}")
        return {}


def check_remaining_lookups() -> dict:
    """Vérifie les lookups restants pour le plan actuel."""
    api_key = _get_api_key()
    try:
        resp = requests.get(
            f"{API_BASE}/kwfinder/limits",
            headers={"x-access-token": api_key},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"[Mangools] Lookups restants : {data}")
            return data
        return {}
    except Exception as e:
        print(f"[Mangools] ❌ Check limits: {e}")
        return {}
