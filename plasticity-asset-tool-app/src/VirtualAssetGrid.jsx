import {createEffect, createMemo, createSignal, For, onCleanup, onMount} from 'solid-js';
import {gridWindow} from './virtualGrid.mjs';

export function VirtualAssetGrid(props) {
  let grid, scroller, observer, frame;
  const [bounds, setBounds] = createSignal({width:800, top:0, viewport:600});
  const layout = createMemo(() => gridWindow({...bounds(), count:props.items.length, size:props.size}));
  function measure() {
    frame = null;
    if (!grid?.offsetWidth) return;
    const rect = grid.getBoundingClientRect();
    const view = scroller === window ? {top:0, height:window.innerHeight} : scroller.getBoundingClientRect();
    setBounds({width:rect.width, top:view.top - rect.top, viewport:view.height});
  }
  function schedule() { if (frame == null) frame = requestAnimationFrame(measure); }
  onMount(() => {
    scroller = grid.parentElement;
    while (scroller && !/(auto|scroll)/.test(getComputedStyle(scroller).overflowY)) scroller = scroller.parentElement;
    scroller ||= window;
    scroller.addEventListener('scroll', schedule, {passive:true});
    window.addEventListener('resize', schedule);
    window.addEventListener('pat:layout', schedule);
    observer = new ResizeObserver(schedule); observer.observe(grid);
    measure();
  });
  createEffect(() => {props.items; props.size; schedule();});
  onCleanup(() => {
    cancelAnimationFrame(frame); observer?.disconnect();
    scroller?.removeEventListener('scroll', schedule);
    window.removeEventListener('resize', schedule);
    window.removeEventListener('pat:layout', schedule);
  });
  return <div ref={grid} class="virtual-asset-grid" style={{height:`${layout().height}px`,
    '--preview-height':`${layout().previewHeight}px`}}>
    <For each={props.items.slice(layout().start, layout().end)}>{(asset, index) =>
      <div class="virtual-asset-slot" style={{width:`${layout().cardWidth}px`,height:`${layout().rowHeight}px`,
        transform:`translate(${((layout().start + index()) % layout().columns) * (layout().cardWidth + 5)}px, ${Math.floor((layout().start + index()) / layout().columns) * layout().pitch}px)`}}>
        {props.children(asset)}
      </div>}
    </For>
  </div>;
}
