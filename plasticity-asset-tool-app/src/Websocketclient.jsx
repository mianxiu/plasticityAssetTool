/**
 *
 * @param {*} url
 * @param {Function} messageEvent
 * @returns {WebSocket}
 */
export class WebsocketClient {
  constructor(url, openEvent, messageEvent, closeEvent) {
    this.socket = new WebSocket(url);
    // 连接建立时的处理
    this.socket.addEventListener("open", () => {
      // console.log("Connected to WebSocket server");
      openEvent();
      // 发送消息到服务器
    });

    // 接收到消息时的处理
    this.socket.addEventListener("message", event => {
      messageEvent(event);
    });

    // 连接关闭时的处理
    this.socket.addEventListener("close", () => {
      // console.log("WebSocket connection closed");
      closeEvent();
    });
  }

  sendMessage(str) {
    console.log(`Send message:${str}`);
    this.socket.send(str);
  }
  // 创建 WebSocket 连接
  // const socket =

  //todo send
  // 监听按键事件
  // document.addEventListener("keydown", function (event) {
  //   if (event.code == "Backquote") {
  //     console.log("init key event done");
  //     window.parent.postMessage("hideContent", "*");
  //   }
  // });
}

export function WebsocketHeartBeat(url) {}
