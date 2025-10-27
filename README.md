# Playlist Sorter / Scrobble Tools

A small toolkit and web UI for reordering Spotify playlists based on playcounts built from your Last.fm scrobbles. The repository contains utilities to fetch Last.fm scrobbles, import them into a local SQLite database, and a Flask web UI to reorder Spotify playlists according to playcount data.

## Features

- Fetch Last.fm scrobbles and save to CSV / import into a SQLite database.
- A Flask-based Web UI (`AppEngine/WebUI.py`) to view and reorder your Spotify playlists using Spotipy.
- Logic to extract playlist tracks and sort them by playcount using the `Logic/playlist_sorter.py` module.

## Repository layout

- `AppEngine/`
  - `WebUI.py` — Flask app that serves the web UI and talks to the Spotify API (Spotipy).
  - `1_LastFM_to_CSV.py` — Script to fetch scrobbles from Last.fm and write a CSV.
  - `2_CSV_to_DataBase.py` — Script to import the CSV into the SQLite database (called by `1_LastFM_to_CSV.py`).
- `Logic/`
  - `playlist_sorter.py` — Core logic for extracting tracks from playlists and sorting them using the playcount DB.
- `DataBases/` — Intended location for SQLite DB (e.g. `All_Scrobble_DataBase.db`).
- `Templates/` or `templates/` — HTML templates used by the Flask app (ensure the name matches `WebUI.py` expectations).
- `static/` — Front-end assets (JS/CSS).

## Requirements / Environment

- Python 3.8 or newer (3.9/3.10 recommended)
- pip
- A Spotify Developer application (Client ID, Client Secret, Redirect URI) — for Spotipy OAuth
- Last.fm API credentials (API key/secret) and a Last.fm account

Python packages used by the project (observed in source):

- flask
- spotipy
- python-dotenv
- pylast
- requests

You can install these manually or create a `requirements.txt` containing:

```
flask
spotipy
python-dotenv
pylast
requests
```

And then install with:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

(If you prefer cmd.exe instead of PowerShell, activate with `.\\.venv\\Scripts\\activate`.)

## Environment variables

Create a `.env` file in the project root (same folder as `AppEngine/`) and set the following variables. Example `.env` (DO NOT commit real secrets):

```
# Spotify
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:5000

# Last.fm
LASTFM_API_KEY=your_lastfm_api_key
LASTFM_API_SECRET=your_lastfm_api_secret
LASTFM_USERNAME=your_lastfm_username
LASTFM_PASSWORD=your_lastfm_password_or_hash
```

Notes:
- `SPOTIPY_REDIRECT_URI` must match the redirect URI registered in your Spotify developer dashboard.
- For Last.fm, the existing code expects `LASTFM_PASSWORD` (a password hash) — check `pylast` docs for how to generate a password hash if required.

## Quick setup and run

1. Clone the repo and set up a venv, then install requirements (see earlier commands).
2. Create `.env` with the required credentials.
3. (Optional) Fetch scrobbles from Last.fm and import into the DB:

```powershell
# This will fetch scrobbles and call the CSV->DB importer
python .\AppEngine\1_LastFM_to_CSV.py
```

4. Start the web UI (this will open a browser tab):

```powershell
python .\AppEngine\WebUI.py
```

The Flask app uses Spotipy OAuth — the first run will open a browser to authenticate with Spotify and obtain tokens.

## How it works (brief)

- `1_LastFM_to_CSV.py` pulls recent tracks from Last.fm using `pylast` / web API and writes a CSV.
- `2_CSV_to_DataBase.py` converts the CSV into a local SQLite DB stored in `DataBases/All_Scrobble_DataBase.db`.
- `AppEngine/WebUI.py` uses Spotipy to read a user's playlists, the playlist sorting logic in `Logic/playlist_sorter.py` to compute playcounts per track using the SQLite DB, and then reorders a playlist by replacing items via the Spotify Web API.

## Troubleshooting

- Template path mismatch: The app constructs a `template_dir` relative to `AppEngine/`. If you have a folder named `Templates` (capital T) or `templates` (lowercase), make sure it matches the path expected by `WebUI.py` (the code currently looks for `templates` in the parent directory). On Windows this usually won't break, but it will on case-sensitive deployments (Linux).
- Missing env vars: If the app fails to authenticate, verify `.env` is in the project root and that variables are spelled correctly.
- Database not found: `1_LastFM_to_CSV.py` and the web UI expect the DB at `DataBases/All_Scrobble_DataBase.db`. Make sure `2_CSV_to_DataBase.py` has run successfully and created that file.
- Rate limits: Both Last.fm and Spotify have rate limits. If fetching many items, the scripts use pagination but may still hit limits; retry or throttle as needed.

## Security & privacy

- Keep your `.env` file and API credentials secret. Add `.env` to `.gitignore`.
- The repository may contain local logs in `Logs/` — review for any sensitive information before sharing.

## Next steps / improvements (suggested)

- Add a `requirements.txt` and/or `pyproject.toml` to lock dependencies.
- Add error handling and logging for long-running Last.fm/Spotify operations.
- Add unit tests for `Logic/playlist_sorter.py`.

---

If you want, I can also:
- Create a `requirements.txt` file in the repo.
- Add a sample `.env.example` with placeholders.
- Add a short CONTRIBUTING.md or LICENSE file.

Tell me which you'd like next and I will add them.