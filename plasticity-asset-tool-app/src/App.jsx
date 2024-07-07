import logo from "./logo.svg";
import styles from "./App.module.css";
import { createSignal } from "solid-js";

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
  const [count, setCount] = createSignal(4);
  const increment = () => setCount(prev => prev + 1);

  const decrement = () => setCount(prev => prev - 1);

  return (
    <div>
      <span>Count:{count()}</span>{" "}
      <button type="button" onClick={increment}>
        add one
      </button>
      <button type="button" onClick={decrement}>
        subtrace one
      </button>
    </div>
  );
}

export default App;
