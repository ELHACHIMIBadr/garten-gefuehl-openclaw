"""
Correcteur Agent — SEO Checker
Vérifie les 20 points SEO Rank Math + règles spécifiques Garten Gefühl.
"""

import re
from typing import List, Dict
from config import (
    TITLE_MIN_CHARS, TITLE_MAX_CHARS, META_MIN_CHARS, META_MAX_CHARS,
    SLUG_MAX_CHARS, KEYWORD_DENSITY_MIN, KEYWORD_DENSITY_MAX,
    MIN_WORDS, POWER_WORDS, FORBIDDEN_AI_PHRASES,
    MIN_H2_COUNT, MIN_H3_COUNT, REQUIRED_SECTIONS,
    TITLE_FORBIDDEN_PATTERNS
)


def normalize_umlauts(text: str) -> str:
    """Normalise les umlauts allemands pour comparaison avec les slugs."""
    return (text.lower()
        .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
        .replace("ß", "ss").replace(" ", "-"))


def strip_html(html: str) -> str:
    """Supprime les balises HTML."""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def count_words(html: str) -> int:
    """Compte les mots dans le HTML."""
    return len(strip_html(html).split())


def calculate_keyword_density(html: str, keyword: str) -> float:
    """Calcule la densité du keyword en %."""
    text = strip_html(html).lower()
    words = text.split()
    keyword_words = keyword.lower().split()
    keyword_count = 0

    for i in range(len(words) - len(keyword_words) + 1):
        if words[i:i+len(keyword_words)] == keyword_words:
            keyword_count += 1

    if not words:
        return 0.0

    return round((keyword_count / len(words)) * 100, 2)


