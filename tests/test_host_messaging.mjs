import assert from 'node:assert/strict';
import {createParentChannel} from '../plasticity-asset-tool-app/src/hostMessaging.mjs';
const sent = [];
const parent = {postMessage(data, origin) {sent.push({data, origin});}};
let channel = createParentChannel(parent);
channel.send({type:'pat:ready'});
assert.equal(sent.at(-1).origin, '*');
assert.equal(channel.receive({source:parent, origin:'null', data:{type:'pat:shown'}}), true);
channel.send({type:'pat:prepare', id:'pick'});
assert.equal(sent.at(-1).origin, '*');
assert.equal(channel.receive({source:parent, origin:'null', data:{type:'pat:prepared',id:'pick',ready:true}}), true);
assert.equal(channel.receive({source:{}, origin:'https://other.example'}), false);
channel.send({type:'pat:show'});
assert.equal(sent.at(-1).origin, '*');
assert.equal(channel.receive({source:parent, origin:'https://cad.example'}), true);
channel.send({type:'pat:hide'});
assert.equal(sent.at(-1).origin, 'https://cad.example');
channel = createParentChannel(parent);
channel.send({type:'pat:ready'});
assert.equal(sent.at(-1).origin, '*');
console.log('Parent handshake and focus preparation messaging passed');

// Exercise the actual injected parent through edit/pick, re-open, UI reload,
// then placement. Opaque CAD origins cannot receive a localhost targetOrigin.
const {default:vm} = await import('node:vm');
const {readFileSync} = await import('node:fs');
const handlers = {}, replies = [];
let activeChannel;
const childOrigin = 'http://127.0.0.1:15150';
const childWindow = {postMessage(data, origin) {
  assert.equal(origin, childOrigin);
  if (activeChannel.receive({source:cadWindow, origin:'null', data})) replies.push(data);
}};
function element(tag) {
  const attrs = new Set();
  return {tagName:tag.toUpperCase(),style:{},hidden:false,children:[],contentWindow:childWindow,
    append(...items){this.children.push(...items)},appendChild(item){this.children.push(item)},
    setAttribute(name){attrs.add(name)},hasAttribute(name){return attrs.has(name)},
    focus(){doc.activeElement=this},blur(){doc.activeElement=null},remove(){}};
}
const canvas=element('canvas');
const doc={activeElement:null,body:element('body'),createElement:element,querySelector:()=>canvas,
  addEventListener(){},removeEventListener(){}};
const cadWindow={focus(){},addEventListener(name,fn){handlers[name]=fn},removeEventListener(){},
  postMessage(data,origin){
    if(origin!=='*') throw new Error('Opaque CAD window cannot accept this target origin');
    handlers.message({source:childWindow,origin:childOrigin,data});
  }};
const context={window:cadWindow,document:doc,URL,console,setTimeout,clearTimeout,
  requestAnimationFrame:fn=>fn(),innerWidth:1200,innerHeight:800};
vm.createContext(context);
vm.runInContext(readFileSync(new URL('../plasticity-javascript-payloads/init.js',import.meta.url),'utf8'),context);
context.installAssetPanel({url:childOrigin+'/?target=hwnd:42',key:'Tab',hidden:true});
const panel=cadWindow.__plasticityAssetToolPanel;
activeChannel=createParentChannel(cadWindow);
panel.toggle(true);
activeChannel.send({type:'pat:ready'});
for(const id of ['base-point-pick','insert-after-edit']) {
  activeChannel.send({type:'pat:prepare',id,preview:false});
  assert(replies.some(reply=>reply.type==='pat:prepared' && reply.id===id && reply.ready));
  assert.equal(doc.activeElement,canvas);
  activeChannel.send({type:'pat:show'});
  assert(panel.isVisible());
  activeChannel=createParentChannel(cadWindow); // hot-reloaded UI document
  activeChannel.send({type:'pat:ready'});
}
panel.dispose();
console.log('Injected parent: base point preparation followed by placement passed');
