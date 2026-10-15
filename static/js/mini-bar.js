/* 移动端迷你吸附条：整页滚动，滚过播放器高度后顶部滑入控制条（播放/搜索/倍速/切集）。
   仅 ≤899px 生效；桌面 display:none 且逻辑不启用。
   注意：倍速弹层 toggleRatePop() 以 #btnRate 定位，这里直接复用，
   通过临时给 #btnRate 抛 click 即可让弹层定位在原按钮处；为体验更直观，
   顶部条的倍速按钮点击时把弹层定位改为自身位置（toggleRatePop 支持传锚点元素）。 */
(function(){
  'use strict';
  const MOBILE = matchMedia('(max-width: 899px)');
  const bar     = document.getElementById('miniBar');
  const player  = document.querySelector('.player');
  if(!bar || !player) return;

  const $  = s => document.querySelector(s);
  const au = document.getElementById('au');

  /* ---------- 显示/隐藏 ---------- */
  let visible = false, ticking = false;
  function update(){
    ticking = false;
    if(!MOBILE.matches){ setVisible(false); return; }
    const sc = document.scrollingElement || document.documentElement;
    const threshold = player.getBoundingClientRect().bottom + sc.scrollTop - 8;
    setVisible(sc.scrollTop > threshold);
  }
  function setVisible(v){
    if(v === visible) return;
    visible = v;
    bar.classList.toggle('show', v);
    bar.setAttribute('aria-hidden', v ? 'false' : 'true');
  }
  addEventListener('scroll', ()=>{
    if(!ticking){ ticking = true; requestAnimationFrame(update); }
  }, {passive:true});
  MOBILE.addEventListener('change', update);
  update();

  /* ---------- 信息区：标题 + 字幕镜像 ---------- */
  const mbTitle = document.getElementById('mbTitle');
  const mbSub   = document.getElementById('mbSub');
  const mbInfo  = document.getElementById('mbInfo');

  function syncTitle(){
    const it = state.curId ? state.items[findIdx(state.curId)] : null;
    mbTitle.textContent = it ? it.name : '未在播放';
    const has = !!(it && it.sub) && state.subOn;
    mbSub.hidden = !has;
    bar.classList.toggle('tall', has);   /* 有字幕行时迷你条加高，压缩标题字号 */
    if(has) mbSub.textContent = mbSub.textContent || '…';
  }
  function syncSub(text){
    if(mbSub.hidden || text === undefined) return;
    mbSub.textContent = text || '…';
  }
  /* 主字幕行变化 → 镜像到迷你条（文本节点监听，写侧无侵入） */
  const subLine = document.getElementById('subLine');
  new MutationObserver(()=>syncSub(subLine.textContent)).observe(subLine, {childList:true, characterData:true, subtree:true});
  /* 字幕开/关、曲目切换 → 行可见性同步 */
  const subBtn = document.getElementById('btnSub');
  new MutationObserver(syncTitle).observe(subBtn, {childList:true, attributes:true, attributeFilter:['class']});
  document.addEventListener('click', e=>{
    /* 曲目切换时标题会经 updateNow() 变化，这里低频兜底拉取 */
    if(e.target.closest && e.target.closest('.track')) setTimeout(syncTitle, 60);
  }, true);

  mbInfo.addEventListener('click', ()=>{
    const sc = document.scrollingElement || document.documentElement;
    sc.scrollTo({top:0, behavior:'smooth'});
  });
  syncTitle();

  /* ---------- 按钮：与主控制条行为一致 ---------- */
  function fire(sel){
    /* 直接复用主控制条既有处理器：模拟点击，逻辑单点维护 */
    const b = $(sel);
    if(b) b.click();
  }
  function syncPlayIcon(){
    const showing = au.paused;
    bar.querySelectorAll('#mbPlay svg').forEach((svg,i)=>{
      svg.style.display = (i===0) === showing ? '' : 'none';
    });
  }
  au.addEventListener('play',  ()=>syncPlayIcon());
  au.addEventListener('pause', ()=>syncPlayIcon());
  syncPlayIcon();

  document.getElementById('mbPrev').addEventListener('click', ()=>fire('#btnPrev'));
  document.getElementById('mbNext').addEventListener('click', ()=>fire('#btnNext'));
  document.getElementById('mbPlay').addEventListener('click', ()=>{
    if(!au.src){ fire('#btnPlay'); return; }
    if(au.paused) au.play().catch(()=>{}); else au.pause();
  });

  /* ---------- 迷你条搜索：过滤 + 输入后滚回列表区 ---------- */
  const mbq = document.getElementById('mbq');
  const q   = document.getElementById('q');
  let qt;
  mbq.addEventListener('input', ()=>{
    q.value = mbq.value;
    q.dispatchEvent(new Event('input', {bubbles:true}));
    document.getElementById('qclr').hidden = !mbq.value;
    clearTimeout(qt);
    qt = setTimeout(()=>{
      if(MOBILE.matches){
        const sc = document.scrollingElement || document.documentElement;
        const listTop = document.querySelector('.sidebar').getBoundingClientRect().bottom + sc.scrollTop - 60;
        sc.scrollTo({top: listTop, behavior: 'smooth'});
      }
    }, 350);
  });

  /* ---------- 迷你条倍速：复用弹层，锚定在迷你条按钮处 ---------- */
  document.getElementById('mbRate').addEventListener('click', ()=>{
    fire('#btnRate');               /* 打开/关闭既有弹层 */
    if(popEl){
      /* 弹层刚按 #btnRate 定位过，改锚到迷你条按钮正下方 */
      const r = document.getElementById('mbRate').getBoundingClientRect();
      const pw = 250, ph = 190;
      popEl.style.left = Math.min(Math.max(8, r.left + r.width/2 - pw/2), innerWidth - pw - 8) + 'px';
      popEl.style.top  = (r.bottom + 8) + 'px';
    }
  });

  /* 主倍速按钮文本变化时同步迷你条 */
  const btnRate = document.getElementById('btnRate');
  new MutationObserver(()=>{ document.getElementById('mbRate').textContent = btnRate.textContent; })
    .observe(btnRate, {childList:true});
  document.getElementById('mbRate').textContent = btnRate.textContent;
})();
