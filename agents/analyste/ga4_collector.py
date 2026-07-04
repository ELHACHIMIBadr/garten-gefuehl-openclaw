"""
Analyste Agent — Collecteur Google Analytics 4 (GA4)

Utilise la Google Analytics Data API v4.
Prérequis : pip install google-analytics-data google-auth
"""

import os
from datetime import date, timedelta
from config import GA4_PROPERTY_ID, GOOGLE_SERVICE_ACCOUNT_JSON


def _get_ga4_client():
    """Initialise le client GA4 via service account."""
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.oauth2 import service_account

        if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_JSON):
            raise FileNotFoundError(
                f"Service account JSON non trouvé : {GOOGLE_SERVICE_ACCOUNT_JSON}\n"
                f"Voir config.py pour les instructions de configuration."
            )

        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_JSON,
            scopes=["https://www.googleapis.com/auth/analytics.readonly"]
        )
        return BetaAnalyticsDataClient(credentials=credentials)

    except ImportError:
        raise ImportError("Installer : pip install google-analytics-data google-auth --break-system-packages")


def collect_daily_metrics(days_ago: int = 1) -> dict:
    """
    Collecte les métriques GA4 pour une journée donnée.

    Args:
        days_ago: 1 = hier, 7 = il y a 7 jours

    Returns:
        dict avec sessions, users, pageviews, bounce_rate, avg_session_duration,
              top_pages (list), traffic_sources (dict)
    """
    if not GA4_PROPERTY_ID:
        print("[Analyste] ⚠️ GA4_PROPERTY_ID non configuré — skip GA4")
        return _empty_ga4_metrics()

    try:
        from google.analytics.data_v1beta.types import (
            RunReportRequest, DateRange, Dimension, Metric, OrderBy
        )

        client = _get_ga4_client()
        target_date = (date.today() - timedelta(days=days_ago)).isoformat()

        # Métriques globales
        global_request = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=target_date, end_date=target_date)],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="screenPageViews"),
                Metric(name="bounceRate"),
                Metric(name="averageSessionDuration"),
                Metric(name="newUsers"),
            ]
        )
        global_resp = client.run_report(global_request)

        metrics = _empty_ga4_metrics()
        metrics["date"] = target_date

        if global_resp.rows:
            row = global_resp.rows[0]
            vals = [v.value for v in row.metric_values]
            metrics["sessions"] = int(float(vals[0])) if vals[0] else 0
            metrics["users"] = int(float(vals[1])) if vals[1] else 0
            metrics["pageviews"] = int(float(vals[2])) if vals[2] else 0
            metrics["bounce_rate"] = round(float(vals[3]) * 100, 1) if vals[3] else 0.0
            metrics["avg_session_duration_s"] = int(float(vals[4])) if vals[4] else 0
            metrics["new_users"] = int(float(vals[5])) if vals[5] else 0

        # Top pages (10 premières)
        pages_request = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=target_date, end_date=target_date)],
            dimensions=[Dimension(name="pagePath")],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="sessions"),
            ],
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"), desc=True)],
            limit=10
        )
        pages_resp = client.run_report(pages_request)

        metrics["top_pages"] = [
            {
                "path": row.dimension_values[0].value,
                "pageviews": int(float(row.metric_values[0].value)),
                "sessions": int(float(row.metric_values[1].value))
            }
            for row in pages_resp.rows
        ]

        # Sources de trafic
        sources_request = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=target_date, end_date=target_date)],
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[Metric(name="sessions")],
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
            limit=6
        )
        sources_resp = client.run_report(sources_request)

        metrics["traffic_sources"] = {
            row.dimension_values[0].value: int(float(row.metric_values[0].value))
            for row in sources_resp.rows
        }

        print(f"[Analyste] ✅ GA4 — {metrics['sessions']} sessions | {metrics['pageviews']} pageviews")
        return metrics

    except Exception as e:
        print(f"[Analyste] ❌ GA4 erreur: {e}")
        return _empty_ga4_metrics()


def collect_weekly_metrics() -> dict:
    """Collecte les métriques GA4 sur 7 jours."""
    if not GA4_PROPERTY_ID:
        return _empty_ga4_metrics()

    try:
        from google.analytics.data_v1beta.types import (
            RunReportRequest, DateRange, Dimension, Metric, OrderBy
        )

        client = _get_ga4_client()
        end_date = (date.today() - timedelta(days=1)).isoformat()
        start_date = (date.today() - timedelta(days=7)).isoformat()

        request = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[Dimension(name="date")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="screenPageViews"),
            ],
            order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))]
        )
        resp = client.run_report(request)

        daily_data = []
        total_sessions = 0
        total_users = 0
        total_pv = 0

        for row in resp.rows:
            day_date = row.dimension_values[0].value
            sessions = int(float(row.metric_values[0].value))
            users = int(float(row.metric_values[1].value))
            pv = int(float(row.metric_values[2].value))
            daily_data.append({"date": day_date, "sessions": sessions, "users": users, "pageviews": pv})
            total_sessions += sessions
            total_users += users
            total_pv += pv

        return {
            "period": f"{start_date} → {end_date}",
            "total_sessions": total_sessions,
            "total_users": total_users,
            "total_pageviews": total_pv,
            "avg_daily_sessions": round(total_sessions / 7, 1),
            "daily_breakdown": daily_data
        }

    except Exception as e:
        print(f"[Analyste] ❌ GA4 hebdo erreur: {e}")
        return {}


def _empty_ga4_metrics() -> dict:
    return {
        "date": None,
        "sessions": 0,
        "users": 0,
        "pageviews": 0,
        "bounce_rate": 0.0,
        "avg_session_duration_s": 0,
        "new_users": 0,
        "top_pages": [],
        "traffic_sources": {}
    }
