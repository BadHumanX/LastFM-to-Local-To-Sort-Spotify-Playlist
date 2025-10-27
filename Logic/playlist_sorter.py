import sqlite3

def load_playcounts(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT `Artist`, `Track Title`, `Playcount` FROM scrobbles")
    data = cursor.fetchall()
    conn.close()
    return {(artist.lower(), title.lower()): count for artist, title, count in data}

def extract_tracks_from_playlist(sp, playlist_id):
    tracks = []
    offset = 0
    while True:
        res = sp.playlist_items(playlist_id, offset=offset, fields="items.track(name,artists(name),id),next")
        for item in res["items"]:
            track = item["track"]
            if track:
                artist = track["artists"][0]["name"] if track["artists"] else ""
                tracks.append({
                    "id": track["id"],
                    "artist": artist,
                    "title": track["name"]
                })
        if res["next"] is None:
            break
        offset += len(res["items"])
    return tracks

def sort_tracks_by_playcount(tracks, playcounts, descending=True):
    for t in tracks:
        key = (t["artist"].lower(), t["title"].lower())
        t["playcount"] = playcounts.get(key, 0)
    return sorted(tracks, key=lambda x: x["playcount"], reverse=descending)
