"""
Scout Agent — Telegram Notifications
Envoie les rapports au bot Telegram.
"""

import requests
import os


def send_telegram_message(message: str):
    """Envoie un message via le bot Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("[Scout] TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant")
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("[Scout] Notification Telegram envoyée")
            return True
        else:
            print(f"[Scout] Erreur Telegram: {resp.status_code}")
            return False
    except Exception as e:
        print(f"[Scout] Erreur Telegram: {e}")
        return False


def notify_brief_ready(brief: dict):
    """Notification quand un brief est prêt."""
    msg = (
        f"🔍 <b>Scout — Brief prêt</b>\n\n"
        f"📅 Date : {brief['date']}\n"
        f"🏷️ Catégorie : {brief['categorie_wp']} ({brief.get('traduction_fr_categorie', '')})\n"
        f"🔑 Keyword : <b>{brief['keyword_principal']}</b>\n"
        f"🇫🇷 Traduction : {brief['traduction_fr']}\n"
        f"📊 Volume : {brief['volume_mensuel']}/mois\n"
        f"💰 CPC : {brief['cpc']}€\n"
        f"📈 Trend : {brief['trend']}%\n"
        f"⭐ Score : {brief['score']}\n"
        f"📐 Angle : {brief['angle_recommande']}\n"
    )
    send_telegram_message(msg)


def notify_scout_error(error: str):
    """Notification en cas d'erreur."""
    msg = f"⚠️ <b>Scout — Erreur</b>\n\n{error}"
    send_telegram_message(msg)


def notify_scout_summary(total_collected: int, total_filtered: int, selected_keyword: str):
    """Résumé de la collecte."""
    msg = (
        f"📋 <b>Scout — Résumé collecte</b>\n\n"
        f"🔎 Keywords collectés : {total_collected}\n"
        f"✅ Après filtrage : {total_filtered}\n"
        f"🏆 Sélectionné : <b>{selected_keyword}</b>"
    )
    send_telegram_message(msg)
