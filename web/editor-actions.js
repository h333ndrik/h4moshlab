'use strict';
const editorHistory=new H4EditorTools.History(40);
let pendingEdit=null;
function editorSnapshot(){return H4EditorTools.copy({clips:state.clips,settings:[...state.settings],active:state.active,sound:state.sound});}
function beginEdit(){if(!pendingEdit)pendingEdit=editorSnapshot();}
function finishEdit(){if(pendingEdit){editorHistory.record(pendingEdit,editorSnapshot());pendingEdit=null;}updateHistoryControls();}
function updateHistoryControls(){
  document.getElementById('undo').disabled=state.busy||!editorHistory.past.length;
  document.getElementById('redo').disabled=state.busy||!editorHistory.future.length;
  document.getElementById('save-project').disabled=state.busy||!state.clips.length;
  document.getElementById('open-project').disabled=state.busy;
}
async function restoreEditor(snapshot){
  await request('/api/sequence/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({clips:snapshot.clips.map(c=>c.id),looks:Object.fromEntries(snapshot.clips.map(c=>[c.id,c.look||'original']))})});
  state.clips=H4EditorTools.copy(snapshot.clips);state.settings=new Map(H4EditorTools.copy(snapshot.settings));state.active=snapshot.active;state.sound=snapshot.sound;
  $('sound').checked=state.sound;player.muted=!state.sound;$('sound-label').textContent=state.sound?'Sound on':'Sound off';
  try{sessionStorage.setItem('h4-audio',JSON.stringify(state.sound));}catch{}
  invalidate();draw();
}
async function travelHistory(redo=false){
  if(state.busy)return;finishEdit();const from=redo?editorHistory.future:editorHistory.past,to=redo?editorHistory.past:editorHistory.future;
  if(!from.length)return;
  const target=from[from.length-1],before=editorSnapshot();busy(true);error();
  try{if($('transition-dialog').open)$('transition-dialog').close();await restoreEditor(target);from.pop();to.push(before);status(redo?'Redone.':'Undone.');}
  catch(e){error(e.message);}finally{busy(false);}
}
function downloadProject(){
  finishEdit();if(!state.clips.length)return;
  const project={format:'h4-mosh-project',version:1,sound:state.sound,clips:state.clips.map(c=>({name:c.name,sha256:c.sha256,frames:c.frames,look:c.look||'original'})),transitions:state.clips.slice(1).map((_,i)=>({...setting(i)}))};
  H4EditorTools.validateProject(project);
  const url=URL.createObjectURL(new Blob([JSON.stringify(project,null,2)+'\n'],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='h4-mosh-project.h4mosh';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  $('project-menu').open=false;status('Project saved. Keep your original videos; they are not included.');
}
let pendingProject=null;
function missingProjectFiles(matches){return pendingProject.clips.filter((_,i)=>!matches[i]);}
async function completeProject(matches){
  if(matches.some(c=>!c))return false;
  await request('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'validate_project',frames:matches.map(c=>c.frames),transitions:pendingProject.transitions})});
  const settings=matches.slice(1).map((c,i)=>[`${matches[i].id}|${c.id}`,pendingProject.transitions[i]]);
  finishEdit();beginEdit();await restoreEditor({clips:matches.map((c,i)=>({...c,look:pendingProject.clips[i].look||'original',preview:`/media/clip/${c.id}?look=${pendingProject.clips[i].look||'original'}`,thumbnail:`/media/thumb/${c.id}?look=${pendingProject.clips[i].look||'original'}`})),settings,active:matches[0].id,sound:pendingProject.sound});finishEdit();
  pendingProject=null;$('project-dialog').close();status('Project opened. Original videos matched by file hash.');return true;
}
async function openProjectFile(file){
  if(state.busy)return;
  try{
    $('project-menu').open=false;
    if(file.size>1024*1024)throw Error('Choose an H4 project file smaller than 1 MiB.');
    pendingProject=H4EditorTools.validateProject(JSON.parse(await file.text()));
    busy(true);error();
    await request('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'validate_project',frames:pendingProject.clips.map(c=>c.frames),transitions:pendingProject.transitions})});
    const library=(await request('/api/library')).clips;
    const matches=H4EditorTools.matchProject(pendingProject,library);
    if(await completeProject(matches))return;
    $('project-error').textContent='';$('project-note').textContent=`Choose the original videos: ${missingProjectFiles(matches).map(c=>c.name).join(', ')}. Files are verified by their content, not just their names.`;
    $('project-dialog').showModal();$('project-menu').open=false;
  }catch(e){pendingProject=null;error(`Could not open project: ${e.message}`);}finally{busy(false);}
}
async function relinkProject(files){
  if(!pendingProject||!files.length||state.busy)return;
  const previous=editorSnapshot();busy(true);$('cancel-project').disabled=true;$('relink-files').disabled=true;
  try{
    // Temporarily archive current media to leave room for up to 12 project clips.
    await request('/api/sequence/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({clips:[]})});
    for(const [i,file]of files.entries()){
      if(file.size>128*1024*1024)throw Error('Choose videos smaller than 128 MiB.');
      await upload(file,i+1,files.length);
    }
    const matches=H4EditorTools.matchProject(pendingProject,(await request('/api/library')).clips);
    if(!(await completeProject(matches))){await restoreEditor(previous);$('project-note').textContent=`Still missing: ${missingProjectFiles(matches).map(c=>c.name).join(', ')}. Choose the matching originals.`;}
  }catch(e){$('project-error').textContent=e.message;try{await restoreEditor(previous);}catch(restoreError){error(restoreError.message);}}
  finally{busy(false);$('progress').hidden=true;$('cancel-project').disabled=false;$('relink-files').disabled=false;}
}
async function applyPreset(){
  const selected=$('preset').value;if(selected==='custom'||state.busy)return;
  const index=state.dialogIndex,conf=setting(index);busy(true);error();
  try{
    const preset=await request('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'preset',effect:conf.effect,preset:Number(selected),frames:state.clips[index+1].frames})});
    finishEdit();beginEdit();state.settings.set(`${state.clips[index].id}|${state.clips[index+1].id}`,{...preset,preset:Number(selected)});clampMotion(index);invalidate();draw();updateDialog();finishEdit();
  }catch(e){error(e.message);}finally{busy(false);}
}
async function applyTempo(){
  if(state.busy)return;const index=state.dialogIndex,conf=setting(index),bpm=Number($('bpm').value),beats=Number($('beats').value);busy(true);error();
  try{
    const tempo=await request('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'tempo',effect:conf.effect,bpm,beats})});
    if(tempo.loop_frames>=state.clips[index+1].frames-1)throw Error('This clip is too short for that interval. Choose fewer beats.');
    finishEdit();beginEdit();delete conf.preset;conf.loop_frames=tempo.loop_frames;conf.duration=Math.max(conf.duration,(tempo.loop_frames+1)/24);conf.tempo={bpm,beats};clampMotion(index);invalidate();draw();updateDialog();finishEdit();
  }catch(e){error(e.message);}finally{busy(false);}
}
window.addEventListener('DOMContentLoaded',()=>{
  $('undo').onclick=()=>travelHistory();$('redo').onclick=()=>travelHistory(true);
  $('save-project').onclick=()=>{try{downloadProject();}catch(e){error(e.message);}};
  $('open-project').onchange=e=>{const file=e.target.files[0];e.target.value='';if(file)openProjectFile(file);};
  $('relink-files').onchange=e=>{const files=[...e.target.files];e.target.value='';relinkProject(files);};
  $('cancel-project').onclick=()=>{if(!state.busy){pendingProject=null;$('project-dialog').close();}};
  $('project-dialog').addEventListener('cancel',e=>{if(state.busy)e.preventDefault();else pendingProject=null;});
  $('preset').onchange=applyPreset;$('apply-tempo').onclick=applyTempo;
  $('transition-dialog').addEventListener('change',finishEdit);
  $('transition-dialog').addEventListener('close',finishEdit);
  document.addEventListener('keydown',e=>{
    if(!(e.metaKey||e.ctrlKey)||e.altKey||!['z','y'].includes(e.key.toLowerCase()))return;
    if(e.target.closest('input[type=number],input[type=text],textarea,[contenteditable=true]'))return;
    e.preventDefault();travelHistory(e.key.toLowerCase()==='y'||e.shiftKey);
  });
});

async function setClipLook(id,look){
  if(state.busy)return;finishEdit();const before=editorSnapshot();busy(true);error();status('Preparing clip look…');
  try{
    const clip=await request(`/api/clips/${id}/look`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({look})});
    state.clips=state.clips.map(c=>c.id===id?clip:c);state.active=id;invalidate();draw();editorHistory.record(before,editorSnapshot());status('Clip look ready. Originals stay unchanged.');
  }catch(e){error(e.message);draw();}finally{busy(false);}
}
