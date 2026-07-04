"""
Analyste Agent — Constructeur de Rapports

Génère :
1. Rapport quotidien Telegram (KPIs concis)
2. Rapport stratégique hebdomadaire Telegram (tendances + recommandations)
"""

import os
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from config import ALERT_THRESHOLDS, REPORTS_DIR, ANALYTICS_DIR


def build_daily_telegram_report(
    ga4: dict,
    search_console: dict,
    pinterest: dict,
    articles_count: int = None
) -> str:
    """
    Construit le rapport Telegram quotidien.
    Format compact mais complet — KPIs essentiels d'un coup d'œil.
    """
    today = date.today().isoformat()
    lines = []

    # En-tête
    lines.append(f"📊 <b>Rapport quotidien — Garten Gefühl</b>")
    lines.append(f"📅 {today}")

    # Alertes critiques
    alerts = _check_alerts(ga4, search_console, pinterest)
    if alerts:
        lines.append("")
        lines.append("🚨 <b>ALERTES</b>")
        for alert in alerts:
            lines.append(f"  ⚠️ {alert}")

    # Google Analytics
    lines.append("")
    lines.append("🌐 <b>Google Analytics (hier)</b>")
    if ga4.get("sessions", 0) > 0:
        duration_min = ga4.get("avg_session_duration_s", 0) // 60
        duration_sec = ga4.get("avg_session_duration_s", 0) % 60
        lines.append(f"  📈 Sessions: <b>{ga4['sessions']}</b> | Users: {ga4['users']}")
        lines.append(f"  👁 Pageviews: {ga4['pageviews']} | Rebond: {ga4['bounce_rate']}%")
        lines.append(f"  ⏱ Durée moy: {duration_min}m{duration_sec:02d}s | Nouveaux: {ga4['new_users']}")

        # Top 3 pages
        top_pages = ga4.get("top_pages", [])[:3]
        if top_pages:
            lines.append(f"  🔝 Top pages:")
            for p in top_pages:
                path = p["path"][-40:] if len(p["path"]) > 40 else p["path"]
                lines.append(f"    • {path} ({p['pageviews']} vues)")
    else:
        lines.append(f"  — Pas encore de trafic (ou API non configurée)")

    # Search Console
    lines.append("")
    lines.append("🔍 <b>Search Console (J-3)</b>")
    if search_console.get("impressions", 0) > 0:
        lines.append(f"  🖱 Clics: <b>{search_console['clicks']}</b> | Impressions: {search_console['impressions']}")
        lines.append(f"  📊 CTR: {search_console['ctr']}% | Position moy: {search_console['position']}")

        top_queries = search_console.get("top_queries", [])[:3]
        if top_queries:
            lines.append(f"  🔑 Top requêtes:")
            for q in top_queries:
                lines.append(f"    • \"{q['query']}\" ({q['clicks']} clics, pos {q['position']})")
    else:
        lines.append(f"  — Pas encore de données (délai Search Console : 2-3 jours)")

    # Pinterest (totaux 5 comptes)
    lines.append("")
    lines.append("📌 <b>Pinterest (5 comptes, J-2)</b>")
    totals = pinterest.get("totals", {})
    if totals.get("impressions", 0) > 0:
        lines.append(f"  👁 Impressions: <b>{totals['impressions']:,}</b>")
        lines.append(f"  💾 Saves: {totals['saves']} | Clics: {totals['link_clicks']}")

        # Meilleur compte
        accounts = pinterest.get("accounts", {})
        if accounts:
            best = max(accounts.items(), key=lambda x: x[1].get("impressions", 0))
            lines.append(f"  🏆 Meilleur: {best[0]} ({best[1]['impressions']:,} impressions)")
    else:
        lines.append(f"  — Comptes en warm-up ou tokens non configurés")

    # Articles publiés
    if articles_count is not None:
        lines.append("")
        lines.append(f"📝 <b>Blog</b>: {articles_count} articles publiés au total")

    lines.append("")
    lines.append("─────────────────────")
    lines.append(f"<i>Prochain rapport demain à 07:00</i>")

    return "\n".join(lines)


