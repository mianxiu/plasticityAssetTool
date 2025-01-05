/**
 *
 * @param {*} url
 * @param {Function} messageEvent
 * @returns {WebSocket}
 */
export class WebsocketClient {
  constructor(url, openEvent, messageEvent, closeEvent) {
    this.url = url;
    // this.socket = new WebSocket(this.url);
    this.ping = "";
    this.connect();
    this.closeEvent = closeEvent;
  }

  sendMessage(str) {
    console.log(`Send message:${str}`);
    this.socket.send(str);
  }

  connect() {
    this.socket = new WebSocket(this.url);
    // 连接建立时的处理
    this.socket.addEventListener("open", event => {
      // console.log("Connected to WebSocket server");
      openEvent(event);
      // 发送消息到服务器
    });

    // 接收到消息时的处理
    this.socket.addEventListener("message", event => {
      messageEvent(event);
    });

    // 连接关闭时的处理
    this.socket.addEventListener("close", event => {
      // console.log("WebSocket connection closed");
      this.closeEvent(event);
      console.log("close");
      console.log("Try Reconnect to server");
      let heartbeatTimeout2 = setTimeout(() => {
        this.connect();
      }, 3000);
      // this.runHeartBeat(3000);
    });

    window.addEventListener("beforeunload", () => {
      this.socket.close();
    });
  }

  runHeartBeat(heartbeatInterval = 3000) {
    let heartbeatTimeout2, heartbeatTimeout;

    const sendHeartbeat = () => {
      if (this.socket.readyState === WebSocket.OPEN) {
        this.socket.send("heartbeat"); // 发送心跳包
        console.log("Heartbeat sent");
        clearTimeout(heartbeatTimeout2);
      }
      // 设置下一个心跳
      heartbeatTimeout = setTimeout(sendHeartbeat, heartbeatInterval);
    };

    sendHeartbeat(heartbeatInterval);
  }

  stopHeartBeat() {
    clearTimeout(heartbeatTimeout);
  }
}

export function WebsocketHeartBeat(url) {}
