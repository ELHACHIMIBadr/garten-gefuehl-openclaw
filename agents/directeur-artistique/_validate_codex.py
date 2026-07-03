def validate_image_with_codex(image_path: str, keyword: str, category: str) -> bool:
    """Valide visuellement une image via Codex CLI (-i flag)."""
    prompt = (
        f"Schau dir dieses Bild genau an.\n\n"
        f"AKZEPTIERT (antworte JA):\n"
        f"- Nahaufnahme von bunten Blumen oder Pflanzen\n"
        f"- Blühende Balkonkästen mit Blumen\n"
        f"- Topfpflanzen auf einem Balkon\n"
        f"- Gartenpflanzen in Blüte\n\n"
        f"ABGELEHNT (antworte NEIN):\n"
        f"- Gebäude oder Fassaden (auch mit Balkonen)\n"
        f"- Leere Balkone ohne Pflanzen\n"
        f"- Architekturfotos\n"
        f"- Stadtlandschaften\n"
        f"- Innenräume\n"
        f"- Bilder wo Pflanzen nur im Hintergrund sind\n\n"
        f"Antworte NUR mit JA oder NEIN. Kein weiterer Text."
    )

    import subprocess, os
    try:
        result = subprocess.run(
            ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-i", image_path],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60
        )
        output = result.stdout.strip().upper()
        print(f"[DA] Validation Codex : {output[:20]}")

        if "NEIN" in output or "NO" in output:
            return False
        return True

    except subprocess.TimeoutExpired:
        print(f"[DA] Timeout — refusée par sécurité")
        return False  # En cas de doute, refuser
    except Exception as e:
        print(f"[DA] Erreur Codex: {e} — refusée par sécurité")
        return False
    finally:
        if image_path and (image_path.startswith("/tmp/") or "Temp" in image_path):
            try:
                os.unlink(image_path)
            except:
                pass
