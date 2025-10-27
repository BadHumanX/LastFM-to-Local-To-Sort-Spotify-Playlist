import os
import sys
import json
from flask import Flask, render_template, request, jsonify
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Include parent directory in sys.path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import playlist logic
from Logic import playlist_sorter

# Load environment variables from .env
load_dotenv()

# Set absolute paths for templates and static folders
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))

# Create Flask app with correct template and static folder paths
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# Setup Spotify client with OAuth
sp = Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="playlist-read-private playlist-modify-private playlist-modify-public"
))

# Path to your SQLite database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "DataBases", "All_Scrobble_DataBase.db"))


def fetch_all_user_playlists(sp, user_id):
    """Fetch all playlists owned by the user with pagination."""
    all_playlists = []
    offset = 0

    while True:
        response = sp.current_user_playlists(limit=50, offset=offset)
        items = response.get("items", [])
        if not items:
            break

        # Filter playlists to only those owned by the current user
        user_playlists = [p for p in items if p.get("owner", {}).get("id") == user_id]
        all_playlists.extend(user_playlists)
        offset += 50

    return all_playlists


@app.route("/")
def index():
    user_id = sp.current_user()["id"]
    playlists_raw = fetch_all_user_playlists(sp, user_id)

    seen_names = set()
    cleaned_playlists = []

    for p in playlists_raw:
        original_name = p["name"]
        playlist_id = p["id"]
        cleaned_name = original_name

        # Example: rename playlists ending with " (2)" to a cleaner format
        if original_name.endswith(" (2)"):
            name_without_suffix = original_name[:-4]
            if name_without_suffix in seen_names:
                cleaned_name = name_without_suffix + " x2"
            else:
                cleaned_name = name_without_suffix

            # Update playlist name on Spotify (optional)
            sp.playlist_change_details(playlist_id, name=cleaned_name)

        seen_names.add(cleaned_name)
        p["name"] = cleaned_name
        cleaned_playlists.append(p)

    # Sort playlists alphabetically by name
    sorted_playlists = sorted(cleaned_playlists, key=lambda x: x["name"].lower())

    return render_template("index.html", playlists=sorted_playlists)


@app.route("/sort_playlist", methods=["POST"])
def sort_playlist():
    playlist_id = request.json.get("playlist_id")

    tracks = playlist_sorter.extract_tracks_from_playlist(sp, playlist_id)
    playcounts = playlist_sorter.load_playcounts(DB_PATH)
    sorted_tracks = playlist_sorter.sort_tracks_by_playcount(tracks, playcounts, descending=True)

    return jsonify(sorted_tracks)


@app.route("/apply_sort", methods=["POST"])
def apply_sort():
    playlist_id = request.json.get("playlist_id")
    track_ids = request.json.get("track_ids")

    if not playlist_id or not track_ids:
        return jsonify({"status": "error", "message": "Missing data"}), 400

    # Replace playlist contents in batches of 100 (Spotify limit)
    sp.playlist_replace_items(playlist_id, track_ids[:100])
    for i in range(100, len(track_ids), 100):
        sp.playlist_add_items(playlist_id, track_ids[i:i + 100])

    return jsonify({"status": "success", "message": "Playlist reordered!"})


if __name__ == "__main__":
    import webbrowser
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=False)
