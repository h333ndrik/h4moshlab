'use strict';
const $ = id => document.getElementById(id);
const state = {clips: [], settings: new Map(), active: null, busy: false, ready: null, job: null, dialogIndex: null, previewEnd: null};
const player = $('player');
const names = {'cut': 'Cut', 'classic-mosh': 'Classic Mosh', 'frame-melt': 'Frame Melt'};
const notes = {'cut': 'An ordinary cut. No datamoshing.', 'classic-mosh': 'Real codec datamoshing: B’s P-frames inherit A’s final image.', 'frame-melt': 'Real codec datamoshing: repeated compressed P-frames accumulate dragging and distortion.'};
const abort = new AbortController();
function error(message = '') { $('error').textContent = message; $('error').hidden = !message; }
function status(message) { $('status').textContent = message; }
function source(url, label) {
  if (state.pendingSeek) { player.removeEventListener('loadedmetadata', state.pendingSeek); state.pendingSeek = null; }
  if (player.getAttribute('src') !== url) { player.pause(); player.removeAttribute('src'); player.load(); player.src = url; player.load(); }
  $('empty').hidden = Boolean(url); $('preview-label').textContent = label;
}
function setting(index) {
  const incoming = state.clips[index + 1], key = `${state.clips[index].id}|${incoming.id}`;
  if (!state.settings.has(key)) state.settings.set(key, {effect: 'classic-mosh', duration: Math.min(24, incoming.frames - 1) / 24, repeat: 4});
  return state.settings.get(key);
}
function invalidate() {
  try { sessionStorage.removeItem('h4-job'); } catch {}
  try { sessionStorage.setItem('h4-sequence', JSON.stringify({order: state.clips.map(c => c.id), settings: [...state.settings]})); } catch {}
  state.ready = null; state.previewEnd = null; $('download').hidden = true;
  const clip = state.clips.find(c => c.id === state.active);
  if (clip) source(clip.preview, `Clip preview · ${clip.name}`);
  else { player.pause(); player.removeAttribute('src'); player.load(); $('empty').hidden = false; $('preview-label').textContent = 'No video selected'; }
  status(state.clips.length ? 'Sequence changed. Assemble to preview the real transitions.' : 'Ready to import.');
}
function controls() {
  $('files').disabled = state.busy;
  $('import-label').style.pointerEvents = state.busy ? 'none' : '';
  $('import-label').setAttribute('aria-disabled', String(state.busy));
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
      const connector = button(`${conf.effect === 'cut' ? 'Cut' : conf.effect === 'frame-melt' ? 'Melt' : 'Mosh'}\n${conf.effect === 'cut' ? '—' : conf.duration.toFixed(2) + 's'}`, () => openTransition(index - 1), `Transition ${index}: ${names[conf.effect]}`);
      connector.className = 'connector'; timeline.append(connector);
    }
    const card = document.createElement('div'); card.className = `clip${state.active === clip.id ? ' active' : ''}`;
    card.draggable = !state.busy;
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
    actions.append(left, right, duration, button('×', () => remove(clip.id), `Remove ${clip.name}`)); card.append(actions); timeline.append(card);
  });
  controls();
}
function move(id, to) {
  if (state.busy || to < 0 || to >= state.clips.length) return;
  const from = state.clips.findIndex(c => c.id === id); if (from < 0 || from === to) return;
  state.clips.splice(to, 0, state.clips.splice(from, 1)[0]); invalidate(); draw();
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
    state.clips = state.clips.filter(c => c.id !== id);
    for (const key of state.settings.keys()) if (key.split('|').includes(id)) state.settings.delete(key);
    if (state.active === id) state.active = state.clips[0]?.id || null;
    invalidate(); draw();
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
  error(); busy(true); $('progress').hidden = false;
  try {
    if (state.clips.length + files.length > 12) throw new Error('Choose at most 12 clips in total.');
    for (const [index, file] of files.entries()) {
      if (file.size > 128 * 1024 * 1024) throw new Error(`${file.name} exceeds 128 MiB.`);
      const clip = await upload(file, index + 1, files.length); state.clips.push(clip); state.active ||= clip.id; invalidate(); draw();
    }
    status('Clips ready. Choose transitions, then assemble the preview.');
  } catch (e) { error(e.message); } finally { busy(false); $('progress').hidden = true; }
};
function openTransition(index) {
  state.dialogIndex = index; const conf = setting(index);
  $('transition-pair').textContent = `${state.clips[index].name} → ${state.clips[index + 1].name}`;
  $('effect').value = conf.effect; $('duration').max = Math.min(144, state.clips[index + 1].frames - 1);
  $('duration').value = Math.round(conf.duration * 24); $('repeat').value = conf.repeat;
  updateDialog(); $('transition-dialog').showModal();
}
function updateDialog() {
  const conf = setting(state.dialogIndex);
  $('duration-control').hidden = conf.effect === 'cut'; $('repeat-control').hidden = conf.effect !== 'frame-melt';
  $('method-note').textContent = notes[conf.effect]; $('duration-value').value = `${conf.duration.toFixed(2)} s`;
  $('repeat-value').value = `${conf.repeat}×`;
}
for (const id of ['effect', 'duration', 'repeat']) $(id).addEventListener('input', () => {
  const conf = setting(state.dialogIndex); conf.effect = $('effect').value; conf.duration = Number($('duration').value) / 24; conf.repeat = Number($('repeat').value);
  invalidate(); draw(); updateDialog();
});
function showResult(job) {
  source(job.url, 'Assembled preview · real codec processing');
  const download = $('download'); download.href = `${job.url}?download=1`; download.download = 'h4-mosh-lab.mp4'; download.hidden = false;
}
function seek(time, end) {
  if (state.pendingSeek) player.removeEventListener('loadedmetadata', state.pendingSeek);
  const apply = () => { state.pendingSeek = null; player.currentTime = Math.min(time, Math.max(0, player.duration - .01)); state.previewEnd = end; player.play().catch(() => {}); };
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
  if (state.busy || !state.clips.length) return;
  error(); busy(true);
  try {
    if (!state.ready) {
      $('progress').hidden = false; $('progress').value = 0; status('Preparing sequence…');
      const job = await request('/api/jobs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({clips: state.clips.map(c => c.id), transitions: state.clips.slice(1).map((_, i) => ({...setting(i)}))})});
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
    if (download) $('download').click();
  } catch (e) { error(e.message); status('Processing failed. Adjust the sequence or retry.'); }
  finally { busy(false); $('progress').hidden = true; }
}
$('assemble').onclick = () => assemble(); $('export').onclick = () => assemble(true);
$('preview-transition').onclick = () => { const index = state.dialogIndex; $('transition-dialog').close(); assemble(false, index); };
player.addEventListener('timeupdate', () => {
  $('time').textContent = `${player.currentTime.toFixed(2)} / ${(Number.isFinite(player.duration) ? player.duration : 0).toFixed(2)} s`;
  if (state.previewEnd !== null && player.currentTime >= state.previewEnd) { player.pause(); state.previewEnd = null; }
  if (state.ready && player.getAttribute('src') === state.ready.url) {
    let index = 0;
    for (const boundary of state.ready.result.boundaries) if (player.currentTime * 24 >= boundary.frame) index++;
    const id = state.clips[index]?.id;
    if (id && id !== state.active) { state.active = id; draw(); }
  }
});
player.addEventListener('error', () => { if (player.getAttribute('src')) error('Preview could not be loaded. Try assembling again or download the MP4.'); });
window.addEventListener('beforeunload', () => { abort.abort(); player.pause(); player.removeAttribute('src'); player.load(); });
async function restore() {
  busy(true);
  try {
    const savedJob = sessionStorage.getItem('h4-job');
    const data = await request('/api/clips');
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
