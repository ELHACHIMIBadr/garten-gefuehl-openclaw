def inject_images_in_html(html_content: str, images: list) -> str:
    """
    Injecte les images dans le HTML.
    Règle simple et robuste :
    - Trouve tous les blocs </p>
    - Injecte une image toutes les N balises </p> (espacées)
    - Distance minimum de 500 chars entre deux images
    - Ne jamais injecter dans les 1000 premiers chars (intro + TOC)
    """
    import re

    if not images:
        return html_content

    p_positions = [m.end() for m in re.finditer(r"</p>", html_content, re.IGNORECASE)]

    if not p_positions:
        return html_content

    result = html_content
    offset = 0
    image_index = 0
    last_inject_pos = 1000  # Skip l'intro et la table des matières

    # Espacer les images : injecter toutes les ~3 balises </p>
    step = max(1, len(p_positions) // (len(images) + 1))

    for j, pos in enumerate(p_positions):
        if image_index >= len(images):
            break

        # Skip les premières positions (intro + TOC)
        if pos < 1000:
            continue

        # Respecter l'espacement minimum
        if pos - last_inject_pos < 500:
            continue

        # Injecter toutes les `step` balises </p>
        if j % step != 0:
            continue

        img = images[image_index]
        img_html = (
            f'\n<figure class="wp-block-image size-large" style="margin:25px 0;">'
            f'<img src="{img.get("url", img.get("path", ""))}" '
            f'alt="{img.get("alt_text", "")}" loading="lazy" /></figure>\n'
        )

        inject_pos = pos + offset
        result = result[:inject_pos] + img_html + result[inject_pos:]
        offset += len(img_html)
        last_inject_pos = pos
        image_index += 1

    print(f"[DA] {image_index} images injectées dans le HTML")
    return result
