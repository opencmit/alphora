(function(){
"use strict";

var EFFECTS = {
  none:       { label: '无效果',  icon: '—',  desc: '文字直接出现' },
  typewriter: { label: '打字机',  icon: '▎',  desc: '经典光标闪烁' },
  fade:       { label: '浮现',    icon: '◐',  desc: '文字从透明渐入' },
  slide:      { label: '滑入',    icon: '↗',  desc: '文字从下方浮入' },
  rainbow:    { label: '彩虹',    icon: '🌈', desc: '彩虹渐变色出现' },
  glow:       { label: '发光',    icon: '✦',  desc: '带荧光效果浮现' },
  blur:       { label: '聚焦',    icon: '◉',  desc: '从模糊渐变清晰' }
};

var CLASS_MAP = {
  fade:'sfx-fade', slide:'sfx-slide', rainbow:'sfx-rainbow',
  glow:'sfx-glow', blur:'sfx-blur'
};

/* ── CSS injection ── */
var css = [
  '.sfx-cursor{display:inline-block;width:2px;height:1em;background:var(--accent);border-radius:1px;margin-left:2px;vertical-align:text-bottom;animation:sfx-blink .6s steps(2) infinite}',
  '@keyframes sfx-blink{0%{opacity:1}100%{opacity:0}}',

  '.sfx-fade{animation:sfx-fi .4s ease-out}',
  '@keyframes sfx-fi{from{opacity:0}to{opacity:1}}',

  '.sfx-slide{display:inline;animation:sfx-si .35s ease-out}',
  '@keyframes sfx-si{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}',

  '.sfx-rainbow{animation:sfx-ri .6s ease-out;background:linear-gradient(90deg,#e74c3c,#e67e22,#f1c40f,#2ecc71,#3498db,#9b59b6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;background-size:200% 100%}',
  '@keyframes sfx-ri{from{opacity:0;background-position:100% 0}to{opacity:1;background-position:0 0}}',

  '.sfx-glow{animation:sfx-gi .5s ease-out}',
  '@keyframes sfx-gi{from{opacity:0;text-shadow:0 0 10px var(--accent)}to{opacity:1;text-shadow:none}}',

  '.sfx-blur{animation:sfx-bi .4s ease-out}',
  '@keyframes sfx-bi{from{opacity:0;filter:blur(4px)}to{opacity:1;filter:blur(0)}}'
].join('\n');

var el = document.createElement('style');
el.textContent = css;
document.head.appendChild(el);

/* ── helpers ── */
function isInsidePre(n){
  var p = n.parentNode;
  while(p && p.nodeType === 1){ if(p.tagName === 'PRE') return true; p = p.parentNode; }
  return false;
}

/**
 * Walk text nodes inside `el`, wrap every character AFTER position
 * `prevLen` (visible-text offset) in a <span class="sfx-xxx">.
 * Skips text inside <pre> blocks to preserve syntax highlighting.
 */
function apply(el, prevLen, effectName){
  if(!effectName || effectName === 'none' || effectName === 'typewriter') return;
  var cls = CLASS_MAP[effectName];
  if(!cls) return;

  var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
  var count = 0, items = [], node;

  while(node = walker.nextNode()){
    if(isInsidePre(node)){ count += node.textContent.length; continue; }
    var len = node.textContent.length, start = count;
    count += len;
    if(count <= prevLen) continue;
    items.push({ node: node, splitAt: start < prevLen ? prevLen - start : -1 });
  }

  for(var i = items.length - 1; i >= 0; i--){
    var it = items[i], target = it.node;
    if(it.splitAt > 0) target = target.splitText(it.splitAt);
    var sp = document.createElement('span');
    sp.className = cls;
    target.parentNode.insertBefore(sp, target);
    sp.appendChild(target);
  }
}

/* ── typewriter cursor ── */
function applyTypewriter(el){
  removeTypewriter(el);
  var last = el.lastElementChild || el;
  var c = document.createElement('span');
  c.className = 'sfx-cursor';
  last.appendChild(c);
}

function removeTypewriter(el){
  el.querySelectorAll('.sfx-cursor').forEach(function(e){ e.remove(); });
}

function cleanup(container){
  removeTypewriter(container);
  container.querySelectorAll('.loading-dots').forEach(function(e){ e.remove(); });
}

/* ── live preview (simulates streaming) ── */
function preview(container, effectName){
  stopPreview(container);
  var sample = '你好！我是 **AI 助手**，很高兴为你服务。\n\n我可以帮你写代码、分析数据、回答问题。';
  var chunks = [];
  for(var i = 0; i < sample.length; i += 2)
    chunks.push(sample.slice(i, Math.min(i+2, sample.length)));

  container.innerHTML = '';
  container.classList.add('md');
  var buf = '', idx = 0;

  function tick(){
    if(idx >= chunks.length){
      removeTypewriter(container);
      container._sfxT = setTimeout(function(){ preview(container, effectName); }, 2000);
      return;
    }
    buf += chunks[idx];
    var prevLen = container.textContent.length;
    try{
      container.innerHTML = marked.parse(buf, {breaks:true, gfm:true});
    }catch(e){ container.textContent = buf; }

    if(effectName === 'typewriter') applyTypewriter(container);
    else apply(container, prevLen, effectName);

    idx++;
    container._sfxT = setTimeout(tick, 50 + Math.random() * 40);
  }
  tick();
}

function stopPreview(container){
  if(container._sfxT){ clearTimeout(container._sfxT); container._sfxT = null; }
}

/* ── public API ── */
window.StreamingEffects = {
  EFFECTS:  EFFECTS,
  apply:    apply,
  applyTypewriter:  applyTypewriter,
  removeTypewriter: removeTypewriter,
  cleanup:  cleanup,
  preview:  preview,
  stopPreview: stopPreview
};

})();
