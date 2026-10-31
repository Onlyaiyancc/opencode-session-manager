'use strict';
const $ = (selector) => document.querySelector(selector);
const state = {token:'', summary:null, view:'all', directory:'', offset:0, page:[], total:0,
  selected:new Set(), current:null, messageOffset:0, plan:null, requestId:0, previewId:0};
let searchTimer, toastTimer;

function localize(message) {
  // 只翻译系统提示，不改动会话原文与用户标题。
  const messages={
    'Large content is kept in OpenCode and is not loaded into this preview.':'内容较大，仍保留在 OpenCode 中，本次预览不加载。',
    'Additional parts omitted from this message preview.':'这条消息还有其他内容，预览中已省略。',
    'Attachment':'附件',
    'Failed to fetch':'无法连接本地服务，请确认管理器仍在运行。',
    'NetworkError when attempting to fetch resource.':'无法连接本地服务，请确认管理器仍在运行。',
    'Session no longer exists. Refresh the list.':'这个会话已不存在，请刷新列表。',
    'Close OpenCode Desktop before editing sessions. You can continue browsing here.':'修改会话前，请先关闭 OpenCode 桌面端。当前仍可浏览和预览。',
    'Could not check OpenCode Desktop. Close it before editing and retry.':'无法确认 OpenCode 桌面端状态，请关闭桌面端后重试。',
    'OpenCode Desktop was not found. Set OPENCODE_DESKTOP_DIR to its installation folder.':'未找到 OpenCode 桌面端。请将 OPENCODE_DESKTOP_DIR 设置为安装目录。',
    'OpenCode management service could not start. See the local runtime log.':'OpenCode 管理服务启动失败，请检查本机运行日志。',
    'OpenCode management service took too long to start. Retry after closing OpenCode Desktop.':'管理服务启动超时，请关闭 OpenCode 桌面端后重试。',
    'OpenCode returned an unexpectedly large response':'OpenCode 返回的内容过大，请刷新后重试。',
    'Deletion preview expired. Review it again.':'删除预览已过期，请重新核对删除范围。',
    'Confirmation does not match':'确认文字不匹配，请按提示输入。',
    'Sessions changed since the preview. Review the selection again.':'会话在预览后发生了变化，请重新核对删除范围。',
    'Some sessions no longer exist. Refresh the list.':'部分会话已不存在，请刷新列表。',
    'OpenCode did not complete deletion. Refresh the list before retrying.':'OpenCode 尚未完成删除，请刷新列表后再试。',
    'Title must contain 1 to 250 characters':'名称不能为空，且最多为 250 个字符。',
    'OpenCode did not save the title':'OpenCode 未能保存名称，请刷新后重试。',
    'OpenCode did not save the archive state':'OpenCode 未能保存归档状态，请刷新后重试。',
    'Invalid request token. Reload this page.':'当前页面的请求凭证已失效，请刷新页面。',
    'Could not read the OpenCode database. Check its path and retry after closing OpenCode.':'无法读取 OpenCode 数据库，请检查路径，或关闭 OpenCode 后重试。',
    'This OpenCode database schema is not supported. Expected the v1 session schema.':'当前数据库结构暂不受支持，管理器需要 OpenCode v1 会话结构。',
    'Select between 1 and 200 sessions':'请选中 1 到 200 个会话。',
    'An unexpected error occurred. Refresh and retry.':'出现意外错误，请刷新后重试。',
    'timed out':'操作超时，请刷新后确认会话状态。',
    'Invalid session ID':'会话标识无效，请刷新列表。',
    'Invalid archive state':'归档状态无效，请刷新后重试。',
    'No update was requested':'没有需要保存的修改。',
    'Invalid cyclic session hierarchy':'会话层级存在循环关系，暂时无法执行删除。',
    'Number is outside the supported range':'输入的数值超出了支持范围。',
    'Invalid number':'请输入有效数值。',
    'Page size must be at least 1':'每页至少需要显示一项。',
    'Invalid archive filter':'归档筛选条件无效。',
    'Cross-origin requests are not allowed':'当前页面来源不受支持，请使用本机地址打开。',
    'Invalid host':'当前访问地址不受支持，请使用本机地址打开。',
    'Request size is invalid':'请求内容大小无效，请刷新后重试。',
    'Expected JSON content':'请求格式无效，请刷新后重试。',
    'Expected an object':'请求格式无效，请刷新后重试。',
    'Invalid internal route':'内部操作地址无效。',
  };
  if(messages[message]) return messages[message];
  const http=String(message).match(/^OpenCode rejected the operation \(HTTP (\d+)\)/);
  if(http) return `OpenCode 未能执行操作（HTTP ${http[1]}），请刷新后重试。`;
  const changed=String(message).match(/^Selection changed\. (\d+) sessions were already deleted/);
  if(changed) return `删除范围发生变化，已删除 ${changed[1]} 个会话。请刷新后重新核对。`;
  if(String(message).includes('[WinError')) return '无法访问本机服务或文件，请检查管理器及 OpenCode 的运行状态。';
  return message;
}

