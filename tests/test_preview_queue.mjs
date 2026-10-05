import assert from 'node:assert/strict';
import {previewQueue} from '../plasticity-asset-tool-app/src/previewQueue.mjs';
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
let available = false, release, pending, errors = [];
const started = [];
const queue = previewQueue({delay:1, available:()=>available, changed:n=>pending=n,
  failed:e=>errors.push(e.message), run:async item=>{
    started.push(item.digest);
    if (item.digest === 'a') await new Promise(resolve=>release=resolve);
    if (item.digest === 'b') throw new Error('failed b');
  }});
queue.add({digest:'a'}); queue.add({digest:'a'}); queue.add({digest:'b'});
await sleep(15); assert.deepEqual(started, []); assert.equal(pending, 2);
available = true;
await sleep(15); assert.deepEqual(started, ['a']);
queue.add({digest:'a'}); available = false; release();
await sleep(15); assert.deepEqual(started, ['a']);
available = true; queue.add({digest:'c'});
await sleep(30); assert.deepEqual(started, ['a','b','c']);
assert.deepEqual(errors, ['failed b']); assert.equal(pending, 0);
queue.add({digest:'d'}); queue.stop(); await sleep(15);
assert.deepEqual(started, ['a','b','c']);
