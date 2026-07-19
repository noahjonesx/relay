import os, subprocess
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, TPE2, ID3NoHeaderError

CLIENT_ID = "dbb786fb7b6e49d9a99640fd5a759a1a"
CLIENT_SECRET = "558f2974c67b44d29afa3f1921d0a76a"
OUTPUT_DIR = r"C:\Users\noahx\Music\iPod"
YTDLP = r"C:\Users\noahx\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.yt-dlp_Microsoft.Winget.Source_8wekyb3d8bbwe\yt-dlp.exe"
ALBUM_ID = "0yZuUc5poB8rtqkbmA0APm"  # Sublime - Robbin' The Hood 1994

def sanitize(s):
    for c in r'\/:*?"<>|':
        s = s.replace(c, "-")
    return s.strip()

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=CLIENT_ID, client_secret=CLIENT_SECRET
))

full_album = sp.album(ALBUM_ID)
artist_name = full_album["artists"][0]["name"]
album_name = full_album["name"]
tracks = full_album["tracks"]["items"]

print(f"Downloading {len(tracks)} tracks from {artist_name} - {album_name}\n")

failed = []
for track in tracks:
    title = track["name"]
    track_num = track["track_number"]
    artist = track["artists"][0]["name"]

    print(f"[{track_num}/{len(tracks)}] {title}")

    out_dir = os.path.join(OUTPUT_DIR, sanitize(artist), sanitize(album_name))
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, f"{track_num:02d} - {sanitize(title)}")
    out_path = stem + ".mp3"

    if os.path.exists(out_path):
        print(f"  Skipping (exists)")
        continue

    result = subprocess.run([
        YTDLP, f"ytsearch1:{artist} {title} Sublime",
        "-x", "--audio-format", "mp3", "--audio-quality", "0",
        "--embed-thumbnail", "--no-playlist",
        "-o", stem + ".%(ext)s",
        "--quiet", "--no-warnings"
    ])

    if result.returncode != 0 or not os.path.exists(out_path):
        print(f"  FAILED")
        failed.append(f"{artist} - {title}")
        continue

    try:
        try:
            tags = ID3(out_path)
        except ID3NoHeaderError:
            tags = ID3()
        tags["TIT2"] = TIT2(encoding=3, text=title)
        tags["TPE1"] = TPE1(encoding=3, text=artist)
        tags["TALB"] = TALB(encoding=3, text=album_name)
        tags["TRCK"] = TRCK(encoding=3, text=str(track_num))
        tags["TPE2"] = TPE2(encoding=3, text=artist_name)
        tags.save(out_path)
        print(f"  Done")
    except Exception as e:
        print(f"  Downloaded but tagging failed: {e}")

print(f"\n--- Done ---")
if failed:
    print(f"Failed ({len(failed)}): {failed}")
else:
    print("All tracks downloaded!")
