from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto('https://www.wordstream.com/keywords', timeout=30000)
    page.wait_for_load_state('domcontentloaded')
    time.sleep(3)
    try:
        page.click('#onetrust-accept-btn-handler')
        time.sleep(2)
    except:
        pass
    field = page.wait_for_selector('input[name="input_1"]', timeout=5000)
    field.fill('balkon ideen')
    time.sleep(1)
    field.press('Enter')
    time.sleep(6)

    # Changer pays
    try:
        country_input = page.wait_for_selector('input[id=":r2:"]', timeout=5000)
        country_input.click()
        time.sleep(0.3)
        country_input.press('Control+a')
        time.sleep(0.3)
        country_input.type('Germany', delay=100)
        time.sleep(2)
        # Screenshot pour voir ce qui apparait
        page.screenshot(path='wordstream_debug.png')
        print('Screenshot sauvegardé')
        # Chercher suggestion
        suggestions = page.query_selector_all('[role="option"], [class*="suggestion"], [class*="option"]')
        print(f'Suggestions trouvées: {len(suggestions)}')
        for s in suggestions[:5]:
            print(f'  -> {s.inner_text()}')
        if suggestions:
            suggestions[0].click()
            time.sleep(1)
    except Exception as e:
        print('Erreur pays:', e)

    page.click('text=Continue')
    time.sleep(8)
    print('URL:', page.url)
    print(page.inner_text('body')[:2000])
    input('Appuie Enter pour fermer...')
    browser.close()
