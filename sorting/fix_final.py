import re

with open('index.html', 'r', encoding='utf-8') as f:
    text = f.read()

# ─────────────────────────────────────────────────────────────
# 1. REPLACE TRIM OVERLAY HTML with a slider-based version
# ─────────────────────────────────────────────────────────────
old_trim_html = '''<!-- ══════════════ TRIM OVERLAY ══════════════ -->
<div class="overlay" id="trim-overlay">
  <div class="dialog" style="max-width: 500px;">
    <div class="dialog-title" style="color: var(--c-cuts);">✂ Trim Track</div>
    <div class="dialog-body">
      <div id="trim-track-name" class="dialog-fname" style="margin-bottom: 15px; font-size: 12px;"></div>
      <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 15px;">
        <span style="font-family: monospace; font-size: 11px;">Start (s):</span>
        <input type="number" id="trim-start" value="0" step="0.1" min="0" style="width: 70px; background: var(--bg-card); border: 1px solid var(--border-md); color: var(--txt-hi); border-radius: 4px; padding: 4px; outline: none;">
        <span style="font-family: monospace; font-size: 11px; margin-left: 10px;">End (s):</span>
        <input type="number" id="trim-end" value="0" step="0.1" min="0" style="width: 70px; background: var(--bg-card); border: 1px solid var(--border-md); color: var(--txt-hi); border-radius: 4px; padding: 4px; outline: none;">
      </div>
      <div class="card-player" style="background: var(--bg-base); padding: 10px; border-radius: var(--r); border: 1px solid var(--border-md);">
        <button class="btn-play" id="trim-play-btn" title="Play Preview">
          <span class="play-icon">▶</span>
          <span class="eq-bars">
            <span class="eq-bar"></span><span class="eq-bar"></span><span class="eq-bar"></span>
          </span>
        </button>
        <div class="progress-wrap" id="trim-prog-wrap">
          <div class="progress-fill" id="trim-prog-fill"></div>
          <div class="progress-dot" id="trim-prog-dot"></div>
        </div>
        <span class="track-time" id="trim-time">0:00 / 0:00</span>
        <audio id="trim-audio" preload="none"></audio>
      </div>
    </div>
    <div class="dialog-btns">
      <button class="btn-cancel" id="trim-cancel">Cancel</button>
      <button class="btn-del-forever" id="trim-save" style="background: rgba(167,139,250,.1); border-color: var(--c-cuts); color: var(--c-cuts);">Save to Cuts</button>
    </div>
  </div>
</div>'''

