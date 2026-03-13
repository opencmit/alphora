(function(){
"use strict";

var SVG_FOLDER = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>';
var SVG_FILE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
var SVG_CODE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>';
var SVG_IMAGE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>';
var SVG_DATA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg>';
var SVG_ARCHIVE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 8v13H3V8"/><path d="M1 3h22v5H1z"/><path d="M10 12h4"/></svg>';
var SVG_DOWNLOAD = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';
var SVG_BACK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="11 17 6 12 11 7"/><line x1="6" y1="12" x2="20" y2="12"/></svg>';

var CODE_EXTS = {py:1,js:1,ts:1,jsx:1,tsx:1,css:1,scss:1,less:1,java:1,c:1,cpp:1,h:1,go:1,rs:1,rb:1,php:1,sh:1,bash:1,vue:1,svelte:1,swift:1,kt:1,r:1,sql:1,dockerfile:1};
var IMAGE_EXTS = {png:1,jpg:1,jpeg:1,gif:1,svg:1,webp:1,ico:1,bmp:1,tiff:1};
var DATA_EXTS = {json:1,yaml:1,yml:1,toml:1,xml:1,txt:1,log:1,ini:1,cfg:1,conf:1,env:1};
var CSV_EXTS = {csv:1,tsv:1};
var MARKDOWN_EXTS = {md:1,markdown:1};
var EXCEL_EXTS = {xlsx:1,xls:1,xlsm:1};
var HTML_EXTS = {html:1,htm:1};
var PDF_EXTS = {pdf:1};
var ARCHIVE_EXTS = {zip:1,tar:1,gz:1,rar:1,'7z':1,bz2:1,xz:1};

function _iconSvg(item) {
  if (item.type === 'directory') return SVG_FOLDER;
  var ext = (item.extension || '').toLowerCase();
  if (CODE_EXTS[ext]) return SVG_CODE;
  if (IMAGE_EXTS[ext]) return SVG_IMAGE;
  if (DATA_EXTS[ext] || MARKDOWN_EXTS[ext] || CSV_EXTS[ext]) return SVG_DATA;
  if (ARCHIVE_EXTS[ext]) return SVG_ARCHIVE;
  return SVG_FILE;
}

function _iconClass(item) {
  return item.type === 'directory' ? 'dir' : '';
}

function _fileKind(name) {
  var ext = (name || '').split('.').pop().toLowerCase();
  if (EXCEL_EXTS[ext]) return 'excel';
  if (PDF_EXTS[ext]) return 'pdf';
  if (IMAGE_EXTS[ext]) return 'image';
  if (HTML_EXTS[ext]) return 'html';
  if (MARKDOWN_EXTS[ext]) return 'markdown';
  if (CSV_EXTS[ext]) return 'csv';
  if (CODE_EXTS[ext]) return 'code';
  if (DATA_EXTS[ext]) return 'text';
  return 'file';
}

var _endpoint = '';
var _sessionId = '';
var _cwd = '/';
var _pollTimer = null;
var _listEl = null;
var _breadEl = null;
var _toolbarEl = null;
var _prevNames = null;
var _available = false;

function _escape(s) {
  var d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function _post(path, body) {
  return fetch(_endpoint + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}

function _parentDir(dir) {
  if (!dir || dir === '/') return '/';
  var parts = dir.replace(/\/+$/, '').split('/').filter(Boolean);
  parts.pop();
  return parts.length ? '/' + parts.join('/') : '/';
}

function _renderBread(cwd) {
  if (!_breadEl) return;
  var parts = cwd.split('/').filter(Boolean);
  var html = '<span class="fb-crumb" data-dir="/">/</span>';
  var acc = '';
  for (var i = 0; i < parts.length; i++) {
    acc += '/' + parts[i];
    html += '<span class="fb-sep">/</span><span class="fb-crumb" data-dir="' + _escape(acc) + '">' + _escape(parts[i]) + '</span>';
  }
  _breadEl.innerHTML = html;
  _breadEl.querySelectorAll('.fb-crumb').forEach(function(el) {
    el.addEventListener('click', function() {
      load(el.getAttribute('data-dir'));
    });
  });
}

function _renderList(files, highlightNew) {
  if (!_listEl) return;

  var newNames = {};
  if (highlightNew && _prevNames) {
    files.forEach(function(f) { if (!_prevNames[f.name]) newNames[f.name] = true; });
  }
  _prevNames = {};
  files.forEach(function(f) { _prevNames[f.name] = true; });

  var html = '';

  if (_cwd !== '/') {
    html += '<div class="fb-item fb-item-back" data-action="back">';
    html += '<span class="fb-icon dir">' + SVG_BACK + '</span>';
    html += '<div class="fb-info"><div class="fb-name" style="color:var(--t3)">..</div></div>';
    html += '</div>';
  }

  if (!files.length && _cwd === '/') {
    _listEl.innerHTML = '<div class="fb-empty">该目录为空</div>';
    return;
  }

  for (var i = 0; i < files.length; i++) {
    var f = files[i];
    var isNew = newNames[f.name] ? ' new' : '';
    var meta = f.type === 'directory' ? '' : (f.size_display || '') + (f.mtime ? ' · ' + f.mtime : '');
    html += '<div class="fb-item' + isNew + '" data-path="' + _escape(f.path) + '" data-type="' + f.type + '" data-name="' + _escape(f.name) + '">';
    html += '<span class="fb-icon ' + _iconClass(f) + '">' + _iconSvg(f) + '</span>';
    html += '<div class="fb-info"><div class="fb-name">' + _escape(f.name) + '</div>';
    if (meta) html += '<div class="fb-meta">' + _escape(meta) + '</div>';
    html += '</div>';
    if (f.type === 'file') {
      html += '<button class="fb-dl" title="下载" data-dl="' + _escape(f.path) + '">' + SVG_DOWNLOAD + '</button>';
    }
    html += '</div>';
  }
  _listEl.innerHTML = html;

  var backItem = _listEl.querySelector('[data-action="back"]');
  if (backItem) {
    backItem.addEventListener('click', function() { load(_parentDir(_cwd)); });
  }

  _listEl.querySelectorAll('.fb-item:not([data-action])').forEach(function(el) {
    el.addEventListener('click', function(e) {
      if (e.target.closest('.fb-dl')) return;
      var type = el.getAttribute('data-type');
      var path = el.getAttribute('data-path');
      if (type === 'directory') {
        load(path);
      } else {
        _previewFile(path, el.getAttribute('data-name'));
      }
    });
  });

  _listEl.querySelectorAll('.fb-dl').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      _downloadFile(btn.getAttribute('data-dl'));
    });
  });
}

