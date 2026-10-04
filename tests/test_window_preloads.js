const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const listeners={};
const makeSession=()=>({preloads:['existing.cjs'],getPreloads(){return this.preloads;},setPreloads(items){this.preloads=items;}});
const defaultSession=makeSession(),otherSession=makeSession();
const app={on(event,fn){listeners[event]=fn;},getPath(){return '/tmp';}};
const modules={electron:{app,session:{defaultSession}},fs:{writeFileSync(){}},path:require('path'),crypto:require('crypto')};
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),{URL,console,setTimeout,clearTimeout,require:name=>modules[name]||{}});
listeners.ready();
assert.equal(defaultSession.preloads.length,2);
function create(session){listeners['browser-window-created']({}, {webContents:{session,on(){}},isDestroyed(){return false;}});}
create(defaultSession);create(otherSession);create(otherSession);
assert.deepEqual(otherSession.preloads,defaultSession.preloads);
assert.equal(otherSession.preloads.filter(path=>path.includes('pat-geometry')).length,1);
console.log('Secondary sessions get the native preload once; existing preloads remain');
