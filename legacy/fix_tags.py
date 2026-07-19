import io, os, urllib.request
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, TPE2, APIC, ID3NoHeaderError
from PIL import Image

CLIENT_ID = "dbb786fb7b6e49d9a99640fd5a759a1a"
CLIENT_SECRET = "558f2974c67b44d29afa3f1921d0a76a"
MUSIC_DIR = r"C:\Users\noahx\Music\iPod"

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=CLIENT_ID, client_secret=CLIENT_SECRET
))

# (file path relative to MUSIC_DIR, spotify search query)
TO_FIX = [
    (r"Bush\Sixteen Stone (2014 Remastered)\14 - Glycerine - 2014 Remastered.mp3", "Glycerine Bush"),
    (r"FKJ\Risk\01 - Risk.mp3", "Risk FKJ Bas"),
    (r"j ember\something more\01 - something more.mp3", "something more j ember"),
    (r"Lord Huron\The Night We Met (feat. Phoebe Bridgers)\01 - The Night We Met (feat. Phoebe Bridgers).mp3", "The Night We Met Lord Huron"),
    (r"Radiohead\OK Computer\12 - The Tourist.mp3", "The Tourist Radiohead"),
    (r"Sublime\Robbin' The Hood\23 - Don't Push.mp3", "Don't Push Sublime"),
    (r"The Black Keys\El Camino\04 - Little Black Submarines.mp3", "Little Black Submarines The Black Keys"),
]

# Delete temp files
for root, dirs, files in os.walk(MUSIC_DIR):
    for f in files:
        if ".temp." in f:
            path = os.path.join(root, f)
            os.remove(path)
            print(f"Deleted temp: {f}")

print()

for rel_path, query in TO_FIX:
    full_path = os.path.join(MUSIC_DIR, rel_path)
    print(f"Fixing: {rel_path}")

    results = sp.search(q=query, type="track", limit=1)
    items = results["tracks"]["items"]
    if not items:
        print(f"  Not found on Spotify, skipping")
        continue

    track = items[0]
    title = track["name"]
    artist = track["artists"][0]["name"]
    album = track["album"]["name"]
    track_num = track["track_number"]
    album_artist = track["album"]["artists"][0]["name"]
    img_url = track["album"]["images"][0]["url"] if track["album"]["images"] else None

    try:
        try:
            tags = ID3(full_path)
        except ID3NoHeaderError:
            tags = ID3()

        tags["TIT2"] = TIT2(encoding=3, text=title)
        tags["TPE1"] = TPE1(encoding=3, text=artist)
        tags["TALB"] = TALB(encoding=3, text=album)
        tags["TRCK"] = TRCK(encoding=3, text=str(track_num))
        tags["TPE2"] = TPE2(encoding=3, text=album_artist)

        if img_url:
            with urllib.request.urlopen(img_url) as r:
                img_data = r.read()
            img = Image.open(io.BytesIO(img_data)).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=90)
            tags["APIC:"] = APIC(encoding=3, mime="image/jpeg",
                                  type=3, desc="Cover", data=buf.getvalue())

            cover_path = os.path.join(os.path.dirname(full_path), "cover.jpg")
            with open(cover_path, "wb") as f:
                f.write(buf.getvalue())

        tags.save(full_path)
        print(f"  Done: {artist} - {title}")
    except Exception as e:
        print(f"  ERROR: {e}")

print("\nAll done.")
