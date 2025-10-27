// script.js

const playlistsCol = document.getElementById('playlists-column');
const tracksList = document.getElementById('tracks-list');
const resultList = document.getElementById('result-list');
const applyBtn = document.getElementById('apply-btn');
const optionButtons = document.querySelectorAll('.option-btn');

let playlists = window.playlistsData || [];  // Passed from Flask
let currentPlaylistId = null;
let currentTracks = [];
let currentSortedTracks = [];
let currentAction = 'sort_desc';

let playlistDataCache = {};

function renderPlaylists() {
  playlistsCol.innerHTML = '';
  playlists.forEach(p => {
    const btn = document.createElement('button');
    btn.textContent = p.name;
    btn.onclick = () => selectPlaylist(p.id);
    btn.className = (p.id === currentPlaylistId) ? 'selected' : '';
    playlistsCol.appendChild(btn);
  });
}

async function selectPlaylist(id) {
  currentPlaylistId = id;
  renderPlaylists();
  if (playlistDataCache[id]) {
    currentTracks = playlistDataCache[id];
    renderTracks(currentTracks);
    applySortAction();
  } else {
    tracksList.innerHTML = '<p>Loading tracks...</p>';
    resultList.innerHTML = '';
    applyBtn.disabled = true;

    try {
      const res = await fetch('/sort_playlist', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({playlist_id: id})
      });
      const data = await res.json();
      currentTracks = data;
      playlistDataCache[id] = data;
      renderTracks(data);
      applySortAction();
    } catch {
      tracksList.innerHTML = '<p style="color:red;">Failed to load tracks</p>';
    }
  }
}

function renderTracks(tracks) {
  tracksList.innerHTML = '';
  tracks.forEach(t => {
    const p = document.createElement('p');
    p.textContent = `${t.artist} - ${t.title} (Playcount: ${t.playcount})`;
    tracksList.appendChild(p);
  });
}

function applySortAction() {
  if (!currentTracks.length) {
    resultList.innerHTML = '<p>No tracks to show.</p>';
    applyBtn.disabled = true;
    return;
  }
  let sorted = [...currentTracks];
  switch(currentAction) {
    case 'sort_desc':
      sorted.sort((a,b) => b.playcount - a.playcount);
      break;
    case 'sort_asc':
      sorted.sort((a,b) => a.playcount - b.playcount);
      break;
    case 'dedupe':
    case 'sort_loved':
    case 'sort_recent':
      // placeholders - no sorting yet
      break;
  }
  currentSortedTracks = sorted;
  renderResult(sorted);
  applyBtn.disabled = false;
}

function renderResult(tracks) {
  resultList.innerHTML = '';
  tracks.forEach((t,i) => {
    const p = document.createElement('p');
    p.textContent = `${i+1}. ${t.artist} - ${t.title} (Playcount: ${t.playcount})`;
    resultList.appendChild(p);
  });
}

applyBtn.onclick = async () => {
  if (!currentPlaylistId || !currentSortedTracks.length) return;
  applyBtn.disabled = true;
  try {
    const res = await fetch('/apply_sort', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        playlist_id: currentPlaylistId,
        track_ids: currentSortedTracks.map(t => t.id)
      })
    });
    const json = await res.json();
    alert(json.message);
  } catch {
    alert('Failed to apply sorted order');
  } finally {
    applyBtn.disabled = false;
  }
};

optionButtons.forEach(btn => {
  btn.onclick = () => {
    optionButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentAction = btn.dataset.action;
    applySortAction();
  };
});

// Initial render
renderPlaylists();
