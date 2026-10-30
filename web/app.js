'use strict';
const $ = id => document.getElementById(id);
const transitionCache = new Map();
const state = {sound:true, clips: [], settings: new Map(), active: null, busy: false, ready: null, job: null, dialogIndex: null, previewEnd: null, sequencePosition: 0};
const player = $('player');
const smoothEffects = ['frame-melt', 'progressive-melt', 'motion-stutter'];
const alignedEffects = ['loop-release', 'progressive-melt', 'motion-stutter', 'reset-pulse'];
const names = {'reset-pulse': 'Reset Pulse', 'progressive-melt': 'Progressive Melt', 'motion-stutter': 'Motion Stutter', 'cut': 'Cut', 'classic-mosh': 'Classic Mosh', 'frame-melt': 'Frame Melt', 'loop-release': 'Loop Release', 'motion-loop': 'Motion Loop'};
const notes = {'reset-pulse': 'Real codec datamoshing: the first clear frame of the incoming video flashes back at each pulse; repeated prediction frames distort it again. Intentionally rhythmic, not a smooth dissolve.', 'progressive-melt': 'Real codec datamoshing: repeated prediction frames gradually give way to uninterrupted motion. Lower repetitions ease the drag, not the accumulated distortion.', 'motion-stutter': 'Real codec datamoshing: repeated prediction bursts alternate with moving passages, then finish with uninterrupted motion. Original audio stays unchanged.', 'loop-release': 'Real codec datamoshing: repeated motion blocks give way to uninterrupted motion before the transition ends. Block changes can still jump. Use Continue motion for an exit without a reference reset.', 'cut': 'An ordinary cut. No datamoshing.', 'classic-mosh': 'Real codec datamoshing: B’s P-frames inherit A’s final image.', 'frame-melt': 'Real codec datamoshing: repeated compressed P-frames accumulate dragging and distortion.', 'motion-loop': 'Real codec datamoshing: a short motion sequence repeats and keeps reshaping the previous image.'};
const abort = new AbortController();
const touchUI = () => window.matchMedia('(pointer:coarse)').matches;
function error(message = '') { $('error').textContent = message; $('error').hidden = !message; }
function status(message) { $('status').textContent = message; }
function source(url, label) {
  if (state.ready && player.readyState >= 1 && player.getAttribute('src') === state.ready.url && url !== state.ready.url) state.sequencePosition = player.currentTime;
  if (state.pendingSeek) { player.removeEventListener('loadedmetadata', state.pendingSeek); state.pendingSeek = null; }
  if (player.getAttribute('src') !== url) { player.pause(); player.removeAttribute('src'); player.load(); player.src = url; player.load(); }
  $('empty').hidden = Boolean(url); $('preview-label').textContent = label; controls();
}
function setting(index) {
  const incoming = state.clips[index + 1], key = `${state.clips[index].id}|${incoming.id}`;
  if (!state.settings.has(key)) state.settings.set(key, {effect: 'classic-mosh', duration: Math.min(24, incoming.frames - 1) / 24, repeat: 4});
  const conf = state.settings.get(key); conf.motion_start ??= 0; conf.loop_frames ??= 12; conf.repeat ??=4;
  return conf;
}
function invalidate() {
  try { sessionStorage.removeItem('h4-job'); } catch {}
  try { sessionStorage.setItem('h4-sequence', JSON.stringify({order: state.clips.map(c => c.id), settings: [...state.settings]})); } catch {}
  state.ready = null; state.previewEnd = null; state.sequencePosition = 0;
  const clip = state.clips.find(c => c.id === state.active);
  if (clip) source(clip.preview, `Clip preview · ${clip.name}`);
  else { player.pause(); player.removeAttribute('src'); player.load(); $('empty').hidden = false; $('preview-label').textContent = 'No video selected'; }
  status(state.clips.length ? 'Sequence changed. Assemble to preview the real transitions.' : 'Ready to import.');
}
function controls() {
  updateHistoryControls();
  for(const id of ['preset','apply-tempo'])$(id).disabled=state.busy;
  $('sound').disabled = state.busy;
  $('files').disabled = state.busy;
  $('import-label').style.pointerEvents = state.busy ? 'none' : '';
  $('import-label').setAttribute('aria-disabled', String(state.busy));
  document.querySelectorAll('.clip-look').forEach(select=>select.disabled=state.busy);
  document.querySelectorAll('#timeline button').forEach(b => b.disabled = state.busy || b.dataset.boundary === 'true');
  $('assemble').disabled = $('export').disabled = state.busy || !state.clips.length;
}
function busy(value) { state.busy = value; controls(); }
function button(label, action, title) { const b = document.createElement('button'); b.type = 'button'; b.textContent = label; b.title = title || label; b.setAttribute('aria-label', title || label); b.onclick = action; return b; }
function draw() {
  const timeline = $('timeline'); timeline.replaceChildren();
  $('count').textContent = `${state.clips.length} clip${state.clips.length === 1 ? '' : 's'}`;
  state.clips.forEach((clip, index) => {
    if (index) {
      const conf = setting(index - 1);
      const connector = button('', () => openTransition(index - 1), `Transition ${index}: ${names[conf.effect]}`);
      const method = document.createElement('span');
      method.textContent = conf.effect === 'reset-pulse' ? 'Pulse' : conf.effect === 'cut' ? 'Cut' : conf.effect === 'progressive-melt' ? 'Progressive' : conf.effect === 'motion-stutter' ? 'Stutter' : conf.effect === 'frame-melt' ? 'Melt' : conf.effect === 'loop-release' ? 'Release' : conf.effect === 'motion-loop' ? 'Loop' : 'Mosh';
      const time = document.createElement('span'); time.textContent = conf.effect === 'cut' ? '—' : `${conf.duration.toFixed(2)} s`;
      connector.className = 'connector'; connector.append(method, time); timeline.append(connector);
    }
    const card = document.createElement('div'); card.className = `clip${state.active === clip.id ? ' active' : ''}`;
    card.draggable = !state.busy && !touchUI();
    card.ondragstart = event => { if (state.busy) return event.preventDefault(); event.dataTransfer.setData('text/plain', clip.id); };
    card.ondragover = event => event.preventDefault();
    card.ondrop = event => { event.preventDefault(); move(event.dataTransfer.getData('text/plain'), index); };
    const select = button('', () => { state.active = clip.id; state.previewEnd = null; source(clip.preview, `Clip preview · ${clip.name}`); draw(); }, `Select ${clip.name}`);
    select.className = 'clip-select'; select.setAttribute('aria-pressed', String(state.active === clip.id));
    const img = document.createElement('img'); img.src = clip.thumbnail; img.alt = ''; img.draggable = false;
    const name = document.createElement('span'); name.textContent = `${index + 1}. ${clip.name}`;
    select.append(img, name); card.append(select);
    const actions = document.createElement('div'); actions.className = 'clip-controls';
    const left = button('←', () => move(clip.id, index - 1), `Move ${clip.name} left`);
    const right = button('→', () => move(clip.id, index + 1), `Move ${clip.name} right`);
    left.dataset.boundary = String(index === 0); right.dataset.boundary = String(index === state.clips.length - 1);
    const duration = document.createElement('small'); duration.textContent = `${clip.duration.toFixed(2)}s`;
    actions.append(left, right, duration, button('×', () => remove(clip.id), `Remove ${clip.name}`)); card.append(actions); const look=document.createElement('select');look.className='clip-look';look.setAttribute('aria-label',`Look for ${clip.name}`);for(const [value,label]of [['original','Original'],['black-white','Black & white'],['negative-bw','B&W negative'],['negative-color','Color negative']]){const option=document.createElement('option');option.value=value;option.textContent=label;look.append(option);}look.value=clip.look||'original';look.onchange=()=>setClipLook(clip.id,look.value);card.append(look);timeline.append(card);
  });
  document.querySelector('.sequence > .hint').textContent = touchUI() ? 'Swipe to browse clips. Use the arrows to reorder. Tap a connector to set a transition.' : 'Drag clips to reorder, or use the arrows. Select the connector between clips to set a transition.';
  controls();
}
function move(id, to) {
  if (state.busy || to < 0 || to >= state.clips.length) return;
  const from = state.clips.findIndex(c => c.id === id); if (from < 0 || from === to) return;
  finishEdit();beginEdit();state.clips.splice(to, 0, state.clips.splice(from, 1)[0]); invalidate(); draw();finishEdit();
}
async function request(url, options = {}) {
  const response = await fetch(url, {...options, signal: abort.signal});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}
