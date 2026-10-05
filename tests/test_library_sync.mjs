import assert from 'node:assert/strict';
import {gridWindow} from '../plasticity-asset-tool-app/src/virtualGrid.mjs';
import {mergeLibrary} from '../plasticity-asset-tool-app/src/librarySync.mjs';
for (const count of [0,100,1000,5000]) {
  for (const width of [80,360,1000]) {
    const first = gridWindow({count,width,size:184,top:0,viewport:700});
    assert(first.start === 0 && first.end <= Math.min(count, 100));
    const end = gridWindow({count,width,size:184,top:Math.max(0,first.height-700),viewport:700});
    assert.equal(end.end,count);
    assert(first.cardWidth <= width && first.columns >= 1);
    // Every viewport is covered; only overscan rows are materialized.
    for (let top = 0; top < first.height; top += 333) {
      const view = gridWindow({count,width,size:184,top,viewport:700});
      assert(view.start * 1 <= Math.floor(top / view.pitch) * view.columns);
      assert(view.end >= Math.min(count, Math.ceil((top + 700)/view.pitch) * view.columns));
    }
  }
}
const one = {id:'one',name:'One'}, two = {id:'two',name:'Two'};
const untouched = [one];
assert.equal(mergeLibrary(untouched,{full:false,changed:[],removed:[]}),untouched);
assert.equal(mergeLibrary([one],{full:true,assets:[{...one}]})[0],one);
const added = mergeLibrary([one],{full:false,changed:[two],removed:[]});
assert.equal(added[0],one); assert.equal(added.length,2);
assert.deepEqual(mergeLibrary(added,{full:false,changed:[{...two,name:'Changed'}],removed:['one']}),[{id:'two',name:'Changed'}]);
