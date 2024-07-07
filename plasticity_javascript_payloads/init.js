// in plasiticity 3d
// object node is list node, and has event
// input node is list name node
var objectNodes = document.querySelectorAll("#left-sidebar .mr-1");
var inputNodes = document.querySelectorAll("#left-sidebar .mr-1 input");

for (let i = 0; i < objectNodes.length; i++) {
  let objectNode = objectNodes[i];
  let inputNode = inputNodes[i];
  objectNode.id = `object_${i}`;
  objectNode.setAttribute("object-index", i);
  inputNode.id = `input_${i}`;
}

var canvas = (document.querySelector("canvas").id = "canvas");

console.log(`PlasticityAssetTool:init node id`);

// add tool node
let node = document.createElement("iframe");
node.id = "plasticity_asset_tool_panel";
node.src = "http://127.0.0.1:15150/index.html";
node.style = "display:block;width:500px;height:500px;position:fixed;";
document.querySelector("body").appendChild(node);

console.log("init");
