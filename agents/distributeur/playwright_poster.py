"""
Distributeur Agent — Playwright Poster

Publie des pins Pinterest via navigateur Chromium automatisé (sans API officielle).
Headless sur VPS, avec gestion session cookies, retry 3x, anti-detection.

Flux par compte :
  1. Charger cookies session → skip login si toujours valide
  2. Sinon login email/password → sauvegarder cookies
  3. Naviguer vers de.pinterest.com/pin-creation-tool/
  4. Uploader image → Titre → Description (hashtags) → Lien → Tags (sans #) → Board → Publier
  5. Vérifier succès → retourner résultat

Selectors vérifiés sur l'interface Pinterest DE (juillet 2026) :
  - Titre       : placeholder "Erzähle allen, worum es bei deinem Pin geht."
  - Description : placeholder "Beschreibe deinen Pin"
  - Lien        : placeholder "Link hinzufügen"
  - Tags        : placeholder "Nach einem Tag suchen"
  - Board       : section "Pinnwand"
  - Publier     : bouton "Veröffentlichen"
"""

import os
import json
import time
import random
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
except ImportError:
    raise ImportError("Playwright non installé. Lancer : pip install playwright && playwright install chromium")


# ── Chemins sessions ─────────────────────────────────────────
SESSIONS_DIR = Path("/root/garten-gefuehl-openclaw/data/pinterest_sessions")
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


# ── Tags par niche (sans # — champ "Markierte Themen") ───────
NICHE_TAGS = {
    "Blumen": [
        "Blumen", "Gartenblumen", "Frühlingsgarten",
        "Pflanzen", "Blumengarten", "Blumenideen",
    ],
    "Balkon": [
        "Balkon", "Balkonpflanzen", "Balkonideen",
        "Stadtgarten", "Balkondeko", "Balkongestaltung",
    ],
    "Rosen": [
        "Rosen", "Rosengarten", "Rosenliebe",
        "Gartenrosen", "Rosenpflege", "Kletterrosen",
    ],
    "Terrasse": [
        "Terrasse", "Terrassengestaltung", "Gartenideen",
        "Outdoor", "Gartenmöbel", "Sichtschutz",
    ],
    "Garten Gefühl": [
        "Garten", "Gartengestaltung", "Gartenliebe",
        "Natur", "Garteninspiration", "Traumgarten",
    ],
}

# ── Description avec hashtags (champ "Beschreibung") ─────────
NICHE_HASHTAGS = {
    "Blumen":        "#Blumen #Gartenblumen #Frühlingsgarten #Pflanzen #Blumengarten",
    "Balkon":        "#Balkon #Balkonpflanzen #Balkonideen #Stadtgarten #Balkondeko",
    "Rosen":         "#Rosen #Rosenliebe #Rosengarten #Gartenrosen #Rosenpflege",
    "Terrasse":      "#Terrasse #Terrassengestaltung #Gartenideen #Outdoor #Garten",
    "Garten Gefühl": "#Garten #Gartengestaltung #Gartenliebe #Natur #Garteninspiration",
}


def build_description(categorie: str, title: str) -> str:
    hashtags = NICHE_HASHTAGS.get(categorie, "#Garten #Gartenideen")
    intro = f"✨ {title[:80]}" if title else f"Entdecke Ideen rund um {categorie}"
    return f"{intro}\n\n{hashtags}\n\n🌱 Mehr auf garten-gefühl.de"


def get_tags_for_niche(categorie: str) -> list:
    return NICHE_TAGS.get(categorie, ["Garten", "Gartenideen"])


# ── Gestion sessions ─────────────────────────────────────────

def _session_file(account_name: str) -> Path:
    slug = account_name.replace(" ", "_").replace("&", "und").replace("ü", "u").replace("Ü", "U")
    return SESSIONS_DIR / f"session_{slug}.json"


