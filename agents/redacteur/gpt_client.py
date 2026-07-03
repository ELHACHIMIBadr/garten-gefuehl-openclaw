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
            timeout=180
        )

        if result.returncode != 0:
            raise Exception(f"Codex CLI erreur: {result.stderr[:300]}")

        output = result.stdout.strip()

        if not output:
            raise Exception("Codex CLI a retourné une réponse vide")

        # Nettoyer les métadonnées Codex si présentes
        output = _clean_codex_output(output)

        return output

    finally:
        os.unlink(prompt_file)


def _clean_codex_output(raw_output: str) -> str:
    """
    Nettoie la sortie Codex CLI en supprimant les métadonnées.
    La réponse GPT commence soit directement, soit après les métadonnées.
    On détecte si la sortie commence par des métadonnées Codex ou directement par le contenu.
    """
    # Si la sortie contient les marqueurs de métadonnées Codex
    metadata_markers = [
        "OpenAI Codex",
        "workdir:",
        "model:",
        "provider:",
        "session id:"
    ]

    lines = raw_output.split("\n")
    content_start = 0

    # Chercher où commence le vrai contenu (après les métadonnées)
    in_header = False
    for i, line in enumerate(lines):
        if any(marker in line for marker in metadata_markers):
            in_header = True

        # La ligne "--------" marque la fin du header
        if in_header and line.strip() == "--------" and i > 2:
            content_start = i + 1
            in_header = False
            continue

        # Ligne "codex" seule = début de la réponse GPT
        if line.strip() == "codex" and i > 0:
            content_start = i + 1
            break

    # Extraire le contenu et supprimer "tokens used" à la fin
    content_lines = lines[content_start:]
    result_lines = []
    for line in content_lines:
        if line.strip().startswith("tokens used"):
            break
        result_lines.append(line)

    result = "\n".join(result_lines).strip()

    # Si rien trouvé, retourner la sortie brute complète
    if not result:
        return raw_output.strip()

    return result
