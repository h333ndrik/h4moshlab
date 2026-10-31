'use strict';
// Pure project validation and bounded undo history, also exercised with Node.
(() => {
  const effects=['cut','classic-mosh','frame-melt','progressive-melt','motion-loop','loop-release','motion-stutter','reset-pulse'];
  const copy=value=>JSON.parse(JSON.stringify(value));
  class History {
    constructor(limit=40){this.limit=limit;this.past=[];this.future=[];}
    record(before,after){if(JSON.stringify(before)===JSON.stringify(after))return;this.past.push(copy(before));if(this.past.length>this.limit)this.past.shift();this.future=[];}
  }
  function validateProject(p){
    if(!p || p.format!=='h4-mosh-project' || p.version!==1 || !Array.isArray(p.clips) || p.clips.length<1 || p.clips.length>12 || !Array.isArray(p.transitions) || p.transitions.length!==p.clips.length-1 || typeof p.sound!=='boolean')throw Error('Not a supported H4 Mosh project.');
    for(const c of p.clips)if(!c || typeof c.name!=='string' || c.name.length>180 || !/^[a-f0-9]{64}$/.test(c.sha256) || !Number.isInteger(c.frames) || c.frames<2 || c.frames>2880 || (c.look!=null&&!['original','black-white','negative-bw','negative-color'].includes(c.look)))throw Error('Invalid project video reference.');
    if(p.order!=null){
      if(!Array.isArray(p.order)||p.order.length!==p.clips.length||p.order.some(id=>typeof id!=='string'||!/^[a-f0-9]{32}$/.test(id)))throw Error('Invalid project clip order.');
      p={...p,clips:p.clips.map((c,i)=>({...c,source_ref:p.order.indexOf(p.order[i])}))};
    }
    for(const [i,c] of p.clips.entries())if(c.source_ref!=null && (!Number.isInteger(c.source_ref)||c.source_ref<0||c.source_ref>i||p.clips[c.source_ref].sha256!==c.sha256))throw Error('Invalid duplicate source reference.');
    const numeric=['duration','motion_start','repeat','loop_frames','release_duration'];
    for(const t of p.transitions){
      if(!t || !effects.includes(t.effect))throw Error('Unsupported project effect.');
      for(const key of numeric)if(t[key]!=null && (typeof t[key]!=='number' || !Number.isFinite(t[key]) || t[key]<0))throw Error('Invalid project setting.');
      if(t.effect!=='cut' && !(t.duration>=1/24 && t.duration<=6))throw Error('Invalid project duration.');
      if(t.ending!=null && !['flow','reset'].includes(t.ending))throw Error('Invalid effect ending.');
      if(t.smooth!=null && typeof t.smooth!=='boolean')throw Error('Invalid movement setting.');
      if(t.repeat!=null && (!Number.isInteger(t.repeat) || t.repeat<2 || t.repeat>12))throw Error('Invalid repetitions.');
      if(t.loop_frames!=null && (!Number.isInteger(t.loop_frames) || t.loop_frames<2 || t.loop_frames>48))throw Error('Invalid motion window.');
      if(t.preset!=null && (!Number.isInteger(t.preset)||t.preset<0||t.preset>2))throw Error('Invalid project preset.');
      if(t.tempo!=null && (!t.tempo || !['motion-loop','motion-stutter','reset-pulse'].includes(t.effect) || typeof t.tempo.bpm!=='number' || !Number.isFinite(t.tempo.bpm) || t.tempo.bpm<40 || t.tempo.bpm>240 || ![.25,.5,1,2,4].includes(t.tempo.beats)))throw Error('Invalid project tempo.');
    }
    const keys=['effect','duration','motion_start','repeat','loop_frames','release_duration','ending','smooth','tempo','preset'];
    return {format:p.format,version:1,sound:p.sound,...(p.order?{order:copy(p.order)}:{}),clips:p.clips.map(c=>({name:c.name,sha256:c.sha256,frames:c.frames,look:c.look||'original',...(c.source_ref!=null?{source_ref:c.source_ref}:{})})),transitions:p.transitions.map(t=>Object.fromEntries(keys.filter(k=>t[k]!=null).map(k=>[k,copy(t[k])])))};
  }
  function matchProject(project,library){
    const used=new Set(),references=new Map();return project.clips.map((source,index)=>{
      if(source.source_ref!=null && source.source_ref<index){const clip=references.get(source.source_ref)||null;references.set(index,clip);return clip;}
      const clip=library.find(c=>!used.has(c.id)&&c.sha256===source.sha256);
      if(clip)used.add(clip.id);references.set(index,clip||null);return clip||null;
    });
  }
  const api={History,copy,validateProject,matchProject};
  globalThis.H4EditorTools=api;
  if(typeof module!=='undefined')module.exports=api;
})();
