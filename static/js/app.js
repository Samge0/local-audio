'use strict';
/* ================= 状态 ================= */
const LS = {
  cur: 'ka.cur', pos: 'ka.pos', rate: 'ka.rate',
  mode: 'ka.mode', sleep: 'ka.sleep', vol: 'ka.vol', sub: 'ka.sub', col: 'ka.col'
};
const state = {
  items: [],            // 服务端列表
  curId: null,          // 当前曲目 id
  playing: false,
  seeking: false,       // 拖动进度条中
  mode: localStorage.getItem(LS.mode) || 'seq',   // seq|one|loop|shuffle
  sleepAt: 0,           // 定时播放结束的时间戳（ms），0=off
  sleepLeft: 0,         // 定时剩余秒（用于显示与恢复）
  sleepTick: null,
  subOn: localStorage.getItem(LS.sub) !== '0',  // 字幕默认开
  collapsed: new Set(JSON.parse(localStorage.getItem(LS.col) || '[]')),  // 折叠的组名（默认全展开）
};
const $ = s => document.querySelector(s);
const au = $('#au');

/* ================= 工具 ================= */
function toast(msg){
  const t = $('#toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(()=>t.classList.remove('show'), 1800);
}
function fmt(s){
  if(!isFinite(s)||s<0) s=0;
  s = Math.floor(s);
  const h=Math.floor(s/3600), m=Math.floor(s%3600/60), sec=s%60;
  return h? `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}` : `${m}:${String(sec).padStart(2,'0')}`;
}
function fmtSize(n){
  if(n>1e9) return (n/1e9).toFixed(2)+' GB';
  if(n>1e6) return (n/1e6).toFixed(1)+' MB';
  return (n/1e3).toFixed(0)+' KB';
}
/* 倍速文案：两位精度去尾零（1.75→"1.75" 1.5→"1.5" 1→"1.0"），
   toFixed(1) 会把 1.75 四舍五入显示成 1.8 */
function fmtRate(r){ return r.toFixed(2).replace(/0$/,''); }
function setV(el, v){ el.style.setProperty('--v', (v*100).toFixed(2)+'%'); }

/* ================= 进度记忆 ================= */
const POS_KEY = id => LS.pos + '.' + id;
function savePos(){
  if(!state.curId || !isFinite(au.currentTime) || au.currentTime < 1) return;
  localStorage.setItem(POS_KEY(state.curId), String(Math.floor(au.currentTime)));
}
function loadPos(id){
  const v = parseInt(localStorage.getItem(POS_KEY(id)) || '0', 10);
  return isFinite(v) ? v : 0;
}
function clearPos(id){
  if(id) localStorage.removeItem(POS_KEY(id));
}
setInterval(savePos, 3000);
window.addEventListener('beforeunload', savePos);
/* 正在播放的行：已听时长实时刷新（不整列重绘） */
setInterval(()=>{
  if(!state.curId || !state.playing || !isFinite(au.currentTime)) return;
  const el = document.getElementById('tr-'+cssId(state.curId));
  if(!el) return;
  let box = el.querySelector('.t-dur');
  if(!box) return;
  let pos = box.querySelector('.t-pos');
  if(!pos){
    box.insertAdjacentHTML('afterbegin',
      `<span class="t-pos"></span><span class="t-sep">/</span>`);
    pos = box.querySelector('.t-pos');
  }
  pos.textContent = fmt(au.currentTime);
}, 1000);

/* ================= 数据加载 ================= */
async function boot(){
  try{
    const r = await fetch('/api/list');
    const d = await r.json();
    state.items = d.items || [];
  }catch(e){
    $('#list').innerHTML = `<div class="empty"><div class="spin"></div><div>加载失败，请刷新重试（提取任务可能仍在进行）</div></div>`;
    return;
  }
  if(state.items.length === 0){
    $('#list').innerHTML = `<div class="empty"><div>音频目录为空<br><span style="font-size:11px">请检查 .env 的 AUDIO_DIR 配置</span></div></div>`;
    setTimeout(boot, 5000);
    return;
  }
  renderList();
  restoreLast();
}

/* ================= 列表渲染 ================= */
function visibleItems(){
  const q = $('#q').value.trim().toLowerCase();
  if(!q) return state.items;
  return state.items.filter(it =>
    it.name.toLowerCase().includes(q) || (it.group||'').toLowerCase().includes(q));
}
function renderList(){
  const list = $('#list');
  const vis = visibleItems();
  if(vis.length === 0){
    list.innerHTML = `<div class="empty" style="position:static;padding:40px 20px"><div>无匹配音频</div></div>`;
    return;
  }
  /* 搜索时强制全部展开（折叠的组可能藏着命中项）；组按渲染结构包裹，支持折叠动画 */
  const q = $('#q').value.trim();
  let html = '', curGroup = null, idx = 0;
  const closeGroup = ()=>{ if(curGroup !== null) html += `</div></div></div>`; };  /* inner + body + .group 本体 */
  for(const it of vis){
    idx++;
    if(it.group !== curGroup){
      closeGroup();
      curGroup = it.group;
      const gname = it.group || '未分组';
      const folded = !q && state.collapsed.has(gname);
      const nInGroup = vis.filter(v => v.group === it.group).length;
      html += `<div class="group ${folded?'folded':''}" data-g="${esc(gname)}">
        <div class="group-title" role="button" tabindex="0" aria-expanded="${!folded}">
          <span class="gt-name">${esc(gname)}</span>
          <span class="gt-count">${nInGroup}</span>
          <svg class="gt-chev" viewBox="0 0 24 24" fill="none"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>
        <div class="group-body"><div class="group-inner">`;
    }
    const pos = loadPos(it.id);
    const durTxt = it.dur ? fmt(it.dur) : '·';
    const posTxt = pos > 2 ? fmt(pos) : '';
    html += `<div class="track" data-id="${it.id}" id="tr-${cssId(it.id)}">
      <div class="idx">${idx}</div>
      <div class="meta">
        <div class="t-name">${esc(it.name)}</div>
        <div class="t-sub">${esc(it.group||'')} · ${fmtSize(it.size)} · ${it.ext.toUpperCase()}</div>
      </div>
      <div class="t-dur">${posTxt ? `<span class="t-pos">${posTxt}</span><span class="t-sep">/</span>` : ''}<span class="t-total">${durTxt}</span></div>
    </div>`;
  }
  closeGroup();
  list.innerHTML = html;
  list.querySelectorAll('.track').forEach(el => {
    el.addEventListener('click', () => play(el.dataset.id));
  });
  markPlaying();
}
function cssId(id){ return 'i' + btoa(unescape(encodeURIComponent(id))).replace(/[^a-zA-Z0-9]/g,''); }
function esc(s){ return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function markPlaying(){
  document.querySelectorAll('.track.playing').forEach(el=>el.classList.remove('playing'));
  document.querySelectorAll('.idx.eq').forEach(el=>{el.classList.remove('eq');});
  if(!state.curId) return;
  const el = document.getElementById('tr-'+cssId(state.curId));
  if(el){
    el.classList.add('playing');
    const idx = el.querySelector('.idx');
    if(idx && state.playing){
      idx.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
      idx.classList.add('eq');
    }
  }
}

/* ================= 播放控制 ================= */
function findIdx(id){ return state.items.findIndex(it => it.id === id); }
function nextId(dir){
  /* 切换序列跟随当前过滤结果（用户搜索时，上一首/下一首/自动续播都应在可见集合内走）；
     当前曲目不在过滤集中时（先播后搜），退回全量列表，保证永远有下一步 */
  const seq = visibleItems().length ? visibleItems() : state.items;
  if(seq.length === 0) return null;
  if(state.mode === 'shuffle'){
    if(seq.length === 1) return state.curId;
    let n;
    do { n = seq[Math.floor(Math.random()*seq.length)].id; } while(n === state.curId);
    return n;
  }
  let i = seq.findIndex(it => it.id === state.curId);
  if(i === -1){
    const full = state.items.findIndex(it => it.id === state.curId);
    if(full === -1) return seq[0].id;
    /* 在全量列表有位置但被过滤隐藏：按全量顺序找过滤集中相邻的下一首 */
    const step = dir > 0 ? 1 : -1;
    for(let k = full + step; k >= 0 && k < state.items.length; k += step){
      const hit = seq.find(it => it.id === state.items[k].id);
      if(hit) return hit.id;
    }
    return null;
  }
  const j = i + dir;
  if(j >= seq.length)
    return state.mode === 'loop' ? seq[0].id : null;   // 列表循环：末尾回开头
  if(j < 0) return seq[0].id;
  return seq[j].id;
}
/* ================= 分组折叠/展开 ================= */
function toggleGroup(gEl){
  const gname = gEl.dataset.g;
  gEl.classList.toggle('folded');
  const folded = gEl.classList.contains('folded');
  gEl.querySelector('.group-title').setAttribute('aria-expanded', String(!folded));
  if(folded) state.collapsed.add(gname);
  else state.collapsed.delete(gname);
  localStorage.setItem(LS.col, JSON.stringify([...state.collapsed]));
}
/* 事件委托：组头点击/回车切换（曲目点击照旧走 .track 监听） */
$('#list').addEventListener('click', e=>{
  const gt = e.target.closest('.group-title');
  if(gt && !e.target.closest('.track')) toggleGroup(gt.parentElement);
});
$('#list').addEventListener('keydown', e=>{
  if(e.key !== 'Enter' && e.key !== ' ') return;
  const gt = e.target.closest('.group-title');
  if(gt){ e.preventDefault(); toggleGroup(gt.parentElement); }
});
/* 播放目标在折叠组内时自动展开（自动续播/随机跳进来也要能看到） */
function expandGroupOf(id){
  const it = state.items[findIdx(id)];
  if(!it) return;
  const gname = it.group || '未分组';
  if(!state.collapsed.has(gname)) return;
  state.collapsed.delete(gname);
  localStorage.setItem(LS.col, JSON.stringify([...state.collapsed]));
  const gEl = document.querySelector(`.group[data-g="${CSS.escape(gname)}"]`);
  if(gEl){ gEl.classList.remove('folded'); gEl.querySelector('.group-title').setAttribute('aria-expanded','true'); }
}

function play(id, opts={}){
  const it = state.items[findIdx(id)];
  if(!it){ toast('曲目不存在'); return; }
  expandGroupOf(id);          /* 目标组若折叠先展开，再标记 playing */
  state.curId = id;
  localStorage.setItem(LS.cur, id);
  au.src = it.url;
  const p = loadPos(id);
  if(p > 2 && !opts.fresh) {
    au.currentTime = p;
    toast(`已从上次进度 ${fmt(p)} 继续`);
  }
  attachSub(it);
  au.playbackRate = state.rate;
  state.seeking = false;   /* 切歌即复位拖动状态，防止拖动中切歌后 timeupdate 被永久抑制 */
  au.play().catch(()=>{});
  updateNow(it);
  markPlaying();
}
/* 挂/卸同名字幕 track；subPref=false 时仅移除 active 让浏览器隐藏 */
function attachSub(it){
  const tr = document.getElementById('subTrack');
  if(!it || !it.sub){
    tr.src=''; tr.track.mode='disabled';
    hideSubLine(); updateSubBtn(); return;
  }
  tr.src = it.sub;
  /* forceLoad 先于 mode 切换：避免 disabled→showing 时 track 未加载、
     cuechange 不再触发的浏览器怪癖（表现为点开字幕要刷新页面才有词） */
  if(tr.track.forceLoad) try{ tr.track.forceLoad(); }catch(_){}
  tr.track.mode = state.subOn ? 'showing' : 'disabled';
  if(state.subOn) renderSubLine('');   /* 开字幕即占位，不等首个 cue */
  else hideSubLine();
  updateSubBtn();
}
/* <audio> 不会渲染 cue 画面：监听 cuechange 自绘台词行。
   字幕开 = 固定宽高占位（cue 空档只清文本，防抖动）；字幕关/无字幕 = 收回占位 */
function hideSubLine(){
  const el = document.getElementById('subLine');
  el.hidden = true; el.textContent = '';
}
function renderSubLine(text){
  const el = document.getElementById('subLine');
  el.hidden = false;
  el.textContent = text || '';
  el.scrollTop = 0;
}
function syncSubFromAudio(){
  /* 兜底：从 <audio> 的 TextTrack 反查当前 cue（cuechange 不触发时仍能渲染） */
  const k = au.textTracks.length;
  for(let i=0;i<k;i++){
    const t = au.textTracks[i];
    if(t.kind !== 'subtitles' || t.mode !== 'showing') continue;
    const ac = t.activeCues;
    if(ac && ac.length){ renderSubLine(ac[ac.length-1].text); return true; }
  }
  return false;
}
function bindSubEvents(){
  const tr = document.getElementById('subTrack');
  tr.addEventListener('cuechange', ()=>{
    if(tr.track.mode !== 'showing'){ hideSubLine(); return; }
    const active = tr.track.activeCues;
    if(active && active.length){ renderSubLine(active[active.length-1].text); return; }
    syncSubFromAudio();   /* activeCues 未就绪时兜底 */
  });
  /* timeupdate 兜底轮询：cuechange 漏发/迟到时也能跟上当前台词 */
  au.addEventListener('timeupdate', ()=>{
    if(tr.track.mode !== 'showing') return;
    const el = document.getElementById('subLine');
    if(el.hidden || !el.textContent) syncSubFromAudio();
  });
}
function updateSubBtn(){
  const b = document.getElementById('btnSub');
  const hasSub = state.curId && (state.items[findIdx(state.curId)]||{}).sub;
  b.classList.toggle('act', !!(hasSub && state.subOn));
  b.textContent = hasSub ? (state.subOn ? '字幕开' : '字幕关') : '字幕';
}
function updateNow(it){
  $('#nowTitle').textContent = it.name;
  $('#nowSub').innerHTML = `${esc(it.group||'')} · ${fmtSize(it.size)} · <span id="nowRateTxt">${fmtRate(state.rate)}×</span>`;
  $('#winTitle').textContent = it.name + ' — 音频播放器';
}
function togglePlay(){
  if(!state.curId){
    const vis = visibleItems();
    if(vis.length) play(vis[0].id); else toast('播放列表为空');
    return;
  }
  if(au.paused) au.play().catch(()=>{}); else au.pause();
}
function step(dir){
  const nid = nextId(dir);
  if(!nid){ toast(dir>0 ? '已经是最后一个了' : '已经是第一个了'); return; }
  play(nid);
}
function seekBy(sec){
  if(!isFinite(au.duration)) return;
  au.currentTime = Math.max(0, Math.min(au.duration - 0.5, au.currentTime + sec));
}

/* ================= audio 事件 ================= */
au.addEventListener('play', ()=>{ state.playing=true; document.body.classList.add('playing'); $('#icPlay').style.display='none'; $('#icPause').style.display=''; markPlaying(); });
au.addEventListener('pause', ()=>{ state.playing=false; document.body.classList.remove('playing'); $('#icPlay').style.display=''; $('#icPause').style.display='none'; markPlaying(); savePos(); });
au.addEventListener('loadedmetadata', ()=>{ $('#tDur').textContent = fmt(au.duration); });
au.addEventListener('durationchange', ()=>{ $('#tDur').textContent = fmt(au.duration); });
au.addEventListener('timeupdate', ()=>{
  if(!state.seeking && isFinite(au.duration) && au.duration>0){
    const v = au.currentTime/au.duration;
    $('#seek').value = Math.round(v*1000);
    setV($('#seek'), v);
  }
  $('#tCur').textContent = fmt(au.currentTime);
});
au.addEventListener('ended', ()=>{
  savePos();
  clearPos(state.curId);
  const nid = nextId(1);          /* loop/shuffle/过滤集处理统一收敛到 nextId */
  if(state.mode === 'one'){ au.currentTime=0; au.play().catch(()=>{}); }
  else if(nid) play(nid);
  else { state.playing=false; document.body.classList.remove('playing'); $('#icPlay').style.display=''; $('#icPause').style.display='none'; }
});
au.addEventListener('error', ()=>{ if(state.curId) toast('音频加载失败'); });
/* 兜底：浏览器在换源/元数据加载后可能把 playbackRate 重置回 1，
   只要与记忆值不符立即拉回（防止 UI 显示与实际速率脱节） */
au.addEventListener('ratechange', ()=>{
  if(Math.abs(au.playbackRate - state.rate) > 0.001){
    au.playbackRate = state.rate;
  }
});

/* ================= 进度条 ================= */
const seek = $('#seek');
seek.addEventListener('input', ()=>{
  state.seeking = true;
  const v = seek.value/1000;
  setV(seek, v);
  if(isFinite(au.duration)) $('#tCur').textContent = fmt(v*au.duration);
});
seek.addEventListener('change', ()=>{
  if(isFinite(au.duration)){
    au.currentTime = (seek.value/1000)*au.duration;
    savePos();
  }
  state.seeking = false;
});

/* ================= 倍速 ================= */
state.rate = clampRate(parseFloat(localStorage.getItem(LS.rate)) || 1);
function clampRate(r){
  if(!isFinite(r)) return 1;
  return Math.max(0.1, Math.min(4, r));  // 只夹边界，保留 0.75/1.25 等精确预设
}
function applyRate(r, round){
  state.rate = clampRate(r);
  if(round) state.rate = clampRate(Math.round(state.rate*10)/10);  // 仅微调时取 1 位小数
  localStorage.setItem(LS.rate, String(state.rate));
  au.playbackRate = state.rate;
  $('#btnRate').textContent = fmtRate(state.rate)+"×";
  const rt = document.getElementById('nowRateTxt');
  if(rt) rt.textContent = fmtRate(state.rate)+"×";
  if(popEl && popEl.parentNode) buildRatePop();
}
const PRESETS = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3, 4];
let popEl = null;
function closePop(){
  if(popEl){ popEl.remove(); popEl=null; }
  document.removeEventListener('pointerdown', popOutside);
}
function popOutside(ev){
  if(!popEl) return;
  if(popEl.contains(ev.target)) return;
  if($('#btnRate').contains(ev.target)) return; // 按钮自身走 toggle
  const mb = document.getElementById('mbRate');
  if(mb && mb.contains(ev.target)) return;      // 迷你条倍速按钮同理，否则关不掉
  closePop();
}
function buildRatePop(){
  popEl.innerHTML = `
    <div class="p-title">播放速度 <b id="popCur">${fmtRate(state.rate)}×</b></div>
    <div class="preset-grid">
      ${PRESETS.map(p=>`<button class="pbtn ${p===state.rate?'on':''}" data-p="${p}">${p}</button>`).join('')}
    </div>
    <div class="fine">
      <button id="rMinus">−</button>
      <div class="fval" id="fval">${fmtRate(state.rate)}×</div>
      <button id="rPlus">＋</button>
    </div>
    <div class="hint">0.1 ~ 4.0，步进 0.1</div>`;
  popEl.querySelectorAll('.pbtn').forEach(b=>b.addEventListener('click',()=>{applyRate(parseFloat(b.dataset.p)); closePop();}));
  popEl.querySelector('#rMinus').addEventListener('click',()=>applyRate(state.rate-0.1,true));
  popEl.querySelector('#rPlus').addEventListener('click',()=>applyRate(state.rate+0.1,true));
}
function toggleRatePop(){
  if(popEl){ closePop(); return; }
  popEl = document.createElement('div');
  popEl.className = 'pop';
  document.body.appendChild(popEl);
  buildRatePop();
  const r = $('#btnRate').getBoundingClientRect();
  const pw = 250, ph = 190;
  let left = Math.min(Math.max(8, r.left + r.width/2 - pw/2), innerWidth - pw - 8);
  let top = r.top - ph - 8;
  if(top < 60) top = r.bottom + 8;
  popEl.style.left = left+'px'; popEl.style.top = top+'px';
  document.addEventListener('pointerdown', popOutside);
}
$('#btnRate').addEventListener('click', toggleRatePop);

/* ================= 播放模式 ================= */
const MODES = [
  {k:'seq', label:'顺序', tip:'顺序播放'},
  {k:'loop', label:'循环', tip:'列表循环'},
  {k:'one', label:'单曲', tip:'单曲循环'},
  {k:'shuffle', label:'随机', tip:'随机播放'},
];
function cycleMode(){
  const i = MODES.findIndex(m=>m.k===state.mode);
  const m = MODES[(i+1)%MODES.length];
  state.mode = m.k;
  localStorage.setItem(LS.mode, m.k);
  $('#btnMode').textContent = m.label;
  toast(m.tip);
}
$('#btnMode').addEventListener('click', cycleMode);

/* ================= 定时关闭（弹层：预设 + 自定义分钟） ================= */
const SLEEPS = [5, 10, 15, 30, 60];
let sleepPopEl = null;
function stopSleepTick(){
  if(state.sleepTick){ clearInterval(state.sleepTick); state.sleepTick = null; }
}
function setSleepBtn(txt, act){
  const b = $('#btnSleep');
  b.textContent = txt;
  b.classList.toggle('act', !!act);
}
function startSleepTick(){
  stopSleepTick();
  state.sleepTick = setInterval(()=>{
    const left = state.sleepAt - Date.now();
    if(left <= 0){
      au.pause(); savePos();
      stopSleepTick(); state.sleepAt = 0;
      setSleepBtn('定时', false);
      toast('定时结束，已停止播放');
    } else {
      $('#btnSleep').textContent = Math.ceil(left/60000)+'分';
    }
  }, 5000);
}
/* 预设值（含自定义分钟数）统一入口：mins=0 表示取消定时 */
function applySleep(mins){
  closeSleepPop();
  if(mins === 0 || !isFinite(mins) || mins < 1){
    stopSleepTick(); state.sleepAt = 0;
    setSleepBtn('定时', false);
    toast('已取消定时');
    return;
  }
  mins = Math.min(720, Math.round(mins));   /* 上限 12 小时 */
  state.sleepAt = Date.now() + mins*60*1000;
  setSleepBtn(mins+'分', true);
  toast(`${mins} 分钟后停止播放`);
  startSleepTick();
}
function closeSleepPop(){
  if(sleepPopEl){ sleepPopEl.remove(); sleepPopEl=null; }
  document.removeEventListener('pointerdown', sleepPopOutside);
}
function sleepPopOutside(ev){
  if(!sleepPopEl) return;
  if(sleepPopEl.contains(ev.target)) return;
  if($('#btnSleep').contains(ev.target)) return;
  closeSleepPop();
}
function buildSleepPop(){
  const left = state.sleepAt ? Math.max(0, Math.ceil((state.sleepAt - Date.now())/60000)) : 0;
  sleepPopEl.innerHTML = `
    <div class="p-title">定时停止 <b>${left ? left+'分' : '关'}</b></div>
    <div class="preset-grid sleep-grid">
      ${SLEEPS.map(m=>`<button class="pbtn ${state.sleepAt && left===m ? 'on':''}" data-m="${m}">${m}分</button>`).join('')}
      <button class="pbtn ${!state.sleepAt?'on':''}" data-m="0">关</button>
    </div>
    <div class="fine">
      <input class="custom-min" id="customMin" type="number" inputmode="numeric" min="1" max="720" step="1" placeholder="自定义分钟">
      <button id="sleepGo">设定</button>
    </div>
    <div class="hint">1 ~ 720 分钟</div>`;
  sleepPopEl.querySelectorAll('.pbtn').forEach(b=>b.addEventListener('click',()=>applySleep(parseInt(b.dataset.m,10))));
  const inp = sleepPopEl.querySelector('#customMin');
  const go = ()=>{ const v = parseInt(inp.value,10); if(!isFinite(v)||v<1){ inp.focus(); return; } applySleep(v); };
  sleepPopEl.querySelector('#sleepGo').addEventListener('click', go);
  inp.addEventListener('keydown', e=>{ if(e.key==='Enter'){ e.preventDefault(); go(); } });
  setTimeout(()=>inp.focus(), 30);
}
function toggleSleepPop(){
  if(sleepPopEl){ closeSleepPop(); return; }
  sleepPopEl = document.createElement('div');
  sleepPopEl.className = 'pop sleep-pop';
  document.body.appendChild(sleepPopEl);
  buildSleepPop();
  const r = $('#btnSleep').getBoundingClientRect();
  const pw = 250, ph = 200;
  let left = Math.min(Math.max(8, r.left + r.width/2 - pw/2), innerWidth - pw - 8);
  let top = r.top - ph - 8;
  if(top < 60) top = r.bottom + 8;
  sleepPopEl.style.left = left+'px'; sleepPopEl.style.top = top+'px';
  document.addEventListener('pointerdown', sleepPopOutside);
}
$('#btnSleep').addEventListener('click', toggleSleepPop);
$('#btnSub').addEventListener('click', ()=>{
  const it = state.items[findIdx(state.curId)];
  if(!(it && it.sub)){ toast('当前音频没有字幕'); return; }  /* 无字幕：优先提示，不切换开关 */
  state.subOn = !state.subOn;
  localStorage.setItem(LS.sub, state.subOn ? '1':'0');
  const tr = document.getElementById('subTrack');
  tr.track.mode = state.subOn ? 'showing' : 'disabled';
  if(state.subOn) renderSubLine(''); else hideSubLine();
  updateSubBtn();
  toast(state.subOn ? '字幕已开启' : '字幕已隐藏');
});

/* ================= 恢复上次 ================= */
function restoreLast(){
  const cid = localStorage.getItem(LS.cur);
  if(cid && findIdx(cid) !== -1){
    const it = state.items[findIdx(cid)];
    state.curId = cid;
    au.src = it.url;
    au.playbackRate = state.rate;   // 恢复记忆倍速（否则浏览器默认 1.0，UI 显示与实际不符）
    attachSub(it);
    const p = loadPos(cid);
    $('#tDur').textContent = '';
    updateNow(it);
    markPlaying();
    if(p > 2){
      $('#tCur').textContent = fmt(p);
      au.addEventListener('loadedmetadata', function once(){
        au.removeEventListener('loadedmetadata', once);
        au.currentTime = Math.min(p, Math.max(0, au.duration - 1));
        $('#seek').value = Math.round(au.currentTime/Math.max(1,au.duration)*1000);
        setV($('#seek'), au.currentTime/Math.max(1,au.duration));
      }, {once:true});
    }
  }
}

/* ================= 搜索 ================= */
let qT;
$('#q').addEventListener('input', e=>{
  $('#qclr').hidden = !e.target.value;
  clearTimeout(qT);
  qT = setTimeout(renderList, 160);
});
$('#qclr').addEventListener('click', ()=>{
  $('#q').value=''; $('#qclr').hidden = true; renderList(); $('#q').focus();
});

/* ================= 按钮 ================= */
$('#btnPlay').addEventListener('click', togglePlay);
$('#btnPrev').addEventListener('click', ()=>step(-1));
$('#btnNext').addEventListener('click', ()=>step(1));
$('#btnBack15').addEventListener('click', ()=>seekBy(-15));
$('#btnFwd15').addEventListener('click', ()=>seekBy(15));
document.addEventListener('keydown', e=>{
  if(e.target.tagName === 'INPUT') return;
  if(e.code === 'Space'){ e.preventDefault(); togglePlay(); }
  else if(e.code === 'ArrowLeft') seekBy(-15);
  else if(e.code === 'ArrowRight') seekBy(15);
  else if(e.code === 'ArrowUp'){ applyRate(state.rate + 0.1); toast('倍速 '+fmtRate(state.rate)+"×"); }
  else if(e.code === 'ArrowDown'){ applyRate(state.rate - 0.1); toast('倍速 '+fmtRate(state.rate)+"×"); }
});

/* ================= init ================= */
$('#btnMode').textContent = (MODES.find(m=>m.k===state.mode)||MODES[0]).label;
$('#btnRate').textContent = fmtRate(state.rate)+"×";
bindSubEvents();
updateSubBtn();
boot();