async function remove(id) {
  if (state.busy) return; busy(true); error();
  try {
    await request(`/api/clips/${id}`, {method: 'DELETE'});
    finishEdit();beginEdit();state.clips = state.clips.filter(c => c.id !== id);
    for (const key of state.settings.keys()) if (key.split('|').includes(id)) state.settings.delete(key);
    if (state.active === id) state.active = state.clips[0]?.id || null;
    invalidate(); draw();finishEdit();
  } catch (e) { error(e.message); } finally { busy(false); }
}
function upload(file, index, total) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest(); xhr.open('POST', '/api/clips'); xhr.responseType = 'json';
    xhr.setRequestHeader('X-Filename', encodeURIComponent(file.name));
    xhr.upload.onprogress = e => { if (e.lengthComputable) { $('progress').value = e.loaded / e.total; status(`Uploading ${index}/${total} · ${file.name}`); } };
    xhr.upload.onload = () => { $('progress').removeAttribute('value'); status(`Preparing ${index}/${total} · ${file.name}`); };
    xhr.onload = () => xhr.status === 201 ? resolve(xhr.response) : reject(new Error(xhr.response?.error || 'Upload failed.'));
    xhr.onerror = () => reject(new Error('Upload connection failed.'));
    xhr.onabort = () => reject(new Error('Upload cancelled.'));
    abort.signal.addEventListener('abort', () => xhr.abort(), {once: true});
    xhr.send(file);
  });
}
$('files').onchange = async event => {
  const files = [...event.target.files]; event.target.value = ''; if (!files.length) return;
  finishEdit();beginEdit();error(); busy(true); $('progress').hidden = false;
  try {
    if (state.clips.length + files.length > 12) throw new Error('Choose at most 12 clips in total.');
    for (const [index, file] of files.entries()) {
      if (file.size > 128 * 1024 * 1024) throw new Error(`${file.name} exceeds 128 MiB.`);
      const clip = await upload(file, index + 1, files.length); state.clips.push(clip); state.active ||= clip.id; invalidate(); draw();
    }
    status('Clips ready. Choose transitions, then assemble the preview.');
  } catch (e) { error(e.message); status('Import failed. See the message below; you can retry.'); } finally { busy(false); $('progress').hidden = true; finishEdit(); }
};
function clampMotion(index) {
  const conf = setting(index), available = state.clips[index + 1].frames - 1;
  const minimum = alignedEffects.includes(conf.effect) ? 12 : conf.effect === 'motion-loop' ? 3 : 1;
  const count = Math.max(minimum, Math.min(144, available, Math.round(conf.duration * 24)));
  conf.duration = count / 24;
  if (conf.release_duration != null) conf.release_duration = Math.max(1, Math.min(Math.max(1, Math.floor(count/2)), Math.round(conf.release_duration*24))) / 24;
  conf.repeat = Math.max(2, Math.min(12, Math.round(conf.repeat)));
  conf.loop_frames = Math.max(['motion-stutter', 'reset-pulse'].includes(conf.effect) ? 4 : 2, Math.min(48, count - 1, available, Math.round(conf.loop_frames)));
  const softened = smoothEffects.includes(conf.effect) && conf.smooth;
  const needed = alignedEffects.includes(conf.effect) || softened ? count : conf.effect === 'motion-loop' ? (conf.tempo ? Math.ceil(24*60/conf.tempo.bpm*conf.tempo.beats) : conf.loop_frames) : conf.effect === 'frame-melt' ? Math.ceil(count / conf.repeat) : count;
  const maximum = alignedEffects.includes(conf.effect) || softened ? 0 : Math.max(0, available - needed);
  conf.motion_start = Math.max(0, Math.min(maximum, Math.round(conf.motion_start * 24))) / 24;
  if(conf.tempo && conf.loop_frames!==Math.floor(24*60/conf.tempo.bpm*conf.tempo.beats+.5))delete conf.tempo;
  return {conf, count, needed, maximum};
}
function openTransition(index) {
  state.dialogIndex = index;
  $('transition-pair').textContent = `${state.clips[index].name} → ${state.clips[index + 1].name}`;
  for (const mode of ['motion-loop', ...alignedEffects]) $('effect').querySelector(`[value="${mode}"]`).disabled = state.clips[index + 1].frames < (alignedEffects.includes(mode) ? 13 : 4);
  updateDialog(); $('transition-dialog').showModal();
}
function motionFrame(play = false) {
  const video = $('motion-preview'), clip = state.clips[state.dialogIndex + 1];
  const {conf, needed} = clampMotion(state.dialogIndex);
  const position = (Math.round(conf.motion_start * 24) + 1) / 24;
  video.pause(); state.motionEnd = null;
  if (state.motionSeek) video.removeEventListener('loadedmetadata', state.motionSeek);
  if (state.motionPlay) video.removeEventListener('seeked', state.motionPlay);
  state.motionSeek = state.motionPlay = null;
  const begin = () => {
    state.motionPlay = null;
    if (!$('transition-dialog').open) return;
    state.motionEnd = position + needed / 24;
    video.play().catch(e => { if ($('transition-dialog').open) error(`Source preview: ${e.message}`); });
  };
  const apply = () => {
    state.motionSeek = null; video.currentTime = Math.min(position, video.duration - .001);
    if (play) { if (video.seeking) { state.motionPlay = begin; video.addEventListener('seeked', begin, {once: true}); } else begin(); }
  };
  if (video.getAttribute('src') !== clip.preview) { video.src = clip.preview; video.load(); }
  if (video.readyState >= 1) apply(); else { state.motionSeek = apply; video.addEventListener('loadedmetadata', apply, {once: true}); }
}
function updateDialog() {
  const {conf, needed, maximum} = clampMotion(state.dialogIndex);
  $('effect').value = conf.effect;
  $('preset-control').hidden=conf.effect==='cut';$('preset').value=conf.preset==null?'custom':String(conf.preset);
  $('tempo-control').hidden=!['motion-loop','motion-stutter','reset-pulse'].includes(conf.effect);
  if(conf.tempo){$('bpm').value=conf.tempo.bpm;$('beats').value=conf.tempo.beats;}
  $('tempo-note').textContent=conf.tempo?`${conf.tempo.bpm} BPM · ${conf.tempo.beats} beat(s) · around ${(conf.loop_frames/24).toFixed(3)} s. Each beat is rounded separately to 24fps; starts with this effect, not automatic beat detection.`:'Manual tempo, rounded to 24fps. Timing starts with this effect; no automatic beat detection.';
  $('smooth-control').hidden = !smoothEffects.includes(conf.effect);
  $('smooth').value = conf.smooth ? 'smooth' : 'original';
  const gentle = smoothEffects.includes(conf.effect) && conf.smooth;
  $('release-control').hidden = !gentle;
  $('release').max = Math.max(1, Math.floor(conf.duration*12));
  $('release').value = Math.round((conf.release_duration ?? Math.max(1, Math.floor(conf.duration*24/4))/24)*24);
  $('release-value').value = `${(Number($('release').value)/24).toFixed(2)} s`;
  $('motion-marks').hidden = $('mark-note').hidden = conf.effect !== 'motion-loop';
  const ending = conf.ending ?? (['frame-melt', 'motion-loop', ...alignedEffects].includes(conf.effect) ? 'flow' : 'reset');
  $('ending').value = ending;
  $('ending-control').hidden = conf.effect === 'cut';
  $('duration-note').textContent = ending === 'flow' ? 'After this duration, normal motion continues without a hard image reset. Distortion can persist.' : 'After this duration, the clear incoming picture is restored. This can create a visible jump.';
  $('duration').min = alignedEffects.includes(conf.effect) ? 12 : conf.effect === 'motion-loop' ? 3 : 1;
  $('duration').max = Math.min(144, state.clips[state.dialogIndex + 1].frames - 1);
  $('duration').value = Math.round(conf.duration * 24);
  $('repeat').value = conf.repeat;
  document.querySelector('label[for="loop-length"]').firstChild.textContent = conf.effect === 'reset-pulse' ? 'Reset interval ' : conf.effect === 'motion-stutter' ? 'Pulse length ' : 'Loop length ';
  document.querySelector('label[for="repeat"]').firstChild.textContent = conf.effect === 'progressive-melt' ? 'Initial P-frame repetitions ' : 'P-frame repetitions ';
  $('loop-length').min = ['motion-stutter', 'reset-pulse'].includes(conf.effect) ? 4 : 2;
  document.querySelector('#loop-control .hint').textContent = conf.effect === 'reset-pulse' ? 'Each pulse restores the first frame of the incoming video. Between pulses, prediction frames are repeated to distort it again.' : conf.effect === 'motion-stutter' ? 'Pulse length: each pulse starts with a repeated prediction frame, then continues motion. The final quarter releases the stutter.' : 'A short motion sequence is repeated, pulling the previous image further each time.';
  $('loop-length').max = Math.min(48, Math.round(conf.duration * 24) - 1, state.clips[state.dialogIndex + 1].frames - 1);
  $('loop-length').value = conf.loop_frames;
  $('motion-start').max = maximum; $('motion-start').value = Math.round(conf.motion_start * 24);
  $('motion-start').disabled = maximum === 0;
  $('duration-control').hidden = conf.effect === 'cut'; $('repeat-control').hidden = !['frame-melt', 'progressive-melt', 'reset-pulse'].includes(conf.effect);
  $('loop-control').hidden = !['motion-loop', 'loop-release', 'motion-stutter', 'reset-pulse'].includes(conf.effect); $('motion-control').hidden = conf.effect === 'cut';
  $('method-note').textContent = notes[conf.effect]; $('duration-value').value = `${conf.duration.toFixed(2)} s`;
  $('repeat-value').value = `${conf.repeat}×`; $('loop-value').value = `${(conf.loop_frames / 24).toFixed(2)} s`;
  const start = conf.motion_start + 1 / 24;
  $('motion-start-value').value = `${start.toFixed(2)} s`;
  $('motion-window').textContent = `${start.toFixed(2)}–${(start + needed / 24).toFixed(2)} s of the incoming clip. The rest of your sequence stays in place.`;
  motionFrame();
}
for (const id of ['effect', 'duration', 'ending', 'repeat', 'loop-length', 'motion-start', 'smooth', 'release']) $(id).addEventListener('input', () => {
  beginEdit();const conf = setting(state.dialogIndex);delete conf.preset;
  if(['effect','loop-length'].includes(id))delete conf.tempo;
  conf.effect = $('effect').value; conf.duration = Number($('duration').value) / 24; conf.repeat = Number($('repeat').value);
  conf.loop_frames = Number($('loop-length').value); conf.motion_start = Number($('motion-start').value) / 24;
  if (id === 'effect') conf.smooth = smoothEffects.includes(conf.effect);
  if (id === 'release') conf.release_duration = Number($('release').value)/24;
  if (id === 'smooth') conf.smooth = $('smooth').value === 'smooth';
  if (id === 'ending') conf.ending = $('ending').value;
  clampMotion(state.dialogIndex); invalidate(); draw(); updateDialog();
});
$('watch-motion').onclick = () => motionFrame(true);
$('motion-preview').addEventListener('timeupdate', () => { if (state.motionEnd !== null && $('motion-preview').currentTime >= state.motionEnd) { $('motion-preview').pause(); state.motionEnd = null; } });
$('transition-dialog').addEventListener('close', () => {
  const video = $('motion-preview'); video.pause();
  if (state.motionSeek) video.removeEventListener('loadedmetadata', state.motionSeek);
  if (state.motionPlay) video.removeEventListener('seeked', state.motionPlay);
  state.motionSeek = state.motionPlay = null; state.motionEnd = null; video.removeAttribute('src'); video.load();
});
function showResult(job) {
  const changed = player.getAttribute('src') !== job.url;
  source(job.url, 'Assembled preview · all clips and transitions');
  if (changed) seek(state.sequencePosition, null, false);
}
function seek(time, end, autoplay = true) {
  if (state.pendingSeek) player.removeEventListener('loadedmetadata', state.pendingSeek);
  const apply = () => { state.pendingSeek = null; player.currentTime = Math.min(time, Math.max(0, player.duration - .01)); state.previewEnd = end; if (autoplay) player.play().catch(() => {}); };
  if (player.readyState >= 1) apply(); else { state.pendingSeek = apply; player.addEventListener('loadedmetadata', apply, {once: true}); }
}
async function waitForJob(id) {
  $('progress').hidden = false;
  while (true) {
    const result = await request(`/api/jobs/${id}`);
    if (result.status === 'error') throw new Error(result.error);
    $('progress').value = result.progress; status(result.stage);
    if (result.status === 'ready') return result;
    await new Promise(resolve => setTimeout(resolve, 350));
  }
}
async function assemble(download = false, transitionIndex = null) {
  if (transitionIndex !== null) return previewTransition(transitionIndex);
  if (state.busy || !state.clips.length) return;
  error(); busy(true);
  const prepared = Boolean(state.ready);
  try {
    if (!state.ready) {
      $('progress').hidden = false; $('progress').value = 0; status('Preparing sequence…');
      const job = await request('/api/jobs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({clips: state.clips.map(c => c.id), audio:state.sound, transitions: state.clips.slice(1).map((_, i) => ({...setting(i)}))})});
      state.job = job.id;
      try { sessionStorage.setItem('h4-job', job.id); } catch {}
      state.ready = await waitForJob(job.id);
    }
    showResult(state.ready); state.previewEnd = null;
    status(`Ready · ${state.ready.result.duration.toFixed(2)}s · verified full decode.`);
    if (transitionIndex !== null) {
      const boundary = state.ready.result.boundaries[transitionIndex];
      const start = boundary.frame / 24; seek(Math.max(0, start - .75), start + boundary.duration + .75);
    }
    if (download && touchUI() && !prepared) {
      status('Video ready. Tap Export MP4 again to save it to your device.');
    } else if (download) {
      const link = document.createElement('a'); link.href = `${state.ready.url}?download=1`; link.download = 'h4-mosh-lab.mp4';
      link.hidden = true; document.body.append(link); link.click(); link.remove();
    }
  } catch (e) { error(e.message); status('Processing failed. Adjust the sequence or retry.'); }
  finally { busy(false); $('progress').hidden = true; }
}
$('sound').onchange=()=>{
  finishEdit();beginEdit();state.sound=$('sound').checked; player.muted=!state.sound;
  $('sound-label').textContent=state.sound ? 'Sound on' : 'Sound off';
  if (!state.sound) $('motion-preview').muted=true;
  try { sessionStorage.setItem('h4-audio',JSON.stringify(state.sound)); } catch {}
  invalidate();
  status(state.sound ? 'Sound on · original audio in preview and export.' : 'Sound off · preview and export are silent.');finishEdit();
};
$('assemble').onclick = () => assemble(); $('export').onclick = () => assemble(true);
async function previewTransition(index, smoothOverride = null) {
  if (state.busy) return;
  if (state.ready && smoothOverride === null) {
    showResult(state.ready);
    const boundary = state.ready.result.boundaries[index];
    seek(Math.max(0, boundary.frame/24-.75), boundary.frame/24+boundary.duration+.75);
    status('Transition preview · cached assembled video · verified full decode.');
    return;
  }
  const transitions = state.clips.slice(1).map((_,i)=>({...setting(i)}));
  if (smoothOverride !== null) transitions[index].smooth = smoothOverride;
  const key = JSON.stringify({audio:state.sound,clips:state.clips.slice(0,index+2).map(c=>`${c.id}:${c.look||'original'}`),transitions:transitions.slice(0,index+1),index});
  error(); busy(true);
  try {
    let result = transitionCache.get(key);
    if (!result) {
      status('Preparing short transition preview…');
      const job = await request('/api/jobs', {method:'POST', headers:{'Content-Type':'application/json'},body:JSON.stringify({clips:state.clips.map(c=>c.id),transitions,audio:state.sound,preview_boundary:index})});
      result = await waitForJob(job.id);
      if (transitionCache.size >= 12) transitionCache.delete(transitionCache.keys().next().value);
      transitionCache.set(key,result);
    }
    state.previewEnd = null;
    source(result.url, `Transition preview · ${names[transitions[index].effect]}${smoothOverride === null ? '' : smoothOverride ? ' · Gentler' : ' · Original'}`);
    seek(0,null);
    status(`Ready · short preview ${result.result.duration.toFixed(2)}s · verified full decode. Assemble preview or Export MP4 uses the complete sequence.`);
  } catch(e) { error(e.message); status('Transition preview failed. Retry or assemble the sequence.'); }
  finally { busy(false); $('progress').hidden=true; }
}
for (const [id,gentle] of [['compare-original',false],['compare-gentler',true]]) $(id).onclick=()=>{
  const index=state.dialogIndex; $('transition-dialog').close(); previewTransition(index,gentle);
};
$('mark-motion-start').onclick=()=>{
  finishEdit();beginEdit();const index=state.dialogIndex, conf=setting(index);delete conf.preset;
  conf.motion_start=Math.max(0,Math.round($('motion-preview').currentTime*24)-1)/24;
  clampMotion(index); invalidate(); draw(); updateDialog();finishEdit();
};
$('mark-motion-end').onclick=()=>{
  const index=state.dialogIndex, conf=setting(index);
  const frames=Math.round($('motion-preview').currentTime*24)-Math.round(conf.motion_start*24);
  if (frames<2 || frames>48) { error('Choose an end after the start, within 2 seconds.'); return; }
  finishEdit();beginEdit();error();delete conf.tempo;delete conf.preset;conf.loop_frames=frames;
  conf.duration=Math.max(conf.duration,(frames+1)/24);
  clampMotion(index); invalidate(); draw(); updateDialog();finishEdit();
};
$('preview-transition').onclick = () => { const index = state.dialogIndex; $('transition-dialog').close(); assemble(false, index); };
$('motion-preview').addEventListener('volumechange',()=>{if (!state.sound && !$('motion-preview').muted) $('motion-preview').muted=true;});
player.addEventListener('volumechange',()=>{if (!state.sound && !player.muted) player.muted=true;});
player.addEventListener('loadedmetadata', () => { $('time').textContent = `${player.currentTime.toFixed(2)} / ${(Number.isFinite(player.duration) ? player.duration : 0).toFixed(2)} s`; });
player.addEventListener('timeupdate', () => {
  $('time').textContent = `${player.currentTime.toFixed(2)} / ${(Number.isFinite(player.duration) ? player.duration : 0).toFixed(2)} s`;
  if (state.previewEnd !== null && player.currentTime >= state.previewEnd) { player.pause(); state.previewEnd = null; status('Transition preview paused. Press play to continue the sequence.'); }
  if (state.ready && player.getAttribute('src') === state.ready.url) {
    let index = 0;
    for (const boundary of state.ready.result.boundaries) if (player.currentTime * 24 >= boundary.frame) index++;
    const id = state.clips[index]?.id;
    if (id && id !== state.active) { state.active = id; draw(); }
  }
});
player.addEventListener('error', () => { if (player.getAttribute('src')) error('Preview could not be loaded. Try assembling again or download the MP4.'); });
window.addEventListener('beforeunload', () => { $('motion-preview').pause(); $('motion-preview').removeAttribute('src'); $('motion-preview').load(); abort.abort(); player.pause(); player.removeAttribute('src'); player.load(); });
async function restore() {
  busy(true);
  try {
    state.sound=sessionStorage.getItem('h4-audio') !== 'false';
    $('sound').checked=state.sound; player.muted=!state.sound;
    $('sound-label').textContent=state.sound ? 'Sound on' : 'Sound off';
    const savedJob = sessionStorage.getItem('h4-job');
    const [data, connection] = await Promise.all([request('/api/clips'), request('/api/connection').catch(() => ({phone_url: null}))]);
    state.phoneUrl = connection.phone_url; $('phone-info').hidden = !state.phoneUrl;
    state.clips = data.clips; state.active = state.clips[0]?.id || null;
    const saved = JSON.parse(sessionStorage.getItem('h4-sequence') || 'null');
    if (saved) {
      const byId = new Map(state.clips.map(c => [c.id, c]));
      const ordered = saved.order.map(id => byId.get(id)).filter(Boolean);
      state.clips = [...ordered, ...state.clips.filter(c => !saved.order.includes(c.id))];
      const valid = new Set(state.clips.map(c => c.id));
      state.settings = new Map(saved.settings.filter(([key]) => key.split('|').every(id => valid.has(id))));
    }
    if (state.clips.length) {
      invalidate(); draw();
      if (savedJob) {
        const initial = await request(`/api/jobs/${savedJob}`);
        state.ready = initial.status === 'ready' ? initial : await waitForJob(savedJob);
        sessionStorage.setItem('h4-job', savedJob);
        showResult(state.ready); status(`Ready · ${state.ready.result.duration.toFixed(2)}s · verified full decode.`);
      }
    }
  } catch (e) { error(`Could not restore session: ${e.message}`); }
  finally { busy(false); $('progress').hidden = true; draw(); }
}
restore();

$('copy-phone').onclick = async () => {
  try {
    await navigator.clipboard.writeText(state.phoneUrl);
    $('phone-status').textContent = ' Link copied. Send it to your phone and open it on the same Wi-Fi.';
  } catch {
    $('phone-status').textContent = ' Copy the full Phone link from the Mac terminal.';
  }
};

const visitButton = $('visit');
let visitCount = 0;
try {
  const saved = Number(localStorage.getItem('h4-visit-count'));
  if (Number.isSafeInteger(saved) && saved >= 0) visitCount = saved;
} catch {}
function showVisitCount() { visitButton.textContent = `visit ${String(visitCount).padStart(4, '0')}`; }
showVisitCount();
visitButton.onclick = () => {
  visitCount += 1;
  try { localStorage.setItem('h4-visit-count', String(visitCount)); } catch {}
  showVisitCount();
};
