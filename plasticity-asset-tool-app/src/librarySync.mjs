export function mergeLibrary(previous, state) {
  if (state.full === false && !state.changed?.length && !state.removed?.length) return previous;
  const old = new Map(previous.map(row => [row.id, row]));
  const stable = row => {
    const existing = old.get(row.id);
    return existing && JSON.stringify(existing) === JSON.stringify(row) ? existing : row;
  };
  if (state.full !== false) return state.assets.map(stable);
  const removed = new Set(state.removed || []);
  for (const id of removed) old.delete(id);
  for (const row of state.changed || []) old.set(row.id, stable(row));
  return [...old.values()];
}
