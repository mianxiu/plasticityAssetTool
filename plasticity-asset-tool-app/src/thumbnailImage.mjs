export function thumbnailSize(width,height) {
  if(!Number.isFinite(width) || !Number.isFinite(height) || width<=0 || height<=0)throw new Error('图片尺寸无效');
  const scale=Math.min(1,512/width,512/height);
  return {width:Math.max(1,Math.round(width*scale)),height:Math.max(1,Math.round(height*scale))};
}

export async function thumbnailImage(file) {
  const image=await createImageBitmap(file);
  try {
    const size=thumbnailSize(image.width,image.height);
    // Keep small JPEGs byte-for-byte, avoiding another lossy encoding.
    if(size.width===image.width && size.height===image.height && file.type==='image/jpeg' && file.size<=5*1024*1024) {
      return await new Promise((resolve,reject)=>{
        const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('无法读取图片'));reader.readAsDataURL(file);
      });
    }
    const canvas=document.createElement('canvas');canvas.width=size.width;canvas.height=size.height;
    const context=canvas.getContext('2d');
    context.fillStyle='#fff';context.fillRect(0,0,size.width,size.height);
    context.drawImage(image,0,0,size.width,size.height);
    return canvas.toDataURL('image/jpeg',.86);
  } finally {image.close();}
}
