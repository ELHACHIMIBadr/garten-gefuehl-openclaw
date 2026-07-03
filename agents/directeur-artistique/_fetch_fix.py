def fetch_image(query: str, save_path: str, keyword: str, category: str) -> dict:
    """
    Fetch une image avec anti-doublon MD5 fiable.
    Un seul téléchargement par candidat.
    Le hash est marqué DÈS la validation (pas après conversion).
    """
    MAX_REJECTIONS = 3
    rejected_count = 0

    all_candidates = []
    all_candidates.extend(search_pexels(query, per_page=10))
    all_candidates.extend(search_pixabay(query, per_page=10))

    print(f"[DA] {len(all_candidates)} candidats pour '{query}'")

    for i, candidate in enumerate(all_candidates):
        if rejected_count >= MAX_REJECTIONS:
            break

        url = candidate["url"]

        # 1. Vérifier historique global par URL
        if HISTORY_AVAILABLE and is_image_already_used(url):
            print(f"[DA] ⏭️ URL déjà utilisée (historique global)")
            continue

        # 2. Télécharger UNE SEULE FOIS
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            image_content = resp.content
        except Exception as e:
            print(f"[DA] Erreur téléchargement: {e}")
            continue

        # 3. Hash MD5 — vérifier doublon intra-article
        image_hash = hashlib.md5(image_content).hexdigest()
        if is_hash_used_in_current_article(image_hash):
            print(f"[DA] ⏭️ Image identique déjà dans cet article (MD5: {image_hash[:8]})")
            continue

        # 4. Marquer le hash IMMÉDIATEMENT (avant validation)
        # Évite que la même photo soit réessayée si validation échoue
        mark_hash_used_in_article(image_hash)

        # 5. Validation visuelle Codex
        print(f"[DA] Candidat {i+1} ({candidate['source']}) — validation Codex...")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(image_content)
            temp_path = f.name

        is_valid = validate_image_with_codex(temp_path, keyword, category)

        if is_valid:
            print(f"[DA] ✅ Image validée ({candidate['source']})")
            if download_and_convert_webp(image_content, save_path):
                if HISTORY_AVAILABLE:
                    add_image_to_history(url, keyword)
                return {
                    "path": save_path,
                    "source": candidate["source"],
                    "photographer": candidate["photographer"],
                    "source_url": candidate["source_url"],
                    "query": query,
                    "validated": True
                }
        else:
            rejected_count += 1
            print(f"[DA] ❌ Rejetée ({rejected_count}/{MAX_REJECTIONS})")

    # Fallback GPT-image-2
    print(f"[DA] 🔄 Fallback GPT-image-2")
    gpt_prompt = (
        f"Close-up photo of colorful spring flowers in balcony planter boxes. "
        f"Primroses, pansies, daffodils in full bloom. No buildings visible. "
        f"Natural daylight. No text. No watermarks."
    )
    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.images.generate(model=GPT_IMAGE_MODEL, prompt=gpt_prompt, size=GPT_IMAGE_SIZE, n=1)
        image_url = response.data[0].url
        resp = requests.get(image_url, timeout=15)
        if resp.status_code == 200:
            if download_and_convert_webp(resp.content, save_path):
                count = increment_gpt_image_count()
                print(f"[DA] GPT-image-2 générée (compteur: {count})")
                return {
                    "path": save_path, "source": "gpt_image",
                    "photographer": "AI Generated", "source_url": "",
                    "query": query, "validated": True
                }
    except Exception as e:
        print(f"[DA] Erreur GPT-image-2: {e}")

    print(f"[DA] ⚠️ Aucune image trouvée pour: {query}")
    return {}
