"""
Scout Agent — DataForSEO API Client
Enrichissement des keywords avec volumes, CPC, concurrence.
"""

import requests
import base64
import json
import time
from typing import List, Dict
from config import DATAFORSEO_LOCATION, DATAFORSEO_LANGUAGE


class DataForSEOClient:
    BASE_URL = "https://api.dataforseo.com/v3"
    
    def __init__(self, login: str, password: str):
        credentials = base64.b64encode(f"{login}:{password}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json"
        }
    
    def get_keyword_volumes(self, keywords: List[str]) -> Dict:
        """
        Récupère volume mensuel, CPC et concurrence pour une liste de keywords.
        Envoie par batch de 100 max (limite DataForSEO).
        """
        all_results = {}
        
        # Batch par 100
        for i in range(0, len(keywords), 100):
            batch = keywords[i:i+100]
            
            payload = [
                {
                    "keywords": batch,
                    "location_code": DATAFORSEO_LOCATION,
                    "language_code": DATAFORSEO_LANGUAGE,
                    "date_from": None,
                    "date_to": None,
                    "include_serp_info": False,
                    "include_clickstream_data": False
                }
            ]
            
            try:
                resp = requests.post(
                    f"{self.BASE_URL}/keywords_data/google_ads/search_volume/live",
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status_code") == 20000:
                        tasks = data.get("tasks", [])
                        for task in tasks:
                            if task.get("result"):
                                for item in task["result"]:
                                    kw = item.get("keyword", "").lower()
                                    all_results[kw] = {
                                        "volume": item.get("search_volume", 0) or 0,
                                        "cpc": item.get("cpc", 0) or 0,
                                        "competition": item.get("competition", 0) or 0,
                                        "competition_level": item.get("competition_level", "UNKNOWN"),
                                        "trend": self._calculate_trend(item.get("monthly_searches", []))
                                    }
                    else:
                        print(f"[Scout] DataForSEO erreur: {data.get('status_message')}")
                else:
                    print(f"[Scout] DataForSEO HTTP {resp.status_code}")
                    
            except Exception as e:
                print(f"[Scout] DataForSEO erreur batch {i}: {e}")
            
            if i + 100 < len(keywords):
                time.sleep(1)  # Pause entre batches
        
        return all_results
    
    def _calculate_trend(self, monthly_searches: list) -> float:
        """
        Calcule le trend (variation %) sur les 3 derniers mois vs 3 mois précédents.
        Retourne un pourcentage : +25.0 = hausse de 25%, -10.0 = baisse de 10%.
        """
        if not monthly_searches or len(monthly_searches) < 6:
            return 0.0
        
        # Les données viennent du plus récent au plus ancien
        recent = monthly_searches[:3]
        previous = monthly_searches[3:6]
        
        recent_avg = sum(m.get("search_volume", 0) or 0 for m in recent) / 3
        previous_avg = sum(m.get("search_volume", 0) or 0 for m in previous) / 3
        
        if previous_avg == 0:
            return 0.0
        
        trend_pct = ((recent_avg - previous_avg) / previous_avg) * 100
        return round(trend_pct, 1)
    
    def get_balance(self) -> float:
        """
        Vérifie le solde restant du compte DataForSEO.
        """
        try:
            resp = requests.get(
                f"{self.BASE_URL}/appendix/user_data",
                headers=self.headers,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("tasks") and data["tasks"][0].get("result"):
                    return data["tasks"][0]["result"][0].get("money", {}).get("balance", 0)
        except Exception as e:
            print(f"[Scout] Erreur vérification solde: {e}")
        return -1
