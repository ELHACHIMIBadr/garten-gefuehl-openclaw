"""
Analyste Agent — Collecteur Pinterest Analytics

Utilise Pinterest API v5 Analytics.
Les tokens sont les mêmes que ceux du Distributeur (réutilisés depuis .env).
Note : Pinterest Analytics a un délai de ~2 jours.
"""

import requests
from datetime import date, timedelta
from config import PINTEREST_ACCOUNTS_TOKENS

PINTEREST_API_BASE = "https://api.pinterest.com/v5"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def collect_account_metrics(account_name: str, token: str, days_ago: int = 2) -> dict:
    """
    Collecte les métriques Pinterest Analytics pour un compte.

    Returns:
        dict avec impressions, saves, link_clicks, pin_clicks, top_pins
    """
    if not token:
        return _empty_pinterest_metrics(account_name)

    end_date = (date.today() - timedelta(days=days_ago)).isoformat()
    start_date = (date.today() - timedelta(days=days_ago + 1)).isoformat()

    try:
        # Métriques globales du compte
        resp = requests.get(
            f"{PINTEREST_API_BASE}/user_account/analytics",
            headers=_headers(token),
            params={
                "start_date": start_date,
                "end_date": end_date,
                "metric_types": "IMPRESSION,SAVE,PIN_CLICK,OUTBOUND_CLICK"
            },
            timeout=15
        )

        metrics = _empty_pinterest_metrics(account_name)
        metrics["period"] = f"{start_date} → {end_date}"

        if resp.status_code == 200:
            data = resp.json()
            # L'API retourne {metric_type: [{date, value}]}
            all_data = data.get("all", {}).get("daily_metrics", [])

            for day_data in all_data:
                for metric in day_data.get("data_status", []):
                    pass

            # Sommation sur la période
            if all_data:
                metrics["impressions"] = sum(
                    d.get("IMPRESSION", 0) for d in all_data
                    if isinstance(d.get("IMPRESSION"), (int, float))
                )
                metrics["saves"] = sum(
                    d.get("SAVE", 0) for d in all_data
                    if isinstance(d.get("SAVE"), (int, float))
                )
                metrics["pin_clicks"] = sum(
                    d.get("PIN_CLICK", 0) for d in all_data
                    if isinstance(d.get("PIN_CLICK"), (int, float))
                )
                metrics["link_clicks"] = sum(
                    d.get("OUTBOUND_CLICK", 0) for d in all_data
                    if isinstance(d.get("OUTBOUND_CLICK"), (int, float))
                )
        else:
            print(f"[Analyste] Pinterest {account_name} ({resp.status_code}): {resp.text[:100]}")

        # Top pins du compte
        metrics["top_pins"] = _get_top_pins(token, start_date, end_date)

        print(f"[Analyste] ✅ Pinterest {account_name} — "
              f"{metrics['impressions']} impressions | "
              f"{metrics['saves']} saves | "
              f"{metrics['link_clicks']} clics liens")
        return metrics

    except Exception as e:
        print(f"[Analyste] ❌ Pinterest {account_name} erreur: {e}")
        return _empty_pinterest_metrics(account_name)


def _get_top_pins(token: str, start_date: str, end_date: str, limit: int = 5) -> list:
    """Récupère les N pins les plus performants."""
    try:
        resp = requests.get(
            f"{PINTEREST_API_BASE}/user_account/analytics/top_pins",
            headers=_headers(token),
            params={
                "start_date": start_date,
                "end_date": end_date,
                "sort_by": "IMPRESSION",
                "metric_types": "IMPRESSION,SAVE,OUTBOUND_CLICK",
                "num_of_pins": limit
            },
            timeout=15
        )

        if resp.status_code == 200:
            data = resp.json()
            return [
                {
                    "pin_id": pin.get("id", ""),
                    "impressions": pin.get("metrics", {}).get("IMPRESSION", 0),
                    "saves": pin.get("metrics", {}).get("SAVE", 0),
                    "link_clicks": pin.get("metrics", {}).get("OUTBOUND_CLICK", 0)
                }
                for pin in data.get("pins", [])
            ]
    except:
        pass
    return []


def collect_all_accounts_metrics(days_ago: int = 2) -> dict:
    """
    Collecte les métriques Pinterest pour TOUS les comptes.

    Returns:
        {
          "accounts": {account_name: metrics_dict},
          "totals": {impressions, saves, link_clicks, pin_clicks}
        }
    """
    results = {"accounts": {}, "totals": {
        "impressions": 0, "saves": 0, "link_clicks": 0, "pin_clicks": 0
    }}

    for account_name, token in PINTEREST_ACCOUNTS_TOKENS.items():
        if not token:
            print(f"[Analyste] ⚠️ Token manquant pour {account_name} — skip")
            results["accounts"][account_name] = _empty_pinterest_metrics(account_name)
            continue

        metrics = collect_account_metrics(account_name, token, days_ago)
        results["accounts"][account_name] = metrics
        results["totals"]["impressions"] += metrics.get("impressions", 0)
        results["totals"]["saves"] += metrics.get("saves", 0)
        results["totals"]["link_clicks"] += metrics.get("link_clicks", 0)
        results["totals"]["pin_clicks"] += metrics.get("pin_clicks", 0)

    return results


def _empty_pinterest_metrics(account_name: str) -> dict:
    return {
        "account": account_name,
        "period": None,
        "impressions": 0,
        "saves": 0,
        "pin_clicks": 0,
        "link_clicks": 0,
        "top_pins": []
    }
