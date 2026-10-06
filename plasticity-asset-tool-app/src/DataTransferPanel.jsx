import {createSignal,For,Show,onCleanup} from 'solid-js';
import {Portal} from 'solid-js/web';
import {t} from './i18n';
import './DataTransfer.css';

export function DataTransferPanel(props) {
  const [busy,setBusy]=createSignal(false),[plan,setPlan]=createSignal(null),[choices,setChoices]=createSignal([]);
  const [message,setMessage]=createSignal(''),[page,setPage]=createSignal(0);
  let input;
  const api=()=>props.api || '';
  const report=(value,error=false)=>{setMessage(value);if(!plan())props.onMessage?.(value,error);};
  const pending=()=>{props.onPendingChange?.(busy() || !!plan());};
  const working=value=>{setBusy(value);pending();};
  async function request(operation,body,json=false) {
    const response=await fetch(`${api()}/api/data/${operation}`,{method:'POST',body:json?JSON.stringify(body):body,headers:json?{'Content-Type':'application/json'}:undefined});
    const result=await response.json();
    if(!response.ok || !result.ok)throw new Error(result.error || t('操作失败'));
    return result.data;
  }
  async function choose(event) {
    const files=[...event.currentTarget.files];event.currentTarget.value='';
    if(!files.length)return;
    working(true);setMessage('');
    try {
      const body=new FormData();files.forEach(file=>body.append('file',file));
      body.append('kind',props.mode==='backup'?'restore':'import');
      body.append('library_id',props.libraryId || 'default');body.append('folder_id',props.folderId || '');
      const result=await request('preview',body);
      setPlan(result);setPage(0);
      setChoices(result.items.map(item=>({mode:item.duplicate || item.conflict==='identical'?'skip':'copy',target_id:item.matches[0]?.id})));
    }catch(error){report(error.message,true);}
    finally{working(false);}
  }
  async function cancel() {
    if(busy())return;
    const token=plan()?.token;setPlan(null);pending();
    if(token)try{await request('cancel',{token},true);}catch{/* Expires on the server. */}
  }
  onCleanup(()=>{const token=plan()?.token;if(token)request('cancel',{token},true).catch(()=>{});props.onPendingChange?.(false);});
  async function commit() {
    working(true);setMessage('');
    try {
      const result=await request('commit',{token:plan().token,choices:choices(),confirm_restore:plan().kind==='restore'},true);
      setPlan(null);
      report(result.rollback_backup?t('整库已恢复；恢复前备份：{path}',{path:result.rollback_backup}):t('已导入 {added}，覆盖 {overwritten}，跳过 {skipped}',{added:result.imported,overwritten:result.overwritten,skipped:result.skipped}));
      await props.onComplete?.(result);
    }catch(error){report(error.message,true);}
    finally{working(false);}
  }
  async function backup() {
    working(true);setMessage('');
    try {
      const response=await fetch(`${api()}/api/data/backup`);
      if(!response.ok){const result=await response.json();throw new Error(result.error || t('操作失败'));}
      const url=URL.createObjectURL(await response.blob());
      const link=document.createElement('a');link.href=url;link.download=`plasticityassettool-backup-${new Date().toISOString().slice(0,10)}.zip`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
      report(t('整库备份已下载'));
    }catch(error){report(error.message,true);}
    finally{working(false);}
  }
  const change=(index,values)=>setChoices(rows=>rows.map((row,i)=>i===index?{...row,...values}:row));
  const all=mode=>setChoices(rows=>rows.map((row,index)=>({mode:mode==='overwrite' && !plan().items[index].matches.length?'copy':mode,target_id:row.target_id})));
  return <>
    <div class="data-transfer-actions">
      <Show when={props.mode==='backup'}><button class="secondary-button" disabled={busy() || !!plan() || props.disabled} onClick={backup}>{t('下载整库备份')}</button></Show>
      <button class={props.mode==='backup'?'secondary-button':'secondary'} disabled={busy() || !!plan() || props.disabled} onClick={()=>input.click()}>{busy()?t('正在处理…'):props.mode==='backup'?t('选择整库备份恢复'):t('↓ 导入组件包')}</button>
      <input ref={input} class="hidden-input" type="file" accept={props.mode==='backup'?'.zip':'.patasset,.zip'} multiple={props.mode!=='backup'} onChange={choose}/>
    </div>
    <Show when={message() && !plan() && !props.onMessage}><p class="data-transfer-message" role="status">{message()}</p></Show>
    <Show when={plan()}><Portal><div class="data-transfer-backdrop"><section class="data-transfer-dialog" role="dialog" aria-modal="true" aria-label={t('导入预览')}>
      <h2>{plan().kind==='restore'?t('整库恢复预览'):t('批量导入预览')}</h2>
      <p>{t('共 {count} 个组件',{count:plan().count})}<Show when={plan().kind==='restore'}> · {t('{count} 个资产库，{folders} 个分组',{count:plan().libraries.length,folders:plan().folders})}</Show></p>
      <Show when={plan().kind==='restore'} fallback={<div class="data-transfer-actions"><button onClick={()=>all('skip')}>{t('全部跳过')}</button><button onClick={()=>all('copy')}>{t('全部保留两份')}</button><button onClick={()=>all('overwrite')}>{t('覆盖冲突项')}</button></div>}><p class="data-transfer-warning">{t('恢复将替换当前所有资产库、分组及归档组件。执行前自动保存当前整库备份；模型窗口不受影响。')}</p><p>{plan().libraries.map(row=>row.name).join(' · ')}</p></Show>
      <div class="data-transfer-list"><For each={plan().items.slice(page()*100,page()*100+100)}>{item=><div class="data-transfer-row"><div><strong>{item.name}</strong><small>{item.file} · {Math.ceil(item.bytes/1024)} KB · {item.category}<Show when={plan().kind==='import' && (item.matches.length || item.duplicate)}> · {item.conflict==='identical'?t('相同模型'):item.matches.length?t('名称冲突'):t('包内重复模型')}</Show></small></div><Show when={plan().kind==='import'}><select aria-label={t('导入方式：{name}',{name:item.name})} value={choices()[item.index]?.mode} onChange={event=>change(item.index,{mode:event.currentTarget.value})}><option value="skip">{t('跳过')}</option><option value="copy">{item.matches.length?t('保留两份（自动改名）'):t('导入')}</option><option value="overwrite" disabled={!item.matches.length}>{t('覆盖')}</option></select><Show when={choices()[item.index]?.mode==='overwrite'}><select aria-label={t('覆盖目标：{name}',{name:item.name})} value={choices()[item.index]?.target_id} onChange={event=>change(item.index,{target_id:event.currentTarget.value})}><For each={item.matches}>{match=><option value={match.id}>{match.name} · {match.id.slice(0,8)}</option>}</For></select></Show></Show></div>}</For></div>
      <Show when={plan().count>100}><div class="data-transfer-actions"><button disabled={!page()} onClick={()=>setPage(page()-1)}>{t('上一页')}</button><span>{page()+1} / {Math.ceil(plan().count/100)}</span><button disabled={(page()+1)*100>=plan().count} onClick={()=>setPage(page()+1)}>{t('下一页')}</button></div></Show>
      <Show when={message()}><p role="alert">{message()}</p></Show>
      <footer><span>{t('预览有效期为 10 分钟；库变化后需重新预览。')}</span><button disabled={busy()} onClick={cancel}>{t('取消')}</button><button disabled={busy()} class="primary" onClick={commit}>{busy()?t('正在处理…'):plan().kind==='restore'?t('确认替换并恢复'):t('确认导入')}</button></footer>
    </section></div></Portal></Show>
  </>;
}
