import csv, os, sys

MUSIC_DIR = r"C:\Users\noahx\Music\iPod"
PLAYLIST_DIR = os.path.join(MUSIC_DIR, "Playlists")

def sanitize(s):
    for c in r'\/:*?"<>|':
        s = s.replace(c, "-")
    return s.strip()

def find_track(artist, album, title):
    artist_dir = os.path.join(MUSIC_DIR, sanitize(artist))
    album_dir = os.path.join(artist_dir, sanitize(album))
    if not os.path.isdir(album_dir):
        return None
    try:
        dir_files = os.listdir(album_dir)
    except OSError:
        return None
    for f in dir_files:
        if sanitize(title).lower() in f.lower() and f.endswith(".mp3"):
            return os.path.join(album_dir, f)
    return None

csv_file = sys.argv[1]
playlist_name = os.path.splitext(os.path.basename(csv_file))[0]

with open(csv_file, encoding="utf-8-sig") as f:
    tracks = list(csv.DictReader(f))

os.makedirs(PLAYLIST_DIR, exist_ok=True)
out_path = os.path.join(PLAYLIST_DIR, playlist_name + ".m3u8")

found, missing = [], []
for row in tracks:
    artist = row["Artist Name(s)"].split(";")[0]
    album = row["Album Name"]
    title = row["Track Name"]
    path = find_track(artist, album, title)
    if path:
        # Convert to iPod-relative path (Unix style from /Music/...)
        rel = path.replace(MUSIC_DIR, "").replace("\\", "/")
        found.append((row["Track Name"], rel))
    else:
        missing.append(f"{artist} - {title}")

with open(out_path, "w", encoding="utf-8") as f:
    for title, rel in found:
        f.write(f"/<HDD0>/Music{rel}\n")

print(f"Playlist written: {out_path}")
print(f"  {len(found)} tracks included")
if missing:
    print(f"  {len(missing)} not found (not downloaded yet):")
    for m in missing:
        print(f"    - {m}")
