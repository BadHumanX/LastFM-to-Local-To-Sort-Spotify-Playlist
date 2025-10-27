// 📦 DOM References
const playlistsCol = document.getElementById('playlist-buttons');
const searchInput = document.getElementById('playlist-search');
const tracksList = document.getElementById('tracks-list');
const resultList = document.getElementById('result-list');
const applyBtn = document.getElementById('apply-btn');
const optionButtons = document.querySelectorAll('.option-btn');

let currentPlaylistId = null;
let currentTracks = [];
let currentSortedTracks = [];
let currentAction = 'sort_desc';

// 🎯 Render Playlist Buttons (filtered)
function renderPlaylists(filter = "") {
  playlistsCol.innerHTML = '';
  const filtered = playlists.filter(p =>
    p.name.toLowerCase().includes(filter.toLowerCase())
  );
  filtered.forEach(p => {
    const btn = document.createElement('button');
    btn.textContent = p.name;
    btn.onclick = () => selectPlaylist(p.id);
    if (p.id === currentPlaylistId) btn.classList.add('selected');
    playlistsCol.appendChild(btn);
  });
}

// 🔍 Playlist Search Event
searchInput.addEventListener('input', () => {
  renderPlaylists(searchInput.value);
});

// 🎧 Select a Playlist
function selectPlaylist(id) {
  currentPlaylistId = id;
  renderPlaylists(searchInput.value);
  tracksList.innerHTML = '<p>Loading tracks...</p>';
  resultList.innerHTML = '';
  applyBtn.disabled = true;
  fetchTracks(id);
}

// 📡 Fetch Playlist Tracks from Backend
async function fetchTracks(playlistId) {
  try {
    const res = await fetch('/sort_playlist', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({playlist_id: playlistId})
    });
    const data = await res.json();
    currentTracks = data;
    renderTracks(data);
    applySortAction();
  } catch {
    tracksList.innerHTML = '<p style="color:red;">Failed to load tracks</p>';
  }
}

// 🎵 Render Track List
function renderTracks(tracks) {
  tracksList.innerHTML = '';
  tracks.forEach(t => {
    const p = document.createElement('p');
    p.textContent = `${t.artist} - ${t.title} (Playcount: ${t.playcount})`;
    tracksList.appendChild(p);
  });
}

// ⚙️ Apply Selected Sorting Option
function applySortAction() {
  if (!currentTracks.length) {
    resultList.innerHTML = '<p>No tracks to show.</p>';
    applyBtn.disabled = true;
    return;
  }

  let sorted = [...currentTracks];
  switch(currentAction) {
    case 'sort_desc':
      sorted.sort((a, b) => b.playcount - a.playcount);
      break;
    case 'sort_asc':
      sorted.sort((a, b) => a.playcount - b.playcount);
      break;
    // Other cases are placeholders
  }

  currentSortedTracks = sorted;
  renderResult(sorted);
  applyBtn.disabled = false;
}

// 🧾 Render Final Sorted Result
function renderResult(tracks) {
  resultList.innerHTML = '';
  tracks.forEach((t, i) => {
    const p = document.createElement('p');
    p.textContent = `${i + 1}. ${t.artist} - ${t.title} (Playcount: ${t.playcount})`;
    resultList.appendChild(p);
  });
}

// 💾 Apply Sorted Result to Spotify
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

// 🕹 Sort Option Button Logic
optionButtons.forEach(btn => {
  btn.onclick = () => {
    optionButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentAction = btn.dataset.action;
    applySortAction();
  };
});

// 🚀 Initial Load
renderPlaylists();
