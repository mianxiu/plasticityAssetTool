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
  const file_select_plasticity_file = () => {
    socket.send("File:select_plasticity_file");
  };
  return (
    <div>
      <span>Home</span>
      <button>Reflash</button>
      <button>Auto injure File</button>
      <button
        onClick={file_select_plasticity_file}
        style={{
          color: "blue",
        }}
      >
        Open As Asset
      </button>
      <ul>
        <li>
          <div>
            <span>test1.plasticity</span>
            <span>c:/test/test1.plascitity</span>
            <button>injure</button>
            <button>reload</button>
            <button>auto injure</button>
          </div>
        </li>
        <li>
          <span>{filePath()}</span>
        </li>
      </ul>
    </div>
  );
}
