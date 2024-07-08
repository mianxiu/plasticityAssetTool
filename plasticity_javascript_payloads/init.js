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
node.style = "display:block;width:500px;height:500px;position:fixed;background-color: antiquewhite;border-radius: 10px;top:100px;left:100px;z-index:300;";
document.querySelector("body").appendChild(node);
// 获取要监听的元素

// 监听按键事件
document.addEventListener("keydown", async function (event) {
  if (event.code == "Backquote") {
    // 按下 "z" 键时切换元素的显示状态
    let el = document.querySelector("#plasticity_asset_tool_panel");
    el.style.display = el.style.display === "none" ? "block" : "none";
  }
});

// 获取 iframe 元素

// 添加消息监听器，用于接收来自 iframe 的通知
window.addEventListener("message", function (event) {
  if (event.data === "hideContent") {
    // 接收到来自 iframe 的通知，隐藏内容
    window.parent.focus();
    let el = document.querySelector("#plasticity_asset_tool_panel");
    el.style.display = "none";
  }
});
console.log("init");
