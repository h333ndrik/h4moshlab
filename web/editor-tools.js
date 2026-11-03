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
    for(const c of p.clips)if(!c || typeof c.name!=='string' || c.name.length>180 || !/^[a-f0-9]{64}$/.test(c.sha256) || !Number.isInteger(c.frames) || c.frames<2 || c.frames>2880 || (c.look!=null&&!['original','black-white','negative-bw','negative-color'].includes(c.look)) || (c.speed!=null&&(typeof c.speed!=='number'||!Number.isFinite(c.speed)||c.speed<.1||c.speed>4||Math.abs(c.speed*10-Math.round(c.speed*10))>1e-9)))throw Error('Invalid project video reference.');
    for(const c of p.clips){
      for(const key of ['source_frames','start_frame','end_frame'])if(key in c&&!Number.isInteger(c[key]))throw Error('Invalid project trim.');
      const full=c.source_frames??c.frames,start=c.start_frame??0,end=c.end_frame??full;
      const speed=c.speed??1,expected=Math.floor((end-start)/speed+.5);
      if(!Number.isInteger(full)||full<2||full>2880||!Number.isInteger(start)||!Number.isInteger(end)||start<0||end>full||end-start<2||!Number.isInteger(expected)||expected<2||expected>2880||c.frames!==expected)throw Error('Invalid project trim or speed.');
    }
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
      if(t.random_seed!=null && (typeof t.random_seed!=='string'||!/^[a-f0-9]{16}$/.test(t.random_seed)))throw Error('Invalid random seed.');
      if(t.audio_follow!=null && typeof t.audio_follow!=='boolean')throw Error('Invalid audio follow setting.');
      if(t.audio_follow===true && !['motion-loop','motion-stutter','reset-pulse'].includes(t.effect))throw Error('Audio follows loop is unavailable for this effect.');
      if(t.tempo!=null && (!t.tempo || !['motion-loop','motion-stutter','reset-pulse'].includes(t.effect) || typeof t.tempo.bpm!=='number' || !Number.isFinite(t.tempo.bpm) || t.tempo.bpm<40 || t.tempo.bpm>240 || ![.25,.5,1,2,4].includes(t.tempo.beats)))throw Error('Invalid project tempo.');
    }
    const keys=['effect','duration','motion_start','repeat','loop_frames','release_duration','ending','smooth','tempo','preset','random_seed','audio_follow'];
    return {format:p.format,version:1,sound:p.sound,...(p.order?{order:copy(p.order)}:{}),clips:p.clips.map(c=>({name:c.name,sha256:c.sha256,frames:c.frames,source_frames:c.source_frames??c.frames,start_frame:c.start_frame??0,end_frame:c.end_frame??c.source_frames??c.frames,speed:c.speed??1,look:c.look||'original',...(c.source_ref!=null?{source_ref:c.source_ref}:{})})),transitions:p.transitions.map(t=>Object.fromEntries(keys.filter(k=>t[k]!=null).map(k=>[k,copy(t[k])])))};
  }
  function matchProject(project,library){
    const used=new Set(),references=new Map();return project.clips.map((source,index)=>{
      if(source.source_ref!=null && source.source_ref<index){const clip=references.get(source.source_ref)||null;references.set(index,clip);return clip;}
      const clip=library.find(c=>!used.has(c.id)&&c.sha256===source.sha256);
      if(clip)used.add(clip.id);references.set(index,clip||null);return clip||null;
    });
  }
  const randomEffects=effects.filter(effect=>effect!=='cut');
  const randomAligned=['loop-release','progressive-melt','motion-stutter','reset-pulse'];
  const randomSmooth=['frame-melt','progressive-melt','motion-stutter'];
  const randomRepeat=['frame-melt','progressive-melt','reset-pulse'];
  const randomLoop=['motion-loop','loop-release','motion-stutter','reset-pulse'];

  // Seeds are exactly 16 lowercase hex characters. The two 32-bit halves are
  // XOR-folded into the mulberry32 state, so every seed character contributes.
  function createSeed(){
    if(!globalThis.crypto?.getRandomValues)throw Error('Secure randomness is unavailable.');
    return Array.from(globalThis.crypto.getRandomValues(new Uint8Array(8)),byte=>byte.toString(16).padStart(2,'0')).join('');
  }
  function seededRandom(seed){
    if(typeof seed!=='string'||!/^[a-f0-9]{16}$/.test(seed))throw Error('Random seed must be 16 lowercase hexadecimal characters.');
    let state=(parseInt(seed.slice(0,8),16)^parseInt(seed.slice(8),16))>>>0;
    return ()=>{
      state=(state+0x6D2B79F5)>>>0;
      let value=state;
      value=Math.imul(value^(value>>>15),value|1);
      value^=value+Math.imul(value^(value>>>7),value|61);
      return ((value^(value>>>14))>>>0)/4294967296;
    };
  }
  function randomInt(rng,min,max){return min+Math.floor(rng()*(max-min+1));}
  function normalized(value,minimum,maximum,fallback){
    return Number.isInteger(value)&&value>=minimum&&value<=maximum?value:fallback;
  }
  function randomizedConfigProblem(config,frames){
    const effect=config.effect,count=Math.round(config.duration*24),offset=Math.round(config.motion_start*24);
    if(!randomEffects.includes(effect))return 'Cut cannot be randomized.';
    if(!Number.isInteger(count)||count<1||count>144||count>frames-1)return 'The transition duration is outside the incoming clip.';
    if(!Number.isFinite(offset)||offset<0)return 'Motion start is invalid.';
    if(randomAligned.includes(effect)&&(offset!==0||count<12))return 'This effect needs at least 0.5 seconds and motion start 0.';
    if(!Number.isInteger(config.repeat)||config.repeat<2||config.repeat>12)return 'The repetition count is invalid.';
    if(!Number.isInteger(config.loop_frames)||config.loop_frames<2||config.loop_frames>48)return 'The loop window is invalid.';
    if(config.ending!=='flow'&&config.ending!=='reset')return 'The effect ending is invalid.';
    if(!/^[a-f0-9]{16}$/.test(config.random_seed||''))return 'The random seed is invalid.';
    if('preset' in config||'tempo' in config)return 'Randomized settings must be Custom without tempo.';
    if('audio_follow' in config && typeof config.audio_follow!=='boolean')return 'The audio follow setting is invalid.';
    if(config.audio_follow===true && !['motion-loop','motion-stutter','reset-pulse'].includes(effect))return 'Audio follows loop is unavailable for this effect.';
    const smooth=randomSmooth.includes(effect)&&config.smooth===true;
    if(config.smooth===true&&!smooth)return 'Gentler is not available for this effect.';
    if(smooth&&offset!==0)return 'Gentler needs motion start 0.';
    if(smooth){
      const tail=Math.round(Number(config.release_duration)*24);
      if(!Number.isFinite(tail)||tail<1||tail>Math.max(1,Math.floor(count/2)))return 'The release exceeds half the effect duration.';
    }
    const available=frames-1-offset;
    if(available<1)return 'Motion start is outside the incoming clip.';
    if(randomLoop.includes(effect)&&(!Number.isInteger(config.loop_frames)||config.loop_frames>=count||config.loop_frames>available))return 'The motion window exceeds the incoming clip.';
    if(effect==='classic-mosh'&&count>available)return 'The transition exceeds the available donor frames.';
    if(effect==='frame-melt'&&Math.floor((count-1)/config.repeat)+1>available)return 'The transition exceeds the available donor frames.';
    return '';
  }
  function randomizeTransition(effect,frames,current={},seed){
    if(!randomEffects.includes(effect))throw Error('Cut cannot be randomized.');
    if(!Number.isInteger(frames)||frames<2||frames>2880)throw Error('Invalid incoming clip length.');
    const rng=seededRandom(seed),count=Math.round(Number(current.duration)*24);
    if(!Number.isFinite(count)||count<1||count>144||count>frames-1)throw Error('The transition duration is outside the incoming clip.');
    const aligned=randomAligned.includes(effect);
    if(aligned&&count<12)throw Error('This effect needs at least 0.5 seconds.');
    let offset=aligned?0:Math.round(Number(current.motion_start??0)*24);
    if(!Number.isFinite(offset)||offset<0)throw Error('Motion start is invalid.');
    let repeat=normalized(current.repeat,2,12,4);
    if(randomRepeat.includes(effect))repeat=randomInt(rng,2,12);
    let smooth=randomSmooth.includes(effect)?rng()<.5:false;
    if(smooth&&effect==='frame-melt'&&count<12)smooth=false;
    if(smooth)offset=0;
    let loopFrames=normalized(current.loop_frames,2,48,12);
    if(randomLoop.includes(effect)){
      const minimum=['motion-stutter','reset-pulse'].includes(effect)?4:2;
      if(!aligned)offset=Math.min(offset,Math.max(0,frames-1-minimum));
      const maximum=Math.min(48,count-1,frames-1-offset);
      if(maximum<minimum)throw Error('The incoming clip is too short for a valid random motion window.');
      loopFrames=randomInt(rng,minimum,maximum);
    }
    const ending=rng()<.5?'flow':'reset';
    const required=effect==='classic-mosh'?count:effect==='frame-melt'?Math.floor((count-1)/repeat)+1:randomLoop.includes(effect)?loopFrames:count;
    if(!aligned&&!smooth)offset=Math.min(offset,Math.max(0,frames-1-required));
    const result={...copy(current),effect,duration:count/24,motion_start:offset/24,repeat,loop_frames:loopFrames,ending,smooth,random_seed:seed};
    delete result.preset;delete result.tempo;
    if(randomSmooth.includes(effect)&&smooth){
      const maximum=Math.max(1,Math.floor(count/2)),candidate=Math.round(Number(result.release_duration)*24);
      result.release_duration=(Number.isFinite(candidate)&&candidate>=1&&candidate<=maximum?candidate:Math.max(1,Math.floor(count/4)))/24;
    }else delete result.release_duration;
    const problem=randomizedConfigProblem(result,frames);
    if(problem)throw Error(problem);
    return result;
  }
  function randomizeProblem(effect,frames,current={}){
    try{randomizeTransition(effect,frames,current,'0000000000000000');return '';}catch(error){return error.message||String(error);}
  }

  const api={History,copy,validateProject,matchProject,createSeed,seededRandom,randomizeTransition,randomizeProblem};
  globalThis.H4EditorTools=api;
  if(typeof module!=='undefined')module.exports=api;
})();
