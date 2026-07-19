import csv, os, subprocess, sys
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, TPE2, ID3NoHeaderError

CLIENT_ID = "dbb786fb7b6e49d9a99640fd5a759a1a"
CLIENT_SECRET = "558f2974c67b44d29afa3f1921d0a76a"
OUTPUT_DIR = r"C:\Users\noahx\Music\iPod"
CSV_FILE = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\noahx\Music\iPod\june26.csv"
YTDLP = r"C:\Users\noahx\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.yt-dlp_Microsoft.Winget.Source_8wekyb3d8bbwe\yt-dlp.exe"

def sanitize(s):
    for c in r'\/:*?"<>|':
        s = s.replace(c, "-")
    return s.strip()

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=CLIENT_ID, client_secret=CLIENT_SECRET
))

with open(CSV_FILE, encoding="utf-8-sig") as f:
    tracks = list(csv.DictReader(f))

print(f"Downloading {len(tracks)} tracks...\n")
failed = []

for i, row in enumerate(tracks):
    track_id = row["Track URI"].split(":")[-1]

    try:
        info = sp.track(track_id)
    except Exception as e:
        print(f"[{i+1}/{len(tracks)}] SPOTIFY ERROR: {e}")
        failed.append(row["Track Name"])
        continue

    artist = info["artists"][0]["name"]
    album = info["album"]["name"]
    title = info["name"]
    track_num = info["track_number"]
    album_artist = info["album"]["artists"][0]["name"]

    print(f"[{i+1}/{len(tracks)}] {artist} - {title}")

    out_dir = os.path.join(OUTPUT_DIR, sanitize(artist), sanitize(album))
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, f"{track_num:02d} - {sanitize(title)}")
    out_path = stem + ".mp3"

    if os.path.exists(out_path):
        print(f"  Skipping (exists)")
        continue

    result = subprocess.run([
        YTDLP, f"ytsearch1:{artist} {title}",
        "-x", "--audio-format", "mp3", "--audio-quality", "0",
        "--embed-thumbnail", "--no-playlist",
        "-o", stem + ".%(ext)s",
        "--quiet", "--no-warnings"
    ])

    if result.returncode != 0 or not os.path.exists(out_path):
        print(f"  FAILED to download")
        failed.append(f"{artist} - {title}")
        continue

    try:
        try:
            tags = ID3(out_path)
        except ID3NoHeaderError:
            tags = ID3()
        tags["TIT2"] = TIT2(encoding=3, text=title)
        tags["TPE1"] = TPE1(encoding=3, text=artist)
        tags["TALB"] = TALB(encoding=3, text=album)
        tags["TRCK"] = TRCK(encoding=3, text=str(track_num))
        tags["TPE2"] = TPE2(encoding=3, text=album_artist)
        tags.save(out_path)
        print(f"  Done")
    except Exception as e:
        print(f"  Downloaded but tagging failed: {e}")

print(f"\n--- Complete ---")
if failed:
    print(f"Failed ({len(failed)}):")
    for t in failed:
        print(f"  - {t}")
else:
    print("All tracks downloaded successfully!")
