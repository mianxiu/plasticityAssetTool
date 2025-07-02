import { createEffect, createSignal } from "solid-js";
import { WebsocketClient, PlasticityInfoJson } from "./WebsocketClient";

export function Home() {
  //   <WebsocketClient />;
  const websocket_server_url = "ws://127.0.0.1:15150/websocket";

  const [filePath, setFilePath] = createSignal("");
  const [plasticityInfo, setPlasticityInfo] = createSignal("");

  /**
   *
   * @param {MessageEvent} event
   */
  const mmm = event => {
    let eventArray = JSON.parse(event.data);
    let ws_url = eventArray[0].ws_url;
    console.log(ws_url);
    setFilePath(ws_url);
  };

  const socketClient = new WebsocketClient(
    websocket_server_url,
    () => {},
    mmm,
    () => {}
  );

  const ccc = () => {
    socketClient.connect();
    socketClient.runHeartBeat(6000);
  };
  const ddd = () => {
    socketClient.stopHeartBeat();
    socketClient.disconnect();
  };

  const file_select_plasticity_file = () => {
    socketClient.sendMessage("File:select_plasticity_file");
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
      <button onclick={ccc}>run heartbeat</button>
      <button onclick={ddd}>stop HeartBeat</button>
      <div>
        <span>websocket stauts</span>
        <span style={{ color: "blue" }}>{websocket_server_url}</span>
      </div>
      <ul>
        <li>
          <div>
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
