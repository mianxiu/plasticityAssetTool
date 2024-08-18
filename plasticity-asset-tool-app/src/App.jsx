import logo from "./logo.svg";
import styles from "./App.module.css";
import { createEffect, createSignal, mergeProps, Show } from "solid-js";
import { Dynamic } from "solid-js/web";

const RedDiv = () => (
  <div
    style={{
      color: "red",
    }}
  ></div>
);

export function MyComponent(props) {
  const [breed, setBreed] = createSignal("cat");
  const animal = { breed: "cat", name: "Midnight" };

  const [theme, setTheme] = createSignal("light");
  const handler = (data, event) => {
    setBreed(data);
  };

  const finalProps = mergeProps({ name: "default name" }, props);
  return (
    <div classList={{ border: theme() === "light", light: theme() === "light", dark: theme() === "dark" }}>
      <p>
        i have a {breed()} named {animal.name} !, props is {finalProps.name}
      </p>
      <button
        onclick={() => {
          setBreed("dog");
        }}
      >
        dog
      </button>
      <button
        onclick={() => {
          setBreed("chicken");
        }}
      >
        chicken
      </button>
      <button
        onclick={() => {
          theme() === "light" ? setTheme("dark") : setTheme("light");
        }}
      >
        {theme()}
      </button>

      <button onclick={[handler, "fromButtonData"]}>handler</button>
    </div>
  );
}

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

  const increment = () => {
    setCount(prev => prev + 1);
    socket.send("Hello, server! from plasiticy" + `is solidjs ${count()}`);
  };

  const decrement = () => setCount(prev => prev - 1);

  createEffect(() => {
    document.querySelector("#c").textContent = count();
    setDouble(count() * 2);
  });

  return (
    <div>
      <Show when={data.loading}>
        <div>loading</div>
      </Show>
      <span>File Manager</span>
      <div class={styles.tab}>
        <ul class={styles.tab_ul}>
          <li class={styles.tab_li}>
            <span>test file 1</span>
            <button>x</button>
          </li>
          <li class={styles.tab_li}>
            {" "}
            <span>test file 2</span>
            <button>x</button>
          </li>
        </ul>
        <button>+</button>
      </div>
      <MyComponent name="props name" />
      <div class={styles.panel}>
        <div class={styles.panel_obj}>
          <img></img>
        </div>
        <div class={styles.panel_obj}>
          <img></img>
        </div>
        <div class={styles.panel_obj}>
          <img></img>
        </div>
        <div class={styles.panel_obj}>
          <img></img>
        </div>
      </div>
    </div>
  );
}
