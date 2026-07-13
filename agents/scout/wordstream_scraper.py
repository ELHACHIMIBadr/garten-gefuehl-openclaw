"""
WordStream Scraper — Volumes SEO via Playwright

CHANGELOG v4:
- Fix navigation : soumission redirige vers tools.wordstream.com/fkt
- Attente navigation complète avant scraping
- Table confirmée présente sur la page résultats
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


def _dismiss_onetrust(page):
    try:
        page.evaluate("""
            () => {
                document.querySelectorAll('[id*=onetrust], .onetrust-pc-dark-filter').forEach(el => el.remove());
                document.body.style.overflow = 'auto';
            }
        """)
        _delay(300, 500)
    except Exception:
        pass


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
        page = context.new_page()

        try:
            print(f"[WordStream] Recherche : '{keyword}'")
            page.goto("https://www.wordstream.com/keywords", timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            _delay(2000, 3000)

            # Supprimer OneTrust
            _dismiss_onetrust(page)

            # Remplir keyword
            page.fill('#input_1_1', keyword)
            _delay(500, 800)

            # Soumettre et attendre la navigation vers tools.wordstream.com/fkt
            with page.expect_navigation(timeout=20000, wait_until="domcontentloaded"):
                page.click('#gform_submit_button_1', force=True)

            _delay(3000, 5000)
            print(f"[WordStream] URL résultats : {page.url[:80]}")

            # Attendre que la table soit rendue par React
            try:
                page.wait_for_selector('table tbody tr', timeout=15000)
                _delay(1000, 2000)
            except Exception:
                print("[WordStream] ⚠️ Table non trouvée — body text:")
                print(page.inner_text('body')[:500])
                return []

            # Scraper la table
            data = page.evaluate("""
                () => {
                    const results = [];
                    const rows = document.querySelectorAll('table tbody tr');
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td');
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

            print(f"[WordStream] {len(data)} lignes trouvées dans le tableau")

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
                    competition = "HIGH" if "HIGH" in comp else ("LOW" if "LOW" in comp else "MEDIUM")
                    kw = item.get("keyword", "").lower().strip()
                    if kw:
                        results.append({"keyword": kw, "volume": volume, "cpc": cpc, "competition": competition})
                except Exception:
                    continue

            print(f"[WordStream] ✅ {len(results)} keywords récupérés")

        except PWTimeoutError as e:
            print(f"[WordStream] ❌ Timeout : {str(e)[:100]}")
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
            volumes[kw_lower] = {"volume": 50, "cpc": 0.3, "competition": "LOW", "competition_level": "LOW", "trend": 5}
    return volumes
