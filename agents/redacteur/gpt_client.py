"""
Rédacteur Agent — GPT Client
Appelle GPT via Codex CLI (quota Codex inclus dans GPT Plus).
Zéro coût API supplémentaire.
"""

import subprocess
import tempfile
import os
from config import MODEL


def call_gpt(prompt: str) -> str:
    """
    Appelle GPT via Codex CLI en mode non-interactif.
    Utilise le quota Codex inclus dans GPT Plus.
    """
    print(f"[Rédacteur] Appel GPT via Codex CLI ({MODEL})...")

    # Écrire le prompt dans un fichier temp pour éviter les problèmes d'encodage
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(prompt)
        prompt_file = f.name

    try:
        result = subprocess.run(
            [
                "codex", "exec",
                "--dangerously-bypass-approvals-and-sandbox",
                "-m", MODEL
            ],
            stdin=open(prompt_file, "r", encoding="utf-8"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180  # 3 minutes max
        )

        if result.returncode != 0:
            raise Exception(f"Codex CLI erreur: {result.stderr[:300]}")

        # Parser la sortie pour extraire uniquement la réponse de codex
        output = result.stdout
        response = _extract_codex_response(output)

        if not response:
            raise Exception(f"Impossible d'extraire la réponse Codex. Sortie brute: {output[:300]}")

        return response

    finally:
        os.unlink(prompt_file)


def _extract_codex_response(raw_output: str) -> str:
    """
    Extrait uniquement la réponse de GPT depuis la sortie Codex CLI.
    La sortie Codex contient des métadonnées (workdir, model, tokens used...).
    On extrait le texte entre "codex" et "tokens used".
    """
    lines = raw_output.split("\n")

    in_response = False
    response_lines = []

    for line in lines:
        # Début de la réponse après la ligne "codex"
        if line.strip() == "codex":
            in_response = True
            continue

        # Fin de la réponse avant "tokens used"
        if line.strip().startswith("tokens used"):
            break

        if in_response:
            response_lines.append(line)

    response = "\n".join(response_lines).strip()
    return response
