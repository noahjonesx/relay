import io, os, urllib.request
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from mutagen.id3 import ID3, APIC, ID3NoHeaderError
from PIL import Image

CLIENT_ID = "dbb786fb7b6e49d9a99640fd5a759a1a"
CLIENT_SECRET = "558f2974c67b44d29afa3f1921d0a76a"
MUSIC_DIR = r"C:\Users\noahx\Music\iPod"

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=CLIENT_ID, client_secret=CLIENT_SECRET
))

def get_spotify_cover(artist, album):
    results = sp.search(q=f"album:{album} artist:{artist}", type="album", limit=1)
    items = results["albums"]["items"]
    if not items:
        results = sp.search(q=f"{artist} {album}", type="album", limit=1)
        items = results["albums"]["items"]
    if not items:
        return None
    images = items[0]["images"]
    return images[0]["url"] if images else None

def download_jpeg(url):
    with urllib.request.urlopen(url) as r:
        data = r.read()
    img = Image.open(io.BytesIO(data)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95)
    return buf.getvalue()

for root, dirs, files in os.walk(MUSIC_DIR):
    mp3s = [f for f in files if f.endswith(".mp3")]
    if not mp3s:
        continue

    # Get artist/album from first tagged track
    artist, album = None, None
    for mp3 in mp3s:
        try:
            tags = ID3(os.path.join(root, mp3))
            if "TPE1" in tags and "TALB" in tags:
                artist = str(tags["TPE1"])
                album = str(tags["TALB"])
                break
        except:
            continue

    if not artist or not album:
        print(f"SKIP (no tags): {os.path.relpath(root, MUSIC_DIR)}")
        continue

    print(f"{artist} - {album}")

    img_url = get_spotify_cover(artist, album)
    if not img_url:
        print(f"  Not found on Spotify")
        continue

    try:
        jpeg_data = download_jpeg(img_url)
    except Exception as e:
        print(f"  Download failed: {e}")
        continue

    # Save cover.jpg
    cover_path = os.path.join(root, "cover.jpg")
    with open(cover_path, "wb") as f:
        f.write(jpeg_data)

    # Update APIC in all MP3s in this folder
    for mp3 in mp3s:
        mp3_path = os.path.join(root, mp3)
        try:
            try:
                tags = ID3(mp3_path)
            except ID3NoHeaderError:
                tags = ID3()
            tags["APIC:"] = APIC(encoding=3, mime="image/jpeg",
                                  type=3, desc="Cover", data=jpeg_data)
            tags.save(mp3_path)
        except Exception as e:
            print(f"  Tag update failed for {mp3}: {e}")

    print(f"  Done")

print("\nAll covers replaced with Spotify album art.")