def _save_cookies(account_name: str, context):
    cookies = context.cookies()
    path = _session_file(account_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookies, f)
    print(f"[Playwright] 🍪 Session sauvegardée pour {account_name}")


def _load_cookies(account_name: str, context) -> bool:
    path = _session_file(account_name)
    if not path.exists():
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        print(f"[Playwright] 🍪 Session chargée pour {account_name}")
        return True
    except Exception as e:
        print(f"[Playwright] ⚠️ Erreur chargement session: {e}")
        return False


def _clear_session(account_name: str):
    path = _session_file(account_name)
    if path.exists():
        path.unlink()


def _delay(min_ms: int = 500, max_ms: int = 1500):
    time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


# ── Login ────────────────────────────────────────────────────

def _is_logged_in(page) -> bool:
    try:
        page.goto("https://www.pinterest.com/", timeout=15000)
        page.wait_for_load_state("networkidle", timeout=10000)
        _delay(1000, 2000)
        login_btn = page.query_selector('[data-test-id="simple-login-button"]')
        return login_btn is None
    except Exception:
        return False


def _login(page, email: str, password: str) -> bool:
    print(f"[Playwright] 🔐 Login Pinterest — {email[:20]}...")
    try:
        page.goto("https://www.pinterest.com/login/", timeout=20000)
        page.wait_for_load_state("networkidle", timeout=10000)
        _delay(1500, 3000)

        email_field = page.wait_for_selector('input[id="email"]', timeout=10000)
        email_field.click()
        _delay(300, 700)
        email_field.fill(email)
        _delay(500, 1000)

        pass_field = page.wait_for_selector('input[id="password"]', timeout=5000)
        pass_field.click()
        _delay(300, 700)
        pass_field.fill(password)
        _delay(800, 1500)

        # Soumettre et attendre la navigation complète
        with page.expect_navigation(timeout=15000, wait_until="networkidle"):
            pass_field.press("Enter")

        _delay(2000, 3000)

        current_url = page.url
        print(f"[Playwright] URL après login : {current_url[:80]}")

        if "security" in current_url or "challenge" in current_url:
            print(f"[Playwright] ⚠️ Challenge de sécurité détecté — skip")
            return False

        if "login" not in current_url and "pinterest.com" in current_url:
            print(f"[Playwright] ✅ Login réussi")
            return True

        # Vérifier erreur visible
        try:
            error = page.query_selector('[data-test-id="error-message"]')
            if error:
                print(f"[Playwright] ❌ Erreur login : {error.inner_text()[:100]}")
                return False
        except Exception:
            pass

        print(f"[Playwright] ⚠️ Login incertain → {current_url[:60]}")
        return True

    except PWTimeoutError:
        # Navigation timeout peut arriver si la page ne navigue pas (erreur credentials)
        try:
            current_url = page.url
            if "login" not in current_url and "pinterest.com" in current_url:
                print(f"[Playwright] ✅ Login réussi (navigation rapide)")
                return True
        except Exception:
            pass
        print(f"[Playwright] ❌ Timeout login")
        return False
    except Exception as e:
        print(f"[Playwright] ❌ Erreur login: {e}")
        return False


# ── Sélection board ──────────────────────────────────────────

def _select_board(page, board_name: str) -> bool:
    try:
        board_section = page.query_selector('[data-test-id="board-dropdown-select-button"]')
        if not board_section:
            board_section = page.get_by_text("Pinnwand").first
        if not board_section:
            print(f"[Playwright] ⚠️ Section Pinnwand introuvable")
            return False

        board_section.click()
        _delay(1000, 2000)

        board_options = page.query_selector_all('[data-test-id="board-row"]')
        for option in board_options:
            text = option.inner_text()
            if board_name.lower() in text.lower():
                option.click()
                _delay(500, 1000)
                print(f"[Playwright] ✅ Board sélectionné : {board_name}")
                return True

        if board_options:
            first_name = board_options[0].inner_text()[:40].strip()
            board_options[0].click()
            _delay(500, 1000)
            print(f"[Playwright] ⚠️ Board '{board_name}' non trouvé → '{first_name}'")
            return True

        print(f"[Playwright] ❌ Aucun board trouvé")
        return False

    except Exception as e:
        print(f"[Playwright] ❌ Erreur sélection board: {e}")
        return False


