// Bounded LRU: at most 2 million numeric values retained across previews.
export function geometryCache(limit = 2000000, maxEntries = 16) {
  const rows = new Map();
  let count = 0;
  return {
    get(key) {
      const row=rows.get(key);
      if (!row) return;
      rows.delete(key);rows.set(key,row);
      return row.mesh;
    },
    set(key, mesh) {
      const size=mesh.parts.reduce((sum,part)=>sum + Object.values(part).reduce((n,value)=>n+(Array.isArray(value)?value.length:0),0),0);
      const old=rows.get(key);
      if (old) {count-=old.size;rows.delete(key);}
      if (size>limit) return;
      rows.set(key,{mesh,size});count+=size;
      while (count>limit || rows.size>maxEntries) {
        const first=rows.keys().next().value;
        count-=rows.get(first).size;rows.delete(first);
      }
    }
  };
}
