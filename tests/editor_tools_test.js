const assert=require('node:assert/strict');
const {History,validateProject,matchProject}=require('../web/editor-tools.js');
const history=new History(2);history.record({n:0},{n:1});history.record({n:1},{n:2});history.record({n:2},{n:3});assert.equal(history.past.length,2);history.future.push({n:4});history.record({n:3},{n:3});assert.equal(history.future.length,1);history.record({n:3},{n:5});assert.equal(history.future.length,0);
const hash='a'.repeat(64),project={format:'h4-mosh-project',version:1,sound:true,clips:[{name:'a.mov',frames:48,sha256:hash,look:'negative-bw'},{name:'a.mov',frames:48,sha256:hash}],transitions:[{effect:'reset-pulse',duration:1,loop_frames:12,tempo:{bpm:120,beats:1}}]};
const validated=validateProject(project);assert.equal(validated.clips[0].look,'negative-bw');assert.equal(validated.clips[1].look,'original');assert.deepEqual(matchProject(validated,[{id:'one',sha256:hash},{id:'two',sha256:hash}]).map(c=>c.id),['one','two']);assert.equal(matchProject(validated,[{id:'one',sha256:hash}])[1],null);
assert.throws(()=>validateProject({...project,version:2}));assert.throws(()=>validateProject({...project,clips:[{...project.clips[0],sha256:'bad'}]}));assert.throws(()=>validateProject({...project,transitions:[{effect:'fake',duration:1}]}));
console.log('PASS: history bounds/deduplication, strict project schema, duplicate source matching');
