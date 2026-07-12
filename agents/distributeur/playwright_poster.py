"""
Distributeur Agent — Playwright Poster v2.1 (Anti-Detection)

Fix v2.1 : playwright-stealth v2 API corrigée.
  - stealth.use_sync() s'applique sur la PAGE (pas sur le browser launcher).
  - Profil Chrome persistant : launch_persistent_context() direct sans stealth wrapper.
  - Stealth appliqué via page.add_init_script() comme fallback universel.

4 améliorations anti-detection :
  1. playwright-stealth → patch sur chaque page via stealth(page)
  2. Profil Chrome persistant par compte (user_data_dir)
  3. Session JSON fallback (storage_state)
  4. Timings humains (frappe caractère par caractère + warm-up)
"""

import json
import time
import random
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
except ImportError:
    raise ImportError("pip install playwright && playwright install chromium")

try:
    from playwright_stealth import stealth_sync
    STEALTH_AVAILABLE = True
except ImportError:
    try:
        from playwright_stealth import Stealth
        _stealth_obj = Stealth()
        def stealth_sync(page):
            try:
                _stealth_obj.use_sync(page)
            except Exception:
                pass
        STEALTH_AVAILABLE = True
    except ImportError:
        STEALTH_AVAILABLE = False
        def stealth_sync(page):
            pass
        print("[Playwright] ⚠️ playwright-stealth non disponible")

# ── Répertoires ───────────────────────────────────────────────

SESSIONS_DIR = Path("/root/garten-gefuehl-openclaw/data/pinterest_sessions")
PROFILES_DIR = Path("/root/garten-gefuehl-openclaw/data/pinterest_profiles")
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR.mkdir(parents=True, exist_ok=True)

# ── Constantes navigateur ─────────────────────────────────────

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--window-size=1280,900",
]

STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    window.chrome = {runtime: {}};
    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
    Object.defineProperty(navigator, 'languages', {get: () => ['de-DE', 'de', 'en-US']});