function _previewFile(path, name) {
  _post('/files/read', { session_id: _sessionId, path: path })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      data._filePath = path;
      var kind = _fileKind(name || data.name || path);
      var node = _buildPreviewNode(data, kind, name);
      if (window.ppShowPreview) {
        window.ppShowPreview(name || data.name || '文件预览', node, path);
      }
    })
    .catch(function(err) {
      console.error('File preview error:', err);
    });
}

function _buildPreviewNode(data, kind, name) {
  var wrap = document.createElement('div');
  wrap.style.cssText = 'padding:4px 0';

  if (kind === 'excel') {
    return _renderExcel(data, wrap);
  }
  if (kind === 'csv') {
    return _renderCsv(data, wrap, name);
  }
  if (kind === 'html') {
    return _renderHtml(data, wrap);
  }
  if (kind === 'markdown') {
    return _renderMarkdown(data, wrap);
  }
  if (kind === 'image') {
    return _renderImage(data, wrap);
  }
  if (kind === 'pdf') {
    return _renderPdf(data, wrap);
  }
  if (kind === 'code') {
    return _renderCode(data, wrap, name);
  }
  if (kind === 'text') {
    var ext = (name || '').split('.').pop().toLowerCase();
    if (ext === 'json') return _renderJson(data, wrap);
    return _renderText(data, wrap);
  }
  var msg = document.createElement('div');
  msg.style.cssText = 'padding:24px;text-align:center;color:var(--t4)';
  msg.textContent = '该文件类型暂不支持预览，请下载查看';
  var dlBtn = document.createElement('button');
  dlBtn.textContent = '下载文件';
  dlBtn.style.cssText = 'margin-top:12px;padding:8px 20px;border-radius:6px;border:1px solid var(--border);background:var(--white);cursor:pointer;color:var(--t1)';
  dlBtn.addEventListener('click', function() {
    var fp = (data._filePath || name || '').split('/');
    _downloadFile(data._filePath || '/' + (name || 'file'));
  });
  msg.appendChild(document.createElement('br'));
  msg.appendChild(dlBtn);
  wrap.appendChild(msg);
  return wrap;
}

