import { createEffect, createSignal } from "solid-js";
import { WebsocketClient } from "./WebsocketClient";

export function Home() {
  //   <WebsocketClient />;
  const websocket_server_url = "ws://127.0.0.1:15150/websocket";

  const [filePath, setFilePath] = createSignal("");
  const [plasticityInfo, setPlasticityInfo] = createSignal("");

  // const socket = new WebSocket(websocket_server_url);
  const mmm = event => {
    console.log("Received message from server:", event.data);
    setFilePath(JSON.parse(event.data));
  };

  const socket = new WebsocketClient(
    websocket_server_url,
    () => {},
    mmm,
    () => {}
  );
  // socket.addEventListener("message", event => {
  //   console.log("Received message from server:", event.data);
  //   setFilePath(JSON.parse(event.data));
  // });

  const file_select_plasticity_file = () => {
    socket.sendMessage("File:select_plasticity_file");
  };

  return (
    <div>
      <span>Home</span>
      <button>Reflash</button>
      <button>Auto injure File</button>
      <button
        onClick={file_select_plasticity_file}
        style={{
          color: "red",
        }}
      >
        Open As Asset
      </button>
      <div>
        <span>websocket stauts</span>
        <span style={{ color: "blue" }}>{websocket_server_url}</span>
      </div>
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
