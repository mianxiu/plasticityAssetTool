import logo from "./logo.svg";
import styles from "./App.module.css";
import { createEffect, createSignal, mergeProps, Show } from "solid-js";
import { Dynamic } from "solid-js/web";
import { Home } from "./Home";
import { ControlCenter } from "./ControlCenter";

export function MyComponent(props) {}

export function App() {
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

  //
  const [count, setCount] = createSignal(2);

  return (
    <div>
      {new URLSearchParams(location.search).has("control") ? <ControlCenter/> : <Home/>}
    </div>
  );
}
