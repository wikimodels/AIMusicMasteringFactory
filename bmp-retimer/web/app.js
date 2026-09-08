// BPM Retimer — cards + WaveSurfer waveform + compact trimmer (like LoopGenerator exports)
(function () {
  const $ = (id) => document.getElementById(id);
  const toastEl = $('toast');
  let wavesurfers = [];
  let prevFilesKey = "";
  let prevOutsKey = "";
  // per-card options, survive re-renders, keyed by file rel
  let cardOpts = {};

  function rateLabel(rate, src) {
    const r = Number(rate).toFixed(2) + 'x';
    if (src != null) return r + ' → ' + Math.round(Number(src) * Number(rate)) + ' BPM';
    return r;
  }
  function freqLabel(hz) {
    hz = Number(hz) || 0;
    if (hz <= 0) return 'Выкл';
    return hz >= 1000 ? (hz / 1000).toFixed(1) + ' кГц' : hz + ' Гц';
  }

  function toast(msg, isErr) {
    const icon = isErr ? 'error' : 'check_circle';
    toastEl.innerHTML = `<span class="material-icons">${icon}</span><span>${esc(msg)}</span>`;
    toastEl.classList.remove('hidden');
    toastEl.classList.remove('ok','err');
    toastEl.classList.add(isErr ? 'err' : 'ok');
    clearTimeout(toastEl.__t);
    toastEl.__t = setTimeout(() => toastEl.classList.add('hidden'), isErr ? 4000 : 2500);
  }

  async function api(path, body) {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : '{}',
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || ('HTTP ' + r.status));
    return j;
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g,
      (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function fmtSize(bytes) {
    if (bytes == null) return "—";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + " KB";
    return (bytes/1024/1024).toFixed(1) + " MB";
  }
  function pluralFiles(n){
    const m10=n%10,m100=n%100;
    if(m10===1&&m100!==11) return n+" файл";
    if(m10>=2&&m10<=4&&(m100<10||m100>=20)) return n+" файла";
    return n+" файлов";
  }

  function chipForStatus(s) {
    if (s === "done") return '<span class="chip chip-done">done</span>';
    if (s === "error") return '<span class="chip chip-error">error</span>';
    if (s === "detecting" || s === "stretching" || s === "saving") return '<span class="chip chip-queue">' + esc(s) + '</span>';
    return '<span class="chip chip-queue">' + esc(s) + '</span>';
  }

  let lastConfig = {};
  function fillConfig(cfg) {
    lastConfig = Object.assign({}, cfg);
    $('cfg-input').value = cfg.input || '';
    $('cfg-output').value = cfg.output || '';
    const ct = $('cfg-target'), cs = $('cfg-spread');
    if (ct) ct.value = cfg.target_bpm;
    if (cs) cs.value = cfg.spread;
    $('cfg-workers').value = cfg.workers;
    // modal
    const mIn=$('modal-cfg-input'), mOut=$('modal-cfg-output'), mT=$('modal-cfg-target'), mS=$('modal-cfg-spread'), mW=$('modal-cfg-workers'), mL=$('modal-cfg-low'), mH=$('modal-cfg-high');
    if(mIn) mIn.value = cfg.input || '';
    if(mOut) mOut.value = cfg.output || '';
    if(mT) mT.value = cfg.target_bpm;
    if(mS) mS.value = cfg.spread;
    if(mW) mW.value = cfg.workers;
    if(mL) mL.value = cfg.low_cut ?? 30;
    if(mH) mH.value = cfg.high_cut ?? 3000;
    document.querySelectorAll('.fmt').forEach((c) => {
      c.checked = (cfg.formats || []).includes(c.value);
    });
    document.querySelectorAll('.modal-fmt').forEach((c)=>{
      c.checked = (cfg.formats || []).includes(c.value);
    });
  }

  function stepState(running, phase) {
    const sp = $('btn-stop');
    const showProcess = running && phase === 'process';
    sp.classList.toggle('hidden', !showProcess);
    $('btn-start').disabled = !!running;
  }

  function destroyWavesurfers() {
    wavesurfers.forEach(ws=>{ try{ ws.destroy(); }catch(e){} });
    wavesurfers = [];
  }

  function createWaveSurfer(container, url, onReady) {
    const ws = WaveSurfer.create({
      container,
      waveColor: '#3a415c',
      progressColor: '#7cc4ff',
      cursorColor: '#eef1f8',
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      height: 64,
      normalize: true,
      url: url,
    });
    wavesurfers.push(ws);
    const loading = container.querySelector('.waveform-loading');
    ws.on('ready', () => {
      if (loading) loading.style.display = 'none';
      if (onReady) onReady(ws);
    });
    ws.on('error', (err)=>{
      console.error('WaveSurfer error', url, err);
      if (loading) loading.innerHTML = '<span style="color:var(--err)">Error loading audio</span>';
    });
    ws.on('finish', ()=>{ /* handled per card */ });
    return ws;
  }

  function attachTrimmer(card, ws, filename, isInput) {
    const trimStart = card.querySelector('.trim-start');
    const trimEnd = card.querySelector('.trim-end');
    const btnSaveTrim = card.querySelector('.save-trim-btn');
    const waveformContainer = card.querySelector('.waveform-container');
    if (!trimStart || !trimEnd || !btnSaveTrim || !waveformContainer) return;

    let trimOverlay = waveformContainer.querySelector('.trim-overlay');
    if (!trimOverlay) {
      trimOverlay = document.createElement('div');
      trimOverlay.className = 'trim-overlay';
      trimOverlay.style.cssText = 'position:absolute;inset:0;pointer-events:none;';
      trimOverlay.innerHTML = '<div class="trim-line trim-start-line" style="position:absolute;top:0;bottom:0;width:2px;background:rgba(74,222,128,.9);left:0%"></div><div class="trim-line trim-end-line" style="position:absolute;top:0;bottom:0;width:2px;background:rgba(244,114,182,.9);left:100%"></div>';
      waveformContainer.style.position = 'relative';
      waveformContainer.appendChild(trimOverlay);
    }

    const updateVisual = ()=>{
      let s = parseInt(trimStart.value), e = parseInt(trimEnd.value);
      if (s >= e) {
        if (document.activeElement === trimStart) { e = Math.min(100, s+1); trimEnd.value = e; }
        else { s = Math.max(0, e-1); trimStart.value = s; }
      }
      trimOverlay.querySelector('.trim-start-line').style.left = s + '%';
      trimOverlay.querySelector('.trim-end-line').style.left = e + '%';
    };
    trimStart.addEventListener('input', updateVisual);
    trimEnd.addEventListener('input', updateVisual);

    btnSaveTrim.addEventListener('click', async ()=>{
      const dur = ws.getDuration();
      if (!dur) { toast('Audio not ready', true); return; }
      const sPct = parseInt(trimStart.value)/100, ePct = parseInt(trimEnd.value)/100;
      if (sPct >= ePct) return;
      btnSaveTrim.disabled = true;
      const origHtml = btnSaveTrim.innerHTML;
      btnSaveTrim.innerHTML = '<span class="material-icons" style="font-size:14px;animation:spin 1s linear infinite">sync</span>';
      try {
        const buffer = ws.getDecodedData();
        if (!buffer) throw new Error('No decoded data');
        const sr = buffer.sampleRate;
        const startSample = Math.floor(buffer.length * sPct);
        const endSample = Math.floor(buffer.length * ePct);
        const newLen = endSample - startSample;
        if (newLen <= 0) throw new Error('Invalid trim range');
        const trimmed = new (window.AudioContext || window.webkitAudioContext)().createBuffer(buffer.numberOfChannels, newLen, sr);
        for (let ch=0; ch<buffer.numberOfChannels; ch++) {
          trimmed.getChannelData(ch).set(buffer.getChannelData(ch).subarray(startSample, endSample));
        }
        const wavBlob = await new Promise(resolve=>{
          const worker = new Worker(URL.createObjectURL(new Blob([`
            self.onmessage = e=>{
              const {buf, sr} = e.data;
              const numCh = buf.length;
              const len = buf[0].length;
              const ab = new ArrayBuffer(44 + len * numCh * 2);
              const view = new DataView(ab);
              const writeStr = (off,s)=>{ for(let i=0;i<s.length;i++) view.setUint8(off+i, s.charCodeAt(i)); };
              writeStr(0,'RIFF'); view.setUint32(4, 36 + len * numCh * 2, true); writeStr(8,'WAVE');
              writeStr(12,'fmt '); view.setUint32(16,16,true); view.setUint16(20,1,true);
              view.setUint16(22,numCh,true); view.setUint32(24,sr,true);
              view.setUint32(28, sr * numCh * 2, true); view.setUint16(32, numCh*2, true); view.setUint16(34,16,true);
              writeStr(36,'data'); view.setUint32(40, len * numCh * 2, true);
              let off=44;
              for(let i=0;i<len;i++) for(let ch=0; ch<numCh; ch++){
                let s = Math.max(-1, Math.min(1, buf[ch][i]));
                view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7FFF, true); off+=2;
              }
              self.postMessage(ab, [ab]);
            }
          `], {type:'application/javascript'})));
          const chData = [];
          for(let c=0;c<trimmed.numberOfChannels;c++) chData.push(trimmed.getChannelData(c).slice());
          worker.postMessage({buf: chData, sr}, []);
          worker.onmessage = e=> resolve(new Blob([e.data], {type:'audio/wav'}));
        });
        const endpoint = isInput ? `/api/trim/input/${encodeURIComponent(filename)}` : `/api/trim/output/${encodeURIComponent(filename)}`;
        const res = await fetch(endpoint, { method:'POST', body: wavBlob, headers:{'Content-Type':'audio/wav'} });
        if (!res.ok) throw new Error('Server trim failed');
        await res.json();
        toast('Trim saved');
        trimStart.value = 0; trimEnd.value = 100; updateVisual();
        // reload waveform
        const newUrl = (isInput ? '/audio/input/' : '/audio/output/') + encodeURIComponent(filename) + '?t=' + Date.now();
        ws.load(newUrl);
        // refresh state soon
        setTimeout(()=>refresh(), 800);
      } catch(err){
        console.error('Trim failed', err);
        toast('Trim failed: '+err.message, true);
      } finally {
        btnSaveTrim.disabled = false;
        btnSaveTrim.innerHTML = origHtml;
      }
    });
  }

  function render(state) {
    $('backend').textContent = 'engine: ' + state.backend;
    const rs = $('runstate');
    rs.textContent = state.running ? state.phase + '…' : 'idle';
    rs.className = 'chip ' + (state.running ? 'run' : 'idle');
    stepState(state.running, state.phase);

    // top sticky bar: overall retiming progress (done/total)
    const isProcess = state.running && state.phase === 'process';
    $('overall-fill').style.width = Math.round((isProcess ? state.progress : (state.done / (state.total || 1))) * 100) + '%';
    $('overall-text').textContent = state.done + ' / ' + state.total + ' готово' + (state.errors_count ? ', ошибок: ' + state.errors_count : '');
    // retiming overall
    const retFill = $('retiming-fill'), retText = $('retiming-text');
    if (retFill && retText) {
      retFill.style.width = Math.round((isProcess ? state.progress : (state.done / (state.total||1))) * 100) + '%';
      retText.textContent = state.done + ' / ' + state.total + ' готово';
    }
    $('qcount').textContent = state.total ? '(' + state.total + ')' : '';
    $('ocount').textContent = (state.outputs && state.outputs.length) ? '(' + state.outputs.length + ')' : '';

    // avoid flicker: if file list unchanged, just patch progress/status without recreating waveforms
    const filesKey = JSON.stringify(state.files.map(f=>[f.rel,f.status,Math.round((f.progress||0)*100),f.source_bpm]));
    const outsKey = JSON.stringify((state.outputs||[]).map(o=>o.rel));
    const sameFiles = filesKey === prevFilesKey;
    const sameOuts = outsKey === prevOutsKey;
    if (sameFiles && sameOuts && document.querySelectorAll('.audio-card').length) {
      // patch existing cards
      state.files.forEach(f=>{
        const card = document.querySelector(`.audio-card[data-audio="${f.audio_url}"]`);
        if (!card) return;
        const chip = card.querySelector('.chip');
        if (chip) chip.outerHTML = chipForStatus(f.status);
        const fill = card.querySelector('.audio-card-progress .fill');
        if (fill) fill.style.width = Math.round((f.progress||0)*100)+'%';
        const errEl = card.querySelector('.audio-card-error');
        if (f.error) {
          if (errEl) errEl.textContent = f.error;
          else {
            const div = document.createElement('div');
            div.className = 'audio-card-error';
            div.textContent = f.error;
            card.appendChild(div);
          }
        } else if (errEl) errEl.remove();
      });
      const errs = state.errors || [];
      $('ecount').textContent = errs.length ? '(' + errs.length + ')' : '';
      $('errors').innerHTML = errs.length
        ? errs.slice().reverse().map((e) =>
            '<div class="err-row"><b>' + esc(e.file) + '</b> [' + esc(e.stage) + '] ' + esc(e.error) + '</div>')
          .join('')
        : 'пока чисто';
      $('errors').classList.toggle('muted', !errs.length);
      return;
    }
    prevFilesKey = filesKey;
    prevOutsKey = outsKey;
    destroyWavesurfers();

    // --- input cards ---
    const grid = $('input-cards');
    grid.innerHTML = '';
    if (!state.files.length) {
      grid.innerHTML = '<div class="muted" style="padding:12px">пусто — добавь файлы или положи их в папку input</div>';
    } else {
      state.files.forEach((f, idx)=>{
        const card = document.createElement('div');
        card.className = 'audio-card';
        card.dataset.audio = f.audio_url;
        const defHigh = lastConfig.high_cut ?? 3000;
        const defLow = lastConfig.low_cut ?? 30;
        const opts = cardOpts[f.rel] || (cardOpts[f.rel] = {rate: 1, high: defHigh, low: defLow});
        card.innerHTML = `
          <div class="audio-card-header">
            <button class="btn-play" title="Play / Pause"><span class="material-icons">play_arrow</span></button>
            <button class="btn-stop" title="Stop"><span class="material-icons">stop</span></button>
            <div class="audio-card-title" title="Клик — переименовать" data-kind="input" data-rel="${esc(f.rel)}" data-orig="${esc(f.name)}">${esc(f.name)}</div>
            ${chipForStatus(f.status)}
            <button class="btn-delete" title="Удалить трек" data-del-kind="input" data-del-rel="${esc(f.rel)}"><span class="material-icons">delete</span></button>
          </div>
          <div class="audio-card-meta">
            <span><span class="material-icons" style="font-size:14px;vertical-align:middle">schedule</span> ${esc(f.duration_str||'—')}</span>
            <span>${fmtSize(f.size)}</span>
            ${f.source_bpm!=null?'<span class="chip chip-queue" style="padding:1px 6px;font-size:.7rem"><span class="material-icons" style="font-size:12px;vertical-align:middle">speed</span> '+esc(f.source_bpm)+' BPM</span>':''}
          </div>
          <div class="waveform-container" id="wf-in-${idx}"><div class="waveform-loading"><span class="material-icons" style="font-size:14px;animation:spin 1s linear infinite">sync</span> Loading…</div></div>
          <div class="trimmer-container">
            <span class="material-icons" title="Trim">content_cut</span>
            <input type="range" class="trim-start" min="0" max="100" value="0" title="Start trim">
            <input type="range" class="trim-end" min="0" max="100" value="100" title="End trim">
            <button class="btn small save-trim-btn" style="padding:3px 8px;font-size:11px;white-space:nowrap"><span class="material-icons" style="font-size:14px">save</span></button>
          </div>
          <div class="trimmer-container" title="Скорость воспроизведения и обработки (превью — как магнитофон, с изменением питча)">
            <span class="material-icons" title="Скорость">speed</span>
            <input type="range" class="rate-slider" min="0.5" max="2" step="0.01" value="${opts.rate}" title="Скорость: медленнее ↔ быстрее">
            <span class="rate-label">${rateLabel(opts.rate, f.source_bpm)}</span>
          </div>
          <div class="trimmer-container" title="Срез верхов после растягивания (0 — выкл)">
            <span class="material-icons" title="Срез верхов">filter_alt</span>
            <input type="range" class="freq-slider" min="0" max="20000" step="100" value="${opts.high}" title="Срез верхов, Гц (0 — выкл)">
            <span class="freq-label">${freqLabel(opts.high)}</span>
          </div>
          <div class="trimmer-container" title="Срез низов после растягивания (0 — выкл)">
            <span class="material-icons" title="Срез низов">filter_alt</span>
            <input type="range" class="low-slider" min="0" max="200" step="1" value="${opts.low}" title="Срез низов, Гц (0 — выкл)">
            <span class="low-label">${freqLabel(opts.low)}</span>
          </div>
          <button class="btn btn-primary btn-process" title="Обработать этот трек с выбранной скоростью и срезом">Обработать</button>
          <div class="audio-card-progress"><div class="fill" style="width:${Math.round(f.progress*100)}%"></div></div>
          ${f.error?'<div class="audio-card-error">'+esc(f.error)+'</div>':''}
        `;
        grid.appendChild(card);

        const playBtn = card.querySelector('.btn-play');
        const stopBtn = card.querySelector('.btn-stop');
        const delBtn = card.querySelector('.btn-delete');
        const wfContainer = card.querySelector('.waveform-container');
        const ws = createWaveSurfer(wfContainer, f.audio_url + '?t=' + Date.now());
        try { ws.setPlaybackRate(opts.rate); } catch(e) {}
        ws.on('ready', ()=>{ try { ws.setPlaybackRate(opts.rate); } catch(e) {} });
        const rateSlider = card.querySelector('.rate-slider');
        const rateLbl = card.querySelector('.rate-label');
        rateSlider.addEventListener('input', ()=>{
          opts.rate = parseFloat(rateSlider.value);
          rateLbl.textContent = rateLabel(opts.rate, f.source_bpm);
          try { ws.setPlaybackRate(opts.rate); } catch(e) {}
        });
        const freqSlider = card.querySelector('.freq-slider');
        const freqLbl = card.querySelector('.freq-label');
        freqSlider.addEventListener('input', ()=>{
          opts.high = parseFloat(freqSlider.value);
          freqLbl.textContent = freqLabel(opts.high);
        });
        const lowSlider = card.querySelector('.low-slider');
        const lowLbl = card.querySelector('.low-label');
        lowSlider.addEventListener('input', ()=>{
          opts.low = parseFloat(lowSlider.value);
          lowLbl.textContent = freqLabel(opts.low);
        });
        const procBtn = card.querySelector('.btn-process');
        procBtn.addEventListener('click', async ()=>{
          try{
            const r = await fetch('/api/process_one', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({rel: f.rel, rate: opts.rate, low_cut: opts.low, high_cut: opts.high})});
            const j = await r.json();
            if (!r.ok || !j.ok) throw new Error(j.error||'process failed');
            toast('Обработка запущена' + (j.final_bpm ? ' → ' + j.final_bpm + ' BPM' : ' (' + opts.rate.toFixed(2) + 'x)'), false);
          }catch(e){ toast('Не Ок — '+(e.message||'ошибка'), true); }
        });
        // play/pause
        playBtn.addEventListener('click', ()=> ws.playPause());
        stopBtn.addEventListener('click', ()=> ws.stop());
        if (delBtn) delBtn.addEventListener('click', async ()=>{
          if (!confirm(`Удалить "${f.name}"?`)) return;
          try{
            const r = await fetch('/api/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({kind:'input', rel: f.rel})});
            const j = await r.json();
            if (!r.ok || !j.ok) throw new Error(j.error||'delete failed');
            toast(`Удалено ${pluralFiles(1)}`, false);
            try{ ws.destroy(); }catch(e){}
            await refresh();
          }catch(e){ toast('Не Ок — '+(e.message||'ошибка'), true); }
        });
        ws.on('play', ()=>{
          playBtn.querySelector('.material-icons').textContent = 'pause';
          // pause others
          wavesurfers.forEach(other=>{ if(other!==ws && other.isPlaying()) other.pause(); });
          card.classList.add('playing');
        });
        ws.on('pause', ()=>{
          playBtn.querySelector('.material-icons').textContent = 'play_arrow';
          card.classList.remove('playing');
        });
        ws.on('finish', ()=>{
          playBtn.querySelector('.material-icons').textContent = 'play_arrow';
          ws.stop();
          card.classList.remove('playing');
        });
        ws.on('ready', ()=>{
          const dur = ws.getDuration();
          if (dur) {
            const m = Math.floor(dur/60), s = Math.floor(dur%60).toString().padStart(2,'0');
            // could update duration display if needed
          }
        });

        attachTrimmer(card, ws, f.rel, true);
      });
    }

    // --- output cards ---
    const ogrid = $('output-cards');
    ogrid.innerHTML = '';
    const outs = state.outputs || [];
    if (!outs.length) {
      ogrid.innerHTML = '<div class="muted" style="padding:12px">пока нет готовых файлов — запусти Retiming</div>';
    } else {
      outs.forEach((o, idx)=>{
        const card = document.createElement('div');
        card.className = 'audio-card';
        card.dataset.audio = o.audio_url;
        card.innerHTML = `
          <div class="audio-card-header">
            <button class="btn-play" title="Play / Pause"><span class="material-icons">play_arrow</span></button>
            <button class="btn-stop" title="Stop"><span class="material-icons">stop</span></button>
            <div class="audio-card-title" title="Клик — переименовать" data-kind="output" data-rel="${esc(o.rel)}" data-orig="${esc(o.name)}">${esc(o.name)}</div>
            <span class="chip chip-done">${o.bpm?esc(o.bpm)+' BPM':(o.rate_tag?esc(o.rate_tag):'—')}</span>
            <button class="btn-delete" title="Удалить трек" data-del-kind="output" data-del-rel="${esc(o.rel)}"><span class="material-icons">delete</span></button>
          </div>
          <div class="audio-card-meta">
            <span><span class="material-icons" style="font-size:14px;vertical-align:middle">schedule</span> ${esc(o.duration_str||'—')}</span>
            <span>${fmtSize(o.size)}</span>
          </div>
          <div class="waveform-container" id="wf-out-${idx}"><div class="waveform-loading"><span class="material-icons" style="font-size:14px;animation:spin 1s linear infinite">sync</span> Loading…</div></div>
          <div class="trimmer-container">
            <span class="material-icons" title="Trim">content_cut</span>
            <input type="range" class="trim-start" min="0" max="100" value="0" title="Start trim">
            <input type="range" class="trim-end" min="0" max="100" value="100" title="End trim">
            <button class="btn small save-trim-btn" style="padding:3px 8px;font-size:11px;white-space:nowrap"><span class="material-icons" style="font-size:14px">save</span></button>
          </div>
        `;
        ogrid.appendChild(card);

        const playBtn = card.querySelector('.btn-play');
        const stopBtn = card.querySelector('.btn-stop');
        const delBtn = card.querySelector('.btn-delete');
        const wfContainer = card.querySelector('.waveform-container');
        const ws = createWaveSurfer(wfContainer, o.audio_url + '?t=' + Date.now());
        playBtn.addEventListener('click', ()=> ws.playPause());
        stopBtn.addEventListener('click', ()=> ws.stop());
        if (delBtn) delBtn.addEventListener('click', async ()=>{
          if (!confirm(`Удалить "${o.name}"?`)) return;
          try{
            const r = await fetch('/api/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({kind:'output', rel: o.rel})});
            const j = await r.json();
            if (!r.ok || !j.ok) throw new Error(j.error||'delete failed');
            toast(`Удалено ${pluralFiles(1)}`, false);
            try{ ws.destroy(); }catch(e){}
            await refresh();
          }catch(e){ toast('Не Ок — '+(e.message||'ошибка'), true); }
        });
        ws.on('play', ()=>{
          playBtn.querySelector('.material-icons').textContent = 'pause';
          wavesurfers.forEach(other=>{ if(other!==ws && other.isPlaying()) other.pause(); });
          card.classList.add('playing');
        });
        ws.on('pause', ()=>{
          playBtn.querySelector('.material-icons').textContent = 'play_arrow';
          card.classList.remove('playing');
        });
        ws.on('finish', ()=>{
          playBtn.querySelector('.material-icons').textContent = 'play_arrow';
          ws.stop();
          card.classList.remove('playing');
        });

        attachTrimmer(card, ws, o.rel, false);
      });
    }

    // inline rename — click title -> editable (all files)
    document.querySelectorAll('.audio-card-title').forEach(el=>{
      el.addEventListener('click', ()=>{
        if (el.isContentEditable) return;
        el.contentEditable = 'true';
        el.focus();
        const range = document.createRange();
        range.selectNodeContents(el);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
      });
      const finish = async (doSave)=>{
        if (!el.isContentEditable) return;
        el.contentEditable = 'false';
        const newName = el.textContent.trim();
        const orig = el.dataset.orig || '';
        const rel = el.dataset.rel || '';
        const kind = el.dataset.kind || 'input';
        if (!doSave || !newName || newName === orig) { el.textContent = orig; return; }
        try {
          const r = await fetch('/api/rename', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({kind, rel, newName})});
          const j = await r.json();
          if (!r.ok || !j.ok) throw new Error(j.error || 'rename failed');
          toast('Ок — переименовано', false);
          await refresh();
        } catch(e){
          el.textContent = orig;
          toast('Не Ок — ' + (e.message||'ошибка'), true);
        }
      };
      el.addEventListener('blur', ()=> finish(true));
      el.addEventListener('keydown', (e)=>{
        if (e.key === 'Enter'){ e.preventDefault(); el.blur(); }
        if (e.key === 'Escape'){ el.textContent = el.dataset.orig || ''; finish(false); el.blur(); }
      });
    });

    // wire BPM edit / redetect for input cards (delegated already inside card creation, but need to re-wire after recreation)
    // already attached per card above, but also need to handle input changes that were not per card? Done.

    // For redundancy, wire again for any remaining inputs (in case cards were not created via wavesurfer path)
    grid.querySelectorAll('[data-edit]').forEach(inp=>{
      inp.addEventListener('keydown', async (e)=>{
        if (e.key !== 'Enter') return;
        try {
          await api('/api/override', { id: inp.dataset.edit, bpm: parseFloat(inp.value) });
          toast('BPM сохранён');
          await refresh();
        } catch (err) { toast(String(err.message || err), true); }
      });
    });
    grid.querySelectorAll('[data-redetect]').forEach(btn=>{
      btn.addEventListener('click', async ()=>{
        try { await api('/api/redetect', { id: btn.dataset.redetect }); }
        catch (err) { toast(String(err.message || err), true); }
      });
    });

    const errs = state.errors || [];
    $('ecount').textContent = errs.length ? '(' + errs.length + ')' : '';
    $('errors').innerHTML = errs.length
      ? errs.slice().reverse().map((e) =>
          '<div class="err-row"><b>' + esc(e.file) + '</b> [' + esc(e.stage) + '] ' + esc(e.error) + '</div>')
        .join('')
      : 'пока чисто';
    $('errors').classList.toggle('muted', !errs.length);
  }

  async function refresh() {
    try {
      const r = await fetch('/api/state');
      const j = await r.json();
      render(j);
    } catch (e) { /* restarting — keep view */ }
  }

  function readConfig() {
    const ct = $('cfg-target'), cs = $('cfg-spread');
    return {
      input: $('cfg-input').value.trim(),
      output: $('cfg-output').value.trim(),
      target_bpm: ct ? parseFloat(ct.value) : lastConfig.target_bpm,
      spread: cs ? parseFloat(cs.value) : lastConfig.spread,
      workers: parseInt($('cfg-workers').value, 10),
      formats: Array.from(document.querySelectorAll('.fmt'))
        .filter((c) => c.checked).map((c) => c.value),
    };
  }

  async function init() {
    try {
      const r = await fetch('/api/state');
      fillConfig((await r.json()).config);
      await refresh();
    } catch (e) { toast('Нет связи с сервером', true); }
    setInterval(refresh, 4000);

    $('btn-save').addEventListener('click', async () => {
      try { const j = await api('/api/config', readConfig()); fillConfig(j.config); await refresh(); toast('Пути сохранены'); }
      catch (e) { toast(String(e.message || e), true); }
    });
    $('btn-start').addEventListener('click', async () => {
      try {
        const j = await api('/api/config', readConfig());
        fillConfig(j.config);
        const s = await api('/api/start');
        toast(s.skipped ? 'Start Retiming (пропущено без BPM: ' + s.skipped + ')' : 'Start Retiming');
      } catch (e) { toast(String(e.message || e), true); }
    });
    $('btn-stop').addEventListener('click', async () => {
      try { await api('/api/stop'); toast('Остановка запрошена'); }
      catch (e) { toast(String(e.message || e), true); }
    });

    // Navbar: open folders + add files + clear
    $('btn-open-input').addEventListener('click', async () => {
      try { const j = await api('/api/open_input'); toast('Открыта папка: ' + j.path); }
      catch (e) { toast(String(e.message || e), true); }
    });
    $('btn-open-output').addEventListener('click', async () => {
      try { const j = await api('/api/open_output'); toast('Открыта папка: ' + j.path); }
      catch (e) { toast(String(e.message || e), true); }
    });
    $('btn-clear-input').addEventListener('click', async () => {
      const cfg = await (await fetch('/api/state')).json().then(j=>j.config).catch(()=>null);
      const dir = cfg ? cfg.input : 'input';
      if (!confirm(`Очистить папку INPUT?\n${dir}\nБудут удалены ВСЕ файлы (включая подпапки). Отменить нельзя.`)) return;
      try { const j = await api('/api/clear_input'); toast(`Удалено ${pluralFiles(j.deleted)}`); await refresh(); }
      catch (e) { toast(String(e.message || e), true); }
    });
    $('btn-clear-output').addEventListener('click', async () => {
      const cfg = await (await fetch('/api/state')).json().then(j=>j.config).catch(()=>null);
      const dir = cfg ? cfg.output : 'output';
      if (!confirm(`Очистить папку OUTPUT?\n${dir}\nБудут удалены ВСЕ файлы (включая подпапки). Отменить нельзя.`)) return;
      try { const j = await api('/api/clear_output'); toast(`Удалено ${pluralFiles(j.deleted)}`); await refresh(); }
      catch (e) { toast(String(e.message || e), true); }
    });
    // Config modal (navbar) — все поля + пути
    const cfgModal = $('config-modal');
    const openCfg = ()=>{
      // sync from last known config
      $('modal-cfg-input').value = lastConfig.input || '';
      $('modal-cfg-output').value = lastConfig.output || '';
      $('modal-cfg-target').value = lastConfig.target_bpm;
      $('modal-cfg-spread').value = lastConfig.spread;
      $('modal-cfg-workers').value = lastConfig.workers;
      $('modal-cfg-low').value = lastConfig.low_cut ?? 30;
      $('modal-cfg-high').value = lastConfig.high_cut ?? 3000;
      document.querySelectorAll('.modal-fmt').forEach(c=>{
        c.checked = document.querySelector(`.fmt[value="${c.value}"]`)?.checked || false;
      });
      cfgModal.classList.remove('hidden');
    };
    const closeCfg = ()=> cfgModal.classList.add('hidden');
    $('btn-config')?.addEventListener('click', openCfg);
    $('btn-close-config')?.addEventListener('click', closeCfg);
    $('btn-cancel-config')?.addEventListener('click', closeCfg);
    cfgModal?.addEventListener('click', e=>{ if(e.target===cfgModal) closeCfg(); });
    $('btn-save-config')?.addEventListener('click', async ()=>{
      const payload = {
        input: $('modal-cfg-input').value.trim(),
        output: $('modal-cfg-output').value.trim(),
        target_bpm: parseFloat($('modal-cfg-target').value),
        spread: parseFloat($('modal-cfg-spread').value),
        workers: parseInt($('modal-cfg-workers').value,10),
        low_cut: parseFloat($('modal-cfg-low').value),
        high_cut: parseFloat($('modal-cfg-high').value),
        formats: Array.from(document.querySelectorAll('.modal-fmt')).filter(c=>c.checked).map(c=>c.value),
      };
      try{
        const j = await api('/api/config', payload);
        fillConfig(j.config);
        closeCfg();
        toast('Конфиг сохранён');
        await refresh();
      }catch(e){ toast(String(e.message||e), true); }
    });
    const picker = $('file-picker');
    $('btn-add-files').addEventListener('click', () => picker.click());
    picker.addEventListener('change', async () => {
      if (!picker.files.length) return;
      const fd = new FormData();
      for (const f of picker.files) fd.append('files', f, f.name);
      picker.value = '';
      try {
        const r = await fetch('/api/upload', { method: 'POST', body: fd });
        const j = await r.json();
        if (!r.ok || !j.ok) throw new Error(j.error || ('HTTP ' + r.status));
        const msg = `Добавлено ${pluralFiles(j.saved.length)}`;
        toast(msg, !!(j.errors && j.errors.length));
        await refresh();
      } catch (e) { toast(String(e.message || e), true); }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
