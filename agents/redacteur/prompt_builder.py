"""
Rédacteur Agent — Prompt Builder
Construit le prompt GPT pour générer l'article en allemand natif.
"""

from config import MIN_WORDS, MAX_WORDS, FORBIDDEN_PHRASES


def build_article_prompt(brief: dict) -> str:
    """
    Construit le prompt complet pour la rédaction de l'article.
    """
    keyword = brief["keyword_principal"]
    keywords_secondaires = brief.get("keywords_secondaires", [])
    angle = brief.get("angle_recommande", "")
    format_article = brief.get("format", "ratgeber")
    faq_questions = brief.get("faq_questions", [])
    categorie = brief.get("categorie_wp", "")
    traduction_fr = brief.get("traduction_fr", "")

    # Construire la liste des keywords secondaires
    secondary_kw_list = "\n".join([
        f"- {kw['keyword']} (volume: {kw.get('volume', '?')}/mois)"
        for kw in keywords_secondaires[:5]
    ])

    # Construire la liste des questions FAQ
    faq_list = "\n".join([f"- {q}" for q in faq_questions[:5]]) if faq_questions else "Aucune"

    # Construire la liste des phrases interdites
    forbidden_list = "\n".join([f"- \"{p}\"" for p in FORBIDDEN_PHRASES])

    prompt = f"""Du bist ein erfahrener deutscher Gartenexperte und Redakteur. Du schreibst leidenschaftliche, praxisnahe Gartenartikel für deutschsprachige Leser.

DEINE AUFGABE:
Schreibe einen vollständigen SEO-optimierten Artikel auf Deutsch für das Keyword: **{keyword}**

---

KEYWORD-DETAILS:
- Haupt-Keyword: {keyword}
- Kategorie: {categorie}
- Empfohlener Winkel: {angle}
- Format: {format_article}
- Sekundär-Keywords (natürlich einbauen):
{secondary_kw_list}

HÄUFIG GESTELLTE FRAGEN (als H2/H3 einbauen wenn relevant):
{faq_list}

---

PFLICHT-SEO-REGELN (alle müssen erfüllt sein):
1. Keyword "{keyword}" im SEO-Titel (am Anfang, getrennt durch Leerzeichen oder em-Dash "–", NIEMALS direkt gefolgt von Doppelpunkt)
   ✅ Richtig: "{keyword} – 15 Tipps für deinen Garten"
   ❌ Falsch: "{keyword}: Tipps..."
2. Keyword "{keyword}" in der Meta-Beschreibung (150-160 Zeichen)
3. Keyword "{keyword}" im Slug (URL-freundlich, Bindestriche statt Leerzeichen)
4. Keyword "{keyword}" in den ersten 10% des Textes (idealerweise erster Satz)
5. Keyword "{keyword}" in mindestens einem H2 oder H3
6. Alt-Text des Hauptbildes enthält "{keyword}" exakt
7. Keyword-Dichte: ~1-1.5% (nicht mehr, nicht weniger)
8. Mindestens 2-3 interne Verlinkungen (Platzhalter: [INTERNER LINK: Thema])
9. Mindestens 1 externer Link zu einer seriösen deutschen Gartenquelle
10. Mindestens eine Zahl im SEO-Titel (z.B. "15 Tipps", "7 Ideen")

---

ARTIKEL-STRUKTUR (Pflicht):
- SEO-Titel (H1): Keyword am Anfang + Zahl + Power-Wort
- Inhaltsverzeichnis (Tabelle mit H2-Links)
- Einleitung (150-200 Wörter): Keyword im ersten Satz, persönlicher Ton, Mehrwert versprechen
- 4-6 Hauptabschnitte (H2) mit je 1-2 Unterabschnitten (H3)
- Praktische Tipps/Listen wo sinnvoll
- Fazit (100-150 Wörter): Zusammenfassung + Call-to-Action
- Nach dem Fazit: [NEWSLETTER_BLOCK] als Platzhalter

---

SCHREIBSTIL:
- Natürliches Deutsch eines leidenschaftlichen Gärtners — KEIN Übersetzungsdeutsch
- Persönlicher Ton: "Ich empfehle...", "In meinem Garten...", "Meine Erfahrung zeigt..."
- Kurze Absätze (3-5 Sätze)
- Abwechslungsreiche Satzstrukturen
- Konkrete, umsetzbare Ratschläge
- Regionale Bezüge wenn sinnvoll (deutsches Klima, deutsche Pflanzensorten)

VERBOTENE PHRASEN (NIEMALS verwenden):
{forbidden_list}

---

LÄNGE: {MIN_WORDS}-{MAX_WORDS} Wörter (ohne Meta-Daten)

---

AUSGABE-FORMAT (exakt einhalten):

```
SEO_TITLE: [Titel hier]
META_DESCRIPTION: [Meta-Beschreibung hier, 150-160 Zeichen]
SLUG: [url-slug-hier]
FOCUS_KEYWORD: {keyword}
ALT_TEXT_MAIN_IMAGE: [Alt-Text mit exaktem Keyword]

---ARTIKEL_START---

[Vollständiger HTML-Artikel hier mit H1, H2, H3, Listen, etc.]

---ARTIKEL_END---
```

Schreibe jetzt den vollständigen Artikel. Keine Erklärungen, direkt mit dem Artikel beginnen.
"""
    return prompt


def build_translation_prompt(keyword_en: str) -> str:
    """
    Prompt pour traduire/adapter un keyword en allemand naturel.
    """
    return f"""Translate this keyword concept to natural German as used in German gardening searches: "{keyword_en}"
    
Return ONLY the German translation, no explanation. Maximum 5 words."""