new_trim_html = '''<!-- ══════════════ TRIM OVERLAY ══════════════ -->
<div class="overlay" id="trim-overlay">
  <div class="dialog" style="max-width: 560px;">
    <div class="dialog-title" style="color: var(--c-cuts);">✂ Trim Track</div>
    <div class="dialog-body">
      <div id="trim-track-name" class="dialog-fname" style="margin-bottom: 18px; font-size: 12px;"></div>

      <!-- Waveform / progress bar -->
      <div class="card-player" style="background: var(--bg-base); padding: 10px 12px; border-radius: var(--r); border: 1px solid var(--border-md); margin-bottom: 16px;">
        <button class="btn-play" id="trim-play-btn" title="Play Preview">
          <span class="play-icon">▶</span>
          <span class="eq-bars">
            <span class="eq-bar"></span><span class="eq-bar"></span><span class="eq-bar"></span>
          </span>
        </button>
        <div class="progress-wrap" id="trim-prog-wrap">
          <div class="progress-fill" id="trim-prog-fill"></div>
          <div class="progress-dot" id="trim-prog-dot"></div>
        </div>
        <span class="track-time" id="trim-time">0:00 / 0:00</span>
        <audio id="trim-audio" preload="none"></audio>
      </div>

      <!-- Range sliders -->
      <div style="margin-bottom: 14px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
          <label style="font-size:11px; color:var(--txt-mid); font-family:monospace;">▶ Start</label>
          <span id="trim-start-label" style="font-size:12px; font-family:monospace; color:var(--c-cuts);">0:00</span>
        </div>
        <input type="range" id="trim-start" min="0" max="300" step="0.1" value="0"
          style="width:100%; accent-color: var(--c-cuts); cursor:pointer;">
      </div>
      <div style="margin-bottom: 14px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
          <label style="font-size:11px; color:var(--txt-mid); font-family:monospace;">■ End</label>
          <span id="trim-end-label" style="font-size:12px; font-family:monospace; color:var(--txt-hi);">0:00</span>
        </div>
        <input type="range" id="trim-end" min="0" max="300" step="0.1" value="300"
          style="width:100%; accent-color: var(--txt-hi); cursor:pointer;">
      </div>

      <!-- Duration preview -->
      <div style="text-align:center; font-size:11px; color:var(--txt-mid); font-family:monospace; background:var(--bg-base); padding:6px; border-radius:6px; border:1px solid var(--border-md);">
        Clip duration: <span id="trim-duration" style="color:var(--c-cuts); font-weight:600;">0:00</span>
      </div>
    </div>
    <div class="dialog-btns">
      <button class="btn-cancel" id="trim-cancel">Cancel</button>
      <button class="btn-del-forever" id="trim-save" style="background: rgba(167,139,250,.1); border-color: var(--c-cuts); color: var(--c-cuts);">Save to Cuts</button>
    </div>
  </div>
</div>

<!-- ══════════════ LIST OVERLAY ══════════════ -->
<div class="overlay" id="list-overlay">
  <div class="dialog" style="max-width: 640px; max-height: 80vh; display:flex; flex-direction:column;">
    <div class="dialog-title" id="list-overlay-title">Tracks</div>
    <div class="dialog-body" style="flex:1; overflow-y:auto; padding-top:8px;">
      <div id="list-overlay-grid" style="display:flex; flex-direction:column; gap:6px;"></div>
    </div>
    <div class="dialog-btns">
      <button class="btn-cancel" id="btn-close-overlay">Close</button>
    </div>
  </div>
</div>'''

if old_trim_html in text:
    text = text.replace(old_trim_html, new_trim_html)
    print("Trim overlay + list overlay HTML replaced successfully")
else:
    print("ERROR: old_trim_html not found exactly, trying partial approach...")
    # Try matching just the trim-overlay block
    if 'id="trim-overlay"' in text and 'id="list-overlay"' not in text:
        # Insert list-overlay after trim-overlay div closing
        idx = text.find('<!-- ══════════════ UPLOAD OVERLAY ══════════════ -->')
        if idx != -1:
            list_overlay_html = '''
<!-- ══════════════ LIST OVERLAY ══════════════ -->
<div class="overlay" id="list-overlay">
  <div class="dialog" style="max-width: 640px; max-height: 80vh; display:flex; flex-direction:column;">
    <div class="dialog-title" id="list-overlay-title">Tracks</div>
    <div class="dialog-body" style="flex:1; overflow-y:auto; padding-top:8px;">
      <div id="list-overlay-grid" style="display:flex; flex-direction:column; gap:6px;"></div>
    </div>
    <div class="dialog-btns">
      <button class="btn-cancel" id="btn-close-overlay">Close</button>
    </div>
  </div>
</div>

'''
            text = text[:idx] + list_overlay_html + text[idx:]
            print("List overlay HTML added before upload overlay")

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(text)

# ─────────────────────────────────────────────────────────────
# 2. REPLACE TRIM JS LOGIC with slider-based version
# ─────────────────────────────────────────────────────────────
with open('index.html', 'r', encoding='utf-8') as f:
    text = f.read()

