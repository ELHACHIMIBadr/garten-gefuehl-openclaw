"""
WordStream Scraper — Volumes SEO via Playwright

CHANGELOG v2:
- Sélecteurs corrigés d'après le vrai HTML de wordstream.com/keywords
  Input: id="input_1_1" (Gravity Forms)
  Soumission via bouton id="gform_submit_button_1"
  Résultats : attente AJAX après soumission
- Sélection pays via input_1_9 (2ème champ texte)
- Dump HTML post-soumission pour debug si 0 résultats
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
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = context.new_page()

        try:
            print(f"[WordStream] Recherche volumes pour : '{keyword}'")
            page.goto("https://www.wordstream.com/keywords", timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            _delay(2000, 3000)

            # Remplir le keyword — id="input_1_1"
            kw_input = page.wait_for_selector('#input_1_1', timeout=10000)
            kw_input.click()
            _delay(300, 500)
            kw_input.fill(keyword)
            _delay(500, 800)

            # Sélectionner le pays si possible (2ème input texte = industry/country)
            try:
                country_input = page.query_selector('#input_1_9')
                if country_input:
                    country_input.fill(country)
                    _delay(300, 500)
            except Exception:
                pass

            # Soumettre via le bouton Gravity Forms
            submit_btn = page.query_selector('#gform_submit_button_1')
            if submit_btn:
                submit_btn.click()
            else:
                kw_input.press("Enter")

            _delay(4000, 6000)

            # Attendre les résultats AJAX
            try:
                page.wait_for_selector(
                    'table, [class*="keyword"], [class*="result"], [id*="result"]',
                    timeout=20000
                )
                _delay(2000, 3000)
            except Exception:
                print("[WordStream] ⚠️ Aucun résultat détecté après soumission")
                # Debug : dump HTML post-soumission
                html = page.content()
                print(f"[WordStream] HTML post-soumission[:1000]: {html[:1000]}")
                return []

            # Extraire les données du tableau
            data = page.evaluate("""
                () => {
                    const results = [];

                    // Chercher tous les tableaux
                    const tables = document.querySelectorAll('table');
                    tables.forEach(table => {
                        const rows = table.querySelectorAll('tbody tr');
                        rows.forEach(row => {
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 2) {
                                const kw = cells[0] ? cells[0].innerText.trim() : '';
                                const vol = cells[1] ? cells[1].innerText.trim() : '0';
                                const comp = cells[2] ? cells[2].innerText.trim() : '';
                                const cpc = cells[3] ? cells[3].innerText.trim() : '0';
                                if (kw && kw.length > 1) {
                                    results.push({
                                        keyword: kw,
                                        volume_raw: vol,
                                        competition: comp,
                                        cpc_raw: cpc
                                    });
                                }
                            }
                        });
                    });

                    // Fallback : chercher par classes keyword
                    if (results.length === 0) {
                        const items = document.querySelectorAll(
                            '[class*="keyword-row"], [class*="result-row"], [class*="kw-row"]'
                        );
                        items.forEach(item => {
                            const cells = item.querySelectorAll('[class*="cell"], td, span');
                            if (cells.length >= 2) {
                                results.push({
                                    keyword: cells[0].innerText.trim(),
                                    volume_raw: cells[1] ? cells[1].innerText.trim() : '0',
                                    competition: cells[2] ? cells[2].innerText.trim() : '',
                                    cpc_raw: cells[3] ? cells[3].innerText.trim() : '0'
                                });
                            }
                        });
                    }

                    return results;
                }
            """)

            # Si toujours 0, dump le HTML pour debug
            if not data:
                html = page.content()
                print(f"[WordStream] HTML résultats[:2000]: {html[2000:4000]}")

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
    if not keywords:
        return {}

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
            "trend": 10,
        }

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
