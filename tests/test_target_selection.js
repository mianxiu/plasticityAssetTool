const assert=require('node:assert/strict'),fs=require('fs');
(async()=>{
 const source=fs.readFileSync('plasticity-asset-tool-app/src/targetSelection.js','utf8');
 const {chooseTarget}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
 const state={targets:[{id:'hwnd:1'},{id:'hwnd:2'}],active_target_id:'hwnd:2'};
 assert.equal(chooseTarget({embedded:true,preferredTarget:'hwnd:3',current:'hwnd:1',followActive:true,state}),'hwnd:3');
 assert.equal(chooseTarget({embedded:true,preferredTarget:'hwnd:1',current:'hwnd:1',followActive:true,state}),'hwnd:1');
 assert.equal(chooseTarget({embedded:false,current:'hwnd:1',followActive:true,state}),'hwnd:2');
 assert.equal(chooseTarget({embedded:false,current:'hwnd:1',followActive:false,state}),'hwnd:1');
 assert.equal(chooseTarget({embedded:false,current:'hwnd:9',followActive:false,state}),'');
 console.log('Embedded ownership, delayed discovery, active following and fixed-window selection passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
