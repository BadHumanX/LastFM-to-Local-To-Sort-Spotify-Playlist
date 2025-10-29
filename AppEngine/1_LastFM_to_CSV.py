import os
import csv
import subprocess
from datetime import datetime, timedelta
import time
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

if not all([API_KEY, API_SECRET, USERNAME]):
    print("[!] Missing Last.fm API credentials in .env file")
    print("Required variables: LASTFM_API_KEY, LASTFM_API_SECRET, LASTFM_USERNAME")
    input("Press Enter to exit...")
    exit(1)

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

def get_next_time_range():
    """Get the next 24-hour range that needs to be fetched."""
    if not os.path.exists(DB_PATH):
        print("\n[!] Database not found. Will start from last 24 hours.")
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=24)
        return int(start_date.timestamp()), int(end_date.timestamp()), None
    
    try:
        current_time = datetime.now()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT `Played Time` FROM scrobbles ORDER BY `Played Time` DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            # Get the timestamp of the last update
            last_update = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            
            # If last update is less than 5 minutes old, we're done
            time_diff = (current_time - last_update).total_seconds()
            if time_diff < 300:  # 5 minutes
                print(f"\n[✨] Database is up to date! Last update was {int(time_diff)} seconds ago.")
                return None, None, last_update
            
            # Start from the last update timestamp
            start_date = last_update
            
            # Calculate end date (24 hours after start or current time if sooner)
            end_date = min(start_date + timedelta(hours=24), current_time)
            
            # If we've caught up to current time, we're done
            if end_date >= current_time:
                print(f"\n[✨] Database is up to date! Last update: {last_update.strftime('%Y-%m-%d %H:%M:%S')}")
                return None, None, last_update
            
            return int(start_date.timestamp()), int(end_date.timestamp()), last_update
            
        print("\n[!] No existing data found. Will start from today and work backwards.")
        end_date = datetime.now().replace(hour=23, minute=59, second=59)
        start_date = end_date.replace(hour=0, minute=0, second=0)
        return int(start_date.timestamp()), int(end_date.timestamp()), None
        
    except Exception as e:
        print(f"\n[!] Error reading database: {str(e)}")
        return None, None, None

def fetch_all_scrobbles(user, time_from=None, time_to=None):
    all_tracks = []
    offset = 0
    limit = 200  # Last.fm API limit per request
    base_url = "https://ws.audioscrobbler.com/2.0/"
    total_tracks = None
    
    # Rate limiting settings
    requests_per_minute = 180  # Last.fm limit is 200/minute, staying just under it
    delay_between_requests = 60 / requests_per_minute  # ~0.33 seconds between requests
    
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

            # Add delay to respect rate limits
            if offset > 0:
                time.sleep(delay_between_requests)

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
            # If we've already fetched all expected tracks, break out of the loop
            if total_tracks is not None and len(all_tracks) >= total_tracks:
                print("[✓] All expected tracks fetched. Moving on.")
                break
            print("[↻] Retrying in 5 seconds...")
            time.sleep(5)
            continue
            
    print("\n[✓] Finished fetching tracks")
    return all_tracks

def process_scrobbles(raw_scrobbles, loved_tracks=None):
    print("\n[🔄] Processing scrobbles...")
    combined = {}
    total = len(raw_scrobbles)
    try:
        for i, track in enumerate(raw_scrobbles, 1):
            try:
                if not isinstance(track, dict):
                    print(f"\n[!] Invalid track format at index {i}")
                    continue
                if "date" not in track or "#text" not in track["date"]:
                    print(f"\n[!] Missing date information at index {i}")
                    continue
                if "artist" not in track or "#text" not in track["artist"]:
                    print(f"\n[!] Missing artist information at index {i}")
                    continue
                if "name" not in track:
                    print(f"\n[!] Missing track name at index {i}")
                    continue

                artist = track["artist"]["#text"]
                title = track["name"]
                timestamp = int(track["date"]["uts"])
                played_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

                # Show progress more frequently
                if i % 50 == 0 or i == total:
                    print(f"\r[🔄] Processing tracks... {i}/{total} ({(i/total*100):.1f}%)", end="", flush=True)

                # Process loved status
                if loved_tracks is not None:
                    try:
                        loved = 1 if any(
                            lt.track.artist.name == artist and lt.track.title == title
                            for lt in loved_tracks
                        ) else 0
                    except Exception as e:
                        print(f"\n[!] Error checking loved status: {str(e)}")
                        loved = 0
                else:
                    loved = 0

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

            except Exception as e:
                print(f"\n[!] Error processing track at index {i}: {str(e)}")
                continue

        print("\n[✓] Processing completed successfully")
        return list(combined.values())

    except Exception as e:
        print(f"\n[!] Critical error during processing: {str(e)}")
        if combined:
            print("[ℹ️] Returning partial results")
            return list(combined.values())
        raise

def save_csv(scrobbles, csv_filename):
    print(f"\n[💾] Saving {len(scrobbles)} tracks to CSV file...")
    with open(csv_filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Played Time", "Artist", "Track Title", "Loved", "Playcount"])
        writer.writeheader()
        writer.writerows(scrobbles)
    print(f"[✓] CSV file saved: {csv_filename}")

def main():
    show_latest_db_played_time()
    user = network.get_user(USERNAME)
    
    # Try to get loved tracks once at the start
    try:
        print("[❤️] Fetching loved tracks...")
        loved_tracks = user.get_loved_tracks()
        print("[✓] Loved tracks fetched successfully")
    except Exception as e:
        print("[!] Could not fetch loved tracks. Will continue without loved status.")
        print(f"[!] Error: {str(e)}")
        loved_tracks = None

    while True:
        # Get the next 24-hour range to process
        start_ts, end_ts, last_update = get_next_time_range()
        
        # If no more time ranges to process, we're done
        if start_ts is None or end_ts is None:
            if last_update:
                print(f"\n[✨] Database is up to date! Last update: {last_update.strftime('%d %B %Y %H:%M:%S')}")
            else:
                print("\n[!] Could not determine time range to update.")
            return
        
        # Show what day we're processing
        day_str = datetime.fromtimestamp(start_ts).strftime("%d %B %Y")
        print(f"\n[📅] Processing scrobbles for: {day_str}")
        
        raw_scrobbles = fetch_all_scrobbles(user, start_ts, end_ts)
        if raw_scrobbles:
            final_scrobbles = process_scrobbles(raw_scrobbles, loved_tracks)
            
            if final_scrobbles:
                csv_filename = f"scrobbles ({day_str}).csv"
                save_csv(final_scrobbles, csv_filename)
                
                print("\n[📥] Updating database...")
                subprocess.run(["python", os.path.join(BASE_DIR, "2_CSV_to_DataBase.py"), csv_filename])
                print(f"[✓] Added {len(final_scrobbles)} tracks for {day_str}")
            else:
                print(f"[ℹ️] No valid scrobbles found for {day_str}")
        else:
            print(f"[ℹ️] No scrobbles found for {day_str}")
        
        # Small delay between days to avoid API issues
        DELAY_BETWEEN_DAYS = 3  # 3 seconds between days
        print(f"\n[⏳] Brief pause before next day", end="")
        for i in range(DELAY_BETWEEN_DAYS):
            time.sleep(1)
            print(".", end="", flush=True)
        print()
    
    print("\n[✨] Update process completed!")

if __name__ == "__main__":
    main()