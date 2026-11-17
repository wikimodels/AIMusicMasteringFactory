/**
 * Baroque Master Album Dashboard - Client Engine (Dried Minimalist Angular Material)
 */

(() => {
  'use strict';

  // State
  const state = {
    albums: [],
    currentAlbumId: null,
    tracks: [],
    filteredTracks: [],
    currentTrack: null,
    isPlaying: false,
    selectedGenre: 'ALL',
    searchQuery: '',
    deleteTarget: null
  };

  // DOM Elements
  const el = {
    albumList: document.getElementById('albumList'),
    albumSearchInput: document.getElementById('albumSearchInput'),
    genreFilter: document.getElementById('genreFilter'),
    refreshBtn: document.getElementById('refreshBtn'),
    menuToggle: document.getElementById('menuToggle'),
    sidenav: document.getElementById('sidenav'),

    currentAlbumTitle: document.getElementById('currentAlbumTitle'),
    currentAlbumSubtitle: document.getElementById('currentAlbumSubtitle'),
    statTrackCount: document.getElementById('statTrackCount'),
    statDuration: document.getElementById('statDuration'),
    trackGrid: document.getElementById('trackGrid'),
    emptyState: document.getElementById('emptyState'),

    // Audio Engine
    audio: document.getElementById('audioEngine'),

    // Dialog & Snackbar
    deleteDialogBackdrop: document.getElementById('deleteDialogBackdrop'),
    deleteTrackName: document.getElementById('deleteTrackName'),
    targetMp3: document.getElementById('targetMp3'),
    targetMid: document.getElementById('targetMid'),
    targetJson: document.getElementById('targetJson'),
    cancelDeleteBtn: document.getElementById('cancelDeleteBtn'),
    confirmDeleteBtn: document.getElementById('confirmDeleteBtn'),
    snackbar: document.getElementById('snackbar'),
    snackbarIcon: document.getElementById('snackbarIcon'),
    snackbarMessage: document.getElementById('snackbarMessage'),
  };

  // =========================================================================
  // INITIALIZATION
  // =========================================================================
  async function init() {
    setupEventListeners();
    await loadAlbums();

    // Check URL hash for direct album link
    const hash = window.location.hash;
    if (hash && hash.startsWith('#album=')) {
      const targetId = hash.replace('#album=', '');
      const found = state.albums.find(a => a.id === targetId);
      if (found) {
        selectAlbum(targetId);
        return;
      }
    }

    // Default to first album with files, or first album
    if (state.albums.length > 0) {
      const active = state.albums.find(a => a.has_files) || state.albums[0];
      selectAlbum(active.id);
    }
  }

  // =========================================================================
  // EVENT LISTENERS
  // =========================================================================
  function setupEventListeners() {
    // Sidenav Search
    if (el.albumSearchInput) {
      el.albumSearchInput.addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase().trim();
        filterAlbumsList(q);
      });
    }

    // Genre Filter (optional)
    if (el.genreFilter) {
      el.genreFilter.addEventListener('change', (e) => {
        state.selectedGenre = e.target.value;
        applyFilters();
      });
    }

    // Refresh (optional)
    if (el.refreshBtn) {
      el.refreshBtn.addEventListener('click', () => {
        if (state.currentAlbumId) {
          loadTracks(state.currentAlbumId);
          showSnackbar('Обновлен список композиций', 'refresh');
        }
      });
    }

    // Mobile Sidenav Toggle (optional)
    if (el.menuToggle && el.sidenav) {
      el.menuToggle.addEventListener('click', () => {
        el.sidenav.classList.toggle('open');
      });
    }

    // Audio Engine Events
    if (el.audio) {
      el.audio.addEventListener('timeupdate', updateAudioProgress);
      el.audio.addEventListener('ended', playNextTrack);
      el.audio.addEventListener('play', () => setPlayingState(true));
      el.audio.addEventListener('pause', () => setPlayingState(false));
    }

    // Delete Modal
    if (el.cancelDeleteBtn) el.cancelDeleteBtn.addEventListener('click', closeDeleteDialog);
    if (el.deleteDialogBackdrop) {
      el.deleteDialogBackdrop.addEventListener('click', (e) => {
        if (e.target === el.deleteDialogBackdrop) closeDeleteDialog();
      });
    }
    if (el.confirmDeleteBtn) el.confirmDeleteBtn.addEventListener('click', executeDeleteTrack);
  }

  // =========================================================================
  // DATA FETCHING: ALBUMS & TRACKS
  // =========================================================================
  async function loadAlbums() {
    try {
      const res = await fetch('/api/albums');
      const data = await res.json();
      state.albums = data.albums || [];
      renderAlbumsList();
    } catch (err) {
      console.error('Failed to load albums:', err);
      showSnackbar('Ошибка загрузки альбомов', 'error');
    }
  }

  function renderAlbumsList() {
    el.albumList.innerHTML = '';
    if (state.albums.length === 0) {
      el.albumList.innerHTML = '<div class="empty-state"><p>Нет томов</p></div>';
      return;
    }

    state.albums.forEach(album => {
      const item = document.createElement('div');
      item.className = `album-nav-item ${album.id === state.currentAlbumId ? 'active' : ''}`;
      item.dataset.albumId = album.id;

      // Compact layout for 160px width
      item.innerHTML = `
        <div class="album-left-group">
          <span class="material-symbols-outlined album-item-icon">album</span>
          <span class="album-item-title">Том ${String(album.volume).padStart(2, '0')}</span>
        </div>
        <span class="album-count-badge">${album.track_count}</span>
      `;

      item.addEventListener('click', () => {
        selectAlbum(album.id);
        if (window.innerWidth <= 768) {
          el.sidenav.classList.remove('open');
        }
      });

      el.albumList.appendChild(item);
    });
  }

  function filterAlbumsList(q) {
    const items = el.albumList.querySelectorAll('.album-nav-item');
    items.forEach(it => {
      const albumId = it.dataset.albumId;
      const album = state.albums.find(a => a.id === albumId);
      if (!album) return;
      const match = album.title.toLowerCase().includes(q) ||
                    album.key.toLowerCase().includes(q) ||
                    album.id.toLowerCase().includes(q) ||
                    `том ${album.volume}`.includes(q);
      it.style.display = match ? 'flex' : 'none';
    });
  }

  async function selectAlbum(albumId) {
    state.currentAlbumId = albumId;
    window.location.hash = `#album=${albumId}`;

    // Update active highlight in sidenav
    el.albumList.querySelectorAll('.album-nav-item').forEach(it => {
      it.classList.toggle('active', it.dataset.albumId === albumId);
    });

    const album = state.albums.find(a => a.id === albumId);
    if (album) {
      if (el.currentAlbumTitle) el.currentAlbumTitle.textContent = album.title;
      if (el.currentAlbumSubtitle) el.currentAlbumSubtitle.textContent = `${album.key} • 30 треков`;
    }

    await loadTracks(albumId);
  }

  async function loadTracks(albumId) {
    el.trackGrid.innerHTML = `
      <div class="loading-state" style="grid-column: 1 / -1; text-align: center; padding: 40px;">
        <span class="material-symbols-outlined spin" style="font-size: 32px; color: var(--mat-primary);">progress_activity</span>
      </div>
    `;
    el.emptyState.style.display = 'none';

    try {
      const res = await fetch(`/api/tracks?album=${encodeURIComponent(albumId)}`);
      const data = await res.json();
      state.tracks = data.tracks || [];
      applyFilters();
      updateStats();
    } catch (err) {
      console.error('Failed to load tracks:', err);
      el.trackGrid.innerHTML = '';
      el.emptyState.style.display = 'block';
      showSnackbar('Ошибка загрузки треков', 'error');
    }
  }

  function updateStats() {
    if (el.statTrackCount) el.statTrackCount.textContent = state.tracks.length;
    if (el.statDuration) {
      const totalSec = state.tracks.reduce((acc, t) => acc + (t.duration_sec || 0), 0);
      const m = Math.floor(totalSec / 60);
      const s = Math.round(totalSec % 60);
      el.statDuration.textContent = `${m}м ${s}с`;
    }
  }

  function applyFilters() {
    let list = [...state.tracks];

    // Filter by Genre
    if (state.selectedGenre !== 'ALL') {
      list = list.filter(t => t.form_code === state.selectedGenre || t.form_name === state.selectedGenre);
    }

    state.filteredTracks = list;
    renderTrackCards();
  }

  // =========================================================================
  // DRIED TRACK CARDS RENDERING (TITLE + DELETE + AUDIO SCRUBBER PLAYER)
  // =========================================================================
  function renderTrackCards() {
    el.trackGrid.innerHTML = '';

    if (state.filteredTracks.length === 0) {
      el.emptyState.style.display = 'block';
      return;
    }
    el.emptyState.style.display = 'none';

    state.filteredTracks.forEach((track, idx) => {
      const card = document.createElement('div');
      card.className = `mat-card ${state.currentTrack && state.currentTrack.stem === track.stem ? 'is-playing' : ''}`;
      card.id = `card-${track.stem}`;

      const isCurrentPlaying = state.currentTrack && state.currentTrack.stem === track.stem && state.isPlaying;

      // Ultra-dried minimal template: Title + Delete on top, Player below
      card.innerHTML = `
        <!-- Card Header: Title on left, Delete on right -->
        <div class="mat-card-header">
          <h3 class="track-title" title="${escapeHtml(track.stem)}">
            #${String(track.index || idx + 1).padStart(3, '0')} ${escapeHtml(track.form_name || track.form_code || track.stem)}
          </h3>
          <button class="delete-card-btn" title="Удалить композицию (.mp3, .mid, .json)" data-track="${escapeHtml(track.stem)}">
            <span class="material-symbols-outlined">delete_outline</span>
          </button>
        </div>

        <!-- In-Card Audio Player Scrubber -->
        <div class="card-audio-controls">
          <button class="card-play-btn" data-track="${escapeHtml(track.stem)}" aria-label="Play/Pause">
            <span class="material-symbols-outlined">${isCurrentPlaying ? 'pause' : 'play_arrow'}</span>
          </button>
          <div class="card-timeline">
            <div class="card-scrub-bar" data-track="${escapeHtml(track.stem)}">
              <div class="card-scrub-fill" id="fill-${track.stem}"></div>
            </div>
            <div class="card-time-row">
              <span id="cur-${track.stem}">0:00</span>
              <span>${formatTime(track.duration_sec || 35)}</span>
            </div>
          </div>
        </div>
      `;

      // Event: Play/Pause button on card
      const playBtn = card.querySelector('.card-play-btn');
      playBtn.addEventListener('click', () => {
        playTrack(track);
      });

      // Event: In-card scrub bar
      const scrubBar = card.querySelector('.card-scrub-bar');
      scrubBar.addEventListener('click', (e) => {
        if (state.currentTrack && state.currentTrack.stem === track.stem) {
          const rect = scrubBar.getBoundingClientRect();
          const pos = (e.clientX - rect.left) / rect.width;
          el.audio.currentTime = pos * el.audio.duration;
        } else {
          playTrack(track);
        }
      });

      // Event: Delete Button
      const deleteBtn = card.querySelector('.delete-card-btn');
      deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openDeleteDialog(track);
      });

      el.trackGrid.appendChild(card);
    });
  }

  // =========================================================================
  // AUDIO PLAYBACK ENGINE
  // =========================================================================
  function playTrack(track) {
    if (state.currentTrack && state.currentTrack.stem === track.stem) {
      togglePlayPause();
      return;
    }

    state.currentTrack = track;
    const audioUrl = `/api/audio?album=${encodeURIComponent(state.currentAlbumId)}&track=${encodeURIComponent(track.stem)}`;
    el.audio.src = audioUrl;
    el.audio.play().catch(err => console.log('Autoplay blocked:', err));

    updateAllCardPlayStates();
  }

  function togglePlayPause() {
    if (!state.currentTrack) {
      if (state.filteredTracks.length > 0) {
        playTrack(state.filteredTracks[0]);
      }
      return;
    }

    if (el.audio.paused) {
      el.audio.play();
    } else {
      el.audio.pause();
    }
  }

  function setPlayingState(playing) {
    state.isPlaying = playing;
    updateAllCardPlayStates();
  }

  function updateAllCardPlayStates() {
    el.trackGrid.querySelectorAll('.mat-card').forEach(card => {
      const stem = card.id.replace('card-', '');
      const btn = card.querySelector('.card-play-btn span');
      if (state.currentTrack && state.currentTrack.stem === stem) {
        card.classList.add('is-playing');
        if (btn) btn.textContent = state.isPlaying ? 'pause' : 'play_arrow';
      } else {
        card.classList.remove('is-playing');
        if (btn) btn.textContent = 'play_arrow';
      }
    });
  }

  function playNextTrack() {
    if (!state.currentTrack || state.filteredTracks.length === 0) return;
    const curIdx = state.filteredTracks.findIndex(t => t.stem === state.currentTrack.stem);
    const nextIdx = (curIdx + 1) % state.filteredTracks.length;
    playTrack(state.filteredTracks[nextIdx]);
  }

  function updateAudioProgress() {
    if (!el.audio.duration) return;
    const cur = el.audio.currentTime;
    const dur = el.audio.duration;
    const pct = (cur / dur) * 100;

    // Update Active Card timeline
    if (state.currentTrack) {
      const cardFill = document.getElementById(`fill-${state.currentTrack.stem}`);
      const cardCur = document.getElementById(`cur-${state.currentTrack.stem}`);
      if (cardFill) cardFill.style.width = `${pct}%`;
      if (cardCur) cardCur.textContent = formatTime(cur);
    }
  }

  // =========================================================================
  // ATOMIC 3-FILE DELETION (.mp3, .mid, .json)
  // =========================================================================
  function openDeleteDialog(track) {
    state.deleteTarget = track;
    el.deleteTrackName.textContent = track.stem;
    el.targetMp3.textContent = `${track.stem}.mp3 (320 kbps Master Audio)`;
    el.targetMid.textContent = `${track.stem}.mid (Standard MIDI Type 1)`;
    el.targetJson.textContent = `${track.stem}.json (Tone.js Structure & Notes)`;

    el.deleteDialogBackdrop.classList.add('open');
  }

  function closeDeleteDialog() {
    el.deleteDialogBackdrop.classList.remove('open');
    state.deleteTarget = null;
  }

  async function executeDeleteTrack() {
    if (!state.deleteTarget || !state.currentAlbumId) return;

    const track = state.deleteTarget;
    closeDeleteDialog();

    try {
      const res = await fetch(`/api/tracks?album=${encodeURIComponent(state.currentAlbumId)}&track=${encodeURIComponent(track.stem)}`, {
        method: 'DELETE'
      });
      const data = await res.json();

      if (data.success) {
        // If deleted track was playing, stop audio
        if (state.currentTrack && state.currentTrack.stem === track.stem) {
          el.audio.pause();
          el.audio.src = '';
          state.currentTrack = null;
          state.isPlaying = false;
        }

        // Animate card removal
        const card = document.getElementById(`card-${track.stem}`);
        if (card) {
          card.style.transition = 'all 0.25s ease';
          card.style.opacity = '0';
          card.style.transform = 'scale(0.85)';
          setTimeout(() => {
            state.tracks = state.tracks.filter(t => t.stem !== track.stem);
            state.filteredTracks = state.filteredTracks.filter(t => t.stem !== track.stem);
            card.remove();
            updateStats();

            // Update Sidenav count badge
            const navBadge = el.albumList.querySelector(`[data-album-id="${state.currentAlbumId}"] .album-count-badge`);
            if (navBadge) {
              navBadge.textContent = `${state.tracks.length}`;
            }

            if (state.filteredTracks.length === 0) {
              el.emptyState.style.display = 'block';
            }
          }, 250);
        }

        showSnackbar('Трек удалён', 'delete');
      } else {
        showSnackbar(`Ошибка удаления: ${data.error || 'Сбой сервера'}`, 'error');
      }
    } catch (err) {
      console.error('Delete request failed:', err);
      showSnackbar('Сетевая ошибка при удалении', 'error');
    }
  }

  // =========================================================================
  // UTILITIES
  // =========================================================================
  function formatTime(sec) {
    if (!sec || isNaN(sec)) return '0:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  let snackbarTimeout = null;
  function showSnackbar(msg, iconName = 'check_circle') {
    el.snackbarMessage.textContent = msg;
    el.snackbarIcon.textContent = iconName;
    el.snackbarIcon.className = `material-symbols-outlined snackbar-icon ${iconName === 'delete' || iconName === 'error' ? 'warn' : ''}`;
    el.snackbar.classList.add('show');

    if (snackbarTimeout) clearTimeout(snackbarTimeout);
    snackbarTimeout = setTimeout(() => {
      el.snackbar.classList.remove('show');
    }, 2200);
  }

  // Start
  document.addEventListener('DOMContentLoaded', init);
})();
