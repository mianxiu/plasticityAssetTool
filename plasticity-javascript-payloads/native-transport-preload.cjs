// Native model encoding stays in memory. The synchronous adapter is removed
// before control returns to the event loop; no OS clipboard method is called.
const transportClipboard = nativeRequire('electron').clipboard;
const modelFormat = 'application/vnd.plasticity.items';
let transportBusy = false;
let calculation = null;
function calculationStatus() {return calculation ? {...calculation} : null;}
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
  return {model:captured.toString('base64')};
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
  if (typeof args.model !== 'string' || args.model.length > 90*1024*1024 || !/^[A-Za-z0-9+/]*={0,2}$/.test(args.model)) throw new Error('组件模型编码无效');
  let data = NativeBuffer.from(args.model,'base64');
  if (data.length < 68 || data.length > 64*1024*1024) throw new Error('组件模型长度无效');
  const Command = args.placement ? editor.commands.PasteWithPlacementCommand : PasteCommand;
  if (typeof Command !== 'function') throw new Error('原生置入命令不可用');
  const command = new Command(editor);
  command.remember = false;
  let configured = !booleanMode && !recipe, placementFactory, progress;
  const report=(step,label,completed)=>progress?.update(step,label,completed);
  const finish=()=>{progress?.finish();progress=null;};
  if (typeof command.register === 'function') {
    const register = command.register;
    if (typeof register !== 'function') throw new Error('当前版本不支持默认布尔置入');
    command.register = function(resource, ...rest) {
      if (resource?.constructor?.name === 'PlaceFactory') {
        // Set the native factory before its controls and first pointer update.
        // Targets are snapshots of this window's selected solids only.
        if (recipe) {
          configureGroupPlacement(editor,command,resource,recipe,args.placement ? targets : [],OperationType,BooleanFactory,!!args.placement,report);
        } else if (booleanMode) {
          resource.targets = targets;
          resource.operationType = operation;
          resource.keepTools = false;
          if (resource.operationType !== operation || resource.targets.length !== targets.length) throw new Error('原生布尔置入设置失败');
        }
        const commit=resource.commit;
        if(typeof commit === 'function') resource.commit=async function(...params) {
          progress=beginCalculation(recipe ? recipe.parts.length : 1);
          if(!recipe) report(1,({union:'正在布尔合并',difference:'正在布尔减去',intersection:'正在布尔相交'})[mode] || '正在置入模型');
          try {
            // Paint the lock before entering a potentially expensive kernel call.
            if(typeof requestAnimationFrame === 'function') await new Promise(resolve=>requestAnimationFrame(()=>setTimeout(resolve,0)));
            const result=await commit.apply(this,params);
            report(recipe ? recipe.parts.length : 1,'正在完成置入',recipe ? recipe.parts.length : 1);
            return result;
          } catch(error) {report(calculation?.step || 0,'计算失败，正在回滚');throw error;}
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
function configureGroupPlacement(editor,command,factory,recipe,targets,OperationType,BooleanFactory,performBoolean,report=()=>{}) {
  // The native command owns the placement and every following factory, so
  // cancellation/failure rolls back its single transaction and undo restores it.
  const commit = factory.commit;
  const booleans=recipe.parts.map(part=>{
    if (!performBoolean || part.mode === 'new-body') return null;
    const boolean=new BooleanFactory(editor);command.register(boolean);return boolean;
  });
  factory.commit = async function(...args) {
    if(this.shells.length !== recipe.parts.length) throw new Error('组子部件与置入模型数量不一致');
    // Native non-boolean placement returns one transformed solid for each
    // input shell, in model-envelope order. Geometry tests verify this with
    // unequal bodies and non-commutative operations; names are never keys.
    const placed = Array.from(await commit.apply(this,args));
    if (placed.length !== recipe.parts.length || placed.some(v=>v.constructor.name !== 'Solid')) throw new Error('置入部件与保存的组顺序不一致');
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
      accumulator=Array.from(await boolean.commit());
      if (!accumulator.length) throw new Error(`部件 ${part.name} 的布尔结果为空，已撤销本次置入`);
    }
    const results=[...accumulator,...independent];
    const group=editor.groups.create(); editor.nodes.setName(editor.nodes.item2key(group),recipe.name);
    for (const [index,result] of results.entries()) {
      const key=editor.nodes.item2key(result);
      editor.groups.deleteMembership(key); editor.groups.addMembership(key,group,index);
    }
    return results;
  };
}
globalThis.__plasticityAssetTransport = Object.freeze({captureSelection,captureGroup,inspectGroup,insertModel,calculationStatus});
