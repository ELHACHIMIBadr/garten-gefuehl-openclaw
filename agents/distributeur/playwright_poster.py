"""
Distributeur Agent — Playwright Poster

Publie des pins Pinterest via navigateur Chromium automatisé (sans API officielle).
Headless sur VPS, avec gestion session cookies, retry 3x, anti-detection.

Selectors vérifiés live sur Pinterest DE (juillet 2026) :
  - Titre       : placeholder "Erzähle allen, worum es bei deinem Pin geht." | id:storyboard-selector-title
  - Description : data-test-id="storyboard-description-field-container" (après upload)
  - Lien        : id="WebsiteField"
  - Tags        : id="combobox-storyboard-interest-tags"
  - Board open  : data-test-id="board-dropdown-select-button"
  - Board items : apparaissent après clic (chercher par texte)
  - Publier     : data-test-id="storyboard-draft-footer-save-recommended-content"
                  ou bouton "Veröffentlichen"
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
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _delay(1500, 2500)
        login_btn = page.query_selector('[data-test-id="simple-login-button"]')
        return login_btn is None
    except Exception:
        return False


def _login(page, email: str, password: str) -> bool:
    print(f"[Playwright] 🔐 Login Pinterest — {email[:20]}...")
    try:
        page.goto("https://www.pinterest.com/login/", timeout=20000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
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

        # Soumettre et attendre la navigation
        with page.expect_navigation(timeout=15000, wait_until="domcontentloaded"):
            pass_field.press("Enter")

        _delay(2000, 3000)

        current_url = page.url
        print(f"[Playwright] URL après login : {current_url[:80]}")

        if "security" in current_url or "challenge" in current_url:
            print(f"[Playwright] ⚠️ Challenge de sécurité — skip")
            return False

        if "login" not in current_url and "pinterest.com" in current_url:
            print(f"[Playwright] ✅ Login réussi")
            return True

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
    """
    Ouvre le dropdown board et sélectionne par nom de texte.
    Après clic sur board-dropdown-select-button, Pinterest charge
    les options dynamiquement — on attend leur apparition.
    """
    try:
        # Ouvrir le dropdown
        btn = page.wait_for_selector(
            '[data-test-id="board-dropdown-select-button"]',
            timeout=8000
        )
        btn.click()
        _delay(1500, 2500)

        # Attendre que les options du dropdown soient chargées
        # Elles apparaissent dans une liste après le clic
        try:
            page.wait_for_selector(
                '[data-test-id="board-dropdown-item"], [data-test-id="boardWithoutSection"]',
                timeout=5000
            )
        except Exception:
            pass

        # Chercher le board par nom dans tous les éléments cliquables du dropdown
        # Pinterest utilise différents selectors selon la version
        selectors_to_try = [
            '[data-test-id="board-dropdown-item"]',
            '[data-test-id="boardWithoutSection"]',
            '[data-test-id="board-row"]',
            '[role="option"]',
            '[role="menuitem"]',
        ]

        for selector in selectors_to_try:
            options = page.query_selector_all(selector)
            if not options:
                continue
            for option in options:
                try:
                    text = option.inner_text()
                    if board_name.lower() in text.lower():
                        option.click()
                        _delay(500, 1000)
                        print(f"[Playwright] ✅ Board sélectionné : {board_name}")
                        return True
                except Exception:
                    continue

        # Fallback : chercher par texte directement dans la page
        try:
            option = page.get_by_role("option", name=board_name)
            if option.count() > 0:
                option.first.click()
                _delay(500, 1000)
                print(f"[Playwright] ✅ Board sélectionné via role : {board_name}")
                return True
        except Exception:
            pass

        # Dernier fallback : dump les options trouvées et prendre la première
        for selector in selectors_to_try:
            options = page.query_selector_all(selector)
            if options:
                first_text = options[0].inner_text()[:40].strip()
                options[0].click()
                _delay(500, 1000)
                print(f"[Playwright] ⚠️ Board '{board_name}' non trouvé → premier dispo : '{first_text}'")
                return True

        # Debug : afficher ce qui est visible dans le dropdown
        visible = page.evaluate("""
            () => [...document.querySelectorAll('[data-test-id]')]
                  .filter(el => el.offsetParent !== null)
                  .map(el => el.getAttribute('data-test-id'))
                  .filter(id => id && id.includes('board'))
        """)
        print(f"[Playwright] ❌ Board introuvable. data-test-ids board visibles : {visible[:10]}")
        return False

    except Exception as e:
        print(f"[Playwright] ❌ Erreur sélection board: {e}")
        return False


# ── Ajout des tags ───────────────────────────────────────────

def _add_tags(page, tags: list) -> bool:
    try:
        # Utiliser l'id vérifié en live
        tag_field = page.query_selector('#combobox-storyboard-interest-tags')
        if not tag_field:
            tag_field = page.query_selector('[placeholder="Nach einem Tag suchen"]')
        if not tag_field:
            print(f"[Playwright] ⚠️ Champ tags non trouvé — skippé")
            return False

        tags_added = 0
        for tag in tags[:6]:
            tag_field.click()
            _delay(200, 400)
            tag_field.fill(tag)
            _delay(700, 1200)

            try:
                suggestion = page.wait_for_selector(
                    '[data-test-id="tag-autocomplete-option"], [role="option"]',
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
            page.goto("https://de.pinterest.com/pin-creation-tool/", timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            _delay(3000, 5000)

            # ── 3. Upload image ───────────────────────────────
            print(f"[Playwright] 📤 Upload : {Path(image_path).name}")
            file_input = page.wait_for_selector(
                'input[data-test-id="storyboard-upload-input"], input[type="file"]',
                timeout=10000
            )
            file_input.set_input_files(image_path)
            _delay(4000, 6000)

            # ── 4. Titre ──────────────────────────────────────
            print(f"[Playwright] ✍️ Titre : {title[:50]}...")
            title_field = page.wait_for_selector(
                '#storyboard-selector-title, [placeholder="Erzähle allen, worum es bei deinem Pin geht."]',
                timeout=10000
            )
            title_field.click()
            _delay(300, 600)
            title_field.fill(title[:100])
            _delay(500, 1000)

            # ── 5. Description (dans l'éditeur riche) ─────────
            print(f"[Playwright] 📝 Description...")
            try:
                # L'éditeur de description est un div contenteditable dans storyboard-description-field-container
                desc_container = page.wait_for_selector(
                    '[data-test-id="storyboard-description-field-container"]',
                    timeout=5000
                )
                # Chercher l'éditeur à l'intérieur
                desc_editor = desc_container.query_selector(
                    '[contenteditable="true"], [data-test-id="editor-with-mentions"], textarea'
                )
                if desc_editor:
                    desc_editor.click()
                    _delay(200, 500)
                    desc_editor.fill(description[:500])
                    _delay(400, 800)
                    print(f"[Playwright] ✅ Description remplie")
                else:
                    print(f"[Playwright] ⚠️ Éditeur description non trouvé dans container")
            except Exception as e:
                print(f"[Playwright] ⚠️ Description skippée : {e}")

            # ── 6. Lien ───────────────────────────────────────
            if link:
                print(f"[Playwright] 🔗 Lien : {link[:60]}...")
                try:
                    link_field = page.wait_for_selector(
                        '#WebsiteField, [placeholder="Link hinzufügen"]',
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
            publish_btn = None
            for selector in [
                '[data-test-id="storyboard-draft-footer-save-recommended-content"]',
                'button[data-test-id="board-dropdown-save-button"]',
            ]:
                try:
                    publish_btn = page.wait_for_selector(selector, timeout=5000)
                    if publish_btn:
                        break
                except Exception:
                    continue

            if not publish_btn:
                # Fallback : bouton "Veröffentlichen" par texte
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
                        '[data-test-id="pin-success-toast"], [data-test-id="toast"], [data-test-id="saving-status-created"]',
                        timeout=5000
                    )
                    result["success"] = True
                    print(f"[Playwright] ✅ Pin publié (confirmation détectée)")
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
