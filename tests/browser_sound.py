"""Real audio-source import, sound toggle, silent preview/export and restoration."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
base=os.environ.get('H4_EDITOR_TEST_URL','http://127.0.0.1:8765')
if len(sys.argv)!=3:raise SystemExit('Usage: browser_sound.py VIDEO_A_WITH_AUDIO VIDEO_B_WITH_AUDIO')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('chromium'))
    page=browser.new_page(accept_downloads=True)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base)
    expect(page.locator('#sound')).to_be_checked()
    page.locator('#files').set_input_files(sys.argv[1:])
    expect(page.locator('#count')).to_have_text('2 clips',timeout=120000)
    expect(page.locator('#assemble')).to_be_enabled(timeout=120000)
    page.locator('#sound').uncheck()
    assert page.locator('#player').evaluate('v=>v.muted')
    expect(page.locator('#sound-label')).to_have_text('Sound off')
    page.locator('#player').evaluate('v=>v.muted=false')
    page.wait_for_function('document.querySelector("#player").muted')
    page.locator('#motion-preview').evaluate('v=>v.muted=false')
    page.wait_for_function('document.querySelector("#motion-preview").muted')
    page.locator('.connector').click();page.locator('#effect').select_option('reset-pulse')
    page.locator('#preview-transition').click()
    expect(page.locator('#status')).to_contain_text('verified full decode',timeout=120000)
    preview_url=page.locator('#player').get_attribute('src')
    report=page.request.get(base+'/api/jobs/'+preview_url.rsplit('/',1)[1]).json()['result']
    assert not report['audio'] and 'preview' in report
    with page.expect_download(timeout=120000) as download:page.locator('#export').click()
    target=ROOT/'work/browser-sound-off.mp4';download.value.save_as(target)
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(target)]))['streams']
    assert not any(s['codec_type']=='audio' for s in streams)
    page.reload()
    expect(page.locator('#status')).to_contain_text('verified full decode',timeout=120000)
    expect(page.locator('#sound')).not_to_be_checked()
    assert page.locator('#player').evaluate('v=>v.muted')
    page.locator('#sound').check()
    page.locator('#assemble').click()
    expect(page.locator('#status')).to_contain_text('verified full decode',timeout=120000)
    url=page.locator('#player').get_attribute('src')
    report=page.request.get(base+'/api/jobs/'+url.rsplit('/',1)[1]).json()['result']
    assert report['audio'] and 'preview' not in report
    assert not page.locator('#player').evaluate('v=>v.muted')
    bad=page.request.post(base+'/api/jobs',data={'clips':[],'transitions':[],'audio':'false'})
    assert bad.status==400
    assert not errors,errors
    browser.close()
print('PASS: sound default on, muted source preview, silent short preview/full export, session recovery and restored original audio')
