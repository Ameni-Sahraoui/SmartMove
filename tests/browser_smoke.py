import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
URL=os.environ.get('SMARTMOVE_TEST_URL','http://127.0.0.1:8501')
credentials=ROOT/'data/LOCAL_CREDENTIALS.txt'
if not credentials.exists():raise SystemExit('Run SmartMove first; local credentials are created at startup.')
line=next(x.split() for x in credentials.read_text(encoding='utf-8').splitlines() if x.startswith('Admin '))
errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1672,'height':1020})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(URL,wait_until='networkidle')
    page.fill('input[name=email]',line[1]);page.fill('input[name=password]',line[2])
    page.click('#auth-form button[type=submit]');page.wait_for_selector('.kpis',timeout=30000)
    assert page.locator('.kpi').count()==8
    for nav in ['operations','fleet','routes','trips','reservations','maintenance','demand','predictive','delay','experience','simulation','quality','security','models']:
        page.locator(f'#navigation [data-nav={nav}]').click()
        page.wait_for_selector('.page-header');page.wait_for_timeout(300)
        assert page.locator('.page-header h1').inner_text()!='Workspace could not load'
    assert not errors,errors
    page.locator('#navigation [data-nav=overview]').click();page.wait_for_selector('.kpis');page.wait_for_timeout(500)
    (ROOT/'docs/screenshots').mkdir(exist_ok=True)
    page.screenshot(path=str(ROOT/'docs/screenshots/local-browser-smoke.png'),full_page=True)
    browser.close()
print('Browser workspace smoke test passed.')