def check_all_seo_rules(article: dict, brief: dict) -> Dict[str, list]:
    """
    Vérifie les 25 règles SEO.
    Retourne un dict avec errors, warnings, passed.
    """
    keyword = brief["keyword_principal"]
    keyword_lower = keyword.lower()

    seo_title = article.get("seo_title", "")
    meta_desc = article.get("meta_description", "")
    slug = article.get("slug", "")
    html_content = article.get("html_content", "")
    alt_text = article.get("alt_text_main_image", "")

    text_content = strip_html(html_content)
    text_lower = text_content.lower()
    title_lower = seo_title.lower()

    errors = []
    warnings = []
    passed = []

    # ============================================================
    # SEO DE BASE (6 points)
    # ============================================================

    # 1. Keyword dans le titre SEO
    if keyword_lower in title_lower:
        passed.append("✅ Keyword dans le titre SEO")
    else:
        errors.append(f"❌ Keyword '{keyword}' absent du titre SEO")

    # 2. Keyword dans la meta description
    if keyword_lower in meta_desc.lower():
        passed.append("✅ Keyword dans la meta description")
    else:
        errors.append(f"❌ Keyword '{keyword}' absent de la meta description")

    # 3. Keyword dans le slug (avec normalisation umlauts)
    keyword_normalized = normalize_umlauts(keyword)
    slug_normalized = slug.lower()
    if keyword_normalized in slug_normalized:
        passed.append("✅ Keyword dans le slug")
    else:
        # Vérification mot par mot
        keyword_words = keyword_lower.split()
        keyword_words_normalized = [normalize_umlauts(w) for w in keyword_words]
        if all(w in slug_normalized for w in keyword_words_normalized):
            passed.append("✅ Keyword dans le slug (mots normalisés)")
        else:
            errors.append(f"❌ Keyword '{keyword}' absent du slug (slug: {slug})")

    # 4. Keyword dans les premiers 10% du contenu
    total_chars = len(text_content)
    first_10pct = text_lower[:max(int(total_chars * 0.10), 200)]
    if keyword_lower in first_10pct:
        passed.append("✅ Keyword dans les premiers 10% du contenu")
    else:
        errors.append(f"❌ Keyword '{keyword}' absent des premiers 10% du contenu")

    # 5. Keyword présent dans le contenu (densité)
    density = calculate_keyword_density(html_content, keyword)
    if density >= KEYWORD_DENSITY_MIN:
        passed.append(f"✅ Keyword présent dans le contenu (densité: {density}%)")
    else:
        errors.append(f"❌ Densité keyword trop faible ({density}%, min {KEYWORD_DENSITY_MIN}%)")

    # 6. Nombre de mots minimum
    word_count = count_words(html_content)
    if word_count >= MIN_WORDS:
        passed.append(f"✅ Contenu suffisant ({word_count} mots)")
    else:
        errors.append(f"❌ Contenu trop court ({word_count} mots, min {MIN_WORDS})")

    # ============================================================
    # SEO SUPPLÉMENTAIRES (7 points)
    # ============================================================

    # 7. Keyword dans H2/H3
    h2h3_matches = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", html_content, re.IGNORECASE | re.DOTALL)
    h2h3_text = " ".join(h2h3_matches).lower()
    if keyword_lower in h2h3_text:
        passed.append("✅ Keyword dans un H2/H3")
    else:
        errors.append(f"❌ Keyword '{keyword}' absent des H2/H3")

    # 8. Alt text image principale contient le keyword
    if keyword_lower in alt_text.lower():
        passed.append("✅ Alt text image principale contient le keyword")
    else:
        errors.append(f"❌ Alt text image principale n'a pas le keyword exact")

    # 9. Densité keyword optimale
    if KEYWORD_DENSITY_MIN <= density <= KEYWORD_DENSITY_MAX:
        passed.append(f"✅ Densité keyword optimale ({density}%)")
    elif density > KEYWORD_DENSITY_MAX:
        warnings.append(f"⚠️ Densité keyword trop élevée ({density}%, max {KEYWORD_DENSITY_MAX}%)")

    # 10. URL < 75 caractères
    if len(slug) <= SLUG_MAX_CHARS:
        passed.append(f"✅ Slug dans la limite ({len(slug)} caractères)")
    else:
        warnings.append(f"⚠️ Slug trop long ({len(slug)} caractères, max {SLUG_MAX_CHARS})")

    # 11. Liens externes
    external_links = re.findall(r'href=["\']https?://(?!xn--garten-gefhl)[^"\']+["\']', html_content)
    if external_links:
        passed.append(f"✅ Liens externes présents ({len(external_links)})")
    else:
        warnings.append("⚠️ Aucun lien externe trouvé")

    # 12. Liens internes
    internal_links = re.findall(r'href=["\'][^"\']*xn--garten-gefhl[^"\']*["\']', html_content)
    internal_placeholders = re.findall(r'\[INTERNER LINK', html_content)
    if internal_links or internal_placeholders:
        passed.append("✅ Liens internes présents")
    else:
        warnings.append("⚠️ Aucun lien interne trouvé")

    # 13. Unicité keyword
    passed.append("✅ Unicité keyword (validée par le Scout)")

    # ============================================================
    # LISIBILITÉ DU TITRE (3 points)
    # ============================================================

    # 14. Keyword au début du titre
    keyword_pos = title_lower.find(keyword_lower)
    if keyword_pos != -1 and keyword_pos <= 5:
        passed.append("✅ Keyword au début du titre SEO")
    elif keyword_pos != -1 and keyword_pos <= 40:
        warnings.append(f"⚠️ Keyword pas tout à fait au début du titre (position {keyword_pos})")
    else:
        errors.append(f"❌ Keyword trop loin du début du titre (position {keyword_pos})")

    # 15. Power word dans le titre
    title_has_power = any(pw in title_lower for pw in POWER_WORDS)
    if title_has_power:
        passed.append("✅ Power word dans le titre")
    else:
        warnings.append("⚠️ Pas de power word dans le titre")

    # 16. Nombre dans le titre
    if re.search(r"\d", seo_title):
        passed.append("✅ Nombre dans le titre SEO")
    else:
        errors.append("❌ Pas de nombre dans le titre SEO")

    # ============================================================
    # LISIBILITÉ DU CONTENU (3 points)
    # ============================================================

    # 17. Table des matières
    has_toc = bool(re.search(r"inhaltsverzeichnis|table.of.contents|<nav|<ul.*toc", html_content, re.IGNORECASE))
    if has_toc:
        passed.append("✅ Table des matières présente")
    else:
        warnings.append("⚠️ Table des matières absente")

    # 18. Paragraphes courts
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html_content, re.IGNORECASE | re.DOTALL)
    long_paragraphs = [p for p in paragraphs if len(strip_html(p).split()) > 80]
    if not long_paragraphs:
        passed.append("✅ Paragraphes courts")
    else:
        warnings.append(f"⚠️ {len(long_paragraphs)} paragraphe(s) trop long(s) (>80 mots)")

    # 19. Images dans le contenu
    images = re.findall(r"<img|\[BILD_\d\]", html_content, re.IGNORECASE)
    if len(images) >= 2:
        passed.append(f"✅ Images dans le contenu ({len(images)} images)")
    else:
        warnings.append(f"⚠️ Peu d'images ({len(images)}) — recommandé: min 2")

    # ============================================================
    # RÈGLES SPÉCIFIQUES GARTEN GEFÜHL
    # ============================================================

    # 20. Règle critique : pas de ponctuation collée après keyword
    for pattern in TITLE_FORBIDDEN_PATTERNS:
        if (keyword_lower + pattern) in title_lower:
            errors.append(
                f"❌ RÈGLE CRITIQUE : keyword suivi de '{pattern}' dans le titre → utiliser ' –'"
            )

    # 21. Longueur du titre
    if len(seo_title) < TITLE_MIN_CHARS:
        errors.append(f"❌ Titre trop court ({len(seo_title)} chars, min {TITLE_MIN_CHARS})")
    elif len(seo_title) > TITLE_MAX_CHARS:
        errors.append(f"❌ Titre trop long ({len(seo_title)} chars, max {TITLE_MAX_CHARS})")
    else:
        passed.append(f"✅ Longueur du titre optimale ({len(seo_title)} chars)")

    # 22. Longueur meta description
    if len(meta_desc) < META_MIN_CHARS:
        errors.append(f"❌ Meta description trop courte ({len(meta_desc)} chars, min {META_MIN_CHARS})")
    elif len(meta_desc) > META_MAX_CHARS:
        errors.append(f"❌ Meta description trop longue ({len(meta_desc)} chars, max {META_MAX_CHARS})")
    else:
        passed.append(f"✅ Meta description optimale ({len(meta_desc)} chars)")

    # 23. Section Fazit présente
    if "fazit" in html_content.lower():
        passed.append("✅ Section Fazit présente")
    else:
        errors.append("❌ Section Fazit (conclusion) manquante")

    # 24. Structure H2/H3 suffisante
    h2_count = len(re.findall(r"<h2", html_content, re.IGNORECASE))
    h3_count = len(re.findall(r"<h3", html_content, re.IGNORECASE))
    if h2_count >= MIN_H2_COUNT:
        passed.append(f"✅ Structure H2 suffisante ({h2_count} H2)")
    else:
        errors.append(f"❌ Pas assez de H2 ({h2_count}, min {MIN_H2_COUNT})")

    if h3_count >= MIN_H3_COUNT:
        passed.append(f"✅ Structure H3 présente ({h3_count} H3)")
    else:
        warnings.append(f"⚠️ Peu de H3 ({h3_count})")

    # 25. Newsletter block présent
    if "[NEWSLETTER_BLOCK]" in html_content or "garten-newsletter-block" in html_content:
        passed.append("✅ Bloc newsletter présent")
    else:
        errors.append("❌ Bloc newsletter manquant")

    return {
        "errors": errors,
        "warnings": warnings,
        "passed": passed,
        "score": len(passed),
        "total": len(errors) + len(warnings) + len(passed)
    }


def check_ai_detection(html_content: str) -> List[str]:
    """Détecte les phrases typiques de rédaction IA."""
    issues = []
    content_lower = html_content.lower()

    for phrase in FORBIDDEN_AI_PHRASES:
        if phrase.lower() in content_lower:
            issues.append(f"Phrase IA détectée : '{phrase}'")

    return issues


def check_german_quality(html_content: str) -> List[str]:
    """Vérifications basiques de qualité allemande."""
    issues = []
    text = strip_html(html_content)

    umlauts = ["ä", "ö", "ü", "Ä", "Ö", "Ü", "ß"]
    has_umlauts = any(u in text for u in umlauts)
    if not has_umlauts:
        issues.append("⚠️ Texte sans umlauts — peut-être pas en allemand natif")

    sentences = re.split(r"[.!?]", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    if sentences:
        avg_length = sum(len(s.split()) for s in sentences) / len(sentences)
        if avg_length > 30:
            issues.append(f"⚠️ Phrases trop longues en moyenne ({avg_length:.0f} mots) — style IA possible")

    return issues
