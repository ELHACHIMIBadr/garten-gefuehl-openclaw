"""
WordStream Scraper — Volumes SEO via Playwright

Navigue vers wordstream.com/keywords, tape le keyword,
scrape les 25 résultats avec volume + CPC + compétition pour DE.

Utilisé par le Scout comme source de volumes réels.
"""

import time
import random

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def _delay(a=800, b=2000):
    time.sleep(random.uniform(a / 1000, b / 1000))


def get_wordstream_volumes(keyword: str, country: str = "DE") -> list:
    """
    Scrape WordStream Free Keyword Tool pour un keyword.

    Returns:
        list of dicts: [{"keyword": str, "volume": int, "cpc": float, "competition": str}]
        Liste vide si erreur ou pas de résultats.
    """
    if not PLAYWRIGHT_AVAILABLE:
        print("[WordStream] Playwright non disponible")
        return []

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="de-DE",
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        page = context.new_page()

        try:
            print(f"[WordStream] Recherche volumes pour : '{keyword}'")
            page.goto("https://www.wordstream.com/keywords", timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            _delay(2000, 3000)

            # Fermer cookie banner si présent
            try:
                accept_btn = page.query_selector('[id*="accept"], [class*="accept"], button:has-text("Accept")')
                if accept_btn:
                    accept_btn.click()
                    _delay(500, 1000)
            except Exception:
                pass

            # Remplir le champ keyword
            keyword_input = page.wait_for_selector(
                'input[name="q"], input[placeholder*="keyword"], input[type="text"]',
                timeout=10000
            )
            keyword_input.click()
            _delay(300, 600)
            keyword_input.fill(keyword)
            _delay(500, 1000)

            # Sélectionner le pays si possible
            try:
                country_select = page.query_selector('select[name="country"], select[id*="country"]')
                if country_select:
                    country_select.select_option(value="DE")
                    _delay(300, 600)
            except Exception:
                pass

            # Soumettre
            keyword_input.press("Enter")
            _delay(3000, 5000)

            # Attendre les résultats
            try:
                page.wait_for_selector(
                    'table, [class*="keyword-result"], [class*="result-table"]',
                    timeout=15000
                )
            except Exception:
                print("[WordStream] ⚠️ Pas de tableau de résultats trouvé")
                return []

            _delay(1000, 2000)

            # Extraire les données
            data = page.evaluate("""
                () => {
                    const results = [];
                    // Chercher les lignes du tableau
                    const rows = document.querySelectorAll('table tbody tr, [class*="keyword-row"], [class*="result-row"]');
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td, [class*="cell"]');
                        if (cells.length >= 2) {
                            const kw = cells[0] ? cells[0].innerText.trim() : '';
                            const vol = cells[1] ? cells[1].innerText.trim() : '0';
                            const comp = cells[2] ? cells[2].innerText.trim() : '';
                            const cpc = cells[3] ? cells[3].innerText.trim() : '0';
                            if (kw && kw.length > 1) {
                                results.push({keyword: kw, volume_raw: vol, competition: comp, cpc_raw: cpc});
                            }
                        }
                    });
                    return results;
                }
            """)

            # Parser les valeurs
            for item in data[:25]:
                try:
                    vol_str = item.get("volume_raw", "0").replace(",", "").replace(".", "").strip()
                    volume = int(''.join(filter(str.isdigit, vol_str))) if vol_str else 0

                    cpc_str = item.get("cpc_raw", "0").replace("$", "").replace("€", "").replace(",", ".").strip()
                    try:
                        cpc = float(cpc_str)
                    except Exception:
                        cpc = 0.0

                    comp = item.get("competition", "").upper()
                    if "HIGH" in comp or "HOCH" in comp:
                        competition = "HIGH"
                    elif "LOW" in comp or "NIEDRIG" in comp:
                        competition = "LOW"
                    else:
                        competition = "MEDIUM"

                    kw = item.get("keyword", "").lower().strip()
                    if kw and volume >= 0:
                        results.append({
                            "keyword": kw,
                            "volume": volume,
                            "cpc": cpc,
                            "competition": competition,
                        })
                except Exception:
                    continue

            print(f"[WordStream] ✅ {len(results)} keywords récupérés")

        except PWTimeoutError as e:
            print(f"[WordStream] ❌ Timeout : {e}")
        except Exception as e:
            print(f"[WordStream] ❌ Erreur : {e}")
        finally:
            try:
                context.close()
                browser.close()
            except Exception:
                pass

    return results


def get_volumes_for_keywords(keywords: list, country: str = "DE") -> dict:
    """
    Récupère les volumes pour une liste de keywords.
    On cherche le keyword principal et on mappe les résultats.

    Returns:
        dict: {keyword_lower: {"volume": int, "cpc": float, "competition": str, ...}}
    """
    if not keywords:
        return {}

    # Utiliser le premier keyword comme seed
    seed = keywords[0]
    ws_results = get_wordstream_volumes(seed, country)

    volumes = {}
    for item in ws_results:
        kw = item["keyword"].lower().strip()
        volumes[kw] = {
            "volume": item["volume"],
            "cpc": item["cpc"],
            "competition": item["competition"],
            "competition_level": item["competition"],
            "trend": 10,  # WordStream ne donne pas les trends
        }

    # Ajouter les keywords demandés non trouvés avec volume minimal
    for kw in keywords:
        kw_lower = kw.lower().strip()
        if kw_lower not in volumes:
            volumes[kw_lower] = {
                "volume": 50,
                "cpc": 0.3,
                "competition": "LOW",
                "competition_level": "LOW",
                "trend": 5,
            }

    return volumes
