import sys
import os
import sqlite3
import csv
from datetime import datetime
from tqdm import tqdm
from send2trash import send2trash

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "DataBases", "All_Scrobble_DataBase.db")
LOG_DIR = os.path.join(BASE_DIR, "..", "Logs")  # 🔧 Fixed log path

def load_csv(csv_path):
    data = []
    for_time_range = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row["Loved"] = int(row["Loved"])
                row["Playcount"] = int(row["Playcount"])
                row["Played Time"] = row["Played Time"].strip()
                dt = datetime.strptime(row["Played Time"], "%Y-%m-%d %H:%M:%S")
                row["Parsed Time"] = dt
                for_time_range.append(dt)
                data.append(row)
            except (ValueError, KeyError):
                continue
    return data, for_time_range

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scrobbles (
            `Played Time` TEXT,
            `Artist` TEXT,
            `Track Title` TEXT,
            `Loved` INTEGER,
            `Playcount` INTEGER
        );
    """)
    return conn

def fetch_db_data(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT `Played Time`, `Artist`, `Track Title`, `Loved`, `Playcount` FROM scrobbles")
    return cursor.fetchall()

def merge_and_save(csv_data, db_data, conn):
    merged = {}
    new_entries = []
    existing_entries = []

    for row in db_data:
        key = (row[1], row[2])  # (Artist, Track Title)
        merged[key] = {
            "Played Time": row[0],
            "Artist": row[1],
            "Track Title": row[2],
            "Loved": row[3],
            "Playcount": row[4],
        }

    for row in tqdm(csv_data, desc="Merging tracks"):
        key = (row["Artist"], row["Track Title"])
        csv_time = row["Parsed Time"]
        if key not in merged:
            merged[key] = row
            new_entries.append(row)
        else:
            existing_entries.append(row)
            try:
                db_time = datetime.strptime(merged[key]["Played Time"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                db_time = csv_time

            time_diff = abs((csv_time - db_time).total_seconds())
            latest_time = max(csv_time, db_time).strftime("%Y-%m-%d %H:%M:%S")

            merged[key]["Played Time"] = latest_time
            merged[key]["Loved"] = max(merged[key]["Loved"], row["Loved"])
            if time_diff > 60:
                merged[key]["Playcount"] += row["Playcount"]

    cursor = conn.cursor()
    cursor.execute("DELETE FROM scrobbles")
    for row in merged.values():
        cursor.execute("""
            INSERT INTO scrobbles (`Played Time`, `Artist`, `Track Title`, `Loved`, `Playcount`)
            VALUES (?, ?, ?, ?, ?)
        """, (
            row["Played Time"],
            row["Artist"],
            row["Track Title"],
            row["Loved"],
            row["Playcount"]
        ))
    conn.commit()
    return new_entries, existing_entries

def print_latest_played_time(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT `Played Time` FROM scrobbles")
    rows = cursor.fetchall()

    latest = None
    for row in rows:
        try:
            played_time = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            if latest is None or played_time > latest:
                latest = played_time
        except ValueError:
            continue

    if latest:
        print("\n[📅] Latest played time in database:")
        print(latest.strftime("%d %B %Y  %H:%M"))

def write_log(csv_path, new_entries, existing_entries, time_range):
    """Write session log as an HTML file under ./Logs/ folder."""
    log_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Logs")
    os.makedirs(log_root, exist_ok=True)

    now = datetime.now()
    now_str = now.strftime("%d %B %Y %H:%M:%S")
    safe_time = now.strftime("%d %B %Y %H-%M-%S")

    if time_range:
        start = min(time_range).strftime("%d %B %Y")
        end = max(time_range).strftime("%d %B %Y")
        range_label = f"{start} to {end}"
    else:
        range_label = "all time"

    filename = f"Log ({safe_time}) - {range_label}.html"
    log_path = os.path.join(log_root, filename)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Last.fm Merge Log - {range_label}</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; background: #f9f9f9; }}
        h1 {{ color: #333; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
        th {{ background-color: #f0f0f0; }}
        .section {{ margin-top: 30px; }}
    </style>
</head>
<body>
    <h1>🎵 Last.fm Scrobble Merge Log</h1>
    <p><strong>Log created on:</strong> {now_str}</p>
    <p><strong>Time range:</strong> {range_label}</p>

    <div class="section">
        <h2>✅ New Entries Added</h2>
        {"<p>None</p>" if not new_entries else ""}
        <table>
            <tr><th>Played Time</th><th>Artist</th><th>Track Title</th><th>Loved</th></tr>
            {''.join(f"<tr><td>{r['Played Time']}</td><td>{r['Artist']}</td><td>{r['Track Title']}</td><td>{r['Loved']}</td></tr>" for r in new_entries)}
        </table>
    </div>

    <div class="section">
        <h2>♻️ Existing Entries Merged or Skipped</h2>
        {"<p>None</p>" if not existing_entries else ""}
        <table>
            <tr><th>Played Time</th><th>Artist</th><th>Track Title</th><th>Loved</th></tr>
            {''.join(f"<tr><td>{r['Played Time']}</td><td>{r['Artist']}</td><td>{r['Track Title']}</td><td>{r['Loved']}</td></tr>" for r in existing_entries)}
        </table>
    </div>
</body>
</html>
"""

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[📝] Log written to: {log_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python 2_CSV_2_SQLite.py <csv_file>")
        return

    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"[✗] CSV file not found: {csv_path}")
        return

    print(f"[→] Loading CSV: {os.path.basename(csv_path)}")
    csv_data, time_range = load_csv(csv_path)

    print("[→] Connecting to database...")
    conn = connect_db()

    print("[→] Fetching existing data...")
    db_data = fetch_db_data(conn)

    print("[→] Merging and saving to database...")
    new_entries, existing_entries = merge_and_save(csv_data, db_data, conn)

    print_latest_played_time(conn)
    conn.close()

    print("\n[📊] Summary:")
    print(f"   ✅ New entries added: {len(new_entries)}")
    print(f"   ♻️  Existing entries merged/skipped: {len(existing_entries)}")

    write_log(csv_path, new_entries, existing_entries, time_range)

    try:
        send2trash(csv_path)
        print(f"[🗑️] Sent '{os.path.basename(csv_path)}' to trash.")
    except Exception as e:
        print(f"[!] Could not move CSV to trash: {e}")

if __name__ == "__main__":
    main()
