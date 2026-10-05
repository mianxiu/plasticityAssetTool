export function meshBounds(mesh) {
  const min=[Infinity,Infinity,Infinity], max=[-Infinity,-Infinity,-Infinity];
  for(const part of mesh.parts) for(const values of [part.positions,part.edges])
    for(let i=0;i<values.length;i++){const axis=i%3;min[axis]=Math.min(min[axis],values[i]);max[axis]=Math.max(max[axis],values[i]);}
  return min.every(Number.isFinite) ? {min,max} : null;
}

export function presetBasePoint(bounds, mode) {
  if(mode==='world')return [0,0,0];
  if(!bounds)return null;
  const center=bounds.min.map((v,i)=>(v+bounds.max[i])/2);
  if(mode==='bottom')center[2]=bounds.min[2]; // Plasticity Z up.
  return center;
}
