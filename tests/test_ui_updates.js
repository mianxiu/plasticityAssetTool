const assert = require('node:assert/strict');

(async () => {
  const {createUpdateController} = await import('../plasticity-asset-tool-app/src/uiUpdates.mjs');
  let allowed = false, revision = 'new', ready = true, reloads = 0, saved = 0;
  const controller = createUpdateController({
    currentRevision:'old', loadBuild:async () => ({revision,ready}),
    canReload:() => allowed, beforeReload:() => saved++, reload:() => reloads++,
  });
  await controller.check();
  assert.equal(reloads,0,'Editing, placement and hidden panels must postpone updates');
  assert.equal(saved,0,'Do not persist/reset state while blocked');
  allowed = true; ready = false;
  await controller.check();
  assert.equal(reloads,0,'Incomplete build must not replace the current UI');
  ready = true; revision = 'old';
  await controller.check();
  assert.equal(reloads,0,'Unchanged build must not reload');
  revision = 'new';
  await controller.check(); await controller.check();
  assert.equal(reloads,1,'New build reloads once when idle');
  assert.equal(saved,1,'Browsing state is saved once before reloading');

  let resolve;
  const stopped = createUpdateController({currentRevision:'old',
    loadBuild:() => new Promise(done => {resolve=done;}),canReload:() => true,reload:() => assert.fail('Disposed watcher reloaded')});
  const pending = stopped.check(); stopped.stop(); resolve({revision:'new',ready:true}); await pending;
  const offline = createUpdateController({currentRevision:'old',loadBuild:async () => {throw new Error('offline');},
    canReload:() => true,reload:() => assert.fail('Offline page reloaded')});
  await offline.check();

  let concurrent = 0, finish;
  const single = createUpdateController({currentRevision:'old',loadBuild:() => {concurrent++;return new Promise(done => {finish=done;});},
    canReload:() => true,reload:() => {}});
  const first = single.check(); await single.check();
  assert.equal(concurrent,1,'Overlapping polls do not race');
  finish({revision:'new',ready:true}); await first;
  console.log('UI update safety checks passed');
})().catch(error => {console.error(error);process.exitCode=1;});
