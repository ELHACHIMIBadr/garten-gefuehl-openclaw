"""
Rédacteur Agent — Prompt Builder
Construit le prompt GPT pour générer l'article en allemand natif.

CHANGEMENT v2:
- GPT place 4 placeholders [BILD_1] à [BILD_4] dans le HTML aux bons endroits.
- Le Directeur Artistique remplace ces placeholders par les vraies <figure>.
- Élimine les bugs d'images dupliquées et d'images empilées.
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

⚠️ KEIN BILD AM ANFANG — Das Hauptbild wird von WordPress automatisch angezeigt. Platziere [BILD_1] NACH dem ersten Absatz, NICHT ganz am Anfang.

⚠️ KEYWORD-WIEDERHOLUNG BEGRENZEN — Das Keyword "{keyword}" darf maximal 1x pro 150 Wörter erscheinen. Verwende Synonyme und Variationen.

⚠️ KEINE LINK-PLATZHALTER — Schreibe KEINE [INTERNER LINK: xxx] Platzhalter. Kein Link-Markup im Text.

---

BILDPLATZHALTER-REGELN (KRITISCH — GENAU EINHALTEN):
Du musst genau 4 Bildplatzhalter im Artikel platzieren:
  [BILD_1] — Nach dem ersten Einleitungsabsatz (vor dem Inhaltsverzeichnis)
  [BILD_2] — Nach dem 2. Hauptabschnitt (H2)
  [BILD_3] — Nach dem 4. Hauptabschnitt (H2)
  [BILD_4] — Nach dem vorletzten Hauptabschnitt (H2), vor dem FAQ

⚠️ JEDER PLATZHALTER NUR 1x VERWENDEN — niemals [BILD_1] zweimal.
⚠️ PLATZHALTER NICHT LÖSCHEN oder in Text umwandeln — sie bleiben exakt so: [BILD_1], [BILD_2], [BILD_3], [BILD_4].
⚠️ MINDESTENS 200 WÖRTER TEXT zwischen zwei aufeinanderfolgenden Platzhaltern.

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
1. Einleitung (150-200 Wörter): Keyword im ersten Satz, persönlicher Ton
   [BILD_1]
2. Inhaltsverzeichnis (einfache HTML-Tabelle mit H2-Links)
3. 1. Hauptabschnitt (H2) mit je 1-2 Unterabschnitten (H3)
4. 2. Hauptabschnitt (H2)
   [BILD_2]
5. 3. Hauptabschnitt (H2) mit je 1-2 Unterabschnitten (H3)
6. 4. Hauptabschnitt (H2)
   [BILD_3]
7. 5. Hauptabschnitt (H2) mit je 1-2 Unterabschnitten (H3)
8. 6. Hauptabschnitt (H2) — optional
   [BILD_4]
9. FAQ-Abschnitt (H2) mit 2-3 echten Fragen
10. Fazit (H2, 100-150 Wörter) + Call-to-Action
11. [NEWSLETTER_BLOCK]

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

[Vollständiger HTML-Artikel — OHNE H1, OHNE Bild ganz am Anfang]
Beginne mit: <p>[Einleitungstext...]</p>
Dann sofort: [BILD_1]
Dann: [Inhaltsverzeichnis als HTML-Tabelle]
Dann: <h2>...</h2> für jeden Abschnitt
Mit [BILD_2], [BILD_3], [BILD_4] an den vorgeschriebenen Stellen.

---ARTIKEL_END---
```
"""
    return prompt
