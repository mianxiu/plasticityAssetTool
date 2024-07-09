import logo from "./logo.svg";
import styles from "./App.module.css";
import { createEffect, createSignal } from "solid-js";

function App() {
  // return (
  //   <div class={styles.App}>
  //     <header class={styles.header}>
  //       <img src={logo} class={styles.logo} alt="logo" />
  //       <p>
  //         Edit <code>src/App.jsx</code> and save to reload.
  //       </p>
  //       <a class={styles.link} href="https://github.com/solidjs/solid" target="_blank" rel="noopener noreferrer">
  //         Plasticity Asset Tool
  //       </a>
  //     </header>
  //   </div>
  // );

  // 创建 WebSocket 连接
  const socket = new WebSocket("ws://127.0.0.1:15151");

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
  const [count, setCount] = createSignal(2);
  const increment = () => {
    setCount(prev => prev + 1);
    socket.send("Hello, server! from plasiticy" + `is solidjs ${count()}`);
  };

  const decrement = () => setCount(prev => prev - 1);

  createEffect(() => {
    document.querySelector("#c").textContent = count();
  });

  return (
    <div>
      <span>Count:{count()}</span>{" "}
      <button type="button" onClick={increment}>
        add one
      </button>
      <button type="button" onClick={decrement}>
        subtrace one
      </button>
      <span id="c"></span>
    </div>
  );
}

export default App;
