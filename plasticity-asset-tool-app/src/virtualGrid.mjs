export function gridWindow({count, width, size, top, viewport, gap = 5, overscan = 2}) {
  width = Math.max(1, width);
  const columns = Math.max(1, Math.floor((width + gap) / (Math.min(width, size) + gap)));
  const cardWidth = (width - (columns - 1) * gap) / columns;
  const previewHeight = (cardWidth - 2) / 1.15;
  const rowHeight = Math.ceil(previewHeight + 70);
  const pitch = rowHeight + gap;
  const rows = Math.ceil(count / columns);
  const first = Math.max(0, Math.floor(Math.max(0, top) / pitch) - overscan);
  const last = Math.min(rows, Math.max(first + 1, Math.ceil(Math.max(0, top + viewport) / pitch) + overscan));
  return {columns, cardWidth, previewHeight, rowHeight, pitch,
    start: Math.min(count, first * columns), end: Math.min(count, last * columns),
    height: Math.max(0, rows * pitch - gap)};
}
