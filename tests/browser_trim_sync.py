"""Optional Chromium regression: fresh server via H4_EDITOR_TEST_URL; FFmpeg tone fixture."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
artifacts=ROOT/'work/trim-sync'
artifacts.mkdir(parents=True,exist_ok=True)
source=artifacts/'tone.mp4'
subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=160x120:rate=24:duration=2',
    '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=2',
    '-c:v','libx264','-threads','2','-c:a','aac',str(source)],check=True)
original=hashlib.sha256(source.read_bytes()).hexdigest()
base=os.environ.get('H4_EDITOR_TEST_URL','http://127.0.0.1:8765')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('chromium'))
    page=browser.new_page(viewport={'width':1200,'height':1000});errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base);expect(page.locator('#files')).to_be_enabled()
    page.locator('#files').set_input_files(str(source))
    expect(page.locator('#count')).to_have_text('1 clip',timeout=120000)
    expect(page.locator('#assemble')).to_be_enabled(timeout=120000)
    page.get_by_role('button',name='Duplicate tone.mp4',exact=True).click()
    expect(page.locator('#count')).to_have_text('2 clips')
    def trim(index,start,end):
        page.locator('.clip').nth(index).get_by_role('button',name='Trim tone.mp4',exact=True).click()
        page.locator('#trim-in').fill(str(start));page.locator('#trim-out').fill(str(end))
        page.locator('#trim-apply').click()
        expect(page.locator('#trim-dialog')).not_to_be_visible(timeout=120000)
    trim(0,4,28)
    expect(page.locator('#assemble')).to_be_enabled(timeout=120000)
    assert page.evaluate('state.clips.map(c=>c.frames)')==[24,48]
    page.locator('.connector').click();page.locator('#effect').select_option('progressive-melt')
    page.get_by_role('button',name='Close settings').click()
    trim(1,12,22)
    assert page.evaluate('state.clips.map(c=>c.frames)')==[24,10]
    assert page.evaluate('state.clips[0].id!==state.clips[1].id && clipSource(state.clips[0])===clipSource(state.clips[1])')
    page.locator('.connector').click()
    option=page.locator('#effect option[value="progressive-melt"]')
    assert option.is_disabled()
    assert option.evaluate('e=>e.disabled && e.matches(":disabled")')
    page.get_by_role('button',name='Close settings').click();page.locator('#undo').click()
    expect(page.locator('#status')).to_have_text('Undone.',timeout=120000)
    expect(page.locator('#undo')).to_be_enabled(timeout=120000)
    expect(page.locator('#assemble')).to_be_enabled(timeout=120000)
    assert page.evaluate('state.clips.map(c=>c.frames)')==[24,48]
    page.locator('.connector').click();assert not option.is_disabled()
    page.get_by_role('button',name='Close settings').click();page.locator('#redo').click()
    expect(page.locator('#status')).to_have_text('Redone.',timeout=120000)
    expect(page.locator('#undo')).to_be_enabled(timeout=120000)
    expect(page.locator('#assemble')).to_be_disabled(timeout=120000)
    assert page.evaluate('state.clips.map(c=>c.frames)')==[24,10]
    page.locator('.connector').click();assert option.is_disabled()
    page.locator('#effect').select_option('classic-mosh');page.get_by_role('button',name='Close settings').click()
    page.locator('#assemble').click()
    expect(page.locator('#status')).to_contain_text('verified full decode',timeout=120000)
    url=page.locator('#player').get_attribute('src')
    report=page.request.get(base+'/api/jobs/'+url.rsplit('/',1)[1]).json()['result']
    assert report['frames']==33 and report['audio_samples']==33*2000 and report['audio']
    assert report['source_sha256']==[original,original] and report['full_decode']=='passed'
    output=artifacts/'trimmed-duplicates.mp4';output.write_bytes(page.request.get(base+url).body())
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(output),'-f','null','-'],check=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==original
    # Two further duplicate actions: the final duplicate must survive Undo/Redo
    # with exactly four entries, stable IDs/order and independent parameters.
    page.locator('.clip').nth(0).get_by_role('button',name='Duplicate tone.mp4',exact=True).click()
    expect(page.locator('#count')).to_have_text('3 clips')
    page.locator('.clip-look').nth(1).select_option('negative-bw')
    expect(page.locator('#assemble')).to_be_enabled(timeout=120000)
    def snapshot():
        return page.evaluate('({clips:state.clips.map(c=>({id:c.id,source:clipSource(c),frames:c.frames,...clipTrim(c),look:c.look})),settings:state.clips.slice(1).map((_,i)=>({...setting(i)}))})')
    before=snapshot()
    page.locator('.clip').nth(1).get_by_role('button',name='Duplicate tone.mp4',exact=True).click()
    expect(page.locator('#count')).to_have_text('4 clips')
    expected=snapshot()
    assert len({c['id'] for c in expected['clips']})==4
    assert len({c['source'] for c in expected['clips']})==1
    page.locator('#undo').click()
    expect(page.locator('#count')).to_have_text('3 clips',timeout=120000)
    expect(page.locator('#status')).to_have_text('Undone.',timeout=120000)
    expect(page.locator('#undo')).to_be_enabled(timeout=120000)
    assert snapshot()==before
    page.locator('#redo').click()
    expect(page.locator('#count')).to_have_text('4 clips',timeout=120000)
    expect(page.locator('#status')).to_have_text('Redone.',timeout=120000)
    expect(page.locator('#undo')).to_be_enabled(timeout=120000)
    assert snapshot()==expected
    # Change the restored duplicate only; its parent retains its own look/trim.
    page.locator('.clip-look').nth(2).select_option('negative-color')
    expect(page.locator('#assemble')).to_be_enabled(timeout=120000)
    trim(2,8,20)
    expect(page.locator('#assemble')).to_be_enabled(timeout=120000)
    assert page.evaluate('state.clips.map(c=>c.frames)')==[24,24,12,10]
    assert page.locator('.clip-look').nth(1).input_value()=='negative-bw'
    assert page.locator('.clip-look').nth(2).input_value()=='negative-color'
    assert page.evaluate('setting(0)!==setting(1) && setting(0).duration!==setting(1).duration')
    page.locator('#assemble').click()
    expect(page.locator('#status')).to_contain_text('verified full decode',timeout=120000)
    url=page.locator('#player').get_attribute('src')
    report=page.request.get(base+'/api/jobs/'+url.rsplit('/',1)[1]).json()['result']
    assert report['frames']==67 and report['audio_samples']==67*2000 and report['audio']
    assert report['source_sha256']==[original]*4 and report['full_decode']=='passed'
    output=artifacts/'four-clips.mp4';output.write_bytes(page.request.get(base+url).body())
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(output),'-f','null','-'],check=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==original
    assert not errors,errors
    page.screenshot(path=str(artifacts/'desktop.png'),full_page=True)
    browser.close()
print(json.dumps({'browser':'chromium','different_duplicate_trims_disable_undo_redo':'passed',
                  'four_clips_after_redo':'passed','initial_frames':33,'initial_audio_samples':66000,'frames':67,'audio_samples':134000,'full_decode':'passed','source_unchanged':True,'javascript_errors':errors}))
