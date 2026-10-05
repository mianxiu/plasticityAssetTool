import { lazy, createEffect } from "solid-js";
import {locale} from './i18n';
const Home = lazy(() => import("./Home").then(module => ({default:module.Home})));
const ControlCenter = lazy(() => import("./ControlCenter").then(module => ({default:module.ControlCenter})));
export function App() {
  createEffect(() => {document.documentElement.lang = locale(); document.title = new URLSearchParams(location.search).has("control") ? "Plasticity Asset Tool — Control Center" : "Plasticity Asset Tool — Component Library";});
  return <div>{new URLSearchParams(location.search).has("control") ? <ControlCenter/> : <Home/>}</div>;
}