function _renderExcel(data, wrap) {
  if (!window.XLSX) {
    wrap.innerHTML = '<div style="padding:24px;text-align:center;color:var(--t4)">Excel 预览组件未加载</div>';
    return wrap;
  }
  try {
    var wb;
    var readOpts = { cellStyles: true, cellNF: true };
    if (data.encoding === 'base64') {
      wb = window.XLSX.read(data.content, Object.assign({ type: 'base64' }, readOpts));
    } else {
      var encoder = new TextEncoder();
      var buf = encoder.encode(data.content);
      wb = window.XLSX.read(buf, Object.assign({ type: 'array' }, readOpts));
    }

    if (wb.SheetNames.length > 1) {
      var tabs = document.createElement('div');
      tabs.style.cssText = 'display:flex;gap:4px;padding:8px 0 12px;flex-wrap:wrap';
      var holder = document.createElement('div');
      holder.style.cssText = 'overflow:auto';
      function renderSheet(sn) {
        tabs.querySelectorAll('button').forEach(function(b) {
          b.style.fontWeight = b.textContent === sn ? '600' : '400';
          b.style.color = b.textContent === sn ? 'var(--accent)' : 'var(--t3)';
          b.style.background = b.textContent === sn ? 'var(--bg)' : 'var(--white)';
        });
        holder.innerHTML = '';
        holder.appendChild(_sheetToTable(wb.Sheets[sn]));
      }
      wb.SheetNames.forEach(function(sn) {
        var btn = document.createElement('button');
        btn.textContent = sn;
        btn.style.cssText = 'padding:4px 12px;border-radius:5px;border:1px solid var(--border);background:var(--white);cursor:pointer;font-size:12px;color:var(--t3);transition:all .15s';
        btn.addEventListener('click', function() { renderSheet(sn); });
        tabs.appendChild(btn);
      });
      wrap.appendChild(tabs);
      wrap.appendChild(holder);
      renderSheet(wb.SheetNames[0]);
    } else {
      var container = document.createElement('div');
      container.style.cssText = 'overflow:auto';
      container.appendChild(_sheetToTable(wb.Sheets[wb.SheetNames[0]]));
      wrap.appendChild(container);
    }
  } catch (e) {
    wrap.innerHTML = '<div style="padding:24px;color:var(--t4)">Excel 解析失败: ' + _escape(e.message) + '</div>';
  }
  return wrap;
}

function _sheetToTable(ws) {
  if (!ws['!ref']) {
    var e = document.createElement('div');
    e.textContent = '空表';
    e.style.cssText = 'padding:16px;color:var(--t4)';
    return e;
  }
  var html = window.XLSX.utils.sheet_to_html(ws, { id: 'xlpv', header: '', footer: '' });
  var frag = document.createElement('div');
  frag.innerHTML = html;
  var table = frag.querySelector('table');
  if (!table) {
    frag.textContent = '无法解析工作表';
    return frag;
  }
  table.style.cssText = 'border-collapse:collapse;font-size:12px;min-width:100%';
  table.querySelectorAll('td,th').forEach(function(cell) {
    if (!cell.style.border) cell.style.border = '1px solid var(--border)';
    cell.style.padding = '5px 8px';
    cell.style.maxWidth = '300px';
    cell.style.overflow = 'hidden';
    cell.style.textOverflow = 'ellipsis';
  });
  var firstRow = table.querySelector('tr');
  if (firstRow) {
    firstRow.querySelectorAll('td,th').forEach(function(cell) {
      if (!cell.style.backgroundColor) cell.style.backgroundColor = 'var(--bg)';
      if (!cell.style.fontWeight) cell.style.fontWeight = '600';
      cell.style.position = 'sticky';
      cell.style.top = '0';
    });
  }
  _applySheetStyles(table, ws);
  return table;
}

function _applySheetStyles(table, ws) {
  if (!ws['!ref']) return;
  var keys = Object.keys(ws);
  for (var i = 0; i < keys.length; i++) {
    var addr = keys[i];
    if (addr[0] === '!') continue;
    var cell = ws[addr];
    if (!cell || !cell.s) continue;
    var el = table.querySelector('#xlpv-' + addr);
    if (!el) continue;
    var s = cell.s;
    if (s.fgColor || s.bgColor || (s.fill && s.fill.fgColor)) {
      var bg = _xlsxColor(s.fgColor) || _xlsxColor(s.bgColor) || (s.fill ? _xlsxColor(s.fill.fgColor) : '');
      if (bg) el.style.backgroundColor = bg;
    }
    if (s.font || s.bold || s.italic || s.color) {
      if (s.bold || (s.font && s.font.bold)) el.style.fontWeight = 'bold';
      if (s.italic || (s.font && s.font.italic)) el.style.fontStyle = 'italic';
      var fc = _xlsxColor(s.color) || (s.font ? _xlsxColor(s.font.color) : '');
      if (fc) el.style.color = fc;
      var sz = s.sz || (s.font ? s.font.sz : 0);
      if (sz) el.style.fontSize = sz + 'pt';
    }
    if (s.alignment) {
      if (s.alignment.horizontal) el.style.textAlign = s.alignment.horizontal;
      if (s.alignment.vertical) el.style.verticalAlign = s.alignment.vertical === 'center' ? 'middle' : s.alignment.vertical;
      if (s.alignment.wrapText) el.style.whiteSpace = 'pre-wrap';
    }
  }
}

