"""
Scout Agent — Scrapers
Scrape Google Autocomplete DE + Pinterest Autocomplete + FAQ (AlsoAsked/AnswerThePublic).
"""

import requests
import json
import time
import random
import re
from typing import List, Set


def scrape_google_autocomplete(keyword: str) -> List[str]:
    """
    Scrape Google Autocomplete pour un keyword donné (marché DE).
    Retourne une liste de suggestions.
    """
    suggestions = []
    url = "https://suggestqueries.google.com/complete/search"
    
    params = {
        "client": "firefox",
        "q": keyword,
        "hl": "de",
        "gl": "de"
    }
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if len(data) > 1 and isinstance(data[1], list):
                suggestions = data[1]
    except Exception as e:
        print(f"[Scout] Erreur Google Autocomplete pour '{keyword}': {e}")
    
    return suggestions


def scrape_google_autocomplete_extended(keyword: str) -> List[str]:
    """
    Scrape étendu : keyword + chaque lettre a-z pour plus de suggestions.
    """
    all_suggestions = set()
    
    # Base keyword
    base = scrape_google_autocomplete(keyword)
    all_suggestions.update(base)
    
    # keyword + lettre a-z
    for letter in "abcdefghijklmnopqrstuvwxyz":
        query = f"{keyword} {letter}"
        results = scrape_google_autocomplete(query)
        all_suggestions.update(results)
        time.sleep(random.uniform(0.3, 0.8))  # Anti-rate-limit
    
    return list(all_suggestions)


def scrape_pinterest_autocomplete(keyword: str) -> List[str]:
    """
    Scrape Pinterest Autocomplete (search suggestions).
    """
    suggestions = []
    url = "https://www.pinterest.com/resource/BaseSearchResource/get/"
    
    params = {
        "source_url": "/search/pins/?q=" + keyword.replace(" ", "%20"),
        "data": json.dumps({
            "options": {
                "query": keyword,
                "scope": "pins"
            },
            "context": {}
        })
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Extraction des guides/suggestions
            if "resource_response" in data:
                resource = data["resource_response"]
                if "data" in resource and "guides" in resource["data"]:
                    for guide in resource["data"]["guides"]:
                        if "display_name" in guide:
                            suggestions.append(guide["display_name"])
    except Exception as e:
        print(f"[Scout] Erreur Pinterest Autocomplete pour '{keyword}': {e}")
    
    # Fallback : Pinterest search suggest API alternative
    if not suggestions:
        suggestions = _pinterest_typeahead(keyword)
    
    return suggestions


def _pinterest_typeahead(keyword: str) -> List[str]:
    """
    Fallback Pinterest typeahead API.
    """
    suggestions = []
    url = f"https://www.pinterest.com/typeahead/?term={keyword.replace(' ', '+')}&type=query&count=20"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "items" in data:
                for item in data["items"]:
                    if "label" in item:
                        suggestions.append(item["label"])
    except Exception as e:
        print(f"[Scout] Erreur Pinterest Typeahead pour '{keyword}': {e}")
    
    return suggestions


def scrape_google_faq(keyword: str) -> List[str]:
    """
    Scrape les 'People Also Ask' / questions fréquentes via Google autocomplete
    en ajoutant des préfixes de questions allemands.
    """
    questions = []
    
    prefixes = [
        "wie ", "was ", "wann ", "warum ", "welche ",
        "wo ", "kann man ", "sollte man ", "muss man ",
        "ist ", "sind ", "gibt es "
    ]
    
    for prefix in prefixes:
        query = f"{prefix}{keyword}"
        results = scrape_google_autocomplete(query)
        # Filtrer seulement les résultats en forme de question
        for r in results:
            r_lower = r.lower()
            if any(r_lower.startswith(p) for p in prefixes) or "?" in r:
                questions.append(r)
        time.sleep(random.uniform(0.3, 0.6))
    
    return list(set(questions))


def collect_all_keywords(seed_keywords: List[str]) -> dict:
    """
    Collecte complète pour une liste de seed keywords.
    Retourne un dict avec les sources de chaque keyword trouvé.
    """
    keywords_data = {}
    
    for seed in seed_keywords:
        print(f"[Scout] Scraping Google pour '{seed}'...")
        google_results = scrape_google_autocomplete_extended(seed)
        for kw in google_results:
            kw_clean = kw.strip().lower()
            if kw_clean not in keywords_data:
                keywords_data[kw_clean] = {
                    "original": kw.strip(),
                    "sources": set(),
                    "faq": []
                }
            keywords_data[kw_clean]["sources"].add("google")
        
        print(f"[Scout] Scraping Pinterest pour '{seed}'...")
        pinterest_results = scrape_pinterest_autocomplete(seed)
        for kw in pinterest_results:
            kw_clean = kw.strip().lower()
            if kw_clean not in keywords_data:
                keywords_data[kw_clean] = {
                    "original": kw.strip(),
                    "sources": set(),
                    "faq": []
                }
            keywords_data[kw_clean]["sources"].add("pinterest")
        
        print(f"[Scout] Scraping FAQ pour '{seed}'...")
        faq_results = scrape_google_faq(seed)
        for kw_clean, kw_data in keywords_data.items():
            related_faqs = [q for q in faq_results if seed.lower() in q.lower()]
            kw_data["faq"].extend(related_faqs)
        
        time.sleep(random.uniform(1, 2))
    
    # Convertir sets en lists pour JSON serialization
    for kw_data in keywords_data.values():
        kw_data["sources"] = list(kw_data["sources"])
        kw_data["faq"] = list(set(kw_data["faq"]))[:5]  # Max 5 FAQs par keyword
    
    print(f"[Scout] Total keywords collectés : {len(keywords_data)}")
    return keywords_data
