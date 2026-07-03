"""
Rédacteur Agent — Prompt Builder
Construit le prompt GPT pour générer l'article en allemand natif.
"""

from config import MIN_WORDS, MAX_WORDS, FORBIDDEN_PHRASES


def build_article_prompt(brief: dict) -> str:
    keyword = brief["keyword_principal"]
    keywords_secondaires = brief.get("keywords_secondaires", [])
    angle = brief.get("angle_recommande", "")
    format_article = brief.get("format", "ratgeber")
    faq_questions = brief.get("faq_questions", [])
    categorie = brief.get("categorie_wp", "")

    secondary_kw_list = "\n".join([
        f"- {kw['keyword']} (volume: {kw.get('volume', '?')}/mois)"
        for kw in keywords_secondaires[:5]
    ])

    faq_list = "\n".join([f"- {q}" for q in faq_questions[:5]]) if faq_questions else "Aucune"
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
- Sekundär-Keywords (natürlich einbauen, NICHT übertreiben):
{secondary_kw_list}

HÄUFIG GESTELLTE FRAGEN (als H2/H3 einbauen wenn relevant):
{faq_list}

---

KRITISCHE REGELN FÜR DEN INHALT:

⚠️ KEIN H1 IM ARTIKEL — WordPress fügt den Titel automatisch als H1 ein. Beginne direkt mit der Einleitung (normaler Text), dann H2 für die Abschnitte.

⚠️ KEIN BILD AM ANFANG — WordPress zeigt das Hauptbild automatisch. Füge kein Bild am Anfang des Artikels ein.

⚠️ KEYWORD-WIEDERHOLUNG BEGRENZEN — Das Keyword "{keyword}" darf maximal 1x pro 150 Wörter erscheinen. Verwende Synonyme und Variationen:
- Statt immer "{keyword}" → verwende auch: "Balkonpflanzen im Frühling", "Frühlingsbalkon", "Balkongarten", "Balkonbepflanzung"

⚠️ KEINE PLATZHALTLER — Schreibe KEINE [INTERNER LINK: xxx] Platzhalter. Wenn du interne Links brauchst, schreibe einfach den Text ohne Link-Markup.

---

PFLICHT-SEO-REGELN:
1. Keyword "{keyword}" im SEO-Titel (am Anfang, mit " –" getrennt, NIEMALS ":")
   ✅ "{keyword} – 15 Tipps für deinen Garten"
   ❌ "{keyword}: Tipps..."
2. Keyword in der Meta-Beschreibung (150-160 Zeichen)
3. Keyword im Slug
4. Keyword im ersten Satz der Einleitung
5. Keyword in mindestens einem H2 oder H3
6. Alt-Text des Hauptbildes = "{keyword}"
7. Keyword-Dichte: 0.8%-1.5% (NICHT mehr)
8. Mindestens 1 externer Link zu einer seriösen deutschen Gartenquelle (z.B. NABU, RHS, Mein schöner Garten)
9. Mindestens eine Zahl im SEO-Titel

---

ARTIKEL-STRUKTUR (Pflicht):
- Einleitung (150-200 Wörter): Keyword im ersten Satz, persönlicher Ton
- Inhaltsverzeichnis (einfache HTML-Tabelle mit H2-Links)
- 4-6 Hauptabschnitte (H2) mit je 1-2 Unterabschnitten (H3)
- FAQ-Abschnitt (H2) mit 2-3 echten Fragen
- Fazit (H2, 100-150 Wörter) + Call-to-Action
- Nach dem Fazit: [NEWSLETTER_BLOCK]

---

SCHREIBSTIL:
- Natürliches Deutsch eines leidenschaftlichen Gärtners
- Persönlicher Ton: "Ich empfehle...", "In meinem Garten..."
- Kurze Absätze (3-5 Sätze)
- Abwechslungsreiche Satzstrukturen
- Synonyme für das Keyword verwenden

VERBOTENE PHRASEN:
{forbidden_list}

---

LÄNGE: {MIN_WORDS}-{MAX_WORDS} Wörter

---

AUSGABE-FORMAT (exakt einhalten):

```
SEO_TITLE: [Titel hier - max 65 Zeichen]
META_DESCRIPTION: [150-160 Zeichen]
SLUG: [url-slug-hier]
FOCUS_KEYWORD: {keyword}
ALT_TEXT_MAIN_IMAGE: [Alt-Text mit exaktem Keyword]

---ARTIKEL_START---

[Vollständiger HTML-Artikel — OHNE H1, OHNE Bild am Anfang]
Beginne mit: <p>[Einleitungstext...]</p>
Dann: [Inhaltsverzeichnis als HTML-Tabelle]
Dann: <h2>...</h2> für jeden Abschnitt

---ARTIKEL_END---
```
"""
    return prompt