function _xlsxColor(c) {
  if (!c) return '';
  if (c.rgb && c.rgb !== '000000') return '#' + c.rgb.replace(/^FF/, '');
  return '';
}

function _renderMarkdown(data, wrap) {
  var content = data.encoding === 'base64' ? _decodeBase64(data.content) : data.content;
  wrap.className = 'md';
  wrap.style.cssText += ';padding:12px 16px;line-height:1.7;font-size:14px';
  try {
    wrap.innerHTML = window.marked.parse(content, { breaks: true, gfm: true });
    wrap.querySelectorAll('pre code').forEach(function(b) {
      if (window.hljs) window.hljs.highlightElement(b);
    });
  } catch (e) {
    wrap.textContent = content;
  }
  return wrap;
}

function _renderImage(data, wrap) {
  var img = document.createElement('img');
  img.style.cssText = 'max-width:100%;border-radius:6px';
  if (data.encoding === 'base64') {
    img.src = 'data:' + (data.mime || 'image/png') + ';base64,' + data.content;
  } else {
    img.src = 'data:' + (data.mime || 'image/png') + ';base64,' + btoa(data.content);
  }
  wrap.style.textAlign = 'center';
  wrap.appendChild(img);
  return wrap;
}

function _renderPdf(data, wrap) {
  var iframe = document.createElement('iframe');
  iframe.style.cssText = 'width:100%;height:calc(100vh - 140px);border:none;border-radius:6px';
  if (data.encoding === 'base64') {
    iframe.src = 'data:application/pdf;base64,' + data.content;
  }
  wrap.appendChild(iframe);
  return wrap;
}

function _renderHtml(data, wrap) {
  var filePath = (data._filePath || '').replace(/^\/+/, '');
  var serveUrl = _endpoint + '/files/serve/' + filePath.split('/').map(encodeURIComponent).join('/') + '?sid=' + encodeURIComponent(_sessionId);
  var iframe = document.createElement('iframe');
  iframe.className = 'pv-html';
  iframe.style.cssText = 'width:100%;height:calc(100vh - 160px);border:none;border-radius:6px;background:#fff';
  iframe.src = serveUrl;
  wrap.appendChild(iframe);
  return wrap;
}

function _renderCode(data, wrap, name) {
  var content = data.encoding === 'base64' ? _decodeBase64(data.content) : data.content;
  var pre = document.createElement('pre');
  pre.style.cssText = 'margin:0;border-radius:6px;overflow:auto;font-size:13px';
  var code = document.createElement('code');
  var ext = (name || '').split('.').pop().toLowerCase();
  if (ext) code.className = 'language-' + ext;
  code.textContent = content;
  pre.appendChild(code);
  wrap.appendChild(pre);
  try { if (window.hljs) window.hljs.highlightElement(code); } catch (e) {}
  return wrap;
}

function _renderJson(data, wrap) {
  var content = data.encoding === 'base64' ? _decodeBase64(data.content) : data.content;
  var pre = document.createElement('pre');
  pre.style.cssText = 'margin:0;border-radius:6px;overflow:auto;font-size:13px';
  var code = document.createElement('code');
  code.className = 'language-json';
  try {
    code.textContent = JSON.stringify(JSON.parse(content), null, 2);
  } catch (e) {
    code.textContent = content;
  }
  pre.appendChild(code);
  wrap.appendChild(pre);
  try { if (window.hljs) window.hljs.highlightElement(code); } catch (e) {}
  return wrap;
}

function _renderText(data, wrap) {
  var content = data.encoding === 'base64' ? _decodeBase64(data.content) : data.content;
  var pre = document.createElement('pre');
  pre.style.cssText = 'margin:0;white-space:pre-wrap;word-break:break-word;font-size:13px;line-height:1.6;font-family:var(--mono,ui-monospace,monospace)';
  pre.textContent = content;
  wrap.appendChild(pre);
  return wrap;
}

