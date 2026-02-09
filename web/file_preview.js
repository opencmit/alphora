// File preview helpers (canvas thumbnail + render)
(function(){
"use strict";
var state={overlay:null,drawer:null,modal:null,drawerTitle:null,drawerBody:null,modalTitle:null,modalBody:null};
function init(opts){
  state.overlay=opts.overlay;state.drawer=opts.drawer;state.modal=opts.modal;
  state.drawerTitle=opts.drawerTitle;state.drawerBody=opts.drawerBody;
  state.modalTitle=opts.modalTitle;state.modalBody=opts.modalBody;
  if(state.overlay){
    state.overlay.addEventListener('click',function(e){if(e.target===state.overlay)close()});
    document.querySelectorAll('[data-fp-close]').forEach(function(b){b.addEventListener('click',close)});
  }
}
function close(){
  if(!state.overlay)return;
  state.overlay.classList.remove('open');
  if(state.drawer)state.drawer.classList.remove('open');
  if(state.modal)state.modal.classList.remove('open');
  if(state.overlay._revoke){state.overlay._revoke();state.overlay._revoke=null}
}
function open(o){
  if(!state.overlay)return;
  close();
  var mode=o&&o.mode==='modal'?'modal':'drawer';
  state.overlay.classList.add('open');
  if(state.drawer)state.drawer.classList.toggle('open',mode==='drawer');
  if(state.modal)state.modal.classList.toggle('open',mode==='modal');
  var tEl=mode==='drawer'?state.drawerTitle:state.modalTitle;
  var bEl=mode==='drawer'?state.drawerBody:state.modalBody;
  if(tEl)tEl.textContent=o&&o.title?o.title:'文件预览';
  if(bEl){bEl.innerHTML='';if(o&&o.node)bEl.appendChild(o.node)}
  if(o&&o.revoke)state.overlay._revoke=o.revoke;
}
function inferFileKind(kind,ty){
  if(kind&&kind!=='auto')return kind;
  var t=(ty||'').toLowerCase();
  if(t.indexOf('excel')>-1||t.indexOf('xlsx')>-1||t.indexOf('xls')>-1)return 'excel';
  if(t.indexOf('pdf')>-1)return 'pdf';
  if(t.indexOf('image')>-1||t.indexOf('img')>-1)return 'image';
  if(t.indexOf('text')>-1||t.indexOf('txt')>-1)return 'text';
  return 'file';
}
function fileMime(kind){
  switch(kind){
    case 'excel':return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
    case 'pdf':return 'application/pdf';
    case 'image':return 'image/png';
    case 'text':return 'text/plain';
    default:return 'application/octet-stream';
  }
}
function fileExt(kind){
  switch(kind){
    case 'excel':return 'xlsx';
    case 'pdf':return 'pdf';
    case 'image':return 'png';
    case 'text':return 'txt';
    default:return 'bin';
  }
}
function cleanBase64(s){
  var v=(s||'').trim();
  if(v.indexOf('data:')===0){
    var i=v.indexOf(',');
    if(i>-1)v=v.slice(i+1);
  }
  return v.replace(/\s+/g,'');
}
function base64BytesLen(b64){
  if(!b64)return 0;
  var p=b64.indexOf('=');
  var len=b64.length;
  if(p>-1)len=p;
  return Math.floor(len*3/4);
}
function fmtBytes(n){
  if(n<1024)return n+' B';
  if(n<1024*1024)return (n/1024).toFixed(1)+' KB';
  if(n<1024*1024*1024)return (n/1024/1024).toFixed(1)+' MB';
  return (n/1024/1024/1024).toFixed(1)+' GB';
}
function b64ToBlobUrl(b64,mime){
  var bin=atob(b64),len=bin.length,bytes=new Uint8Array(len);
  for(var i=0;i<len;i++)bytes[i]=bin.charCodeAt(i);
  var blob=new Blob([bytes],{type:mime||'application/octet-stream'});
  return URL.createObjectURL(blob);
}
function buildFileObject(info){
  if(info.srcType==='url')return {srcType:'url',url:info.url,raw:info.raw};
  try{
    var url=b64ToBlobUrl(info.base64,fileMime(info.kind));
    return {srcType:'base64',url:url,raw:info.raw,revoke:function(){URL.revokeObjectURL(url)}};
  }catch(e){
    return {srcType:'base64',url:'',raw:info.raw,error:true};
  }
}
function decodeBase64Text(b64){
  try{return atob(b64)}catch(e){return ''}
}
function sheetToTable(ws,maxRows,maxCols){
  var data=window.XLSX.utils.sheet_to_json(ws,{header:1,raw:true});
  if(!data||!data.length){var empty=document.createElement('div');empty.textContent='空表';return empty}
  var rows=data.slice(0,maxRows);
  var cols=0;
  for(var i=0;i<rows.length;i++)cols=Math.max(cols,rows[i].length||0);
  cols=Math.min(cols,maxCols);
  var table=document.createElement('table');
  table.style.cssText='border-collapse:collapse;width:100%;font-size:12px;border-radius:8px;overflow:hidden';
  for(var r=0;r<rows.length;r++){
    var tr=document.createElement('tr');
    for(var c=0;c<cols;c++){
      var td=document.createElement('td');
      td.style.cssText='border:1px solid var(--border);padding:6px 8px;vertical-align:top';
      var v=rows[r][c];td.textContent=v==null?'':String(v);
      tr.appendChild(td);
    }
    table.appendChild(tr);
  }
  return table;
}
function renderXlsxPreview(info){
  var wrap=document.createElement('div');
  var note=document.createElement('div');note.className='fp-note';wrap.appendChild(note);
  var holder=document.createElement('div');wrap.appendChild(holder);
  if(!window.XLSX){
    note.textContent='Excel 预览组件未加载，请下载打开';
    return wrap;
  }
  note.textContent='Excel 预览（最多显示前 200 行、50 列）';
  function renderWb(wb){
    var sn=wb.SheetNames[0];var ws=wb.Sheets[sn];
    holder.innerHTML='';holder.appendChild(sheetToTable(ws,200,50));
  }
  if(info.srcType==='url'){
    fetch(info.url).then(function(r){return r.arrayBuffer()}).then(function(buf){
      var wb=window.XLSX.read(buf,{type:'array'});renderWb(wb);
    }).catch(function(err){note.textContent='Excel 加载失败: '+err.message});
  }else{
    try{var wb=window.XLSX.read(info.base64,{type:'base64'});renderWb(wb)}
    catch(e){note.textContent='Excel 解析失败: '+e.message}
  }
  return wrap;
}
function buildPreviewNode(info,obj){
  var wrap=document.createElement('div');
  var kind=info.kind;
  if(kind==='excel'){
    return renderXlsxPreview(info);
  }else if(kind==='pdf'){
    var ifp=document.createElement('iframe');ifp.src=obj.url;wrap.appendChild(ifp);
  }else if(kind==='image'){
    var img=document.createElement('img');img.src=obj.url;wrap.appendChild(img);
  }else if(kind==='text'){
    if(info.srcType==='base64'){
      var pre=document.createElement('pre');pre.textContent=decodeBase64Text(info.base64)||'(无法解码文本)';wrap.appendChild(pre);
    }else{
      var a=document.createElement('a');a.href=obj.url;a.target='_blank';a.rel='noopener';a.textContent='打开链接预览';wrap.appendChild(a);
    }
  }else{
    var an=document.createElement('a');an.href=obj.url;an.target='_blank';an.rel='noopener';an.textContent='打开文件';wrap.appendChild(an);
  }
  return wrap;
}
function fileBadge(kind){
  switch(kind){
    case 'excel':return 'XLSX';
    case 'pdf':return 'PDF';
    case 'image':return 'IMG';
    case 'text':return 'TXT';
    default:return 'FILE';
  }
}
function drawExcelThumb(canvas,ws){
  var dpr=window.devicePixelRatio||1;
  var w=canvas.parentElement?canvas.parentElement.offsetWidth:320;
  var h=canvas.parentElement?canvas.parentElement.offsetHeight:120;
  canvas.width=w*dpr;canvas.height=h*dpr;
  canvas.style.width=w+'px';canvas.style.height=h+'px';
  var ctx=canvas.getContext('2d');
  ctx.scale(dpr,dpr);
  ctx.clearRect(0,0,w,h);
  ctx.fillStyle='#f8fafc';ctx.fillRect(0,0,w,h);
  var data=window.XLSX.utils.sheet_to_json(ws,{header:1,raw:true});
  if(!data||!data.length)return;
  var maxR=Math.min(data.length,6),maxC=0,i;
  for(i=0;i<maxR;i++)maxC=Math.max(maxC,(data[i]||[]).length);
  maxC=Math.min(maxC,6);
  if(!maxC)return;
  var cw=w/maxC,ch=h/maxR;
  /* header row bg */
  ctx.fillStyle='#eef2ff';ctx.fillRect(0,0,w,ch);
  /* grid lines */
  ctx.strokeStyle='#e2e8f0';ctx.lineWidth=0.5;
  for(i=0;i<=maxR;i++){ctx.beginPath();ctx.moveTo(0,i*ch);ctx.lineTo(w,i*ch);ctx.stroke()}
  for(i=0;i<=maxC;i++){ctx.beginPath();ctx.moveTo(i*cw,0);ctx.lineTo(i*cw,h);ctx.stroke()}
  /* cell text */
  for(var r=0;r<maxR;r++){
    ctx.fillStyle=r===0?'#334155':'#64748b';
    ctx.font=(r===0?'600 ':'')+'9px system-ui,sans-serif';
    for(var c=0;c<maxC;c++){
      var v=(data[r]||[])[c];if(v==null)continue;
      var txt=String(v);if(txt.length>8)txt=txt.slice(0,7)+'…';
      ctx.fillText(txt,c*cw+4,r*ch+ch*0.65);
    }
  }
}
function updateFileThumb(card,kind,obj,srcType,info){
  var t=card.querySelector('[data-file-thumb]');
  var thumb=card.querySelector('.file-thumb');
  if(!t||!thumb)return;
  t.textContent=fileBadge(kind);
  var img=thumb.querySelector('img');
  var canvas=thumb.querySelector('canvas');
  if(kind==='image'&&obj&&obj.url){
    if(!img){img=document.createElement('img');thumb.appendChild(img)}
    img.src=obj.url;
    if(canvas)canvas.remove();
    t.style.display='none';
    return;
  }
  if(img)img.remove();
  t.style.display='';
  if(kind==='excel'&&window.XLSX&&info){
    if(!canvas){canvas=document.createElement('canvas');canvas.style.cssText='position:absolute;inset:0;width:100%;height:100%';thumb.appendChild(canvas)}
    var key=kind+'|'+(info.raw?info.raw.length:'0');
    if(card._thumbKey===key)return;
    card._thumbKey=key;
    t.style.display='none';
    if(info.srcType==='url'){
      fetch(info.url).then(function(r){return r.arrayBuffer()}).then(function(buf){
        var wb=window.XLSX.read(buf,{type:'array'});drawExcelThumb(canvas,wb.Sheets[wb.SheetNames[0]]);
      }).catch(function(){t.style.display=''});
    }else{
      try{var wb=window.XLSX.read(info.base64,{type:'base64'});drawExcelThumb(canvas,wb.Sheets[wb.SheetNames[0]])}catch(e){t.style.display=''}
    }
  }else if(canvas){canvas.remove()}
}
function ensureFileCard(el){
  var card=el.querySelector('.file-card');
  if(card)return card;
  card=document.createElement('div');card.className='file-card';
  card.innerHTML=[
    '<div class="file-thumb"><span class="file-thumb-text" data-file-thumb>FILE</span></div>',
    '<div class="file-body">',
      '<div class="file-head"><div class="file-ico">📄</div><div class="file-name">文件</div></div>',
      '<div class="file-sub" data-file-sub></div>',
      '<div class="file-actions"><button class="fp-prev">预览</button><a class="fp-dl" href="#" download>下载</a><button class="fp-open">打开</button></div>',
    '</div>',
    '<div class="file-preview-inline"></div>'
  ].join('');
  el.innerHTML='';el.appendChild(card);
  return card;
}
window.FilePreview={
  init:init,open:open,close:close,
  inferFileKind:inferFileKind,fileMime:fileMime,fileExt:fileExt,
  cleanBase64:cleanBase64,base64BytesLen:base64BytesLen,fmtBytes:fmtBytes,
  buildFileObject:buildFileObject,buildPreviewNode:buildPreviewNode,
  ensureFileCard:ensureFileCard,updateFileThumb:updateFileThumb
};
})();
