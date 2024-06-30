//  plasiticity use pointerup to target click
var targetElement = document.querySelector("#object_2");

var existingPointerEvent = new PointerEvent("pointerup");
targetElement.dispatchEvent(existingPointerEvent);
