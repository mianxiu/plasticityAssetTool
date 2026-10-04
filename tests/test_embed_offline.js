// Exercise the actual injected script without starting or editing a CAD model.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const events = {}, sent = [];
function element(tag) {
  const attrs = new Map();
  return {tagName:tag.toUpperCase(),hidden:false,style:{},children:[],
    append(...items){this.children.push(...items)},appendChild(item){this.children.push(item)},
    setAttribute(k,v){attrs.set(k,v)},hasAttribute(k){return k==='src' ? !!this.src : attrs.has(k)},
    focus(){context.document.activeElement=this},blur(){context.document.activeElement=null},remove(){this.removed=true},
    contentWindow:{postMessage(data){sent.push(data)}}};
}
const canvas = element('canvas');
const context = {URL,console,requestAnimationFrame:fn=>fn(),
  setTimeout,clearTimeout,innerWidth:1000,innerHeight:700,
  document:{body:element('body'),createElement:element,activeElement:null,
    querySelector:()=>canvas,addEventListener(){},removeEventListener(){}},
  window:{focus(){},addEventListener(name,fn){events[name]=fn},removeEventListener(){}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
context.installAssetPanel({url:'http://127.0.0.1:15150/?target=hwnd:42',key:'Tab',hidden:true});
const panel = context.window.__plasticityAssetToolPanel;
panel.toggle(false);
assert(panel.isVisible());assert(panel.frame.hidden);assert(!panel.offline.hidden);
assert.strictEqual(panel.offline.children[0].textContent,'组件库后台未连接');
panel.toggle(false);assert(!panel.isVisible());
panel.toggle(true);assert(!panel.frame.hidden);assert(panel.offline.hidden);
events.message({source:panel.frame.contentWindow,origin:'http://127.0.0.1:15150',data:{type:'pat:ready'}});
assert(sent.some(item=>item.type==='pat:shown'));
canvas.getBoundingClientRect=()=>({left:200,top:50,right:1000,bottom:700});
events.message({source:panel.frame.contentWindow,origin:'http://127.0.0.1:15150',data:{type:'pat:prepare',id:'preview-test',preview:true}});
assert.deepStrictEqual(JSON.parse(JSON.stringify(panel.previewRect('preview-test'))),{x:200,y:50,width:800,height:650});
assert.strictEqual(panel.previewRect('forged'),null);
panel.completePreview('preview-test','data:image/jpeg;base64,test');
assert(sent.some(item=>item.id==='preview-test'&&item.preview==='data:image/jpeg;base64,test'&&item.ready));
assert.strictEqual(panel.previewRect('preview-test'),null);
panel.toggle(true);
panel.toggle();assert(!panel.isVisible());
panel.toggle(false);panel.offline.children[2].onclick();assert(!panel.isVisible());
panel.dispose();assert(panel.frame.removed);assert(panel.offline.removed);
console.log('OFFLINE_PANEL_OK');
