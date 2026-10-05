// Native model encoding stays in memory. The synchronous adapter is removed
// before control returns to the event loop; no OS clipboard method is called.
const transportClipboard = nativeRequire('electron').clipboard;
const modelFormat = 'application/vnd.plasticity.items';
let transportBusy = false;
let calculation = null;
function calculationStatus() {return calculation ? {...calculation} : null;}
function labelGroupModel(data,recipe) {
  // Paste/placement may return bodies in a different order. Bind each body to
  // its recipe step with a unique temporary name, never the user's name.
  let offset=56;
  const block=()=>{const n=data.readUInt32LE(offset);offset+=4;const value=data.subarray(offset,offset+n);offset+=n;if(offset>data.length)throw new Error('组模型数据不完整');return value;};
  block();block();
  const count=data.readUInt32LE(offset);offset+=4;
  if(count!==recipe.parts.length)throw new Error('组子部件与模型数量不一致');
  const chunks=[data.subarray(0,offset)],names=[];
  const token=nativeRequire('crypto').randomUUID().replace(/-/g,'');
  const encodedBlock=value=>{const header=NativeBuffer.alloc(4);header.writeUInt32LE(value.length);return [header,value];};
  for(let index=0;index<count;index++) {
    const geometry=block(),metadata=JSON.parse(block().toString('utf8'));
    const name=`PAT-${token}-${index}`;names.push(name);
    chunks.push(...encodedBlock(geometry),...encodedBlock(NativeBuffer.from(JSON.stringify({...metadata,name}))));
  }
  return {data:NativeBuffer.concat(chunks),names};
}
function showCalculationError(error) {
  if(typeof document==='undefined') return;
  document.querySelector('#pat-calculation-error')?.remove();
  const alert=document.createElement('section');alert.id='pat-calculation-error';alert.setAttribute('role','alert');
  alert.style.cssText='position:fixed;top:24px;left:50%;transform:translateX(-50%);z-index:2147483647;max-width:calc(100vw - 48px);padding:16px;border:1px solid #b96969;border-radius:8px;background:#352326;color:#f1cccc;font:14px "Segoe UI","Microsoft YaHei",sans-serif;box-shadow:0 8px 32px #0008';
  const text=document.createElement('p');text.textContent=`组件库置入失败：${error.message || error}`;text.style.cssText='margin:0 0 10px;overflow-wrap:anywhere';
  const close=document.createElement('button');close.textContent='关闭';close.onclick=()=>alert.remove();
  alert.append(text,close);document.body.append(alert);
}
function beginCalculation(total) {
  if (calculation) throw new Error('组件正在计算，请等待本次操作结束');
  calculation = {startedAt:Date.now(),total,completed:0,step:0,label:'正在置入模型'};
  let overlay, text, timer;
  const events=['pointerdown','pointerup','pointermove','mousedown','mouseup','mousemove','click','dblclick','contextmenu','wheel','keydown','keyup','dragstart','drop','touchstart','touchmove','touchend'];
  const block=event=>{event.preventDefault();event.stopImmediatePropagation();};
  const render=()=>{
    if (!text || !calculation) return;
    const seconds=Math.floor((Date.now()-calculation.startedAt)/1000);
    text.textContent=`${calculation.label}${calculation.step ? ` · 第 ${calculation.step}/${calculation.total} 个部件` : ''} · 已用时 ${seconds} 秒`;
    timer=setTimeout(render,1000);
  };
  if (typeof document !== 'undefined') {
    document.querySelector('#pat-calculation-error')?.remove();
    overlay=document.createElement('div');
    overlay.id='pat-calculation-lock';
    overlay.style.cssText='position:fixed;inset:0;z-index:2147483647;background:#0004;display:grid;place-items:center;cursor:wait;user-select:none';
    const card=document.createElement('section');
    card.style.cssText='max-width:calc(100vw - 40px);padding:18px 24px;border:1px solid #555;border-radius:10px;background:#222;color:#eee;font:14px "Segoe UI","Microsoft YaHei",sans-serif;box-shadow:0 8px 40px #0008';
    card.setAttribute('role','status');card.setAttribute('aria-live','polite');
    const title=document.createElement('strong');title.textContent='组件库正在计算';
    text=document.createElement('p');text.style.cssText='margin:10px 0;overflow-wrap:anywhere';
    const hint=document.createElement('small');hint.textContent='此窗口的操作暂时锁定，计算结束后自动恢复';hint.style.color='#aaa';
    card.append(title,text,hint);overlay.append(card);document.body.append(overlay);
    for(const event of events) window.addEventListener(event,block,{capture:true,passive:false});
    console.log('PAT_OPERATION_LOCK:on');
    render();
  }
  return {
    update(step,label,completed=calculation?.completed || 0) {
      if (!calculation) return;
      Object.assign(calculation,{step,label,completed});
      if(timer) clearTimeout(timer);render();
    },
    finish() {
      if(timer) clearTimeout(timer);
      overlay?.remove();
      if(typeof document !== 'undefined') {
        for(const event of events) window.removeEventListener(event,block,true);
        console.log('PAT_OPERATION_LOCK:off');
      }
      calculation=null;
    }
  };
}
function requireIdle(editor) {
  if (calculation) throw new Error('组件正在计算，请等待本次操作结束');
  const active = editor.executor.activeCommand;
  if (!transportBusy && !editor.executor.isBusy && !active) return;
  const name = active?.constructor?.name || '';
  const tool = /Paste|Place/.test(name) ? '置入' : /Offset|PushFace/.test(name) ? '偏移' : /Move/.test(name) ? '移动' : /Rotate/.test(name) ? '旋转' : /Scale/.test(name) ? '缩放' : '';
  throw new Error(tool ? `当前${tool}操作尚未结束。请先在视口确认或结束操作，再使用组件库。` : '当前建模操作尚未结束。请先在视口确认或结束操作，再使用组件库。');
}
function inspectGroup(editor) {
  requireIdle(editor);
  const selected = editor.selection.selected;
  const ids = Array.from(selected.groupIds || []);
  if (!ids.length) return {recipe:null};
  if (ids.length !== 1 || selected.size !== 1 || ids[0] === 0) throw new Error('请只选择一个组件组');
  const id = ids[0], group = editor.groups.lookupById(id);
  const keys = Array.from(editor.groups.getChildren(id));
  if (!keys.length || keys.length > 128) throw new Error('组必须包含 1 至 128 个直接子实体');
  const parts = keys.map((key,index) => {
    const item = editor.db.key2item(key);
    if (item?.constructor?.name !== 'Solid') throw new Error('当前组保存仅支持直接子实体，请移出子组、曲线或曲面');
    const name = editor.nodes.getName(key) || `部件 ${index+1}`;
    if (name.length > 120) throw new Error('子部件名称不能超过 120 字符');
    return {index,name,mode:({'+':'union','-':'difference','&':'intersection','^':'new-body'})[name.trimStart()[0]] || 'new-body'};
  });
  const name = editor.nodes.getName(editor.nodes.item2key(group)) || `组 ${id}`;
  if (name.length > 120) throw new Error('组名称不能超过 120 字符');
  return {recipe:{version:1,name,parts},signature:JSON.stringify([id,keys,parts,name,keys.map(key=>editor.db.key2item(key).userData.versionId)])};
}
function captureGroup(editor, signature) {
  const inspected = inspectGroup(editor);
  if (!inspected.recipe || inspected.signature !== signature) throw new Error('组或模型已变化，请重新选择组并点击保存组件');
  const groupId = Array.from(editor.selection.selected.groupIds)[0];
  const keys = Array.from(editor.groups.getChildren(groupId));
  const selected = editor.selection.selected, saved = selected.saveToMemento();
  const chunks = []; let header;
  try {
    for (const key of keys) {
      selected.removeAll(); selected.add(editor.db.key2item(key));
      const data = NativeBuffer.from(captureSelection(editor).model,'base64');
      let offset = 56;
      for (let i=0;i<2;i++) {const n=data.readUInt32LE(offset);offset+=4+n;}
      if (data.readUInt32LE(offset) !== 1) throw new Error('子部件模型编码不兼容');
      if (!header) header = NativeBuffer.from(data.subarray(0,offset+4));
      offset += 4; const start=offset;
      for (let i=0;i<2;i++) {const n=data.readUInt32LE(offset);offset+=4+n;}
      chunks.push(data.subarray(start,offset));
    }
  } finally {selected.restoreFromMemento(saved);}
  header.writeUInt32LE(keys.length,header.length-4);
  const model=NativeBuffer.concat([header,...chunks]);
  if (model.length > 64*1024*1024) throw new Error('组模型超过 64 MB');
  return {model:model.toString('base64'),recipe:inspected.recipe};
}
function captureSelection(editor) {
  requireIdle(editor);
  if (!editor.selection.selected.size) throw new Error('请先选中要保存的模型');
  const selected = editor.selection.selected;
  const solids = Array.from(selected.solids || []).length;
  const curves = Array.from(selected.curves || []).length;
  const kind = solids + curves !== selected.size ? 'unknown' : solids && curves ? 'mixed' : curves ? 'curve' : solids ? 'solid' : 'unknown';
  const original = transportClipboard.writeBuffer;
  let captured, writes = 0;
  transportBusy = true;
  transportClipboard.writeBuffer = (format, data) => {
    if (format !== modelFormat || ++writes !== 1) throw new Error('原生模型格式不支持');
    captured = NativeBuffer.from(data);
  };
  try {
    const result = editor.clipboard.copy();
    if (result?.then) throw new Error('当前版本的模型编码接口不兼容');
  } finally {
    transportClipboard.writeBuffer = original;
    transportBusy = false;
  }
  if (!captured?.length || captured.length > 64*1024*1024) throw new Error('没有取得有效的模型数据');
  return {model:captured.toString('base64'),kind,counts:{solids,curves}};
}
async function captureWithBasePoint(editor, CopyWithPlacementCommand, temporary) {
  requireIdle(editor);
  if (!temporary && !editor.selection.selected.size) throw new Error('请先选中原组件或参考模型，再拾取基点');
  if (typeof CopyWithPlacementCommand !== 'function') throw new Error('当前版本不支持原生基点拾取');
  const clipboard = editor.clipboard, originalCopy = clipboard.copy;
  let captured, calls = 0, timer, expired = false;
  // Intercept the synchronous encoding call only, not the system clipboard
  // throughout the interactive point picker. Forward native placement arguments.
  const copyHook = function(...args) {
    if(expired) throw new Error('基点拾取已结束');
    if (++calls !== 1) throw new Error('原生基点复制接口不兼容');
    const originalWrite = transportClipboard.writeBuffer;
    let writes = 0;
    transportClipboard.writeBuffer = (format, data) => {
      if (format !== modelFormat || ++writes !== 1) throw new Error('原生基点模型格式不支持');
      captured = NativeBuffer.from(data);
    };
    try {
      const result = originalCopy.apply(this,args);
      if (result?.then) throw new Error('原生基点编码接口不兼容');
      return result;
    } finally {transportClipboard.writeBuffer = originalWrite;}
  };
  const selected=editor.selection.selected;
  const solids=Array.from(selected.solids || []).length, curves=Array.from(selected.curves || []).length;
  const kind=solids+curves !== selected.size ? 'unknown' : solids && curves ? 'mixed' : curves ? 'curve' : solids ? 'solid' : 'unknown';
  const command = new CopyWithPlacementCommand(editor);
  command.remember = false;
  const selectionMemento = selected.saveToMemento?.();
  let resolveFinished, rejectFinished;
  const finished = new Promise((resolve,reject)=>{resolveFinished=resolve;rejectFinished=reject;});
  const execute=command.execute;
  const rollbackSuccess = temporary ? new temporary.Cancel() : null;
  if(typeof execute !== 'function') throw new Error('原生基点命令接口不兼容');
  command.execute = async function(...args) {
    try {
      let value;
      try {
        if(temporary) await loadBasePointReference(editor,command,temporary);
        if(expired) throw new Error('基点拾取已结束');
        value=temporary?.base_mode === 'world' ? clipboard.copy() : await execute.apply(this,args);
      } finally {
        if(temporary?.items?.length) {
          const transaction=editor.db.makeTransaction();
          for(const item of temporary.items) transaction.delete(item.view);
          await editor.db.commit(transaction);
        }
      }
      resolveFinished(value);
      // The executor rolls back the entire temporary import on both paths.
      if(temporary) throw rollbackSuccess;
      return value;
    } catch(error) {if(error !== rollbackSuccess) rejectFinished(error);throw error;}
  };
  clipboard.copy = copyHook;
  transportBusy = true;
  try {
    const deadline = new Promise((_,reject)=>{timer=setTimeout(async()=>{
      expired = true;
      if(editor.executor.activeCommand === command) {
        try {await editor.executor.cancelActiveCommand();} catch {}
      }
      reject(new Error('基点拾取超时，未保存组件'));
    },120000);});
    const launched=editor.exec(command);
    Promise.resolve(launched).catch(rejectFinished);
    await Promise.race([finished,deadline]);
    if (!captured || captured.length < 68 || captured.length > 64*1024*1024) throw new Error('基点拾取已取消，未保存组件');
    return {model:captured.toString('base64'),kind,counts:{solids,curves}};
  } finally {
    clearTimeout(timer);
    expired = true;
    if(clipboard.copy === copyHook) clipboard.copy = originalCopy;
    // execute() finishing precedes the native executor's selection cleanup.
    // Restore after that cleanup so group validation sees an idle executor.
    for(let attempt=0;editor.executor.activeCommand === command && attempt<100;attempt++) {
      await new Promise(resolve=>setTimeout(resolve,10));
    }
    if(selectionMemento !== undefined) selected.restoreFromMemento(selectionMemento);
    transportBusy = false;
    if(editor.executor.activeCommand === command) throw new Error('基点命令尚未结束，未保存组件');
  }
}
async function loadBasePointReference(editor, command, temporary) {
  const {data,PasteCommand}=temporary;
  const pk=nativeRequire(nativeRequire('path').join(nativeRequire('process').resourcesPath,'app','.webpack','renderer','pk.node'));
  const partition=pk.Session.GetPrimaryPartition();
  const before=new Set(partition.GetBodies().map(body=>body.Id()));
  const paste=new PasteCommand(editor);
  paste.remember=false;
  if(typeof command.register === 'function') paste.register=command.register.bind(command);
  const read=transportClipboard.readBuffer,formats=transportClipboard.availableFormats,has=transportClipboard.has;
  let pending,reads=0;
  try {
    transportClipboard.availableFormats=()=>[modelFormat];
    transportClipboard.has=format=>format===modelFormat;
    transportClipboard.readBuffer=format=>{
      if(format!==modelFormat || ++reads!==1) throw new Error('临时组件读取接口不兼容');
      return NativeBuffer.from(data);
    };
    pending=paste.execute();
    if(reads!==1) throw new Error('未能加载临时组件');
  } finally {
    transportClipboard.readBuffer=read;transportClipboard.availableFormats=formats;transportClipboard.has=has;
  }
  try {await pending;} finally {
    temporary.items=partition.GetBodies().filter(body=>!before.has(body.Id())).map(body=>editor.db.lookupByBodyId(body.Id())).filter(item=>item?.view);
  }
  editor.selection.selected.removeAll();
  for(const item of temporary.items) editor.selection.selected.add(item.view);
  if(!editor.selection.selected.size) throw new Error('组件没有可用于拾取的模型');
  if(temporary.base_mode === 'pick') for(const viewport of editor.viewports || []) viewport.focus();
}
async function rebaseModel(editor, args, CopyCommand, PasteCommand, Cancel) {
  if(!['world','pick'].includes(args.base_mode) || (typeof PasteCommand !== 'function' || typeof Cancel !== 'function')) throw new Error('组件基点接口不兼容，请更新插件');
  if(typeof args.model !== 'string' || args.model.length>90*1024*1024 || !/^[A-Za-z0-9+/]*={0,2}$/.test(args.model)) throw new Error('组件模型编码无效');
  const data=NativeBuffer.from(args.model,'base64');
  if(data.length<68 || data.length>64*1024*1024) throw new Error('组件模型长度无效');
  return captureWithBasePoint(editor,CopyCommand,{data,PasteCommand,Cancel,base_mode:args.base_mode});
}
async function captureGroupWithBasePoint(editor, signature, CopyWithPlacementCommand) {
  const group = captureGroup(editor,signature);
  const selected = editor.selection.selected, saved = selected.saveToMemento();
  const groupId = Array.from(selected.groupIds)[0];
  let captured;
  try {
    // Native Copy with Placement consumes selected geometry, not group IDs.
    // Expand only for picking; keep the separately encoded recipe ordering.
    const children = Array.from(editor.groups.getChildren(groupId));
    selected.removeAll();
    for (const key of children) selected.add(editor.db.key2item(key));
    captured = await captureWithBasePoint(editor,CopyWithPlacementCommand);
  } finally {selected.restoreFromMemento(saved);}
  if(inspectGroup(editor).signature !== signature) throw new Error('组或模型已变化，未保存组件');
  // Preserve ordered bodies and opaque native placement bytes as a unit.
  const data=NativeBuffer.from(group.model,'base64');
  NativeBuffer.from(captured.model,'base64').copy(data,0,0,56);
  return {...group,model:data.toString('base64')};
}
async function insertModel(editor, args, PasteCommand, OperationType, BooleanFactory) {
  requireIdle(editor);
  const recipe = args.recipe;
  const mode = recipe ? 'new-body' : args.insert_mode || 'new-body';
  if (!['new-body','union','difference','intersection'].includes(mode)) throw new Error('无效的默认置入模式');
  const booleanMode = mode !== 'new-body';
  if (booleanMode && !args.placement) throw new Error('布尔模式需要使用定位置入');
  const targets = booleanMode || recipe ? Array.from(editor.selection.selected.solids || []) : [];
  if (recipe) {
    if (!args.placement) throw new Error('组组件请使用定位置入，以保持部件顺序和组信息');
    if (recipe.version !== 1 || !Array.isArray(recipe.parts) || !recipe.parts.length || recipe.parts.length>128) throw new Error('组运算数据无效');
    if (typeof BooleanFactory !== 'function' || !OperationType) throw new Error('当前版本不支持组运算');
    const first = recipe.parts.find(p=>p.mode !== 'new-body');
    if (args.placement && !targets.length && first && first.mode !== 'union') throw new Error('组的第一个布尔操作需要目标实体，请先选中目标');
  }
  if (booleanMode && !targets.length) throw new Error('请先在 Plasticity 选中布尔目标实体，再置入组件');
  const operation = booleanMode ? OperationType?.[{union:'Union',difference:'Difference',intersection:'Intersection'}[mode]] : null;
  if (booleanMode && typeof operation !== 'number') throw new Error('当前版本不支持默认布尔置入，请更新内嵌插件');
  if (booleanMode && typeof BooleanFactory !== 'function') throw new Error('当前版本不支持安全布尔置入，请更新内嵌插件');
  if (typeof args.model !== 'string' || args.model.length > 90*1024*1024 || !/^[A-Za-z0-9+/]*={0,2}$/.test(args.model)) throw new Error('组件模型编码无效');
  let data = NativeBuffer.from(args.model,'base64');
  if (data.length < 68 || data.length > 64*1024*1024) throw new Error('组件模型长度无效');
  let partNames;
  if(recipe) {const tagged=labelGroupModel(data,recipe);data=tagged.data;partNames=tagged.names;}
  const Command = args.placement ? editor.commands.PasteWithPlacementCommand : PasteCommand;
  if (typeof Command !== 'function') throw new Error('原生置入命令不可用');
  const command = new Command(editor);
  command.remember = false;
  let configured = !booleanMode && !recipe, placementFactory, progress, calculationError;
  const report=(step,label,completed)=>progress?.update(step,label,completed);
  const finish=()=>{progress?.finish();progress=null;if(calculationError)showCalculationError(calculationError);};
  if (typeof command.register === 'function') {
    const register = command.register;
    if (typeof register !== 'function') throw new Error('当前版本不支持默认布尔置入');
    command.register = function(resource, ...rest) {
      if (resource?.constructor?.name === 'PlaceFactory') {
        // Set the native factory before its controls and first pointer update.
        // Targets are snapshots of this window's selected solids only.
        if (recipe) {
          configureGroupPlacement(editor,command,resource,recipe,args.placement ? targets : [],OperationType,BooleanFactory,!!args.placement,report,partNames);
        } else if (booleanMode) {
          // PlaceFactory's boolean path can commit its placement cache rather
          // than the requested operation. Use the same explicit kernel factory
          // as recipes, inside this command's single undo transaction.
          configureBooleanPlacement(editor,command,resource,targets,operation,BooleanFactory);
        }
        const commit=resource.commit;
        if(typeof commit === 'function') resource.commit=async function(...params) {
          progress=beginCalculation(recipe ? recipe.parts.length : 1);
          if(!recipe) report(1,({union:'正在布尔合并',difference:'正在布尔减去',intersection:'正在布尔相交'})[mode] || '正在置入模型');
          try {
            // Paint the lock before entering a potentially expensive kernel call.
            if(typeof requestAnimationFrame === 'function') await new Promise(resolve=>requestAnimationFrame(()=>setTimeout(resolve,0)));
            const result=await commit.apply(this,params);
            if(booleanMode && !Array.from(result || []).length) throw new Error('布尔结果为空，已撤销本次置入');
            report(recipe ? recipe.parts.length : 1,'正在完成置入',recipe ? recipe.parts.length : 1);
            return result;
          } catch(error) {calculationError=error;report(calculation?.step || 0,'计算失败，正在回滚');throw error;}
        };
        configured = true;
        placementFactory = resource;
      }
      return register.call(this,resource,...rest);
    };
  } else if(booleanMode || recipe) throw new Error('当前版本不支持默认布尔置入');
  const execute = command.execute;
  let startedResolve, startedReject, invoked = false;
  const started = new Promise((resolve,reject)=>{startedResolve=resolve;startedReject=reject;});
  command.execute = function() {
    const original = transportClipboard.readBuffer;
    const originalFormats = transportClipboard.availableFormats;
    const originalHas = transportClipboard.has;
    let reads = 0, deliveredBuffer;
    transportBusy = true;
    transportClipboard.availableFormats = () => [modelFormat];
    if (typeof originalHas === 'function') transportClipboard.has = format => format === modelFormat;
    transportClipboard.readBuffer = format => {
      if (format !== modelFormat || ++reads !== 1) throw new Error('原生置入数据接口不兼容');
      deliveredBuffer = NativeBuffer.from(data);
      return deliveredBuffer;
    };
    let pending;
    try {
      pending = execute.call(this);
      if (reads !== 1) throw new Error('原生置入未接收组件数据');
      invoked = true;
    } catch(error) {startedReject(error);throw error;}
    finally {
      transportClipboard.readBuffer=original;
      transportClipboard.availableFormats=originalFormats;
      if (typeof originalHas === 'function') transportClipboard.has=originalHas;
      transportBusy=false;
    }
    // Catch early deserialization failures; interactive placement stays pending.
    Promise.resolve(pending).catch(startedReject);
    const deadline = Date.now() + 4000;
    const acknowledge = () => {
      if (!configured && Date.now() < deadline && editor.executor.activeCommand === command) {setTimeout(acknowledge,50);return;}
      if (!configured) {
        startedReject(new Error('当前版本的置入工具不支持默认布尔模式'));
        if(editor.executor.activeCommand === command) Promise.resolve(editor.executor.cancelActiveCommand()).catch(()=>{});
      } else if (booleanMode && placementFactory.shells?.length === 0) {
        startedReject(new Error('当前组件没有可用于布尔运算的实体或曲面'));
        if(editor.executor.activeCommand === command) Promise.resolve(editor.executor.cancelActiveCommand()).catch(()=>{});
      } else startedResolve({started:true,transport:'native',insert_mode:mode});
    };
    setTimeout(acknowledge,100);
    if (args.placement) {
      // Keep the initial native placement untouched. After confirmation only,
      // end its empty continuation. Identity binds this to our own model job;
      // unrelated commands, even other Paste commands, are never cancelled.
      const finishContinuation = () => {
        const active = editor.executor.activeCommand;
        if (!active || active.buffer !== deliveredBuffer) return;
        if (active.constructor.name === 'RepeatPasteWithPlacementCommand') {
          Promise.resolve(editor.executor.cancelActiveCommand()).catch(()=>{});
        } else if (active.constructor.name === 'PasteWithPlacementCommand') {
          setTimeout(finishContinuation,100);
        }
      };
      setTimeout(finishContinuation,100);
    }
    return pending;
  };
  try {
    Promise.resolve(editor.exec(command)).then(()=>{
      finish();
      if (!invoked) startedReject(new Error('置入命令未执行'));
    },error=>{finish();startedReject(error);});
  } catch(error) {finish();throw error;}
  return started;
}
function configureBooleanPlacement(editor,command,factory,targets,operation,BooleanFactory) {
  const boolean=new BooleanFactory(editor);command.register(boolean);
  const commit=factory.commit;
  factory.commit=async function(...args) {
    if(this.shouldPerformBoolean) throw new Error('定位置入被切换为整体布尔，请重新置入；组件布尔在确认后执行');
    const placed=Array.from(await commit.apply(this,args));
    if(!placed.length) throw new Error('未取得置入实体，已停止布尔运算');
    boolean.targets=targets;boolean.tools=placed;boolean.keepTools=false;boolean.operationType=operation;
    const result=Array.from(await boolean.commit());
    if(!result.length) throw new Error('布尔结果为空，已撤销本次置入');
    return result;
  };
}
function configureGroupPlacement(editor,command,factory,recipe,targets,OperationType,BooleanFactory,performBoolean,report=()=>{},partNames) {
  // The native command owns the placement and every following factory, so
  // cancellation/failure rolls back its single transaction and undo restores it.
  const commit = factory.commit;
  for (const [index, part] of recipe.parts.entries()) {
    if (part.index !== index || !['new-body','union','difference','intersection'].includes(part.mode)) throw new Error('组运算步骤或顺序无效');
    if (performBoolean && part.mode !== 'new-body' && typeof OperationType?.[{union:'Union',difference:'Difference',intersection:'Intersection'}[part.mode]] !== 'number') throw new Error('当前版本的组布尔运算接口不兼容');
  }
  const booleans=recipe.parts.map(part=>{
    if (!performBoolean || part.mode === 'new-body') return null;
    const boolean=new BooleanFactory(editor);command.register(boolean);return boolean;
  });
  factory.commit = async function(...args) {
    if(this.shells.length !== recipe.parts.length) throw new Error('组子部件与置入模型数量不一致');
    if(this.shouldPerformBoolean) throw new Error('组定位置入被切换为整体布尔，请重新置入；组内布尔由子部件名称决定');
    let placed = Array.from(await commit.apply(this,args));
    if (placed.length !== recipe.parts.length || placed.some(v=>v.constructor.name !== 'Solid')) throw new Error('置入部件与保存的组顺序不一致');
    if(partNames) {
      const byName=new Map();
      for(const body of placed) {
        const name=editor.nodes.getName(editor.nodes.item2key(body));
        if(!partNames.includes(name) || byName.has(name)) throw new Error('无法确认置入子部件的身份，已停止组运算');
        byName.set(name,body);
      }
      placed=partNames.map(name=>byName.get(name));
      if(placed.some(body=>!body)) throw new Error('组子部件身份不完整，已停止组运算');
    }
    let accumulator=targets.slice(); const independent=[];
    for (const part of recipe.parts) {
      const action=({union:'布尔合并',difference:'布尔减去',intersection:'布尔相交','new-body':'保留独立实体'})[part.mode];
      report(part.index+1,`${action}：${part.name}`,part.index);
      const tool=placed[part.index];
      editor.nodes.setName(editor.nodes.item2key(tool),part.name);
      if (!performBoolean || part.mode === 'new-body') {independent.push(tool);continue;}
      if (!accumulator.length && part.mode === 'union') {accumulator=[tool];continue;}
      if (!accumulator.length) throw new Error(`部件 ${part.name} 没有可用的布尔目标`);
      const boolean = booleans[part.index];
      boolean.targets=accumulator; boolean.tools=[tool]; boolean.keepTools=false;
      boolean.operationType=OperationType[{union:'Union',difference:'Difference',intersection:'Intersection'}[part.mode]];
      try {accumulator=Array.from(await boolean.commit());}
      catch(error) {throw new Error(`第 ${part.index+1} 个部件“${part.name}”${action}失败：${error.message || error}`);}
      if (!accumulator.length) throw new Error(`部件 ${part.name} 的布尔结果为空，已撤销本次置入`);
    }
    const results=[...accumulator,...independent];
    const group=editor.groups.create(); editor.nodes.setName(editor.nodes.item2key(group),recipe.name);
    // create() allocates a group but does not attach it to the scene. Moving
    // the results into an orphan group removes them from the visible tree.
    editor.groups.addMembership(editor.nodes.item2key(group),editor.groups.root);
    for (const [index,result] of results.entries()) {
      const key=editor.nodes.item2key(result);
      editor.groups.deleteMembership(key); editor.groups.addMembership(key,group,index);
    }
    return results;
  };
}
globalThis.__plasticityAssetTransport = Object.freeze({captureSelection,captureWithBasePoint,rebaseModel,captureGroupWithBasePoint,captureGroup,inspectGroup,insertModel,calculationStatus});
