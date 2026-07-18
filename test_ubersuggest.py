from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto('https://app.neilpatel.com/en/ubersuggest/overview?keyword=balkon+ideen&lang=de&locId=2276&mode=keyword', timeout=30000)
    page.wait_for_load_state('domcontentloaded')
    time.sleep(5)
    print('URL:', page.url)
    print(page.inner_text('body')[:2000])
    input('Appuie Enter pour fermer...')
    browser.close()
