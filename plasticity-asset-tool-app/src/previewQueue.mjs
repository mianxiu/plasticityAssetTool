// One preview at a time; model commands take priority between jobs.
export function previewQueue({run, available, changed = () => {}, failed = () => {}, delay = 100}) {
  const pending = new Map();
  let active = null, timer = null, stopped = false;
  const report = () => changed(pending.size + (active ? 1 : 0));
  async function pump() {
    timer = null;
    if (stopped || active || !pending.size) return;
    if (!available()) { timer = setTimeout(pump, delay); return; }
    const [key, item] = pending.entries().next().value;
    pending.delete(key); active = key; report();
    try { await run(item); } catch (error) { if (!stopped) failed(error, item); }
    finally { active = null; if (!stopped) { report(); timer = setTimeout(pump, delay); } }
  }
  return {
    add(item) {
      if (stopped || active === item.digest || pending.has(item.digest)) return;
      if (pending.size >= 64) throw new Error('预览队列已满，请稍后重试');
      pending.set(item.digest, item); report();
      if (!active && timer === null) timer = setTimeout(pump, delay);
    },
    stop() { stopped = true; clearTimeout(timer); pending.clear(); }
  };
}