function _renderCsv(data, wrap, name) {
  var content = data.encoding === 'base64' ? _decodeBase64(data.content) : data.content;
  var ext = (name || '').split('.').pop().toLowerCase();
  var sep = ext === 'tsv' ? '\t' : ',';
  var rows = _parseCsv(content, sep);
  if (!rows.length) {
    wrap.innerHTML = '<div style="padding:16px;color:var(--t4)">空文件</div>';
    return wrap;
  }
  var maxR = Math.min(rows.length, 500);
  var maxC = 0;
  for (var i = 0; i < maxR; i++) maxC = Math.max(maxC, rows[i].length);
  maxC = Math.min(maxC, 100);
  var table = document.createElement('table');
  table.style.cssText = 'border-collapse:collapse;width:100%;font-size:12px';
  for (var r = 0; r < maxR; r++) {
    var tr = document.createElement('tr');
    for (var c = 0; c < maxC; c++) {
      var td = document.createElement(r === 0 ? 'th' : 'td');
      td.style.cssText = 'border:1px solid var(--border);padding:5px 8px;text-align:left;white-space:nowrap;max-width:200px;overflow:hidden;text-overflow:ellipsis';
      if (r === 0) td.style.cssText += ';background:var(--bg);font-weight:600;position:sticky;top:0';
      td.textContent = (rows[r][c] != null) ? rows[r][c] : '';
      tr.appendChild(td);
    }
    table.appendChild(tr);
  }
  wrap.appendChild(table);
  return wrap;
}

function _parseCsv(text, sep) {
  var lines = text.split('\n');
  var result = [];
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].replace(/\r$/, '');
    if (!line && i === lines.length - 1) continue;
    var row = [];
    var inQuote = false;
    var cell = '';
    for (var j = 0; j < line.length; j++) {
      var ch = line[j];
      if (inQuote) {
        if (ch === '"') {
          if (j + 1 < line.length && line[j + 1] === '"') {
            cell += '"';
            j++;
          } else {
            inQuote = false;
          }
        } else {
          cell += ch;
        }
      } else {
        if (ch === '"') {
          inQuote = true;
        } else if (ch === sep) {
          row.push(cell);
          cell = '';
        } else {
          cell += ch;
        }
      }
    }
    row.push(cell);
    result.push(row);
  }
  return result;
}

function _decodeBase64(b64) {
  try {
    return decodeURIComponent(escape(atob(b64)));
  } catch (e) {
    try { return atob(b64); } catch (e2) { return b64; }
  }
}

function _downloadFile(path) {
  _post('/files/download', { session_id: _sessionId, path: path })
    .then(function(r) {
      var filename = path.split('/').pop() || 'download';
      return r.blob().then(function(b) { return { blob: b, name: filename }; });
    })
    .then(function(res) {
      var url = URL.createObjectURL(res.blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = res.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    })
    .catch(function(err) {
      console.error('File download error:', err);
    });
}

function init(els) {
  _listEl = els.list;
  _breadEl = els.bread;
  _toolbarEl = els.toolbar;
}

function setEndpoint(baseUrl) {
  _endpoint = baseUrl.replace(/\/chat\/completions\/?$/, '').replace(/\/+$/, '');
}

function setSessionId(sid) {
  _sessionId = sid || '';
}

function load(dir) {
  dir = dir || '/';
  _cwd = dir;
  _renderBread(dir);
  if (!_endpoint) {
    if (_listEl) _listEl.innerHTML = '<div class="fb-empty">未配置 API 地址</div>';
    return Promise.resolve(false);
  }
  return _post('/files/list', { session_id: _sessionId, dir: dir })
    .then(function(r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    })
    .then(function(data) {
      _available = true;
      _renderList(data.files, true);
      return true;
    })
    .catch(function() {
      _available = false;
      if (_listEl) _listEl.innerHTML = '<div class="fb-empty">文件服务不可用</div>';
      return false;
    });
}

function refresh() {
  return load(_cwd);
}

function startPolling(intervalMs) {
  stopPolling();
  _pollTimer = setInterval(function() { refresh(); }, intervalMs || 5000);
}

function stopPolling() {
  if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
}

function isAvailable() {
  return _available;
}

function probe() {
  if (!_endpoint) return Promise.resolve(false);
  return _post('/files/list', { session_id: _sessionId, dir: '/' })
    .then(function(r) {
      _available = r.ok;
      return r.ok;
    })
    .catch(function() {
      _available = false;
      return false;
    });
}

window.FileBrowser = {
  init: init,
  setEndpoint: setEndpoint,
  setSessionId: setSessionId,
  load: load,
  refresh: refresh,
  startPolling: startPolling,
  stopPolling: stopPolling,
  isAvailable: isAvailable,
  probe: probe,
  _downloadFile: _downloadFile,
};

})();
