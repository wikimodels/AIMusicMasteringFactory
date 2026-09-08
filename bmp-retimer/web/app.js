// BPM Retimer — 2-stage flow: 1) Analyse (detect BPM) 2) Set target+spread -> Start Retiming
(function () {
  const $ = (id) => document.getElementById(id);
  const toastEl = $('toast');

  function toast(msg, isErr) {
    toastEl.textContent = msg;
    toastEl.classList.remove('hidden', 'err');
    if (isErr) toastEl.classList.add('err');
    clearTimeout(toastEl.__t);
    toastEl.__t = setTimeout(() => toastEl.classList.add('hidden'), isErr ? 8000 : 3000);
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

  function fillConfig(cfg) {
    $('cfg-input').value = cfg.input || '';
    $('cfg-output').value = cfg.output || '';
    $('cfg-target').value = cfg.target_bpm;
    $('cfg-spread').value = cfg.spread;
    $('cfg-workers').value = cfg.workers;
    document.querySelectorAll('.fmt').forEach((c) => {
      c.checked = (cfg.formats || []).includes(c.value);
    });
  }

  function stepState(running, phase) {
    const s1 = $('st-1'), s2 = $('st-2');
    s1.classList.remove('active', 'done');
    s2.classList.remove('active', 'done');
    if (!running) {
      s1.classList.add('done');
      s2.classList.add('active');
    } else if (phase === 'detect') {
      s1.classList.add('active');
    } else if (phase === 'process') {
      s1.classList.add('done');
      s2.classList.add('active');
    }
    const sd = $('btn-stop-detect'), sp = $('btn-stop');
    const showDetect = running && phase === 'detect';
    const showProcess = running && phase === 'process';
    sd.classList.toggle('hidden', !showDetect);
    sp.classList.toggle('hidden', !showProcess);
    const startBtn = $('btn-start');
    startBtn.disabled = !!running;
    $('btn-detect').disabled = !!running;
  }

  function render(state) {
    $('backend').textContent = 'engine: ' + state.backend;
    const rs = $('runstate');
    rs.textContent = state.running ? state.phase + '…' : 'idle';
    rs.className = 'chip ' + (state.running ? 'run' : 'idle');
    stepState(state.running, state.phase);

    const hint = $('detect-hint');
    if (state.running && state.phase === 'detect') hint.textContent = 'Анализ…';
    else if (!state.files.length) hint.textContent = 'Добавь файлы и запусти анализ';
    else {
      const missing = state.files.filter((f) => f.source_bpm == null).length;
      hint.textContent = missing ? 'Без BPM: ' + missing : 'Готово к ретаймингу — задай целевой BPM и нажми Start Retiming';
    }

    $('overall-fill').style.width = Math.round(state.progress * 100) + '%';
    $('overall-text').textContent =
      state.done + ' / ' + state.total + ' готово' +
      (state.errors_count ? ', ошибок: ' + state.errors_count : '');
    $('qcount').textContent = state.total ? '(' + state.total + ')' : '';

    const tb = $('qbody');
    tb.innerHTML = '';
    if (!state.files.length) {
      tb.innerHTML = '<tr><td colspan="6" class="muted">пусто — добавь файлы или положи их в папку input</td></tr>';
    }
    for (const f of state.files) {
      const tr = document.createElement('tr');
      tr.className = 'st-' + f.status;
      tr.innerHTML =
        '<td title="' + esc(f.rel) + '">' + esc(f.name) + '</td>' +
        '<td>' + esc(f.status) + (f.error ? '<div class="err-text">' + esc(f.error) + '</div>' : '') + '</td>' +
        '<td><input type="number" min="1" step="0.1" value="' + (f.source_bpm == null ? '' : f.source_bpm) +
        '" data-edit="' + esc(f.id) + '" title="Ручной BPM (Enter — сохранить)"></td>' +
        '<td>' + (f.final_bpm == null ? '—' : f.final_bpm) + '</td>' +
        '<td><div class="bar small"><div class="fill" style="width:' +
        Math.round(f.progress * 100) + '%"></div></div></td>' +
        '<td><button class="btn btn-icon" data-redetect="' + esc(f.id) + '" title="Переопределить BPM"><span class="material-icons" style="font-size:18px">refresh</span></button></td>';
      tb.appendChild(tr);
    }
    tb.querySelectorAll('[data-edit]').forEach((inp) => {
      inp.addEventListener('keydown', async (e) => {
        if (e.key !== 'Enter') return;
        try {
          await api('/api/override', { id: inp.dataset.edit, bpm: parseFloat(inp.value) });
          toast('BPM сохранён');
          await refresh();
        } catch (err) { toast(String(err.message || err), true); }
      });
    });
    tb.querySelectorAll('[data-redetect]').forEach((btn) => {
      btn.addEventListener('click', async () => {
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
    return {
      input: $('cfg-input').value.trim(),
      output: $('cfg-output').value.trim(),
      target_bpm: parseFloat($('cfg-target').value),
      spread: parseFloat($('cfg-spread').value),
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
    setInterval(refresh, 1000);

    $('btn-save').addEventListener('click', async () => {
      try { const j = await api('/api/config', readConfig()); fillConfig(j.config); await refresh(); toast('Пути сохранены'); }
      catch (e) { toast(String(e.message || e), true); }
    });
    $('btn-scan').addEventListener('click', async () => {
      try { const j = await api('/api/scan'); render(j); }
      catch (e) { toast(String(e.message || e), true); }
    });
    $('btn-detect').addEventListener('click', async () => {
      try { const j = await api('/api/detect'); toast(j.targets ? 'Анализ запущен: ' + j.targets : 'Все BPM уже определены'); }
      catch (e) { toast(String(e.message || e), true); }
    });
    $('btn-stop-detect').addEventListener('click', async () => {
      try { await api('/api/stop'); toast('Остановка запрошена'); }
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

    // Navbar: open folders + add files
    $('btn-open-input').addEventListener('click', async () => {
      try { const j = await api('/api/open_input'); toast('Открыта папка: ' + j.path); }
      catch (e) { toast(String(e.message || e), true); }
    });
    $('btn-open-output').addEventListener('click', async () => {
      try { const j = await api('/api/open_output'); toast('Открыта папка: ' + j.path); }
      catch (e) { toast(String(e.message || e), true); }
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
        let msg = 'Добавлено: ' + j.saved.join(', ');
        if (j.errors && j.errors.length) msg += ' | ' + j.errors.join('; ');
        toast(msg, !!(j.errors && j.errors.length));
        await refresh();
      } catch (e) { toast(String(e.message || e), true); }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
