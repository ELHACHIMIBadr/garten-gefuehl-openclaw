"""
Analyste Agent — Collecteur Google Search Console

Utilise la Google Search Console API.
Prérequis : pip install google-api-python-client google-auth
Note : Search Console a un délai de ~2 jours → données d'avant-hier au minimum.
"""

import os
from datetime import date, timedelta
from config import SEARCH_CONSOLE_SITE, GOOGLE_SERVICE_ACCOUNT_JSON


def _get_sc_service():
    """Initialise le service Search Console via service account."""
    try:
        from googleapiclient.discovery import build
        from google.oauth2 import service_account

        if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_JSON):
            raise FileNotFoundError(f"Service account JSON non trouvé : {GOOGLE_SERVICE_ACCOUNT_JSON}")

        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_JSON,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
        )
        return build("searchconsole", "v1", credentials=credentials, cache_discovery=False)

    except ImportError:
        raise ImportError("Installer : pip install google-api-python-client google-auth --break-system-packages")


def collect_daily_metrics(days_ago: int = 3) -> dict:
    """
    Collecte les métriques Search Console pour une période donnée.
    Note : Search Console a un délai de 2-3 jours → utiliser days_ago=3 minimum.

    Returns:
        dict avec clicks, impressions, ctr, position, top_queries, top_pages
    """
    if not SEARCH_CONSOLE_SITE:
        print("[Analyste] ⚠️ SEARCH_CONSOLE_SITE non configuré — skip SC")
        return _empty_sc_metrics()

    try:
        service = _get_sc_service()
        end_date = (date.today() - timedelta(days=days_ago)).isoformat()
        start_date = (date.today() - timedelta(days=days_ago + 1)).isoformat()

        # Métriques globales
        global_response = service.searchanalytics().query(
            siteUrl=SEARCH_CONSOLE_SITE,
            body={
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": [],
                "rowLimit": 1
            }
        ).execute()

        metrics = _empty_sc_metrics()
        metrics["period"] = f"{start_date} → {end_date}"

        rows = global_response.get("rows", [])
        if rows:
            row = rows[0]
            metrics["clicks"] = row.get("clicks", 0)
            metrics["impressions"] = row.get("impressions", 0)
            metrics["ctr"] = round(row.get("ctr", 0) * 100, 2)
            metrics["position"] = round(row.get("position", 0), 1)

        # Top 10 requêtes
        queries_response = service.searchanalytics().query(
            siteUrl=SEARCH_CONSOLE_SITE,
            body={
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["query"],
                "rowLimit": 10,
                "orderBy": [{"fieldName": "clicks", "sortOrder": "DESCENDING"}]
            }
        ).execute()

        metrics["top_queries"] = [
            {
                "query": row.get("keys", [""])[0],
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1)
            }
            for row in queries_response.get("rows", [])
        ]

        # Top 10 pages
        pages_response = service.searchanalytics().query(
            siteUrl=SEARCH_CONSOLE_SITE,
            body={
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["page"],
                "rowLimit": 10,
                "orderBy": [{"fieldName": "clicks", "sortOrder": "DESCENDING"}]
            }
        ).execute()

        metrics["top_pages"] = [
            {
                "page": row.get("keys", [""])[0],
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "position": round(row.get("position", 0), 1)
            }
            for row in pages_response.get("rows", [])
        ]

        print(f"[Analyste] ✅ Search Console — {metrics['clicks']} clics | "
              f"CTR: {metrics['ctr']}% | Pos: {metrics['position']}")
        return metrics

    except Exception as e:
        print(f"[Analyste] ❌ Search Console erreur: {e}")
        return _empty_sc_metrics()


def collect_weekly_metrics() -> dict:
    """Collecte les métriques Search Console sur 7 jours."""
    if not SEARCH_CONSOLE_SITE:
        return {}

    try:
        service = _get_sc_service()
        end_date = (date.today() - timedelta(days=3)).isoformat()
        start_date = (date.today() - timedelta(days=10)).isoformat()

        # Données par jour
        daily_response = service.searchanalytics().query(
            siteUrl=SEARCH_CONSOLE_SITE,
            body={
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["date"],
                "rowLimit": 10
            }
        ).execute()

        daily_data = [
            {
                "date": row.get("keys", [""])[0],
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1)
            }
            for row in daily_response.get("rows", [])
        ]

        total_clicks = sum(r["clicks"] for r in daily_data)
        total_impressions = sum(r["impressions"] for r in daily_data)

        # Top requêtes sur la semaine
        queries_response = service.searchanalytics().query(
            siteUrl=SEARCH_CONSOLE_SITE,
            body={
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["query"],
                "rowLimit": 20,
                "orderBy": [{"fieldName": "impressions", "sortOrder": "DESCENDING"}]
            }
        ).execute()

        return {
            "period": f"{start_date} → {end_date}",
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "avg_ctr": round(total_clicks / total_impressions * 100, 2) if total_impressions else 0,
            "daily_breakdown": daily_data,
            "top_queries": [
                {
                    "query": row.get("keys", [""])[0],
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "position": round(row.get("position", 0), 1)
                }
                for row in queries_response.get("rows", [])
            ]
        }

    except Exception as e:
        print(f"[Analyste] ❌ Search Console hebdo erreur: {e}")
        return {}


def _empty_sc_metrics() -> dict:
    return {
        "period": None,
        "clicks": 0,
        "impressions": 0,
        "ctr": 0.0,
        "position": 0.0,
        "top_queries": [],
        "top_pages": []
    }