def build_weekly_telegram_report(
    ga4_weekly: dict,
    sc_weekly: dict,
    pinterest_weekly: dict = None
) -> str:
    """
    Construit le rapport stratégique hebdomadaire.
    Inclut tendances, analyse et recommandations actionables.
    """
    lines = []
    period = ga4_weekly.get("period", "7 derniers jours")

    lines.append(f"📊 <b>Rapport hebdomadaire — Garten Gefühl</b>")
    lines.append(f"📅 Semaine du {period}")
    lines.append("")

    # Performance globale
    lines.append("═══ PERFORMANCE GLOBALE ═══")
    lines.append("")

    # GA4 hebdo
    lines.append("🌐 <b>Google Analytics</b>")
    total_sessions = ga4_weekly.get("total_sessions", 0)
    total_pv = ga4_weekly.get("total_pageviews", 0)
    avg_daily = ga4_weekly.get("avg_daily_sessions", 0)
    lines.append(f"  Sessions: <b>{total_sessions}</b> | Moy/jour: {avg_daily}")
    lines.append(f"  Pageviews: {total_pv} | Users: {ga4_weekly.get('total_users', 0)}")

    # Tendance GA4
    daily = ga4_weekly.get("daily_breakdown", [])
    if len(daily) >= 2:
        first_half = sum(d["sessions"] for d in daily[:len(daily)//2])
        second_half = sum(d["sessions"] for d in daily[len(daily)//2:])
        trend = "📈" if second_half > first_half else ("📉" if second_half < first_half else "➡️")
        trend_pct = round((second_half - first_half) / max(first_half, 1) * 100)
        lines.append(f"  Tendance: {trend} {'+' if trend_pct >= 0 else ''}{trend_pct}% (2e moitié vs 1ère)")

    lines.append("")

    # Search Console hebdo
    lines.append("🔍 <b>Search Console</b>")
    total_clicks = sc_weekly.get("total_clicks", 0)
    total_impressions = sc_weekly.get("total_impressions", 0)
    avg_ctr = sc_weekly.get("avg_ctr", 0)
    lines.append(f"  Clics: <b>{total_clicks}</b> | Impressions: {total_impressions:,}")
    lines.append(f"  CTR moyen: {avg_ctr}%")

    top_queries_w = sc_weekly.get("top_queries", [])[:5]
    if top_queries_w:
        lines.append(f"  🔑 Top 5 requêtes de la semaine:")
        for q in top_queries_w:
            lines.append(f"    • \"{q['query']}\" — {q['clicks']} clics, pos {q['position']}")

    lines.append("")

    # Recommandations stratégiques automatiques
    lines.append("═══ RECOMMANDATIONS ═══")
    lines.append("")
    recommendations = _generate_recommendations(ga4_weekly, sc_weekly, total_sessions, avg_ctr)
    for i, rec in enumerate(recommendations, 1):
        lines.append(f"  {i}. {rec}")

    lines.append("")
    lines.append("─────────────────────")
    lines.append(f"<i>Rapport généré automatiquement par Agent Analyste</i>")

    return "\n".join(lines)


def _check_alerts(ga4: dict, sc: dict, pinterest: dict) -> list:
    """Vérifie les seuils d'alerte et retourne une liste de messages d'alerte."""
    alerts = []
    thresholds = ALERT_THRESHOLDS

    if ga4.get("sessions", 0) < thresholds["min_daily_sessions"] and ga4.get("sessions") is not None:
        if ga4["sessions"] > 0:  # Pas d'alerte si 0 sessions (site trop récent)
            alerts.append(f"Trafic faible : {ga4['sessions']} sessions (seuil: {thresholds['min_daily_sessions']})")

    if sc.get("ctr", 0) > 0 and sc["ctr"] < thresholds["ctr_warning_threshold"] * 100:
        alerts.append(f"CTR faible : {sc['ctr']}% (seuil: {thresholds['ctr_warning_threshold'] * 100}%)")

    totals = pinterest.get("totals", {})
    if totals.get("impressions", 0) > 0:
        if totals["impressions"] < thresholds["min_pinterest_impressions"]:
            alerts.append(f"Impressions Pinterest faibles : {totals['impressions']}")

    return alerts


def _generate_recommendations(ga4_weekly: dict, sc_weekly: dict, total_sessions: int, avg_ctr: float) -> list:
    """Génère des recommandations automatiques basées sur les données."""
    recs = []

    # Trafic global
    if total_sessions < 50:
        recs.append("Continuer la publication quotidienne — trafic en phase de démarrage (normal)")
    elif total_sessions < 200:
        recs.append("Renforcer les mots-clés à longue traîne dans les nouveaux articles")

    # CTR Search Console
    if avg_ctr > 0:
        if avg_ctr < 2:
            recs.append(f"CTR {avg_ctr}% — optimiser les meta descriptions pour améliorer le taux de clic")
        elif avg_ctr > 5:
            recs.append(f"Excellent CTR ({avg_ctr}%) — dupliquer la formule de titre/meta sur les nouveaux articles")

    # Requêtes à fort potentiel (position 4-20, nombreuses impressions)
    top_queries = sc_weekly.get("top_queries", [])
    quick_wins = [q for q in top_queries if 4 <= q.get("position", 100) <= 20 and q.get("impressions", 0) > 10]
    if quick_wins:
        recs.append(
            f"Quick wins : renforcer les articles sur {', '.join([q['query'] for q in quick_wins[:2]])} "
            f"(pos {quick_wins[0].get('position', '?')}) pour passer en page 1"
        )

    # Pinterest
    if total_sessions > 0:
        recs.append("Créer des pins supplémentaires pour les articles les plus vus (réutiliser le DA manuellement)")

    if not recs:
        recs.append("Maintenir le rythme de publication — les données sont encore insuffisantes pour des recommandations ciblées")

    return recs


def save_report(report_type: str, data: dict):
    """Sauvegarde les données de rapport en JSON pour archivage."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    today = date.today().isoformat()
    filename = f"{today}_{report_type}.json"
    filepath = Path(REPORTS_DIR) / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "type": report_type,
            "data": data
        }, f, ensure_ascii=False, indent=2)

    print(f"[Analyste] Rapport sauvegardé : {filepath}")
    return str(filepath)
