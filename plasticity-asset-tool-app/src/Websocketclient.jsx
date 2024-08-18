export function Websocket_Client() {
  // 创建 WebSocket 连接
  const socket = new WebSocket("ws://127.0.0.1:15150/websocket");

  // 连接建立时的处理
  socket.addEventListener("open", () => {
    console.log("Connected to WebSocket server");
    // 发送消息到服务器
  });

  // 接收到消息时的处理
  socket.addEventListener("message", event => {
    console.log("Received message from server:", event.data);
  });

  // 连接关闭时的处理
  socket.addEventListener("close", () => {
    console.log("WebSocket connection closed");
  });

  // 监听按键事件
  document.addEventListener("keydown", function (event) {
    if (event.code == "Backquote") {
      console.log("init key event done");
      window.parent.postMessage("hideContent", "*");
    }
  });
}