function icon(name) {
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  const use=document.createElementNS('http://www.w3.org/2000/svg','use');
  use.setAttribute('href','#i-'+name); svg.append(use); svg.setAttribute('aria-hidden','true'); return svg;
}
function el(tag, className, text) {
  const node=document.createElement(tag); if(className) node.className=className;
  if(text!==undefined) node.textContent=text; return node;
}
function bytes(value) {
  if(!value) return '0 B';
  const units=['B','KB','MB','GB','TB']; let i=Math.min(Math.floor(Math.log(value)/Math.log(1000)),4);
  return (value/1000**i).toFixed(i>0?1:0)+' '+units[i];
}
function date(value, full=false) {
  if(!value) return '—';
  return new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',day:'2-digit',month:'numeric',
    ...(full?{year:'numeric',hour:'2-digit',minute:'2-digit'}:{})}).format(value);
}
function relative(value) {
  const days=Math.max(0,Math.floor((Date.now()-value)/86400000));
  if(days===0) return '今天'; if(days===1) return '昨天';
  if(days<7) return days+' 天前'; return date(value);
}
function basename(path) { return path.replaceAll('\\','/').replace(/\/$/,'').split('/').pop()||path; }
function toast(message) {
  $('#toast').textContent=message; $('#toast').hidden=false; clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>$('#toast').hidden=true,5000);
}
function error(message) { $('#error-banner').textContent=message; $('#error-banner').hidden=!message; }
async function api(path, body) {
  const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Manager-Token':state.token},body:JSON.stringify(body)});
  const value=await response.json();
  if(!response.ok) throw new Error(localize(value.error||'请求未完成，请刷新后重试。'));
  return value;
}
function status(text) { $('#sync-status').textContent=text; }
function busy(button, value, text) {
  button.disabled=value; if(text) { if(value) { button.dataset.previousText=button.textContent; button.textContent=text; }
    else button.textContent=button.dataset.previousText; }
}
function emptyList(heading, description) {
  const box=el('div','list-status'); box.append(icon('search'),el('h3','',heading),el('p','',description));
  $('#session-list').replaceChildren(box);
}

