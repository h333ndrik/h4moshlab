"""Exercise actual new-effect selection, render evidence and export in Chromium."""
from pathlib import Path
import json
import os
import shutil
import subprocess
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
base=os.environ.get('H4_EDITOR_TEST_URL','http://127.0.0.1:8765')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('chromium'))
    page=browser.new_page(accept_downloads=True)
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base)
    page.locator('#files').set_input_files([str(ROOT/'samples/clip-a.mp4'),str(ROOT/'samples/clip-b.mp4')])
    expect(page.locator('#count')).to_have_text('2 clips',timeout=120000)
    expect(page.locator('#assemble')).to_be_enabled(timeout=120000)
    for effect in ('progressive-melt','motion-stutter'):
        page.locator('.connector').click()
        page.locator('#effect').select_option(effect)
        expect(page.locator('#motion-start')).to_be_disabled()
        page.locator('#duration').fill('48')
        if effect=='progressive-melt':
            expect(page.locator('#repeat-control')).to_be_visible()
            expect(page.locator('#loop-control')).to_be_hidden()
            page.locator('#repeat').fill('6')
        else:
            expect(page.locator('#repeat-control')).to_be_hidden()
            expect(page.locator('#loop-control')).to_be_visible()
            page.locator('#loop-length').fill('8')
            expect(page.locator('label[for=loop-length]')).to_contain_text('Pulse length')
        with page.expect_response(lambda r:'/api/jobs' in r.url and r.request.method=='POST') as response:
            page.locator('#preview-transition').click()
        job=response.value.json()['id']
        expect(page.locator('#status')).to_contain_text('verified full decode',timeout=120000)
        report=page.request.get(base+'/api/jobs/'+job).json()
        assert report['result']['boundaries'][0]['effect']==effect
        assert report['result']['boundaries'][0]['ending']=='flow'
        assert report['result']['boundaries'][0]['b_vop_indices'][-12:]==list(range(37,49))
        with page.expect_download() as download: page.locator('#export').click()
        target=ROOT/'work'/f'browser-{effect}.mp4'
        download.value.save_as(target)
        subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(target),'-f','null','-'],check=True)
        page.locator('.clip-select').first.click()
        page.locator('#assemble').click()
        expect(page.locator('#status')).to_contain_text('verified full decode')
    assert not errors,errors
    browser.close()
print('PASS: Progressive Melt and Motion Stutter settings, rendered plan, flow ending, full decode, export and Assemble return')
