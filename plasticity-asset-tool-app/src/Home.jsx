import { createEffect, createSignal } from "solid-js";
import { WebsocketClient } from "./WebsocketClient";

export function Home() {
  //   <WebsocketClient />;
  const socket = new WebSocket("ws://127.0.0.1:15150/websocket");
  const c = () => {
    socket.send("Menu:select_plasticity_file");
  };
  return (
    <div>
      <span>Home</span>
      <button>refleshdd</button>
      <button
        onClick={c}
        style={{
          color: "blue",
        }}
      >
        openfile
      </button>
    </div>
  );
}
