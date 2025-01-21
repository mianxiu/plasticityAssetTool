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
    // this.connect();
    this.openEvent = openEvent;
    this.messageEvent = messageEvent;
    this.closeEvent = closeEvent;

    let heartbeatTimeout2, heartbeatTimeout;
    this.heartbeatTimeout2 = heartbeatTimeout2;
    this.heartbeatTimeout = heartbeatTimeout;
  }

  sendMessage(str) {
    console.log(`Send message:${str}`);
    this.socket.send(str);
  }

  connect() {
    console.log("Connect Server");
    this.socket = new WebSocket(this.url);
    // 连接建立时的处理
    this.socket.addEventListener("open", event => {
      // console.log("Connected to WebSocket server");
      this.openEvent(event);
      // 发送消息到服务器
    });

    // 接收到消息时的处理
    this.socket.addEventListener("message", event => {
      this.messageEvent(event);
    });

    // 连接关闭时的处理
    this.socket.addEventListener("close", event => {
      // console.log("WebSocket connection closed");
      // this.closeEvent(event);
      // console.log("close");
      // console.log("Try Reconnect to server");
      // let heartbeatTimeout2 = setTimeout(() => {
      //   this.connect();
      // }, 3000);
      // this.runHeartBeat(3000);
    });

    window.addEventListener("beforeunload", () => {
      this.socket.close();
    });
  }

  disconnect() {
    this.socket.close();
    console.log("Disconnect WebSocket");
  }

  runHeartBeat(heartbeatInterval = 3000) {
    const sendHeartbeat = () => {
      if (this.socket.readyState === WebSocket.OPEN) {
        this.socket.send("Client_Info:HEARTBEAT"); // 发送心跳包
        console.log("Heartbeat sent");
        clearTimeout(this.heartbeatTimeout2);
      }
      // 设置下一个心跳
      this.heartbeatTimeout = setTimeout(sendHeartbeat, heartbeatInterval);
    };

    sendHeartbeat(this.heartbeatInterval);
  }

  stopHeartBeat() {
    console.log("clearTimeout");
    clearTimeout(this.heartbeatTimeout);
  }
}

export function WebsocketHeartBeat(url) {}
