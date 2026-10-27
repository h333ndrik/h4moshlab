"""Chromium touch emulation, not a physical Safari compatibility test."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
base = os.environ.get('H4_EDITOR_TEST_URL', 'http://127.0.0.1:8765')
files = sys.argv[1:] or [str(ROOT/'samples/clip-a.mp4'), str(ROOT/'samples/clip-b.mp4')]
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=shutil.which('chromium'))
    context = browser.new_context(viewport={'width':390,'height':844}, has_touch=True, is_mobile=True, accept_downloads=True)
    page = context.new_page()
    errors = []
    downloads = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('download', lambda d: downloads.append(d))
    page.goto(base)
    expect(page.locator('#phone-info')).to_be_hidden()
    page.locator('#files').set_input_files(files[:2])
    expect(page.locator('#count')).to_have_text('2 clips', timeout=120000)
    expect(page.locator('#export')).to_be_enabled(timeout=120000)
    assert page.locator('.clip').evaluate_all('(cards) => cards.every(c => !c.draggable)')
    for width in (320,390,430):
        page.set_viewport_size({'width':width,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    controls = page.locator('.clip-controls button').evaluate_all('(buttons) => buttons.map(b => ({w:b.getBoundingClientRect().width,h:b.getBoundingClientRect().height}))')
    assert all(c['w'] >= 44 and c['h'] >= 44 for c in controls)
    original = [s.split('. ', 1)[1] for s in page.locator('.clip-select span').all_text_contents()]
    page.locator('.clip').first.locator('.clip-controls button').nth(1).click()
    assert [s.split('. ', 1)[1] for s in page.locator('.clip-select span').all_text_contents()] == original[::-1]
    page.locator('.connector').click()
    expect(page.locator('#transition-dialog')).to_be_visible()
    assert page.locator('#effect').evaluate('(e) => parseFloat(getComputedStyle(e).fontSize)') >= 16
    page.keyboard.press('Escape')
    page.locator('#export').click()
    expect(page.locator('#status')).to_contain_text('Tap Export MP4 again', timeout=120000)
    assert not downloads
    with page.expect_download(timeout=30000) as result:
        page.locator('#export').click()
    target = ROOT/'work/mobile-smoke.mp4'
    result.value.save_as(target)
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(target),'-f','null','-'], check=True)
    assert not errors, errors
    page.screenshot(path=str(ROOT/'work/mobile-smoke.png'), full_page=True)
    browser.close()
print('PASS: touch import, reorder, layout, transition dialog, two-tap export and full video decode')
