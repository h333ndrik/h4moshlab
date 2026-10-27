"""Optional Chromium checks for the original H4 cursor and native fallbacks."""
from pathlib import Path
import os
import shutil
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
base = os.environ.get('H4_EDITOR_TEST_URL', 'http://127.0.0.1:8765')
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=shutil.which('chromium'))
    page = browser.new_page(viewport={'width':1000,'height':900})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(base)
    cursor = page.locator('.h4-cursor')
    page.locator('h1').hover()
    expect(cursor).to_be_visible()
    expect(cursor).not_to_have_class('h4-cursor is-clickable')
    assert cursor.bounding_box()['width'] == 22
    page.wait_for_timeout(220)
    assert page.locator('.h4-cursor img').evaluate('e => getComputedStyle(e).transform').startswith('matrix(0.906308, -0.422618')
    page.locator('#export').hover(force=True)
    expect(cursor).not_to_have_class('h4-cursor is-clickable')
    page.locator('label.button').hover()
    expect(cursor).to_have_class('h4-cursor is-clickable')
    page.wait_for_timeout(220)
    assert page.locator('.h4-cursor img').evaluate('e => getComputedStyle(e).transform').startswith('matrix(1, 0, 0, 1, 0, 0)')
    page.locator('#files').set_input_files([str(ROOT/'samples/clip-a.mp4'),str(ROOT/'samples/clip-b.mp4')])
    expect(page.locator('#count')).to_have_text('2 clips',timeout=120000)
    expect(page.locator('#assemble')).to_be_enabled(timeout=120000)
    page.locator('.connector').click()
    page.locator('#effect').hover()
    expect(page.locator('dialog .h4-cursor')).to_be_visible()
    expect(cursor).to_have_class('h4-cursor is-clickable')
    page.keyboard.press('Escape')
    page.locator('h1').hover()
    expect(page.locator('body > .h4-cursor')).to_be_visible()
    page.locator('#player').hover()
    expect(cursor).to_be_hidden()
    assert page.locator('html').get_attribute('class') in (None, '')
    page.locator('h1').hover()
    page.emulate_media(reduced_motion='reduce')
    assert page.locator('.h4-cursor img').evaluate('e => getComputedStyle(e).transitionDuration') == '0s'
    page.emulate_media(reduced_motion='no-preference')
    page.locator('label.button').hover()
    page.wait_for_timeout(220)
    (ROOT/'work').mkdir(exist_ok=True)
    page.screenshot(path=str(ROOT/'work/h4-cursor.png'),full_page=True)
    assert not errors, errors
    touch = browser.new_context(is_mobile=True,has_touch=True,viewport={'width':390,'height':844})
    mobile = touch.new_page(); mobile.goto(base); mobile.mouse.move(50,50)
    expect(mobile.locator('.h4-cursor')).to_be_hidden()
    broken = browser.new_page()
    broken.route('**/h4-cursor.svg', lambda route: route.abort())
    broken.goto(base); broken.locator('h1').hover()
    expect(broken.locator('.h4-cursor')).to_be_hidden()
    assert broken.locator('html').get_attribute('class') in (None, '')
    browser.close()
print('PASS: original cursor size, rotation, disabled controls, modal, native video/touch, reduced motion and asset failure fallback')
