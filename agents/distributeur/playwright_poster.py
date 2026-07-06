"""
Distributeur Agent — Playwright Poster
Selectors vérifiés live sur Pinterest DE (juillet 2026)
"""

import json
import time
import random
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
except ImportError:
    raise ImportError("pip install playwright && playwright install chromium")

SESSIONS_DIR = Path("/root/garten-gefuehl-openclaw/data/pinterest_sessions")
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

NICHE_TAGS = {
    "Blumen":        ["Blumen", "Gartenblumen", "Frühlingsgarten", "Pflanzen", "Blumengarten", "Blumenideen"],
    "Balkon":        ["Balkon", "Balkonpflanzen", "Balkonideen", "Stadtgarten", "Balkondeko", "Balkongestaltung"],
    "Rosen":         ["Rosen", "Rosengarten", "Rosenliebe", "Gartenrosen", "Rosenpflege", "Kletterrosen"],
    "Terrasse":      ["Terrasse", "Terrassengestaltung", "Gartenideen", "Outdoor", "Gartenmöbel", "Sichtschutz"],
    "Garten Gefühl": ["Garten", "Gartengestaltung", "Gartenliebe", "Natur", "Garteninspiration", "Traumgarten"],
}

NICHE_HASHTAGS = {
    "Blumen":        "#Blumen #Gartenblumen #Frühlingsgarten #Pflanzen #Blumengarten",
    "Balkon":        "#Balkon #Balkonpflanzen #Balkonideen #Stadtgarten #Balkondeko",
    "Rosen":         "#Rosen #Rosenliebe #Rosengarten #Gartenrosen #Rosenpflege",
    "Terrasse":      "#Terrasse #Terrassengestaltung #Gartenideen #Outdoor #Garten",
    "Garten Gefühl": "#Garten #Gartengestaltung #Gartenliebe #Natur #Garteninspiration",
}


def build_description(categorie, title):
    h = NICHE_HASHTAGS.get(categorie, "#Garten #Gartenideen")
    intro = f"✨ {title[:80]}" if title else f"Entdecke Ideen rund um {categorie}"
    return f"{intro}\n\n{h}\n\n🌱 Mehr auf garten-gefühl.de"


def get_tags_for_niche(categorie):
    return NICHE_TAGS.get(categorie, ["Garten", "Gartenideen"])


# ── Sessions ──────────────────────────────────────────────────

def _session_file(account_name):
    slug = (account_name
            .replace(" ", "_")
            .replace("&", "und")
            .replace("ü", "u")
            .replace("Ü", "U"))
    return SESSIONS_DIR / f"session_{slug}.json"


def _save_cookies(account_name, context):
    with open(_session_file(account_name), "w") as f:
        json.dump(context.cookies(), f)
    print(f"[Playwright] 🍪 Session sauvegardée — {account_name}")


def _load_cookies(account_name, context):
    p = _session_file(account_name)
    if not p.exists():
        return False
    try:
        context.add_cookies(json.loads(p.read_text()))
        print(f"[Playwright] 🍪 Session chargée — {account_name}")
        return True
    except Exception:
        return False


def _clear_session(account_name):
    p = _session_file(account_name)
    if p.exists():
        p.unlink()


def _delay(a=500, b=1500):
    time.sleep(random.uniform(a / 1000, b / 1000))


# ── Login ─────────────────────────────────────────────────────

