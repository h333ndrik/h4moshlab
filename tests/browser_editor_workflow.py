"""End-to-end undo, presets, BPM, clip look, project save/relink and real exports."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
base=os.environ.get('H4_EDITOR_TEST_URL','http://127.0.0.1:8801')
cold=os.environ.get('H4_EDITOR_COLD_URL','http://127.0.0.1:8802')
files=sys.argv[1:] or [str(ROOT/'samples/clip-a.mp4'),str(ROOT/'samples/clip-b.mp4')]
artifacts=ROOT/'work/editor-workflow';artifacts.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('chromium'))
    page=browser.new_page(accept_downloads=True,viewport={'width':1200,'height':1000});errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base);expect(page.locator('#files')).to_be_enabled()
    page.locator('#files').set_input_files(files)
    expect(page.locator('#count')).to_have_text('2 clips',timeout=120000);expect(page.locator('#assemble')).to_be_enabled(timeout=120000)
    page.locator('#undo').click();expect(page.locator('#count')).to_have_text('0 clips')
    page.locator('#redo').click();expect(page.locator('#count')).to_have_text('2 clips')
    original=page.locator('.clip-select span').all_text_contents()
    page.locator('.clip').first.locator('.clip-controls button').nth(1).click()
    page.locator('#undo').click();expect(page.locator('.clip-select span').first).to_have_text(original[0])
    page.locator('.connector').click();page.locator('#effect').select_option('reset-pulse');page.locator('#preset').select_option('1')
    expect(page.locator('#preset')).to_have_value('1');expect(page.locator('#apply-tempo')).to_be_enabled()
    expect(page.locator('#repeat-value')).to_have_text('4×')
    page.locator('#tempo-control summary').click();page.locator('#bpm').fill('137');page.locator('#apply-tempo').click()
    expect(page.locator('#tempo-note')).to_contain_text('137 BPM');expect(page.locator('#loop-value')).to_have_text('0.46 s')
    page.keyboard.press('Escape');page.locator('#undo').click();page.locator('.connector').click()
    expect(page.locator('#loop-value')).to_have_text('0.50 s');page.keyboard.press('Escape');page.locator('#redo').click()
    page.locator('.connector').click();expect(page.locator('#tempo-note')).to_contain_text('137 BPM')
    # A slider gesture is one undo step rather than one per input event.
    page.locator('#repeat').evaluate("e=>{for(const n of [5,6,7,8]){e.value=n;e.dispatchEvent(new Event('input',{bubbles:true}));}e.dispatchEvent(new Event('change',{bubbles:true}));}")
    expect(page.locator('#repeat-value')).to_have_text('8×');page.keyboard.press('Escape');page.locator('#undo').click()
    page.locator('.connector').click();expect(page.locator('#repeat-value')).to_have_text('4×');page.keyboard.press('Escape')
    page.locator('#sound').uncheck();page.locator('#undo').click();expect(page.locator('#sound')).to_be_checked()
    page.locator('.clip-controls').last.locator('button').last.click();expect(page.locator('#count')).to_have_text('1 clip')
    page.locator('#undo').click();expect(page.locator('#count')).to_have_text('2 clips')
    page.locator('.clip-look').first.select_option('negative-color');expect(page.locator('#status')).to_contain_text('Clip look ready',timeout=120000)
    page.locator('#undo').click();expect(page.locator('.clip-look').first).to_have_value('original')
    page.locator('#redo').click();expect(page.locator('.clip-look').first).to_have_value('negative-color')
    # Project is a lightweight settings file, with hashes and clip looks.
    page.locator('#project-menu summary').click()
    with page.expect_download() as download:page.locator('#save-project').click()
    project=artifacts/'saved.h4mosh';download.value.save_as(project);saved=json.loads(project.read_text())
    assert saved['clips'][0]['look']=='negative-color';assert saved['transitions'][0]['tempo']['bpm']==137
    assert saved['transitions'][0]['loop_frames']==11
    assert len(project.read_bytes())<16384
    page.locator('#assemble').click();expect(page.locator('#status')).to_contain_text('verified full decode',timeout=120000)
    result_url=page.locator('#player').get_attribute('src')
    report=page.request.get(base+'/api/jobs/'+result_url.rsplit('/',1)[1]).json()['result']
    assert report['boundaries'][0]['tempo']['bpm']==137
    assert report['boundaries'][0]['reference_reset_offsets']==[10,20,31,41]
    with page.expect_download(timeout=120000) as export:page.locator('#export').click()
    export.value.save_as(artifacts/'sequence.mp4')
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(artifacts/'sequence.mp4'),'-f','null','-'],check=True)
    # New server = no cached media. Relink renamed original files by SHA256.
    other=browser.new_page(accept_downloads=True,viewport={'width':390,'height':844});other.on('pageerror',lambda e:errors.append(str(e)))
    other.goto(cold);expect(other.locator('#files')).to_be_enabled();other.locator('#project-menu summary').click();other.locator('#open-project').set_input_files(project)
    expect(other.locator('#project-dialog')).to_be_visible();expect(other.locator('#project-note')).to_contain_text('original videos')
    with tempfile.TemporaryDirectory() as directory:
        originals=[]
        for i,file in enumerate(files):
            target=Path(directory)/f'renamed-{i}.mp4';shutil.copyfile(file,target);originals.append(str(target))
        other.locator('#relink-files').set_input_files(originals)
        expect(other.locator('#project-dialog')).not_to_be_visible(timeout=120000)
    expect(other.locator('#count')).to_have_text('2 clips');expect(other.locator('.clip-look').first).to_have_value('negative-color')
    other.locator('.connector').click();expect(other.locator('#tempo-note')).to_contain_text('137 BPM');expect(other.locator('#repeat-value')).to_have_text('4×')
    other.keyboard.press('Escape');other.locator('#undo').click();expect(other.locator('#count')).to_have_text('0 clips')
    other.locator('#redo').click();expect(other.locator('#count')).to_have_text('2 clips')
    other.locator('#assemble').click();expect(other.locator('#status')).to_contain_text('verified full decode',timeout=120000)
    assert other.evaluate('document.documentElement.scrollWidth<=innerWidth')
    other.screenshot(path=str(artifacts/'mobile.png'),full_page=True)
    page.screenshot(path=str(artifacts/'desktop.png'),full_page=True)
    assert not errors,errors
    browser.close()
print('PASS: imports/removals/reorder/slider/sound/look undo-redo, presets, BPM, real export, project hash relink after restart and narrow layout')
