// Native model encoding stays in memory. The synchronous adapter is removed
// before control returns to the event loop; no OS clipboard method is called.
const transportClipboard = nativeRequire('electron').clipboard;
const modelFormat = 'application/vnd.plasticity.items';
let transportBusy = false;
function requireIdle(editor) {
  const active = editor.executor.activeCommand;
  if (!transportBusy && !editor.executor.isBusy && !active) return;
  const name = active?.constructor?.name || '';
  const tool = /Paste|Place/.test(name) ? '置入' : /Offset|PushFace/.test(name) ? '偏移' : /Move/.test(name) ? '移动' : /Rotate/.test(name) ? '旋转' : /Scale/.test(name) ? '缩放' : '';
  throw new Error(tool ? `当前${tool}操作尚未结束。请先在视口确认或结束操作，再使用组件库。` : '当前建模操作尚未结束。请先在视口确认或结束操作，再使用组件库。');
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
async function insertModel(editor, args, PasteCommand, OperationType) {
  requireIdle(editor);
  const mode = args.insert_mode || 'new-body';
  if (!['new-body','union','difference','intersection'].includes(mode)) throw new Error('无效的默认置入模式');
  const booleanMode = mode !== 'new-body';
  if (booleanMode && !args.placement) throw new Error('布尔模式需要使用定位置入');
  const targets = booleanMode ? Array.from(editor.selection.selected.solids || []) : [];
  if (booleanMode && !targets.length) throw new Error('请先在 Plasticity 选中布尔目标实体，再置入组件');
  const operation = booleanMode ? OperationType?.[{union:'Union',difference:'Difference',intersection:'Intersection'}[mode]] : null;
  if (booleanMode && typeof operation !== 'number') throw new Error('当前版本不支持默认布尔置入，请更新内嵌插件');
  if (typeof args.model !== 'string' || args.model.length > 90*1024*1024 || !/^[A-Za-z0-9+/]*={0,2}$/.test(args.model)) throw new Error('组件模型编码无效');
  const data = NativeBuffer.from(args.model,'base64');
  if (data.length < 68 || data.length > 64*1024*1024) throw new Error('组件模型长度无效');
  const Command = args.placement ? editor.commands.PasteWithPlacementCommand : PasteCommand;
  if (typeof Command !== 'function') throw new Error('原生置入命令不可用');
  const command = new Command(editor);
  command.remember = false;
  let configured = !booleanMode, placementFactory;
  if (booleanMode) {
    const register = command.register;
    if (typeof register !== 'function') throw new Error('当前版本不支持默认布尔置入');
    command.register = function(resource, ...rest) {
      if (resource?.constructor?.name === 'PlaceFactory') {
        // Set the native factory before its controls and first pointer update.
        // Targets are snapshots of this window's selected solids only.
        resource.targets = targets;
        resource.operationType = operation;
        resource.keepTools = false;
        if (resource.operationType !== operation || resource.targets.length !== targets.length) throw new Error('原生布尔置入设置失败');
        configured = true;
        placementFactory = resource;
      }
      return register.call(this,resource,...rest);
    };
  }
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
  Promise.resolve(editor.exec(command)).then(()=>{
    if (!invoked) startedReject(new Error('置入命令未执行'));
  },startedReject);
  return started;
}
globalThis.__plasticityAssetTransport = Object.freeze({captureSelection,insertModel});
