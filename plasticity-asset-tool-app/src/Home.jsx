import { createEffect, createSignal } from "solid-js";
import { WebsocketClient } from "./WebsocketClient";

export function Home() {
  //   <WebsocketClient />;
  const [filePath, setFilePath] = createSignal("");

  const socket = new WebSocket("ws://127.0.0.1:15150/websocket");
  socket.addEventListener("message", event => {
    console.log("Received message from server:", event.data);
    setFilePath(event.data);
  });
  const c = () => {
    socket.send("File:select_plasticity_file");
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
      <ul>
        <li>
          <span>{filePath()}</span>
        </li>
      </ul>
    </div>
  );
}
