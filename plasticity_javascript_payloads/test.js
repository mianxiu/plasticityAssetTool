// 2024-6-23
// Copy with placement

//  获取目标元素
var targetElement = document.querySelector("#viewport > plasticity-viewport > canvas");

var existingPointerEvent = new Event("edit:copy-with-placement");
targetElement.dispatchEvent(existingPointerEvent);

//2 need move mouse
document.querySelector("#viewport > plasticity-viewport > plasticity-snap-overlay > div").innerHTML = `<div class="absolute px-2 py-1 ml-5 -mt-5 text-xs rounded shadow-md text-neutral-50 bg-neutral-500 border-neutral-400 shadow-black/20" style="left: 0px; top: 0px; transform: translate(1712.58px, 823.699px); will-change: transform;">XY</div>`;

//3 创建一个已有的PointerEvent对象
var existingPointerEvent = new PointerEvent("pointermove");

// 触发已有的pointerup事件
targetElement.dispatchEvent(existingPointerEvent);

var existingPointerEvent = new Event("point-picker:finish");
targetElement.dispatchEvent(existingPointerEvent);
//-----rename
// first to select

var inputElement = document.querySelector("#input_2");
var objectElement = inputElement.parentElement;
objectElement.dispatchEvent(new PointerEvent("pointerup"));
objectElement.dispatchEvent(new MouseEvent("dblclick"));
inputElement.value = "is rename 202021";
var inputElement = document.querySelector("#input_2");
objectElement.dispatchEvent(new PointerEvent("pointerup"));
//targetElement.dispatchEvent(new Event("Command:SetName"));
