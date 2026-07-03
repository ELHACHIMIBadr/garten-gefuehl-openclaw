"""
Correcteur Agent — GPT Fixer
Utilise GPT via Codex CLI pour corriger les erreurs détectées.
"""

import subprocess
import tempfile
import os
from config import MODEL


def fix_article_with_gpt(article: dict, errors: list, warnings: list, brief: dict) -> dict:
    """
    Envoie l'article + la liste des erreurs à GPT pour correction.
    Retourne l'article corrigé.
    """
    keyword = brief["keyword_principal"]

    errors_text = "\n".join(errors) if errors else "Aucune erreur bloquante"
    warnings_text = "\n".join(warnings) if warnings else "Aucun avertissement"

    prompt = f"""Du bist ein erfahrener SEO-Korrektor für deutsche Gartenartikel.

AUFGABE: Korrigiere den folgenden Artikel und behefte alle aufgeführten SEO-Fehler.

HAUPT-KEYWORD: {keyword}

FEHLER (müssen behoben werden):
{errors_text}

WARNUNGEN (sollten verbessert werden):
{warnings_text}

ARTIKEL ZU KORRIGIEREN:
SEO_TITLE: {article.get('seo_title', '')}
META_DESCRIPTION: {article.get('meta_description', '')}
SLUG: {article.get('slug', '')}
FOCUS_KEYWORD: {keyword}
ALT_TEXT_MAIN_IMAGE: {article.get('alt_text_main_image', '')}

---ARTIKEL_START---
{article.get('html_content', '')}
---ARTIKEL_END---

KORREKTUREN:
1. Titel muss {keyword} am Anfang haben, max 65 Zeichen, mit Zahl
2. NIEMALS Doppelpunkt direkt nach dem Keyword (immer " –" verwenden)
3. Meta-Beschreibung: 120-160 Zeichen, Keyword enthalten
4. Keyword-Dichte: 0.8%-1.5%
5. Alle anderen Fehler beheben

Gib den korrigierten Artikel im EXAKT gleichen Format aus:
SEO_TITLE: [korrigierter Titel]
META_DESCRIPTION: [korrigierte Meta]
SLUG: [slug]
FOCUS_KEYWORD: {keyword}
ALT_TEXT_MAIN_IMAGE: [korrigierter Alt-Text mit Keyword]

---ARTIKEL_START---
[korrigierter HTML-Artikel]
---ARTIKEL_END---
"""

    result = _call_codex(prompt)
    return result


def _call_codex(prompt: str) -> str:
    """Appelle GPT via Codex CLI."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(prompt)
        prompt_file = f.name

    try:
        result = subprocess.run(
            ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-m", MODEL],
            stdin=open(prompt_file, "r", encoding="utf-8"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180
        )

        output = result.stdout.strip()

        # Nettoyer les métadonnées Codex
        lines = output.split("\n")
        content_lines = []
        skip_header = True

        for line in lines:
            if skip_header and line.strip() == "--------":
                skip_header = False
                continue
            if not skip_header:
                if line.strip().startswith("tokens used"):
                    break
                content_lines.append(line)

        cleaned = "\n".join(content_lines).strip()
        return cleaned if cleaned else output

    finally:
        os.unlink(prompt_file)