# ── Ajout des tags ───────────────────────────────────────────

def _add_tags(page, tags: list) -> bool:
    try:
        tag_field = page.query_selector('[placeholder="Nach einem Tag suchen"]')
        if not tag_field:
            tag_field = page.query_selector('[data-test-id="pin-draft-topic-tags"] input')
        if not tag_field:
            print(f"[Playwright] ⚠️ Champ tags non trouvé — skippé")
            return False

        tags_added = 0
        for tag in tags[:6]:
            tag_field.click()
            _delay(200, 400)
            tag_field.fill(tag)
            _delay(600, 1000)

            try:
                suggestion = page.wait_for_selector(
                    '[data-test-id="tag-autocomplete-option"]',
                    timeout=2000
                )
                if suggestion:
                    suggestion.click()
                    _delay(300, 500)
                    tags_added += 1
                    continue
            except Exception:
                pass

            tag_field.press("Enter")
            _delay(300, 500)
            tags_added += 1

        print(f"[Playwright] 🏷️ {tags_added} tags ajoutés")
        return True

    except Exception as e:
        print(f"[Playwright] ⚠️ Erreur ajout tags: {e}")
        return False


# ── Post pin principal ───────────────────────────────────────

def post_pin(
    account_name: str,
    email: str,
    password: str,
    image_path: str,
    title: str,
    description: str,
    board_name: str,
    categorie: str,
    link: str = None,
    headless: bool = True,
) -> dict:
    result = {"success": False, "pin_url": None, "error": None}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1280,900",
            ]
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="de-DE",
        )

        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        """)

        page = context.new_page()

        try:
            # ── 1. Session ────────────────────────────────────
            session_loaded = _load_cookies(account_name, context)
            logged_in = False

            if session_loaded:
                logged_in = _is_logged_in(page)

            if not logged_in:
                _clear_session(account_name)
                logged_in = _login(page, email, password)
                if logged_in:
                    _save_cookies(account_name, context)
                else:
                    result["error"] = "Login échoué"
                    return result

            # ── 2. Pin creation tool ──────────────────────────
            print(f"[Playwright] 🎨 Ouverture pin-creation-tool...")
            page.goto("https://de.pinterest.com/pin-creation-tool/", timeout=20000)
            page.wait_for_load_state("networkidle", timeout=15000)
            _delay(2000, 3000)

            # ── 3. Upload image ───────────────────────────────
            print(f"[Playwright] 📤 Upload : {Path(image_path).name}")
            file_input = page.wait_for_selector('input[type="file"]', timeout=10000)
            file_input.set_input_files(image_path)
            _delay(3000, 5000)

            # ── 4. Titre ──────────────────────────────────────
            print(f"[Playwright] ✍️ Titre : {title[:50]}...")
            title_field = page.wait_for_selector(
                '[placeholder="Erzähle allen, worum es bei deinem Pin geht."]',
                timeout=10000
            )
            title_field.click()
            _delay(300, 600)
            title_field.fill(title[:100])
            _delay(500, 1000)

            # ── 5. Description ────────────────────────────────
            print(f"[Playwright] 📝 Description...")
            try:
                desc_field = page.wait_for_selector(
                    '[placeholder="Beschreibe deinen Pin"]',
                    timeout=5000
                )
                desc_field.click()
                _delay(200, 500)
                desc_field.fill(description[:500])
                _delay(400, 800)
            except Exception:
                print(f"[Playwright] ⚠️ Champ description non trouvé — skippé")

            # ── 6. Lien ───────────────────────────────────────
            if link:
                print(f"[Playwright] 🔗 Lien : {link[:60]}...")
                try:
                    link_field = page.wait_for_selector(
                        '[placeholder="Link hinzufügen"]',
                        timeout=8000
                    )
                    link_field.click()
                    _delay(300, 600)
                    link_field.fill(link)
                    _delay(500, 1000)
                    link_field.press("Tab")
                    _delay(800, 1500)
                except PWTimeoutError:
                    print(f"[Playwright] ⚠️ Champ lien non trouvé — pin sans lien")

            # ── 7. Tags ───────────────────────────────────────
            tags = get_tags_for_niche(categorie)
            _add_tags(page, tags)

            # ── 8. Board ──────────────────────────────────────
            board_ok = _select_board(page, board_name)
            if not board_ok:
                result["error"] = f"Board '{board_name}' introuvable"
                return result

            # ── 9. Publier ────────────────────────────────────
            print(f"[Playwright] 🚀 Publication...")
            try:
                publish_btn = page.wait_for_selector(
                    'button[data-test-id="board-dropdown-save-button"]',
                    timeout=8000
                )
            except PWTimeoutError:
                publish_btn = page.get_by_role("button", name="Veröffentlichen").first

            publish_btn.click()
            _delay(3000, 6000)

            # ── 10. Vérification succès ───────────────────────
            current_url = page.url
            if "pin/" in current_url and "creation-tool" not in current_url:
                result["success"] = True
                result["pin_url"] = current_url
                print(f"[Playwright] ✅ Pin publié : {current_url[:80]}")
            else:
                try:
                    page.wait_for_selector(
                        '[data-test-id="pin-success-toast"], [data-test-id="toast"]',
                        timeout=4000
                    )
                    result["success"] = True
                    print(f"[Playwright] ✅ Pin publié (toast détecté)")
                except Exception:
                    error_el = page.query_selector('[data-test-id="error-message"]')
                    if error_el:
                        result["error"] = f"Erreur Pinterest: {error_el.inner_text()[:100]}"
                    else:
                        result["success"] = True
                        print(f"[Playwright] ✅ Pin publié (aucune erreur détectée)")

        except PWTimeoutError as e:
            result["error"] = f"Timeout: {str(e)[:100]}"
            print(f"[Playwright] ❌ {result['error']}")
        except Exception as e:
            result["error"] = f"Erreur: {str(e)[:150]}"
            print(f"[Playwright] ❌ {result['error']}")
        finally:
            try:
                context.close()
                browser.close()
            except Exception:
                pass

    return result


# ── Retry wrapper ────────────────────────────────────────────

def post_pin_with_retry(
    account_name: str,
    email: str,
    password: str,
    image_path: str,
    title: str,
    description: str,
    board_name: str,
    categorie: str,
    link: str = None,
    max_retries: int = 3,
    headless: bool = True,
) -> dict:
    """Retry 3x. Force re-login au 2ème essai."""
    for attempt in range(1, max_retries + 1):
        print(f"[Playwright] Tentative {attempt}/{max_retries} — {account_name}")

        if attempt == 2:
            print(f"[Playwright] 🔄 Re-login forcé")
            _clear_session(account_name)

        result = post_pin(
            account_name=account_name,
            email=email,
            password=password,
            image_path=image_path,
            title=title,
            description=description,
            board_name=board_name,
            categorie=categorie,
            link=link,
            headless=headless,
        )

        if result["success"]:
            return result

        if attempt < max_retries:
            wait = random.randint(30, 60)
            print(f"[Playwright] ⏳ Retry dans {wait}s (erreur: {result.get('error', '?')})")
            time.sleep(wait)

    result["error"] = f"Échec après {max_retries} tentatives: {result.get('error', '?')}"
    print(f"[Playwright] ❌ {result['error']}")
    return result
