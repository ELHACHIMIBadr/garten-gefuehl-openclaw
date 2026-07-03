"""
Rédacteur Agent — Parser
Parse la sortie GPT et extrait les métadonnées + le contenu HTML.
"""

import re
from typing import dict as Dict, Optional


def parse_gpt_output(raw_output: str) -> dict:
    """
    Parse la sortie brute de GPT et extrait toutes les métadonnées + l'article HTML.
    Retourne un dict structuré.
    """
    result = {
        "seo_title": "",
        "meta_description": "",
        "slug": "",
        "focus_keyword": "",
        "alt_text_main_image": "",
        "html_content": "",
        "word_count": 0,
        "parse_errors": []
    }

    # Extraire SEO_TITLE
    title_match = re.search(r"SEO_TITLE:\s*(.+)", raw_output)
    if title_match:
        result["seo_title"] = title_match.group(1).strip()
    else:
        result["parse_errors"].append("SEO_TITLE manquant")

    # Extraire META_DESCRIPTION
    meta_match = re.search(r"META_DESCRIPTION:\s*(.+)", raw_output)
    if meta_match:
        result["meta_description"] = meta_match.group(1).strip()
    else:
        result["parse_errors"].append("META_DESCRIPTION manquant")

    # Extraire SLUG
    slug_match = re.search(r"SLUG:\s*(.+)", raw_output)
    if slug_match:
        result["slug"] = slug_match.group(1).strip().lower().replace(" ", "-")
    else:
        result["parse_errors"].append("SLUG manquant")

    # Extraire FOCUS_KEYWORD
    kw_match = re.search(r"FOCUS_KEYWORD:\s*(.+)", raw_output)
    if kw_match:
        result["focus_keyword"] = kw_match.group(1).strip()
    else:
        result["parse_errors"].append("FOCUS_KEYWORD manquant")

    # Extraire ALT_TEXT_MAIN_IMAGE
    alt_match = re.search(r"ALT_TEXT_MAIN_IMAGE:\s*(.+)", raw_output)
    if alt_match:
        result["alt_text_main_image"] = alt_match.group(1).strip()
    else:
        result["parse_errors"].append("ALT_TEXT_MAIN_IMAGE manquant")

    # Extraire le contenu HTML entre les marqueurs
    content_match = re.search(
        r"---ARTIKEL_START---\s*\n(.*?)\n\s*---ARTIKEL_END---",
        raw_output,
        re.DOTALL
    )
    if content_match:
        html_content = content_match.group(1).strip()
        result["html_content"] = html_content
        result["word_count"] = count_words(html_content)
    else:
        result["parse_errors"].append("Contenu article manquant (ARTIKEL_START/END non trouvé)")

    return result


def count_words(html_content: str) -> int:
    """Compte les mots dans le HTML (sans les balises)."""
    # Supprimer les balises HTML
    text = re.sub(r"<[^>]+>", " ", html_content)
    # Supprimer les espaces multiples
    text = re.sub(r"\s+", " ", text).strip()
    return len(text.split())


def validate_seo_title(title: str, keyword: str) -> list:
    """
    Valide le titre SEO selon les règles :
    - Keyword au début
    - Pas de ponctuation directement après le keyword
    - Contient un nombre
    - Contient un power word (si possible)
    """
    errors = []
    keyword_lower = keyword.lower()
    title_lower = title.lower()

    # Keyword doit être au début (dans les 40 premiers caractères)
    keyword_pos = title_lower.find(keyword_lower)
    if keyword_pos == -1:
        errors.append(f"Keyword '{keyword}' absent du titre SEO")
    elif keyword_pos > 40:
        errors.append(f"Keyword '{keyword}' trop loin du début du titre (position {keyword_pos})")

    # Vérifier que le keyword n'est pas suivi directement par ':'
    if keyword_lower + ":" in title_lower:
        errors.append(f"Keyword suivi directement par ':' — utiliser ' –' à la place")

    # Doit contenir un nombre
    if not re.search(r"\d", title):
        errors.append("Titre SEO ne contient pas de nombre")

    # Longueur recommandée
    if len(title) < 30:
        errors.append(f"Titre SEO trop court ({len(title)} caractères, min 30)")
    elif len(title) > 65:
        errors.append(f"Titre SEO trop long ({len(title)} caractères, max 65)")

    return errors


def validate_meta_description(meta: str, keyword: str) -> list:
    """Valide la meta description."""
    errors = []

    if keyword.lower() not in meta.lower():
        errors.append(f"Keyword '{keyword}' absent de la meta description")

    if len(meta) < 120:
        errors.append(f"Meta description trop courte ({len(meta)} caractères, min 120)")
    elif len(meta) > 160:
        errors.append(f"Meta description trop longue ({len(meta)} caractères, max 160)")

    return errors


def validate_content(html_content: str, keyword: str, min_words: int = 1500) -> list:
    """
    Validation basique du contenu HTML.
    """
    errors = []
    text = re.sub(r"<[^>]+>", " ", html_content)
    text_lower = text.lower()
    keyword_lower = keyword.lower()

    # Keyword dans les premiers 10% du texte
    total_chars = len(text)
    first_10pct = text_lower[:int(total_chars * 0.10)]
    if keyword_lower not in first_10pct:
        errors.append(f"Keyword '{keyword}' absent des premiers 10% du contenu")

    # Keyword dans un H2/H3
    h2h3_match = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", html_content, re.IGNORECASE | re.DOTALL)
    h2h3_text = " ".join(h2h3_match).lower()
    if keyword_lower not in h2h3_text:
        errors.append(f"Keyword '{keyword}' absent des H2/H3")

    # Nombre de mots minimum
    word_count = count_words(html_content)
    if word_count < min_words:
        errors.append(f"Article trop court ({word_count} mots, minimum {min_words})")

    # Présence du Fazit
    if "fazit" not in html_content.lower():
        errors.append("Section Fazit (conclusion) manquante")

    # Présence du placeholder newsletter
    if "[NEWSLETTER_BLOCK]" not in html_content:
        errors.append("Placeholder [NEWSLETTER_BLOCK] manquant")

    return errors
