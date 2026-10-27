"""Real browser coverage for short previews, reset pulses, A/B and source marks."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
base=os.environ.get('H4_EDITOR_TEST_URL','http://127.0.0.1:8765')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('chromium'))
    page=browser.new_page(accept_downloads=True,viewport={'width':1000,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base)
    files=sys.argv[1:] or [str(ROOT/'samples/clip-a.mp4'),str(ROOT/'samples/clip-b.mp4'),str(ROOT/'samples/clip-a.mp4')]
    page.locator('#files').set_input_files(files)
    expect(page.locator('#count')).to_have_text('3 clips',timeout=120000)
    expect(page.locator('#assemble')).to_be_enabled(timeout=120000)
    page.locator('.connector').first.click();page.locator('#effect').select_option('reset-pulse')
    expect(page.locator('#smooth-control')).to_be_hidden()
    expect(page.locator('#repeat-control')).to_be_visible()
    expect(page.locator('label[for=loop-length]')).to_contain_text('Reset interval')
    page.locator('#duration').fill('48');page.locator('#loop-length').fill('12')
    with page.expect_response(lambda r:r.url.endswith('/api/jobs') and r.request.method=='POST') as response:
        page.locator('#preview-transition').click()
    job=response.value.json()['id']
    expect(page.locator('#status')).to_contain_text('verified full decode',timeout=120000)
    report=page.request.get(base+'/api/jobs/'+job).json()['result']
    assert report['frames']==84
    assert report['preview']['boundary_index']==0
    assert report['boundaries'][0]['reference_reset_offsets']==[11,23,35,47]
    assert page.evaluate('sessionStorage.getItem("h4-job")') is None
    with page.expect_download(timeout=120000) as download:page.locator('#export').click()
    target=ROOT/'work/browser-reset-pulse.mp4';download.value.save_as(target)
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(target),'-f','null','-'],check=True)
    full_url=page.locator('#player').get_attribute('src')
    full=page.request.get(base+'/api/jobs/'+full_url.rsplit('/',1)[1]).json()['result']
    assert full['frames']>report['frames'] and 'preview' not in full
    # A cached assembled movie stays intact when inspecting a transition.
    page.locator('.connector').first.click();page.locator('#preview-transition').click()
    assert page.locator('#player').get_attribute('src')==full_url
    page.locator('.connector').first.click();page.locator('#effect').select_option('frame-melt')
    page.locator('#duration').fill('48');page.locator('#release').fill('12')
    expect(page.locator('#release-value')).to_have_text('0.50 s')
    settings=page.evaluate('sessionStorage.getItem("h4-sequence")')
    page.locator('#compare-control summary').click()
    urls=[]
    for button,gentle in [('compare-original',False),('compare-gentler',True)]:
        if button=='compare-gentler':page.locator('.connector').first.click()
        with page.expect_response(lambda r:r.url.endswith('/api/jobs') and r.request.method=='POST') as response:
            page.locator('#'+button).click()
        expect(page.locator('#status')).to_contain_text('verified full decode',timeout=120000)
        result=page.request.get(base+'/api/jobs/'+response.value.json()['id']).json()['result']
        assert result['boundaries'][0]['parameters'].get('smooth',False)==gentle
        if gentle:assert result['boundaries'][0]['parameters']['release_duration']==.5
        assert page.evaluate('sessionStorage.getItem("h4-sequence")')==settings
        urls.append(page.locator('#player').get_attribute('src'))
    assert urls[0]!=urls[1]
    requests=[]
    page.on('request',lambda r:requests.append(r.url) if r.method=='POST' else None)
    page.locator('.connector').first.click();page.locator('#compare-original').click()
    expect(page.locator('#preview-label')).to_contain_text('Original')
    assert page.locator('#player').get_attribute('src')==urls[0]
    assert not requests
    page.locator('#assemble').click()
    expect(page.locator('#preview-label')).to_contain_text('Assembled preview',timeout=120000)
    assert page.locator('#player').get_attribute('src') not in urls
    page.locator('.connector').first.click();page.locator('#effect').select_option('motion-loop')
    page.locator('#motion-control').evaluate('(e)=>e.open=true')
    page.wait_for_function('document.querySelector("#motion-preview").readyState>=1')
    page.locator('#motion-preview').evaluate('v=>v.currentTime=.5')
    page.wait_for_function('!document.querySelector("#motion-preview").seeking')
    page.locator('#mark-motion-start').click()
    expect(page.locator('#motion-start-value')).to_have_text('0.50 s')
    page.locator('#motion-preview').evaluate('v=>v.currentTime=1')
    page.wait_for_function('!document.querySelector("#motion-preview").seeking')
    page.locator('#mark-motion-end').click()
    expect(page.locator('#loop-value')).to_have_text('0.54 s')
    # New controls remain usable in a narrow dialog.
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.get_by_role('button',name='Close settings').click()
    bad=page.request.post(base+'/api/jobs',data={'clips':[],'transitions':[],'preview_boundary':99})
    assert bad.status==400
    assert not errors,errors
    browser.close()
print('PASS: codec Reset Pulse, short preview, full export, preserved full cache, original/Gentler A/B cache, adjustable release and source marks')