async function bootstrap() {
  const result=await api('/api/bootstrap'); state.token=result.token; state.summary=result.summary;
  const {summary:s}=result;
  $('#all-count').textContent=s.total; $('#active-count').textContent=s.total-s.archived;
  $('#archive-count').textContent=s.archived; $('#database-size').textContent=bytes(s.database_bytes);
  $('#project-count').textContent=s.directories.length;
  $('#heading-count').textContent=s.total+' 个会话已保存在本地';
  const projects=s.directories.map(project=>{
    const button=el('button','nav-item project-item');
    if(state.directory===project.directory) button.classList.add('active');
    const label=el('span','',basename(project.directory));
    label.append(el('small','',project.count+' 个会话'));
    button.title=project.directory; button.append(icon('folder'),label);
    button.addEventListener('click',()=>{state.directory=state.directory===project.directory?'':project.directory; resetFilters(); bootstrap().catch(e=>error(localize(e.message)));});
    return button;
  });
  $('#project-list').replaceChildren(...projects);
}
function buildQuery() {
  const params=new URLSearchParams({q:$('#search').value,archive:state.view,directory:state.directory,
    offset:state.offset,limit:30,children:$('#include-children').checked?'1':'0'});
  const before=$('#before-date').value;
  if(before) params.set('before_ms',String(new Date(before+'T00:00:00+08:00').getTime()));
  return params;
}
async function loadSessions() {
  const id=++state.requestId; status('正在加载会话…'); error('');
  $('#session-list').setAttribute('aria-busy','true');
  try {
    const result=await api('/api/sessions?'+buildQuery()); if(id!==state.requestId) return;
    state.page=result.items; state.total=result.total; renderSessions();
    $('#page-label').textContent=result.total?`第 ${result.offset+1}–${Math.min(result.offset+result.limit,result.total)} 项，共 ${result.total} 个会话`:'暂无会话';
    $('#previous-page').disabled=result.offset===0;
    $('#next-page').disabled=result.offset+result.limit>=result.total;
    const hasFilters=$('#search').value||$('#before-date').value||state.directory||!$('#include-children').checked;
    $('#clear-filters').hidden=!hasFilters;
    $('#filter-summary').textContent=state.directory?basename(state.directory):result.total+' 个会话';
    status('更新于 '+new Intl.DateTimeFormat('zh-CN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Shanghai'}).format(Date.now()));
  } catch(e) { if(id===state.requestId) { error(localize(e.message)); emptyList('无法加载会话','请确认 OpenCode 数据库可用，然后点击刷新。'); status('本地连接需要检查'); } }
  finally { if(id===state.requestId) $('#session-list').setAttribute('aria-busy','false'); }
}
function renderSessions() {
  const rows=state.page.map(session=>{
    const row=el('article','session-row'+(state.current?.id===session.id?' selected':''));
    const checkLabel=el('label','row-check'); const check=el('input'); check.type='checkbox';
    check.checked=state.selected.has(session.id); check.setAttribute('aria-label','选择 '+session.title);
    check.addEventListener('change',()=>{check.checked?state.selected.add(session.id):state.selected.delete(session.id); renderSelection();});
    checkLabel.append(check);
    const button=el('button','row-open'); button.setAttribute('aria-label','预览 '+session.title);
    const rowIcon=el('span','row-icon'); rowIcon.append(icon(session.parent_id?'branch':'chat'));
    const main=el('span','row-main'); const title=el('span','row-title',session.title||'未命名会话'); title.title=session.title;
    const subtitle=el('span','row-subtitle'); subtitle.append(el('span','',basename(session.directory)),el('span','','· '+session.message_count+' 条消息'));
    if(session.parent_id) subtitle.append(el('span','nested-label','子会话'));
    main.append(title,subtitle);
    const time=el('span','row-time',relative(session.time_updated)); time.title=date(session.time_updated,true)+'（北京时间）';
    if(session.time_archived>0) time.append(el('span','archived-label','已归档'));
    const arrow=icon('arrow'); arrow.classList.add('row-arrow');
    button.append(rowIcon,main,time,arrow); button.addEventListener('click',()=>openSession(session.id));
    row.append(checkLabel,button); return row;
  });
  if(rows.length) $('#session-list').replaceChildren(...rows);
  else emptyList('没有找到会话','试试其他关键词、清除筛选，或切换会话视图。');
  renderSelection();
}
function renderSelection() {
  $('#bulk-bar').hidden=state.selected.size===0; $('#selected-count').textContent=state.selected.size;
  const checked=state.page.filter(s=>state.selected.has(s.id)).length;
  $('#select-all').checked=state.page.length>0&&checked===state.page.length;
  $('#select-all').indeterminate=checked>0&&checked<state.page.length;
  $('#select-all').disabled=!state.page.length;
}
function resetFilters() { state.offset=0; state.selected.clear(); loadSessions(); }
function closeDetail() {
  ++state.previewId; state.current=null; $('#detail-content').hidden=true; $('#detail-empty').hidden=false;
  $('#detail-panel').classList.remove('open'); renderSessions();
}
async function openSession(id, offset=0) {
  const requestId=++state.previewId; state.messageOffset=offset;
  state.current=null;
  for(const button of document.querySelectorAll('.detail-actions button')) button.disabled=true;
  $('#export').removeAttribute('href');
  $('#detail-title').textContent='正在加载会话…'; $('#detail-directory').textContent='';
  $('#created-time').textContent='—'; $('#updated-time').textContent='—'; $('#session-id').textContent='—';
  $('#detail-panel').classList.add('open'); $('#detail-empty').hidden=true; $('#detail-content').hidden=false;
  const loading=el('div','list-status','正在加载对话内容…'); loading.prepend(el('span','spinner'));
  $('#preview-messages').replaceChildren(loading);
  try {
    const result=await api(`/api/session/${encodeURIComponent(id)}/preview?offset=${offset}`);
    if(requestId!==state.previewId) return;
    state.current=result.session; const s=result.session; const archived=s.time_archived>0;
    for(const button of document.querySelectorAll('.detail-actions button')) button.disabled=false;
    $('#detail-title').textContent=s.title; $('#detail-directory').textContent=s.directory;
    $('#detail-status').textContent=archived?'已归档':'未归档'; $('#detail-status').classList.toggle('is-archived',archived);
    $('#archive span').textContent=archived?'取消归档':'归档';
    $('#created-time').textContent=date(s.time_created,true); $('#updated-time').textContent=date(s.time_updated,true);
    $('#session-id').textContent=s.id; $('#export').href=`/api/session/${encodeURIComponent(s.id)}/export`;
    $('#message-count').textContent=result.total+' 条消息';
    const messages=result.messages.map(message=>{
      const article=el('article','message '+message.role); const meta=el('div','message-meta');
      meta.append(el('span','message-avatar',message.role==='user'?'你':'O'),el('span','',message.role==='user'?'你':message.role==='assistant'?'OpenCode':'系统消息'),el('span','message-time',date(message.time)));
      article.append(meta);
      if(!message.parts.length) article.append(el('div','message-content','这条消息没有可预览的文本。'));
      for(const part of message.parts) {
        if(part.type==='file'||part.type==='large') {
          const note=el('div','attachment-note'); note.append(icon('file'),el('span','',localize(part.text)+(part.bytes?' ('+bytes(part.bytes)+')':''))); article.append(note);
        } else {
          article.append(el('div','message-content '+(part.type==='tool'?'tool':part.type==='reasoning'?'reasoning':''),part.text));
          if(part.truncated) article.append(el('div','detail-footnote','此处仅显示前 6,000 个字符，完整内容仍保留在 OpenCode 中。'));
        }
      }
      return article;
    });
    $('#preview-messages').replaceChildren(...messages);
    if(!messages.length) $('#preview-messages').append(el('div','list-status','这个会话还没有消息。'));
    $('#older-messages').disabled=offset+result.limit>=result.total;
    $('#older-messages').hidden=result.total<=result.limit;
    $('#latest-messages').hidden=offset===0;
    $('#detail-panel').scrollTop=0; renderSessions();
  } catch(e) { if(requestId===state.previewId) { $('#preview-messages').replaceChildren(el('div','notice',localize(e.message))); error(localize(e.message)); } }
}
async function refreshAll() { await bootstrap(); await loadSessions(); }
async function prepareDelete(ids, button) {
  busy(button,true); error('');
  try {
    state.plan=await api('/api/delete-plan',{ids});
    const n=state.plan.count; $('#delete-heading').textContent=`删除 ${n} 个会话？`;
    $('#delete-description').textContent=state.plan.extra?`已选择 ${ids.length} 个会话，还会一并删除 ${state.plan.extra} 个子会话，完整范围如下。`:'请核对下列将被永久删除的会话。';
    $('#delete-list').replaceChildren(...state.plan.sessions.map(s=>{const row=el('div','delete-item',s.title); row.append(el('small','','更新于 '+date(s.time_updated,true)));return row;}));
    $('#delete-confirm-label').textContent=`输入「删除 ${n}」以确认`;
    $('#delete-confirm').value=''; $('#delete-error').textContent=''; $('#confirm-delete').disabled=true;
    $('#delete-dialog').showModal();
  } catch(e) { error(localize(e.message)); } finally { busy(button,false); }
}