def _is_logged_in(page):
    try:
        page.goto("https://www.pinterest.com/", timeout=15000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _delay(1500, 2500)
        return page.query_selector('[data-test-id="simple-login-button"]') is None
    except Exception:
        return False


def _login(page, email, password):
    print(f"[Playwright] 🔐 Login — {email[:25]}...")
    try:
        page.goto("https://www.pinterest.com/login/", timeout=20000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _delay(1500, 3000)

        page.wait_for_selector('input[id="email"]', timeout=10000).click()
        _delay(300, 600)
        page.fill('input[id="email"]', email)
        _delay(500, 1000)

        page.wait_for_selector('input[id="password"]', timeout=5000).click()
        _delay(300, 600)
        page.fill('input[id="password"]', password)
        _delay(800, 1500)

        with page.expect_navigation(timeout=15000, wait_until="domcontentloaded"):
            page.press('input[id="password"]', "Enter")
        _delay(2000, 3000)

        url = page.url
        print(f"[Playwright] URL post-login : {url[:70]}")
        if "security" in url or "challenge" in url:
            print("[Playwright] ⚠️ Challenge sécurité")
            return False
        if "login" not in url and "pinterest.com" in url:
            print("[Playwright] ✅ Login OK")
            return True
        print("[Playwright] ⚠️ Login incertain")
        return True

    except PWTimeoutError:
        try:
            if "login" not in page.url and "pinterest.com" in page.url:
                print("[Playwright] ✅ Login OK (nav rapide)")
                return True
        except Exception:
            pass
        print("[Playwright] ❌ Timeout login")
        return False
    except Exception as e:
        print(f"[Playwright] ❌ Erreur login: {e}")
        return False


# ── Attente formulaire ────────────────────────────────────────

def _wait_for_form_ready(page):
    """Attend que le formulaire soit activé après upload image."""
    print("[Playwright] ⏳ Attente activation formulaire...")
    try:
        page.wait_for_function(
            """() => {
                const t = document.querySelector('#storyboard-selector-title');
                return t && !t.disabled && t.offsetParent !== null;
            }""",
            timeout=30000
        )
        print("[Playwright] ✅ Formulaire prêt")
        _delay(1000, 2000)
    except Exception:
        try:
            page.wait_for_function(
                """() => {
                    const b = document.querySelector('[data-test-id="board-dropdown-select-button"]');
                    return b && !b.disabled && b.offsetParent !== null;
                }""",
                timeout=20000
            )
            print("[Playwright] ✅ Formulaire prêt (fallback)")
            _delay(1000, 2000)
        except Exception:
            print("[Playwright] ⚠️ Formulaire pas confirmé — attente 6s")
            _delay(6000, 8000)


# ── Remplissage champs ────────────────────────────────────────

def _fill_title(page, title):
    try:
        field = page.wait_for_selector('#storyboard-selector-title', timeout=8000)
        field.click()
        _delay(300, 500)
        field.fill(title[:100])
        _delay(400, 800)
        print("[Playwright] ✅ Titre rempli")
    except Exception as e:
        print(f"[Playwright] ⚠️ Titre skippé : {e}")


def _fill_description(page, description):
    try:
        container = page.wait_for_selector(
            '[data-test-id="storyboard-description-field-container"]',
            timeout=8000
        )
        container.click()
        _delay(500, 800)
        editor = container.query_selector(
            'div[role="textbox"], [contenteditable="true"], p[data-placeholder]'
        )
        if editor:
            editor.click()
            _delay(300, 500)
        page.keyboard.type(description[:500], delay=8)
        _delay(400, 700)
        print("[Playwright] ✅ Description remplie")
    except Exception as e:
        print(f"[Playwright] ⚠️ Description skippée : {e}")


def _fill_link(page, link):
    if not link:
        return
    try:
        field = page.wait_for_selector('#WebsiteField', timeout=8000)
        field.click()
        _delay(300, 500)
        field.fill(link)
        _delay(500, 1000)
        field.press("Tab")
        _delay(800, 1500)
        print("[Playwright] ✅ Lien ajouté")
    except Exception as e:
        print(f"[Playwright] ⚠️ Lien skippé : {e}")


def _fill_tags(page, tags):
    try:
        field = page.query_selector('#combobox-storyboard-interest-tags')
        if not field:
            field = page.query_selector('[placeholder="Nach einem Tag suchen"]')
        if not field:
            print("[Playwright] ⚠️ Champ tags non trouvé")
            return
        added = 0
        for tag in tags[:6]:
            field.click()
            _delay(200, 400)
            field.fill(tag)
            _delay(700, 1100)
            try:
                sug = page.wait_for_selector(
                    '[data-test-id="tag-autocomplete-option"], [role="option"]',
                    timeout=2000
                )
                if sug:
                    sug.click()
                    _delay(300, 500)
                    added += 1
                    continue
            except Exception:
                pass
            field.press("Enter")
            _delay(300, 500)
            added += 1
        print(f"[Playwright] ✅ {added} tags ajoutés")
    except Exception as e:
        print(f"[Playwright] ⚠️ Tags : {e}")


def _select_board(page, board_name):
    try:
        # Attendre que le bouton soit cliquable
        page.wait_for_function(
            """() => {
                const b = document.querySelector('[data-test-id="board-dropdown-select-button"]');
                return b && !b.disabled && b.offsetParent !== null;
            }""",
            timeout=15000
        )
        btn = page.query_selector('[data-test-id="board-dropdown-select-button"]')
        btn.click()
        _delay(2000, 3000)

        # Selector confirmé live : data-test-id="boardWithoutSection"
        options = page.query_selector_all('[data-test-id="boardWithoutSection"]')

        if options:
            for opt in options:
                try:
                    text = opt.inner_text().strip()
                    if board_name.lower() in text.lower():
                        opt.click()
                        _delay(500, 1000)
                        print(f"[Playwright] ✅ Board : {board_name}")
                        return True
                except Exception:
                    continue
            # Non trouvé → premier dispo
            try:
                first_text = options[0].inner_text().strip()[:30]
                options[0].click()
                _delay(500, 1000)
                print(f"[Playwright] ⚠️ Board '{board_name}' non trouvé → '{first_text}'")
                return True
            except Exception:
                pass

        # Fallback : data-test-id commençant par "board-row-"
        options2 = page.query_selector_all('[data-test-id^="board-row-"]')
        if options2:
            for opt in options2:
                try:
                    text = opt.inner_text().strip()
                    if board_name.lower() in text.lower():
                        opt.click()
                        _delay(500, 1000)
                        print(f"[Playwright] ✅ Board (board-row) : {board_name}")
                        return True
                except Exception:
                    continue
            first_text = options2[0].inner_text().strip()[:30]
            options2[0].click()
            _delay(500, 1000)
            print(f"[Playwright] ⚠️ Board fallback → '{first_text}'")
            return True

        print(f"[Playwright] ❌ Aucune option board trouvée")
        return False

    except Exception as e:
        print(f"[Playwright] ❌ Board erreur : {e}")
        return False


def _publish(page):
    for sel in [
        '[data-test-id="storyboard-draft-footer-save-recommended-content"]',
        'button[data-test-id="board-dropdown-save-button"]',
    ]:
        try:
            btn = page.wait_for_selector(sel, timeout=5000)
            if btn:
                btn.click()
                _delay(3000, 6000)
                print("[Playwright] ✅ Publié")
                return True
        except Exception:
            continue
    try:
        page.get_by_role("button", name="Veröffentlichen").first.click()
        _delay(3000, 6000)
        print("[Playwright] ✅ Publié (Veröffentlichen)")
        return True
    except Exception as e:
        print(f"[Playwright] ❌ Bouton publier non trouvé : {e}")
        return False


# ── Post pin ──────────────────────────────────────────────────

def post_pin(account_name, email, password, image_path, title,
             description, board_name, categorie, link=None, headless=True):

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
            window.chrome = {runtime: {}};
        """)
        page = context.new_page()

        try:
            # 1. Session
            logged_in = _load_cookies(account_name, context) and _is_logged_in(page)
            if not logged_in:
                _clear_session(account_name)
                if not _login(page, email, password):
                    result["error"] = "Login échoué"
                    return result
                _save_cookies(account_name, context)

            # 2. Pin creation tool
            print("[Playwright] 🎨 Ouverture pin-creation-tool...")
            page.goto("https://de.pinterest.com/pin-creation-tool/", timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            _delay(3000, 5000)

            # 3. Upload image
            print(f"[Playwright] 📤 Upload : {Path(image_path).name}")
            file_input = page.wait_for_selector(
                'input[data-test-id="storyboard-upload-input"], input[type="file"]',
                timeout=10000
            )
            file_input.set_input_files(image_path)

            # 4. Attendre formulaire prêt
            _wait_for_form_ready(page)

            # 5. Titre
            _fill_title(page, title)

            # 6. Description
            _fill_description(page, description)

            # 7. Lien
            _fill_link(page, link)

            # 8. Tags
            _fill_tags(page, get_tags_for_niche(categorie))

            # 9. Board
            if not _select_board(page, board_name):
                result["error"] = f"Board '{board_name}' introuvable"
                return result

            # 10. Publier
            if not _publish(page):
                result["error"] = "Bouton publier non trouvé"
                return result

            # 11. Vérifier succès
            url = page.url
            if "pin/" in url and "creation-tool" not in url:
                result["success"] = True
                result["pin_url"] = url
                print(f"[Playwright] ✅ Pin publié : {url[:80]}")
            else:
                try:
                    page.wait_for_selector(
                        '[data-test-id="pin-success-toast"], '
                        '[data-test-id="toast"], '
                        '[data-test-id="saving-status-created"]',
                        timeout=5000
                    )
                    result["success"] = True
                    print("[Playwright] ✅ Pin publié (confirmation)")
                except Exception:
                    err = page.query_selector('[data-test-id="error-message"]')
                    if err:
                        result["error"] = f"Erreur Pinterest: {err.inner_text()[:100]}"
                    else:
                        result["success"] = True
                        print("[Playwright] ✅ Pin publié (pas d'erreur)")

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


# ── Retry wrapper ─────────────────────────────────────────────

def post_pin_with_retry(account_name, email, password, image_path, title,
                        description, board_name, categorie, link=None,
                        max_retries=3, headless=True):
    for attempt in range(1, max_retries + 1):
        print(f"[Playwright] Tentative {attempt}/{max_retries} — {account_name}")
        if attempt == 2:
            print("[Playwright] 🔄 Re-login forcé")
            _clear_session(account_name)

        result = post_pin(
            account_name, email, password, image_path,
            title, description, board_name, categorie, link, headless
        )
        if result["success"]:
            return result

        if attempt < max_retries:
            wait = random.randint(30, 60)
            print(f"[Playwright] ⏳ Retry dans {wait}s ({result.get('error', '?')})")
            time.sleep(wait)

    result["error"] = f"Échec {max_retries} tentatives: {result.get('error', '?')}"
    print(f"[Playwright] ❌ {result['error']}")
    return result