old_trim_js = '''// ═══════════════════════════════════════════════════════
// Trim Overlay Logic
// ═══════════════════════════════════════════════════════
const trimOverlay = document.getElementById('trim-overlay');
const trimAudio = document.getElementById('trim-audio');
const trimStart = document.getElementById('trim-start');
const trimEnd = document.getElementById('trim-end');
const trimPlayBtn = document.getElementById('trim-play-btn');
const trimProgFill = document.getElementById('trim-prog-fill');
const trimProgDot = document.getElementById('trim-prog-dot');
const trimTime = document.getElementById('trim-time');
const trimProgWrap = document.getElementById('trim-prog-wrap');

let currentTrimCard = null;
let trimInterval = null;

function openTrimOverlay(card) {
  currentTrimCard = card;
  const audio = card.querySelector('audio');
  document.getElementById('trim-track-name').textContent = card.dataset.filename;
  trimStart.value = "0";
  const endVal = audio.duration ? audio.duration : (parseFloat(card.dataset.duration) || 0);
  trimEnd.value = endVal.toFixed(1);
  trimAudio.src = audio.src || `/audio/${card.dataset.folder}/${encodeURIComponent(card.dataset.filename)}`;
  trimAudio.currentTime = 0;
  trimPlayBtn.classList.remove('is-playing');
  trimProgFill.style.width = '0%';
  trimTime.textContent = `0:00 / ${fmt(parseFloat(trimEnd.value))}`;
  trimOverlay.classList.add('open');
}

trimPlayBtn.addEventListener('click', () => {
  if (trimAudio.paused) {
    trimAudio.currentTime = parseFloat(trimStart.value);
    trimAudio.play();
    trimPlayBtn.classList.add('is-playing');
    trimInterval = setInterval(() => {
      const start = parseFloat(trimStart.value);
      const end = parseFloat(trimEnd.value);
      if (trimAudio.currentTime >= end) {
        trimAudio.pause();
        trimPlayBtn.classList.remove('is-playing');
        clearInterval(trimInterval);
      }
      const dur = end - start;
      const cur = trimAudio.currentTime - start;
      const pct = Math.max(0, Math.min(100, (cur / dur) * 100));
      trimProgFill.style.width = pct + '%';
      trimProgDot.style.right = (100 - pct) + '%';
      trimTime.textContent = `${fmt(cur)} / ${fmt(dur)}`;
    }, 50);
  } else {
    trimAudio.pause();
    trimPlayBtn.classList.remove('is-playing');
    clearInterval(trimInterval);
  }
});

trimProgWrap.addEventListener('click', (e) => {
  const start = parseFloat(trimStart.value);
  const end = parseFloat(trimEnd.value);
  const dur = end - start;
  const r = trimProgWrap.getBoundingClientRect();
  const pct = (e.clientX - r.left) / r.width;
  trimAudio.currentTime = start + pct * dur;
});

document.getElementById('trim-cancel').addEventListener('click', () => {
  trimAudio.pause();
  clearInterval(trimInterval);
  trimOverlay.classList.remove('open');
});

document.getElementById('trim-save').addEventListener('click', async () => {
  trimAudio.pause();
  clearInterval(trimInterval);
  const btn = document.getElementById('trim-save');
  btn.textContent = 'Saving...';
  btn.disabled = true;
  
  try {
    const res = await fetch('/api/trim', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: currentTrimCard.dataset.filename,
        folder: currentTrimCard.dataset.folder,
        start: parseFloat(trimStart.value),
        end: parseFloat(trimEnd.value)
      })
    });
    const data = await res.json();
    if (data.success) {
      toast('Saved to cuts!');
      loadTracks();
      trimOverlay.classList.remove('open');
    } else {
      toast('Error: ' + data.error, 'err');
    }
  } catch (err) {
    toast('Error trimming: ' + err.message, 'err');
  }
  btn.textContent = 'Save to Cuts';
  btn.disabled = false;
});'''