document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{
  state.view=button.dataset.view; state.directory='';
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b===button));
  $('#view-title').textContent={all:'全部会话',active:'未归档',archived:'已归档'}[state.view];
  $('#sidebar').classList.remove('mobile-open'); resetFilters(); bootstrap().catch(e=>error(localize(e.message)));
}));
$('#search').addEventListener('input',()=>{clearTimeout(searchTimer); searchTimer=setTimeout(resetFilters,220);});
$('#before-date').addEventListener('change',resetFilters);
$('#include-children').addEventListener('change',resetFilters);
$('#older-month').addEventListener('click',()=>{
  // 按北京时间减一个日历月，月末自动收敛到上个月最后一天。
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(Date.now());
  const values=Object.fromEntries(parts.map(p=>[p.type,p.value]));
  const year=Number(values.year), month=Number(values.month)-1, day=Number(values.day);
  const lastDay=new Date(Date.UTC(year,month,0)).getUTCDate();
  const cutoff=new Date(Date.UTC(year,month-1,Math.min(day,lastDay)));
  $('#before-date').value=cutoff.toISOString().slice(0,10); resetFilters();
});
$('#clear-filters').addEventListener('click',()=>{$('#search').value='';$('#before-date').value='';$('#include-children').checked=true;state.directory='';resetFilters();bootstrap().catch(e=>error(localize(e.message)));});
$('#refresh').addEventListener('click',async()=>{busy($('#refresh'),true);try{await refreshAll();if(state.current)await openSession(state.current.id,state.messageOffset);}catch(e){error(localize(e.message));}finally{busy($('#refresh'),false);}});
$('#previous-page').addEventListener('click',()=>{state.offset=Math.max(0,state.offset-30);loadSessions();});
$('#next-page').addEventListener('click',()=>{state.offset+=30;loadSessions();});
$('#select-all').addEventListener('change',event=>{for(const s of state.page)event.target.checked?state.selected.add(s.id):state.selected.delete(s.id);renderSessions();});
$('#clear-selection').addEventListener('click',()=>{state.selected.clear();renderSessions();});
$('#close-detail').addEventListener('click',closeDetail);
$('#older-messages').addEventListener('click',()=>{if(state.current)openSession(state.current.id,state.messageOffset+12);});
$('#latest-messages').addEventListener('click',()=>{if(state.current)openSession(state.current.id);});
$('#rename').addEventListener('click',()=>{if(!state.current)return;$('#rename-input').value=state.current.title;$('#rename-error').textContent='';$('#rename-dialog').showModal();$('#rename-input').select();});
$('#rename-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!state.current)return;const id=state.current.id;busy($('#save-title'),true,'正在保存…');
  try{await api('/api/update',{id,title:$('#rename-input').value});$('#rename-dialog').close();await refreshAll();await openSession(id);toast('会话名称已更新');}
  catch(e){$('#rename-error').textContent=localize(e.message);}finally{busy($('#save-title'),false,'正在保存…');}
});
$('#archive').addEventListener('click',async()=>{
  if(!state.current)return;const id=state.current.id, archived=!(state.current.time_archived>0);busy($('#archive'),true);
  try{await api('/api/update',{id,archived});await refreshAll();await openSession(id);toast(archived?'会话已归档':'会话已取消归档');}
  catch(e){error(localize(e.message));}finally{busy($('#archive'),false);}
});
$('#delete-one').addEventListener('click',()=>{if(state.current)prepareDelete([state.current.id],$('#delete-one'));});
$('#bulk-delete').addEventListener('click',()=>prepareDelete([...state.selected],$('#bulk-delete')));
$('#delete-confirm').addEventListener('input',()=>{$('#confirm-delete').disabled=$('#delete-confirm').value!==`删除 ${state.plan?.count}`;});
$('#delete-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!state.plan)return;busy($('#confirm-delete'),true,'正在删除…');
  try{const result=await api('/api/delete',{token:state.plan.token,confirmation:$('#delete-confirm').value});$('#delete-dialog').close();state.selected.clear();closeDetail();state.offset=0;await refreshAll();toast(`已删除 ${result.deleted} 个会话`);}
  catch(e){$('#delete-error').textContent=localize(e.message);state.plan=null;}
  finally{busy($('#confirm-delete'),false,'正在删除…');$('#confirm-delete').disabled=!state.plan;}
});
document.querySelectorAll('.dialog-cancel').forEach(button=>button.addEventListener('click',()=>button.closest('dialog').close()));
$('#menu-button').addEventListener('click',()=>$('#sidebar').classList.toggle('mobile-open'));
$('#stop').addEventListener('click',async()=>{if(!window.confirm('关闭本地会话管理器？此操作不会修改 OpenCode 会话数据。'))return;try{await api('/api/shutdown',{});status('会话管理器已关闭');toast('管理器已关闭。下次可双击启动脚本重新打开。');}catch(e){error(localize(e.message));}});
document.addEventListener('keydown',event=>{
  if(event.key==='/'&&!['INPUT','TEXTAREA'].includes(document.activeElement.tagName)&&!$('dialog[open]')){event.preventDefault();$('#search').focus();}
  if(event.key==='Escape'&&!$('dialog[open]')){$('#sidebar').classList.remove('mobile-open');closeDetail();}
});
refreshAll().catch(e=>{error(localize(e.message));emptyList('暂时无法打开会话库','请检查启动配置中的数据库路径，然后刷新。');status('本地连接需要检查');});
