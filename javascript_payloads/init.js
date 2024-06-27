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

console.log(`PlasticityAssetTool:init node id`);
