export class WebsocketClient {
  constructor(url, onStatus, onEvent) {
    this.url = url;
    this.onStatus = onStatus;
    this.onEvent = onEvent;
    this.pending = new Map();
    this.stopped = false;
    this.sequence = 0;
  }

  connect() {
    if (this.stopped || this.socket?.readyState === WebSocket.OPEN || this.socket?.readyState === WebSocket.CONNECTING) return;
    this.onStatus("connecting");
    const socket = this.socket = new WebSocket(this.url);
    socket.addEventListener("open", () => {
      if (this.socket === socket && !this.stopped) this.onStatus("connected");
    });
    socket.addEventListener("message", event => {
      if (this.socket !== socket || this.stopped) return;
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      if (message.type === "response") {
        const pending = this.pending.get(message.id);
        if (!pending) return;
        clearTimeout(pending.timer);
        this.pending.delete(message.id);
        message.ok ? pending.resolve(message.data) : pending.reject(new Error(message.error || "操作失败"));
      } else {
        this.onEvent(message);
      }
    });
    socket.addEventListener("error", () => socket.close());
    socket.addEventListener("close", () => {
      if (this.socket !== socket) return;
      this.onStatus("disconnected");
      for (const pending of this.pending.values()) {
        clearTimeout(pending.timer);
        pending.reject(new Error("连接已断开；操作结果未知，请检查视口后再试"));
      }
      this.pending.clear();
      if (!this.stopped) this.reconnectTimer = setTimeout(() => this.connect(), 2000);
    });
  }

  request(action, args = {}) {
    if (this.socket?.readyState !== WebSocket.OPEN) return Promise.reject(new Error("组件库服务未连接"));
    const id = `${Date.now()}-${++this.sequence}`;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error("操作响应超时；请先检查视口，避免重复置入"));
      }, args.base_mode === "pick" || action === "library.rebase" ? 160000 : 45000);
      this.pending.set(id, { resolve, reject, timer });
      try { this.socket.send(JSON.stringify({ id, action, args })); }
      catch (error) { clearTimeout(timer); this.pending.delete(id); reject(error); }
    });
  }

  disconnect() {
    this.stopped = true;
    clearTimeout(this.reconnectTimer);
    const socket = this.socket;
    this.socket = null;
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(new Error("连接已断开；操作结果未知，请检查视口后再试"));
    }
    this.pending.clear();
    socket?.close();
    this.onStatus("disconnected");
  }
}
