"""Optional real-browser test. Start tools/server.py on port 8765 first.
Requires Playwright + Chromium only for development tests, not the application.
"""
from pathlib import Path
import json
import os
import re
import hashlib
import sys
import shutil
import urllib.error
import urllib.request
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
files = sys.argv[1:]
if len(files) < 3:
    raise SystemExit('Usage: python3 tests/browser_smoke.py VIDEO_A VIDEO_B VIDEO_C')
artifacts = ROOT/'work/browser-smoke'
artifacts.mkdir(parents=True, exist_ok=True)
base = os.environ.get('H4_EDITOR_TEST_URL', 'http://127.0.0.1:8765')
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=shutil.which('chromium'))
    page = browser.new_page(viewport={'width': 1200, 'height': 1000}, accept_downloads=True)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(base)
    expect(page.locator('#files')).to_be_enabled()
    page.locator('#files').set_input_files(files[:3])
    expect(page.locator('#count')).to_have_text('3 clips', timeout=120000)
    expect(page.locator('#assemble')).to_be_enabled(timeout=120000)
    original_order = page.locator('.clip-select span').all_text_contents()
    page.get_by_role('button', name=f'Move {Path(files[0]).name} right', exact=True).click()
    assert page.locator('.clip-select span').all_text_contents()[1].endswith(Path(files[0]).name)
    page.get_by_role('button', name=f'Move {Path(files[0]).name} left', exact=True).click()
    assert page.locator('.clip-select span').all_text_contents() == original_order
    page.locator('.clip').nth(0).drag_to(page.locator('.clip').nth(1))
    assert page.locator('.clip-select span').all_text_contents()[1].endswith(Path(files[0]).name)
    page.get_by_role('button', name=f'Move {Path(files[0]).name} left', exact=True).click()
    assert page.locator('.clip-select span').all_text_contents() == original_order
    page.locator('.connector').first.click()
    page.locator('#effect').select_option('cut')
    expect(page.locator('#duration-control')).to_be_hidden()
    expect(page.locator('#motion-control')).to_be_hidden()
    page.locator('#effect').select_option('classic-mosh')
    expect(page.locator('#repeat-control')).to_be_hidden()
    page.locator('#effect').select_option('frame-melt')
    expect(page.locator('#repeat-control')).to_be_visible()
    expect(page.locator('#loop-control')).to_be_hidden()
    page.locator('#effect').select_option('motion-loop')
    expect(page.locator('#ending')).to_have_value('flow')
    page.locator('#ending').select_option('reset')
    expect(page.locator('#duration-note')).to_contain_text('visible jump')
    page.locator('#ending').select_option('flow')
    expect(page.locator('#duration-note')).to_contain_text('without a hard image reset')
    page.locator('#duration').fill('24')
    page.locator('#loop-length').fill('6')
    expect(page.locator('#duration-value')).to_have_text('1.00 s')
    expect(page.locator('#loop-value')).to_have_text('0.25 s')
    page.get_by_text('Choose motion', exact=True).click()
    page.locator('#motion-start').fill('12')
    expect(page.locator('#motion-start-value')).to_have_text('0.54 s')
    page.locator('#watch-motion').click()
    page.wait_for_function('document.querySelector("#motion-preview").currentTime > .56')
    page.get_by_role('button', name='Close settings').click()
    expect(page.locator('#motion-preview')).not_to_have_attribute('src', re.compile('.+'))
    page.locator('.connector').nth(1).click()
    page.locator('#effect').select_option('classic-mosh')
    page.locator('#duration').fill('12')
    page.locator('#motion-start').fill('6')
    page.get_by_role('button', name='Close settings').click()
    # Reload preserves ordered clips and settings without duplicating uploads.
    page.reload()
    expect(page.locator('#count')).to_have_text('3 clips')
    expect(page.locator('.connector').first).to_contain_text('Loop')
    page.locator('#assemble').click()
    expect(page.locator('#status')).to_contain_text('verified full decode', timeout=120000)
    page.wait_for_function('document.querySelector("#player").videoWidth === 640 && document.querySelector("#player").videoHeight === 480')
    page.locator('#player').evaluate('(v) => v.play()')
    page.wait_for_function('document.querySelector("#player").currentTime > .3')
    page.locator('#player').evaluate('(v) => v.pause()')
    url = page.locator('#player').get_attribute('src')
    duration = page.locator('#player').evaluate('(v) => v.duration')
    with urllib.request.urlopen(base+'/api/jobs/'+url.rsplit('/', 1)[1]) as response:
        report = json.load(response)['result']
    assert report['boundaries'][0]['effect'] == 'motion-loop'
    assert report['boundaries'][0]['ending'] == 'flow'
    assert report['boundaries'][0]['reset_frame'] is None
    assert report['boundaries'][1]['ending'] == 'reset'
    assert report['boundaries'][0]['b_vop_indices'] == [13+i%6 for i in range(24)]
    assert report['boundaries'][1]['b_vop_indices'] == list(range(7,19))
    assert report['source_sha256'] == [hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in files[:3]]
    # Returning from an individual clip must reuse the complete render and position.
    page.locator('#player').evaluate('(v) => {v.pause(); v.currentTime=1.1}')
    page.wait_for_function('!document.querySelector("#player").seeking')
    page.get_by_role('button', name=f'Select {Path(files[2]).name}', exact=True).click()
    expect(page.locator('#preview-label')).to_contain_text('Clip preview')
    render_posts = []
    def record_job(request):
        if request.method == 'POST' and request.url.endswith('/api/jobs'):
            render_posts.append(request.url)
    page.on('request', record_job)
    page.locator('#assemble').click()
    page.wait_for_function('document.querySelector("#player").readyState >= 2 && !document.querySelector("#player").seeking')
    expect(page.locator('#preview-label')).to_contain_text('Assembled preview')
    assert page.locator('#player').get_attribute('src') == url
    assert abs(page.locator('#player').evaluate('(v) => v.currentTime') - 1.1) < .1
    assert render_posts == []
    page.remove_listener('request', record_job)
    page.get_by_role('button', name=f'Select {Path(files[0]).name}', exact=True).click()
    page.locator('#assemble').click()
    expect(page.locator('#preview-label')).to_contain_text('Assembled preview')

    page.reload()
    expect(page.locator('#status')).to_contain_text('verified full decode', timeout=120000)
    assert page.locator('#player').get_attribute('src') == url
    page.locator('#player').evaluate('(v) => {v.currentTime = v.duration - .25}')
    page.wait_for_function('document.querySelector("#player").currentTime > document.querySelector("#player").duration - .3')
    with page.expect_download() as event:
        page.locator('#export').click()
    event.value.save_as(artifacts/'sequence.mp4')
    assert (artifacts/'sequence.mp4').stat().st_size > 1000
    with urllib.request.urlopen(base+url) as response:
        assert response.read() == (artifacts/'sequence.mp4').read_bytes()
    page.locator('.connector').first.click()
    page.locator('#preview-transition').click()
    page.wait_for_function('document.querySelector("#player").currentTime < document.querySelector("#player").duration - 1')
    # Editing invalidates the previous assembled/download resource.
    page.locator('.connector').first.click()
    page.locator('#duration').fill('25')
    page.get_by_role('button', name='Close settings').click()
    expect(page.locator('#download')).to_be_hidden()
    page.route('**/api/jobs', lambda route: route.fulfill(status=503, content_type='application/json', body='{"error":"Test processing failure"}'))
    page.locator('#assemble').click()
    expect(page.locator('#error')).to_have_text('Test processing failure')
    expect(page.locator('#assemble')).to_be_enabled()
    page.unroute('**/api/jobs')
    page.locator('#assemble').click()
    page.wait_for_function('sessionStorage.getItem("h4-job") !== null')
    page.reload()
    expect(page.locator('#status')).to_contain_text('verified full decode', timeout=120000)
    page.wait_for_function('document.querySelector("#player").readyState >= 2')
    page.locator('#player').evaluate('(v) => {v.pause(); v.currentTime = Math.min(3.4, v.duration - .1)}')
    page.wait_for_function('!document.querySelector("#player").seeking && document.querySelector("#player").readyState >= 2')
    page.locator('#player').evaluate('(v) => v.play()')
    page.wait_for_function('document.querySelector("#player").currentTime > 3.6')
    page.locator('#player').evaluate('(v) => v.pause()')
    page.wait_for_timeout(400)  # Let native media-control seek/loading animations settle.
    page.screenshot(path=str(artifacts/'desktop.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    assert page.locator('.connector').evaluate_all('items => items.every(el => el.scrollWidth <= el.clientWidth)')
    page.screenshot(path=str(artifacts/'mobile.png'), full_page=True)
    page.locator('.connector').first.click()
    page.locator('#motion-control').evaluate('(el) => {el.open = true}')
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    assert page.locator('.connector').evaluate_all('items => items.every(el => el.scrollWidth <= el.clientWidth)')
    page.locator('#preview-transition').scroll_into_view_if_needed()
    page.screenshot(path=str(artifacts/'motion-settings.png'), full_page=True)
    page.get_by_role('button', name='Close settings').click()
    # Remove releases the server-side clip and invalidates the render.
    page.get_by_role('button', name=f'Remove {Path(files[2]).name}', exact=True).click()
    expect(page.locator('#count')).to_have_text('2 clips')
    assert not errors, errors
    browser.close()

for header, expected_length in [('bytes=0-63', 64), ('bytes=-16', 16)]:
    with urllib.request.urlopen(urllib.request.Request(base+url, headers={'Range': header})) as response:
        assert response.status == 206
        assert len(response.read()) == expected_length
try:
    urllib.request.urlopen(urllib.request.Request(base+url, headers={'Range': 'bytes=999999999-'}))
    raise AssertionError('Expected range error')
except urllib.error.HTTPError as e:
    assert e.code == 416
try:
    urllib.request.urlopen(urllib.request.Request(base+'/api/jobs', data=b'{}', headers={'Origin':'https://other.example'}))
    raise AssertionError('Expected same-origin rejection')
except urllib.error.HTTPError as e:
    assert e.code == 403
print(json.dumps({'browser': 'chromium', 'clips': 3, 'duration': duration, 'javascript_errors': errors,
                  'upload_reorder_settings_reload_render_scrub_transition_preview_download_error_retry_remove_ranges': 'passed'}))
