import os
import csv
import subprocess
from datetime import datetime
from dotenv import load_dotenv
import pylast
import requests
import sqlite3

# Load Last.fm API credentials from .env
load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")
API_SECRET = os.getenv("LASTFM_API_SECRET")
USERNAME = os.getenv("LASTFM_USERNAME")
PASSWORD_HASH = os.getenv("LASTFM_PASSWORD")

network = pylast.LastFMNetwork(
    api_key=API_KEY,
    api_secret=API_SECRET,
    username=USERNAME,
    password_hash=PASSWORD_HASH
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "DataBases", "All_Scrobble_DataBase.db")

def show_latest_db_played_time():
    if not os.path.exists(DB_PATH):
        print("\n[📅] Database not found.")
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT `Played Time` FROM scrobbles ORDER BY `Played Time` DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            latest_time = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            print("\n[📅] Latest played time in database:")
            print("    " + latest_time.strftime("%d %B %Y  %H:%M"))
    except Exception:
        print("[!] Failed to read latest played time from DB.")

def parse_date_or_datetime(dt_str, is_start=True):
    dt_str = dt_str.strip()
    try:
        dt = datetime.strptime(dt_str, "%d %B %Y %H:%M:%S")
    except ValueError:
        dt = datetime.strptime(dt_str, "%d %B %Y")
        dt = dt.replace(hour=0, minute=1, second=0) if is_start else dt.replace(hour=23, minute=59, second=59)
    return int(dt.timestamp())

def get_time_range_from_user():
    # Automatically select option 3 (Append Newest Duration) without prompting
    if not os.path.exists(DB_PATH):
        print("\n[!] Database not found. Will download all time data.")
        return None, None
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT `Played Time` FROM scrobbles ORDER BY `Played Time` DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            start_ts = int(datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").timestamp()) + 1
            current_ts = int(datetime.now().timestamp())
            print(f"\n[🔄] Automatically fetching new scrobbles since last update")
            print(f"[📅] From: {datetime.fromtimestamp(start_ts).strftime('%d %B %Y %H:%M:%S')}")
            return start_ts, current_ts
            
        print("\n[!] No existing data found. Will download all time data.")
        return None, None
        
    except Exception as e:
        print(f"\n[!] Error reading database: {str(e)}")
        print("[!] Will download all time data.")
        return None, None

def fetch_all_scrobbles(user, time_from=None, time_to=None):
    all_tracks = []
    offset = 0
    limit = 200  # Last.fm API limit per request
    base_url = "https://ws.audioscrobbler.com/2.0/"
    total_tracks = None
    
    while True:
        try:
            params = {
                "method": "user.getRecentTracks",
                "user": user.get_name(),
                "api_key": API_KEY,
                "format": "json",
                "limit": limit,
                "offset": offset,
            }
            if time_from: params["from"] = time_from
            if time_to: params["to"] = time_to

            # Add delay to respect rate limits (5 requests per second)
            if offset > 0:
                import time
                time.sleep(0.25)  # 250ms delay between requests

            resp = requests.get(base_url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            # Get total number of tracks if not already set
            if total_tracks is None:
                total_tracks = int(data["recenttracks"]["@attr"]["total"])
                print(f"\n[📊] Total tracks to fetch: {total_tracks}")
            
            tracks_data = data.get("recenttracks", {}).get("track", [])
            if not tracks_data:
                break
                
            all_tracks.extend(tracks_data)
            
            # Show progress
            progress = min(len(all_tracks), total_tracks)
            print(f"\r[↓] Fetching tracks... {progress}/{total_tracks} ({(progress/total_tracks*100):.1f}%)", end="")
            
            if len(tracks_data) < limit:
                break
                
            offset += limit
            
        except requests.exceptions.RequestException as e:
            print(f"\n[!] Error fetching tracks (offset={offset}): {str(e)}")
            print("[↻] Retrying in 5 seconds...")
            time.sleep(5)
            continue
            
    print("\n[✓] Finished fetching tracks")
    return all_tracks

def process_scrobbles(raw_scrobbles, loved_tracks):
    combined = {}
    for track in raw_scrobbles:
        if not isinstance(track, dict) or "date" not in track or "#text" not in track["date"]:
            continue
        artist = track["artist"]["#text"]
        title = track["name"]
        timestamp = int(track["date"]["uts"])
        played_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        loved = 1 if any(
            lt.track.artist.name == artist and lt.track.title == title
            for lt in loved_tracks
        ) else 0
        key = (artist, title)
        if key not in combined:
            combined[key] = {
                "Played Time": played_time,
                "Artist": artist,
                "Track Title": title,
                "Loved": loved,
                "Playcount": 1
            }
        else:
            combined[key]["Playcount"] += 1
            combined[key]["Played Time"] = max(combined[key]["Played Time"], played_time)
            combined[key]["Loved"] = max(combined[key]["Loved"], loved)
    return list(combined.values())

def save_csv(scrobbles, csv_filename):
    with open(csv_filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Played Time", "Artist", "Track Title", "Loved", "Playcount"])
        writer.writeheader()
        writer.writerows(scrobbles)

def main():
    show_latest_db_played_time()
    time_from, time_to = get_time_range_from_user()

    if time_from and time_to:
        start_str = datetime.fromtimestamp(time_from).strftime("%d %B %Y")
        end_str = datetime.fromtimestamp(time_to).strftime("%d %B %Y")
        csv_filename = f"scrobbles ({start_str} to {end_str}).csv"
    else:
        csv_filename = "scrobbles_all_time.csv"

    user = network.get_user(USERNAME)
    loved_tracks = user.get_loved_tracks()
    raw_scrobbles = fetch_all_scrobbles(user, time_from, time_to)
    final_scrobbles = process_scrobbles(raw_scrobbles, loved_tracks)

    if not final_scrobbles:
        print("[✗] No scrobbles found.")
        return

    save_csv(final_scrobbles, csv_filename)
    print(f"[✓] Saved {len(final_scrobbles)} scrobbles to {csv_filename}")

    subprocess.run(["python", os.path.join(BASE_DIR, "2_CSV_to_DataBase.py"), csv_filename])

if __name__ == "__main__":
    main()