"""

# ── Niche tags / hashtags ─────────────────────────────────────

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


# ── Helpers ───────────────────────────────────────────────────

def _account_slug(account_name: str) -> str:
    return (
        account_name
        .replace(" ", "_")
        .replace("&", "und")
        .replace("ü", "u")
        .replace("Ü", "U")
    )


def _profile_dir(account_name: str) -> Path:
    return PROFILES_DIR / _account_slug(account_name)


def _session_file(account_name: str) -> Path:
    return SESSIONS_DIR / f"session_{_account_slug(account_name)}.json"


def _save_session(account_name: str, context):
    try:
        sf = _session_file(account_name)
        context.storage_state(path=str(sf))
        print(f"[Playwright] 💾 Session sauvegardée — {account_name}")
    except Exception as e:
        print(f"[Playwright] ⚠️ Échec sauvegarde session: {e}")


def _clear_session(account_name: str):
    sf = _session_file(account_name)
    if sf.exists():
        sf.unlink()
        print(f"[Playwright] 🗑️ Session effacée — {account_name}")


# ── Délais humains ────────────────────────────────────────────

def _delay(a=500, b=1500):
    time.sleep(random.uniform(a / 1000, b / 1000))


# ── Warm-up ───────────────────────────────────────────────────

def _warmup(page):
    try:
        print("[Playwright] 🔥 Warm-up Pinterest...")
        page.goto("https://de.pinterest.com/", timeout=20000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _delay(2000, 4000)
        page.evaluate("window.scrollTo(0, 400)")
        _delay(1000, 2000)
        page.evaluate("window.scrollTo(0, 800)")
        _delay(800, 1500)
        page.evaluate("window.scrollTo(0, 0)")
        _delay(500, 1000)
        print("[Playwright] ✅ Warm-up terminé")
    except Exception as e:
        print(f"[Playwright] ⚠️ Warm-up skippé: {e}")


# ── Login ─────────────────────────────────────────────────────

def _is_logged_in(page) -> bool:
    try:
        page.goto("https://de.pinterest.com/me/", timeout=15000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _delay(1500, 2500)
        return "/login" not in page.url and "pinterest.com" in page.url
    except Exception:
        return False


def _login(page, email: str, password: str) -> bool:
    print(f"[Playwright] 🔐 Login — {email[:25]}...")
    try:
        page.goto("https://de.pinterest.com/login/", timeout=20000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _delay(1500, 3000)

        page.wait_for_selector('input[id="email"]', timeout=10000).click()
        _delay(300, 600)
        for char in email:
            page.press('input[id="email"]', char)
            time.sleep(random.uniform(0.04, 0.12))
        _delay(500, 1000)

        page.wait_for_selector('input[id="password"]', timeout=5000).click()
        _delay(300, 600)
        for char in password:
            page.press('input[id="password"]', char)
            time.sleep(random.uniform(0.04, 0.12))
        _delay(800, 1500)

        with page.expect_navigation(timeout=15000, wait_until="domcontentloaded"):
            page.press('input[id="password"]', "Enter")
        _delay(3000, 5000)

        url = page.url
        print(f"[Playwright] URL post-login : {url[:70]}")
        if "security" in url or "challenge" in url:
            print("[Playwright] ⚠️ Challenge sécurité détecté")
            return False
        if "login" not in url and "pinterest.com" in url:
            print("[Playwright] ✅ Login réussi")
            return True
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


# ── Lancement navigateur ──────────────────────────────────────

def _launch_browser_with_stealth(p, account_name: str, headless: bool):
    """
    Lance Chromium avec profil persistant si possible, sinon session JSON.
    Stealth appliqué sur la page via stealth_sync(page) après création.
    """
    profile_dir = _profile_dir(account_name)
    session_file = _session_file(account_name)

    # Tentative profil Chrome persistant
    try:
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport={"width": 1280, "height": 900},
            user_agent=USER_AGENT,
            locale="de-DE",
            args=LAUNCH_ARGS,
        )
        context.add_init_script(STEALTH_SCRIPT)
        page = context.pages[0] if context.pages else context.new_page()
        # Appliquer stealth sur la page
        try:
            stealth_sync(page)
        except Exception:
            pass
        print(f"[Playwright] 🗂️ Profil Chrome persistant : {profile_dir.name}")
        return context, page, True, None

    except Exception as e:
        print(f"[Playwright] ⚠️ Profil persistant échoué ({e}) — fallback session JSON")

    # Fallback : browser classique + session JSON
    browser = p.chromium.launch(headless=headless, args=LAUNCH_ARGS)
    storage = str(session_file) if session_file.exists() else None
    context = browser.new_context(
        storage_state=storage,
        viewport={"width": 1280, "height": 900},
        user_agent=USER_AGENT,
        locale="de-DE",
    )
    context.add_init_script(STEALTH_SCRIPT)
    page = context.new_page()
    try:
        stealth_sync(page)
    except Exception:
        pass

    if storage:
        print(f"[Playwright] 🍪 Session JSON chargée — {account_name}")
    else:
        print(f"[Playwright] 🆕 Nouveau contexte — {account_name}")

    return context, page, False, browser


# ── Attente formulaire ────────────────────────────────────────

def _wait_for_form_ready(page):
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

def _fill_title(page, title: str):
    try:
        field = page.wait_for_selector('#storyboard-selector-title', timeout=8000)
        field.click()
        _delay(300, 500)
        field.triple_click()
        _delay(200, 300)
        for char in title[:100]:
            field.press(char)
            time.sleep(random.uniform(0.03, 0.10))
        _delay(400, 800)
        print("[Playwright] ✅ Titre rempli")
    except Exception as e:
        print(f"[Playwright] ⚠️ Titre skippé : {e}")


def _fill_description(page, description: str):
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
        page.keyboard.type(description[:500], delay=random.uniform(20, 50))
        _delay(400, 700)
        print("[Playwright] ✅ Description remplie")
    except Exception as e:
        print(f"[Playwright] ⚠️ Description skippée : {e}")


def _fill_link(page, link: str):
    if not link:
        return
    try:
        field = page.wait_for_selector('#WebsiteField', timeout=8000)
        field.click()
        _delay(300, 500)
        for char in link:
            field.press(char)
            time.sleep(random.uniform(0.02, 0.07))
        _delay(500, 1000)
        field.press("Tab")
        _delay(800, 1500)
        print("[Playwright] ✅ Lien ajouté")
    except Exception as e:
        print(f"[Playwright] ⚠️ Lien skippé : {e}")


def _fill_tags(page, tags: list):
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
            for char in tag:
                field.press(char)
                time.sleep(random.uniform(0.04, 0.10))
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


def _select_board(page, board_name: str) -> bool:
    try:
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
            try:
                first_text = options[0].inner_text().strip()[:30]
                options[0].click()
                _delay(500, 1000)
                print(f"[Playwright] ⚠️ Board '{board_name}' non trouvé → '{first_text}'")
                return True
            except Exception:
                pass

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

        print("[Playwright] ❌ Aucune option board trouvée")
        return False

    except Exception as e:
        print(f"[Playwright] ❌ Board erreur : {e}")
        return False


def _publish(page) -> bool:
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


# ── Post pin principal ────────────────────────────────────────

def post_pin(account_name, email, password, image_path, title,
             description, board_name, categorie, link=None, headless=True):

    result = {"success": False, "pin_url": None, "error": None}

    with sync_playwright() as p:
        context, page, used_persistent, browser = _launch_browser_with_stealth(
            p, account_name, headless
        )

        try:
            # 1. Vérifier session / login
            if _is_logged_in(page):
                print(f"[Playwright] ✅ Déjà connecté — {account_name}")
            else:
                print(f"[Playwright] 🔐 Session expirée — re-login")
                if not used_persistent:
                    _clear_session(account_name)
                if not _login(page, email, password):
                    result["error"] = "Login échoué"
                    return result
                if not used_persistent:
                    _save_session(account_name, context)

            # 2. Warm-up
            _warmup(page)

            # 3. Pin creation tool
            print("[Playwright] 🎨 Ouverture pin-creation-tool...")
            page.goto("https://de.pinterest.com/pin-creation-tool/", timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            _delay(3000, 5000)

            # 4. Upload image
            print(f"[Playwright] 📤 Upload : {Path(image_path).name}")
            file_input = page.wait_for_selector(
                'input[data-test-id="storyboard-upload-input"], input[type="file"]',
                timeout=10000
            )
            file_input.set_input_files(image_path)

            # 5. Attendre formulaire
            _wait_for_form_ready(page)

            # 6. Remplir champs
            _fill_title(page, title)
            _fill_description(page, description)
            _fill_link(page, link)
            _fill_tags(page, get_tags_for_niche(categorie))

            # 7. Board
            if not _select_board(page, board_name):
                result["error"] = f"Board '{board_name}' introuvable"
                return result

            # 8. Publier
            if not _publish(page):
                result["error"] = "Bouton publier non trouvé"
                return result

            # 9. Vérifier succès
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
                    print("[Playwright] ✅ Pin publié (toast)")
                except Exception:
                    err = page.query_selector('[data-test-id="error-message"]')
                    if err:
                        result["error"] = f"Erreur Pinterest: {err.inner_text()[:100]}"
                    else:
                        result["success"] = True
                        print("[Playwright] ✅ Pin publié (pas d'erreur visible)")

            # 10. Sauvegarder session
            if result["success"] and not used_persistent:
                _save_session(account_name, context)

        except PWTimeoutError as e:
            result["error"] = f"Timeout: {str(e)[:100]}"
            print(f"[Playwright] ❌ {result['error']}")
        except Exception as e:
            result["error"] = f"Erreur: {str(e)[:150]}"
            print(f"[Playwright] ❌ {result['error']}")
        finally:
            try:
                context.close()
            except Exception:
                pass
            if browser:
                try:
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
            print("[Playwright] 🔄 Effacement session — re-login forcé")
            _clear_session(account_name)

        result = post_pin(
            account_name, email, password, image_path,
            title, description, board_name, categorie, link, headless
        )
        if result["success"]:
            return result

        if attempt < max_retries:
            wait = random.randint(45, 90)
            print(f"[Playwright] ⏳ Retry dans {wait}s ({result.get('error', '?')})")
            time.sleep(wait)

    result["error"] = f"Échec {max_retries} tentatives: {result.get('error', '?')}"
    print(f"[Playwright] ❌ {result['error']}")
    return result
