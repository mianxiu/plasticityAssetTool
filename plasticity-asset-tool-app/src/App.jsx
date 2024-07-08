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
  // 监听按键事件
  document.addEventListener("keydown", function (event) {
    // 按下 "z" 键（键码为 90）
    if (event.code == "Backquote") {
      // 阻止 "z" 键的默认行为，即不显示任何内容

      console.log("init key event done");
      // 向父页面发送消息，通知隐藏内容
      window.parent.postMessage("hideContent", "*");
    }
  });
  const [count, setCount] = createSignal(2);
  const increment = () => setCount(prev => prev + 1);

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
