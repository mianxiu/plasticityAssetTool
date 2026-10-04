import { lazy } from "solid-js";
const Home = lazy(() => import("./Home").then(module => ({default:module.Home})));
const ControlCenter = lazy(() => import("./ControlCenter").then(module => ({default:module.ControlCenter})));
export function App() {
  return <div>{new URLSearchParams(location.search).has("control") ? <ControlCenter/> : <Home/>}</div>;
}
