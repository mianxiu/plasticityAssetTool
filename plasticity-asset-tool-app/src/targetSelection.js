// An embedded panel belongs to one HWND even when desktop enumeration is late.
export function chooseTarget({embedded, preferredTarget, current, followActive, state}) {
  if (embedded && preferredTarget) return preferredTarget;
  const ids=new Set(state.targets.map(target=>target.id));
  if (followActive && ids.has(state.active_target_id)) return state.active_target_id;
  if (ids.has(current)) return current;
  return ids.size===1 ? state.targets[0].id : '';
}