new_trim_js = '''// ═══════════════════════════════════════════════════════
// Trim Overlay Logic (slider-based)
// ═══════════════════════════════════════════════════════
const trimOverlay  = document.getElementById('trim-overlay');
const trimAudio    = document.getElementById('trim-audio');
const trimStart    = document.getElementById('trim-start');
const trimEnd      = document.getElementById('trim-end');
const trimPlayBtn  = document.getElementById('trim-play-btn');
const trimProgFill = document.getElementById('trim-prog-fill');
const trimProgDot  = document.getElementById('trim-prog-dot');
const trimTime     = document.getElementById('trim-time');
const trimProgWrap = document.getElementById('trim-prog-wrap');
const trimStartLbl = document.getElementById('trim-start-label');
const trimEndLbl   = document.getElementById('trim-end-label');
const trimDurLbl   = document.getElementById('trim-duration');

let currentTrimCard = null;
let trimInterval = null;
let trimTotalDur = 0;

function updateTrimLabels() {
  const s = parseFloat(trimStart.value);
  const e = parseFloat(trimEnd.value);
  trimStartLbl.textContent = fmt(s);
  trimEndLbl.textContent = fmt(e);
  const clip = Math.max(0, e - s);
  trimDurLbl.textContent = fmt(clip);
}

function openTrimOverlay(card) {
  currentTrimCard = card;
  const audio = card.querySelector('audio');
  document.getElementById('trim-track-name').textContent = card.dataset.filename;

  trimTotalDur = audio.duration ? audio.duration : (parseFloat(card.dataset.duration) || 300);
  const maxVal = trimTotalDur;

  trimStart.max = maxVal;
  trimEnd.max = maxVal;
  trimStart.value = 0;
  trimEnd.value = maxVal;

  trimAudio.src = audio.src || `/audio/${card.dataset.folder}/${encodeURIComponent(card.dataset.filename)}`;
  trimAudio.currentTime = 0;
  trimPlayBtn.classList.remove('is-playing');
  trimProgFill.style.width = '0%';
  trimTime.textContent = `0:00 / ${fmt(maxVal)}`;
  updateTrimLabels();
  trimOverlay.classList.add('open');

  // Once audio metadata loads, update max values with real duration
  trimAudio.addEventListener('loadedmetadata', function onMeta() {
    trimTotalDur = trimAudio.duration;
    trimStart.max = trimTotalDur;
    trimEnd.max = trimTotalDur;
    trimEnd.value = trimTotalDur;
    trimTime.textContent = `0:00 / ${fmt(trimTotalDur)}`;
    updateTrimLabels();
    trimAudio.removeEventListener('loadedmetadata', onMeta);
  });
}

trimStart.addEventListener('input', () => {
  if (parseFloat(trimStart.value) >= parseFloat(trimEnd.value)) {
    trimStart.value = Math.max(0, parseFloat(trimEnd.value) - 0.1);
  }
  updateTrimLabels();
});

trimEnd.addEventListener('input', () => {
  if (parseFloat(trimEnd.value) <= parseFloat(trimStart.value)) {
    trimEnd.value = Math.min(trimTotalDur, parseFloat(trimStart.value) + 0.1);
  }
  updateTrimLabels();
});

trimPlayBtn.addEventListener('click', () => {
  if (trimAudio.paused) {
    trimAudio.currentTime = parseFloat(trimStart.value);
    trimAudio.play();
    trimPlayBtn.classList.add('is-playing');
    trimInterval = setInterval(() => {
      const start = parseFloat(trimStart.value);
      const end = parseFloat(trimEnd.value);
      if (trimAudio.currentTime >= end) {
        trimAudio.pause();
        trimPlayBtn.classList.remove('is-playing');
        clearInterval(trimInterval);
      }
      const dur = end - start;
      const cur = trimAudio.currentTime - start;
      const pct = Math.max(0, Math.min(100, (cur / dur) * 100));
      trimProgFill.style.width = pct + '%';
      trimProgDot.style.right = (100 - pct) + '%';
      trimTime.textContent = `${fmt(cur)} / ${fmt(dur)}`;
    }, 50);
  } else {
    trimAudio.pause();
    trimPlayBtn.classList.remove('is-playing');
    clearInterval(trimInterval);
  }
});

trimProgWrap.addEventListener('click', (e) => {
  const start = parseFloat(trimStart.value);
  const end = parseFloat(trimEnd.value);
  const dur = end - start;
  const r = trimProgWrap.getBoundingClientRect();
  const pct = (e.clientX - r.left) / r.width;
  trimAudio.currentTime = start + pct * dur;
});

document.getElementById('trim-cancel').addEventListener('click', () => {
  trimAudio.pause();
  clearInterval(trimInterval);
  trimOverlay.classList.remove('open');
});

document.getElementById('trim-save').addEventListener('click', async () => {
  trimAudio.pause();
  clearInterval(trimInterval);
  const btn = document.getElementById('trim-save');
  btn.textContent = 'Saving...';
  btn.disabled = true;
  try {
    const res = await fetch('/api/trim', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: currentTrimCard.dataset.filename,
        folder: currentTrimCard.dataset.folder,
        start: parseFloat(trimStart.value),
        end: parseFloat(trimEnd.value)
      })
    });
    const data = await res.json();
    if (data.success) {
      toast('✓ Saved to Cuts!');
      loadTracks();
      trimOverlay.classList.remove('open');
    } else {
      toast('Error: ' + data.error, 'err');
    }
  } catch (err) {
    toast('Error trimming: ' + err.message, 'err');
  }
  btn.textContent = 'Save to Cuts';
  btn.disabled = false;
});

// ═══════════════════════════════════════════════════════
// List Overlay Logic (Cuts / Redo / Liked / Disliked)
// ═══════════════════════════════════════════════════════
const listOverlay     = document.getElementById('list-overlay');
const listOverlayGrid = document.getElementById('list-overlay-grid');

const LIST_TITLES = {
  redo:     'Redo',
  liked:    'Liked',
  disliked: 'Disliked',
  cuts:     'Cuts'
};
const LIST_COLORS = {
  redo:     'var(--c-redo)',
  liked:    'var(--c-liked)',
  disliked: 'var(--c-disliked)',
  cuts:     'var(--c-cuts)'
};

function openListView(folder) {
  const title = document.getElementById('list-overlay-title');
  title.textContent = LIST_TITLES[folder] || folder;
  title.style.color = LIST_COLORS[folder] || 'var(--txt-hi)';
  listOverlayGrid.innerHTML = '';

  const tracks = window._tracksData ? window._tracksData[folder] : [];
  if (!tracks || tracks.length === 0) {
    const empty = document.createElement('div');
    empty.style.cssText = 'text-align:center; color:var(--txt-dim); padding:30px; font-size:13px;';
    empty.textContent = 'No tracks in this folder';
    listOverlayGrid.appendChild(empty);
  } else {
    tracks.forEach(t => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex; align-items:center; gap:10px; background:var(--bg-card); border:1px solid var(--border-md); border-radius:6px; padding:8px 12px;';
      row.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="${LIST_COLORS[folder]}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
        <span style="flex:1; font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--txt-hi);" title="${t.name}">${t.name}</span>
        <span style="font-family:monospace; font-size:11px; color:var(--txt-mid); white-space:nowrap;">${fmt(t.duration)}</span>
      `;
      listOverlayGrid.appendChild(row);
    });
  }

  listOverlay.classList.add('open');
}

document.getElementById('btn-close-overlay').addEventListener('click', () => {
  listOverlay.classList.remove('open');
  listOverlayGrid.innerHTML = '';
});

// Close list overlay on Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (listOverlay.classList.contains('open')) {
      listOverlay.classList.remove('open');
      listOverlayGrid.innerHTML = '';
    }
  }
});'''

if old_trim_js in text:
    text = text.replace(old_trim_js, new_trim_js)
    print("Trim JS replaced successfully")
else:
    print("ERROR: old_trim_js not found exactly")
    # Check partial
    if "// Trim Overlay Logic" in text:
        print("Found 'Trim Overlay Logic' in text, trying partial replacement...")

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(text)

# ─────────────────────────────────────────────────────────────
# 3. Store tracks data globally so openListView can access it
# ─────────────────────────────────────────────────────────────
with open('index.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Find the loadTracks function and add _tracksData storage
old_store = "const data = await res.json();"
new_store = "const data = await res.json();\n  window._tracksData = data;"

# Only replace first occurrence in loadTracks
idx = text.find("async function loadTracks()")
if idx != -1:
    block = text[idx:idx+500]
    if old_store in block:
        new_block = block.replace(old_store, new_store, 1)
        text = text[:idx] + new_block + text[idx+500:]
        print("Added _tracksData storage in loadTracks")
    else:
        print("WARNING: Could not find data store in loadTracks")

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("All done!")
