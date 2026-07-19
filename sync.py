import io, json, os, shutil, subprocess, sys, urllib.request
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, TPE2, APIC, ID3NoHeaderError
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────────
from config import SPOTIFY_CLIENT_ID as CLIENT_ID, SPOTIFY_CLIENT_SECRET as CLIENT_SECRET, REDIRECT_URI
MUSIC_DIR      = r"C:\Users\noahx\Music\iPod"
IPOD_DRIVE     = "D:"
YTDLP          = r"C:\Users\noahx\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.yt-dlp_Microsoft.Winget.Source_8wekyb3d8bbwe\yt-dlp.exe"
REPO_DIR       = os.path.dirname(os.path.abspath(__file__))
PLAYLISTS_FILE = os.path.join(REPO_DIR, "playlists.json")
MANIFEST_FILE  = os.path.join(REPO_DIR, "tracks.json")

def sanitize(s):
    for c in r'\/:*?"<>|':
        s = s.replace(c, "-")
    return s.strip()

# ── Manifest ──────────────────────────────────────────────────────────────────
def load_manifest():
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_manifest(manifest):
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

# ── Cover art ─────────────────────────────────────────────────────────────────
def fetch_jpeg(images):
    if not images:
        return None
    try:
        with urllib.request.urlopen(images[0]["url"]) as r:
            data = r.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=95)
        return buf.getvalue()
    except Exception:
        return None

# ── Download one track ────────────────────────────────────────────────────────
def process_track(track, manifest):
    uri          = track["uri"]
    artist       = track["artists"][0]["name"]
    album        = track["album"]["name"]
    title        = track["name"]
    tnum         = track["track_number"]
    album_artist = track["album"]["artists"][0]["name"]

    out_dir  = os.path.join(MUSIC_DIR, sanitize(artist), sanitize(album))
    os.makedirs(out_dir, exist_ok=True)
    stem     = os.path.join(out_dir, f"{tnum:02d} - {sanitize(title)}")
    out_path = stem + ".mp3"
    rel_path = out_path.replace(MUSIC_DIR + os.sep, "").replace("\\", "/")

    # Download only if file doesn't exist
    if not os.path.exists(out_path):
        # Clean up any leftover temp file from a previous failed attempt
        for f in os.listdir(out_dir):
            if f.startswith(os.path.basename(stem)) and ".temp." in f:
                try:
                    os.remove(os.path.join(out_dir, f))
                except Exception:
                    pass

        result = subprocess.run([
            YTDLP, f"ytsearch1:{artist} {title}",
            "-x", "--audio-format", "mp3", "--audio-quality", "0",
            "--embed-thumbnail", "--no-playlist",
            "-o", stem + ".%(ext)s",
            "--quiet", "--no-warnings"
        ])
        if result.returncode != 0 or not os.path.exists(out_path):
            return None

    # Cover art — fetch from Spotify, write to album folder
    jpeg = fetch_jpeg(track["album"]["images"])
    cover_path = os.path.join(out_dir, "cover.jpg")
    if jpeg and not os.path.exists(cover_path):
        with open(cover_path, "wb") as f:
            f.write(jpeg)

    # Write ID3 tags from Spotify metadata
    try:
        try:
            tags = ID3(out_path)
        except ID3NoHeaderError:
            tags = ID3()
        tags["TIT2"] = TIT2(encoding=3, text=title)
        tags["TPE1"] = TPE1(encoding=3, text=artist)
        tags["TALB"] = TALB(encoding=3, text=album)
        tags["TRCK"] = TRCK(encoding=3, text=str(tnum))
        tags["TPE2"] = TPE2(encoding=3, text=album_artist)
        if jpeg:
            tags["APIC:"] = APIC(encoding=3, mime="image/jpeg",
                                  type=3, desc="Cover", data=jpeg)
        tags.save(out_path)
    except Exception as e:
        print(f"    Warning: tagging failed: {e}")

    return rel_path

# ── Fetch one playlist's tracks from Spotify ──────────────────────────────────
def fetch_playlist_tracks(sp, config):
    pid = config["url"].split("/playlist/")[1].split("?")[0]
    tracks = []
    page = sp.playlist_tracks(pid)
    while page:
        for item in page["items"]:
            t = item.get("item") or item.get("track")
            if t and t.get("id") and not t.get("is_local"):
                tracks.append(t)
        page = sp.next(page) if page["next"] else None
    return tracks

# ── Write .m3u8 for one playlist ──────────────────────────────────────────────
def write_playlist(name, all_tracks, manifest):
    pl_dir = os.path.join(MUSIC_DIR, "Playlists")
    os.makedirs(pl_dir, exist_ok=True)
    lines = []
    for t in all_tracks:
        entry = manifest.get(t["uri"])
        if entry and not entry.get("deleted"):
            lines.append(f"/<HDD0>/Music/{entry['path']}")
    with open(os.path.join(pl_dir, f"{name}.m3u8"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return len(lines)

# ── Clean deleted tracks ──────────────────────────────────────────────────────
def clean_deleted(manifest):
    missing = {uri: info for uri, info in manifest.items()
               if not info.get("deleted")
               and not os.path.exists(os.path.join(MUSIC_DIR, info["path"].replace("/", os.sep)))}
    if not missing:
        return

    print(f"\nCleaning {len(missing)} deleted track(s) from manifest and iPod...")
    ipod_music = f"{IPOD_DRIVE}\\Music"
    ipod_connected = os.path.isdir(ipod_music)

    for uri, info in missing.items():
        print(f"  - {info['artist']} - {info['title']}")
        if ipod_connected:
            ipod_path = os.path.join(ipod_music, info["path"].replace("/", os.sep))
            if os.path.exists(ipod_path):
                os.remove(ipod_path)
            # Remove cover.jpg and prune empty album/artist dirs on iPod
            parent = os.path.dirname(ipod_path)
            for _ in range(2):
                try:
                    entries = os.listdir(parent)
                    if entries == ["cover.jpg"]:
                        os.remove(os.path.join(parent, "cover.jpg"))
                        entries = []
                    if not entries:
                        os.rmdir(parent)
                    parent = os.path.dirname(parent)
                except Exception:
                    break
        manifest[uri]["deleted"] = True

    save_manifest(manifest)
    if not ipod_connected:
        print("  (iPod not connected — files will be removed from iPod on next sync)")

# ── Sync to iPod ──────────────────────────────────────────────────────────────
def sync_to_ipod(synced_names):
    ipod_music = f"{IPOD_DRIVE}\\Music"
    ipod_pl    = f"{IPOD_DRIVE}\\Playlists"

    if not os.path.isdir(ipod_music):
        print(f"\niPod not connected at {IPOD_DRIVE} — skipping sync.")
        print("Plug in and run:  py sync.py --ipod-only")
        return

    print(f"\nSyncing to iPod...")
    subprocess.run([
        "robocopy", MUSIC_DIR, ipod_music,
        "/E", "/XF", "*.csv", "*.m3u8", "/XD", "Playlists",
        "/NP", "/NFL"
    ])

    os.makedirs(ipod_pl, exist_ok=True)
    for name in synced_names:
        src = os.path.join(MUSIC_DIR, "Playlists", f"{name}.m3u8")
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(ipod_pl, f"{name}.m3u8"))
            print(f"  Playlist synced: {name}.m3u8")

    print("  Done — safely eject your iPod.")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args      = sys.argv[1:]
    no_ipod   = "--no-ipod"   in args
    ipod_only = "--ipod-only" in args
    target    = args[args.index("--playlist") + 1] if "--playlist" in args else None

    with open(PLAYLISTS_FILE, encoding="utf-8") as f:
        playlists = json.load(f)

    if target:
        playlists = [p for p in playlists if p["name"] == target]
        if not playlists:
            print(f"Playlist '{target}' not found in playlists.json")
            sys.exit(1)

    if ipod_only:
        sync_to_ipod([p["name"] for p in playlists])
        return

    # Authenticate
    sp_oauth = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope="playlist-read-private playlist-read-collaborative",
        cache_path=os.path.join(REPO_DIR, ".spotify_cache"),
        open_browser=False,
    )
    if not sp_oauth.get_cached_token():
        print("\nOpen this URL in your browser and log in:")
        print(sp_oauth.get_authorize_url())
        print("\nAfter logging in, your browser will show an error page.")
        print("Copy the full URL from the address bar and paste it here:")
        response = input("> ").strip()
        code = sp_oauth.parse_response_code(response)
        sp_oauth.get_access_token(code, as_dict=False)
    sp = spotipy.Spotify(auth_manager=sp_oauth)
    me = sp.current_user()
    print(f"Authenticated as: {me['display_name']} ({me['id']})")

    manifest = load_manifest()
    clean_deleted(manifest)

    # Phase 1: fetch all playlists from Spotify
    print(f"\nFetching {len(playlists)} playlist(s) from Spotify...")
    playlist_data = []
    for pl in playlists:
        tracks = fetch_playlist_tracks(sp, pl)
        playlist_data.append((pl["name"], tracks))
        print(f"  {pl['name']}: {len(tracks)} tracks")

    # Phase 2: collect unique tracks that need downloading
    seen, to_download = set(), []
    for _, tracks in playlist_data:
        for t in tracks:
            if t["uri"] in seen:
                continue
            seen.add(t["uri"])
            entry = manifest.get(t["uri"])
            needs_dl = (
                not entry
                or (not entry.get("deleted")
                    and not os.path.exists(os.path.join(MUSIC_DIR, entry["path"])))
            )
            if needs_dl:
                to_download.append(t)

    total_tracks = sum(len(t) for _, t in playlist_data)
    print(f"\n{len(playlists)} playlists  |  {total_tracks} total tracks  |  {len(to_download)} to download")

    # Phase 3: download
    failed = []
    for i, track in enumerate(to_download, 1):
        label = f"{track['artists'][0]['name']} - {track['name']}"
        print(f"\n[{i}/{len(to_download)}] {label}")
        rel = process_track(track, manifest)
        if rel:
            manifest[track["uri"]] = {
                "path":   rel,
                "artist": track["artists"][0]["name"],
                "title":  track["name"],
                "album":  track["album"]["name"],
            }
            save_manifest(manifest)
            print(f"  Done")
        else:
            print(f"  FAILED")
            failed.append(label)

    if failed:
        print(f"\nFailed ({len(failed)}):")
        for f in failed:
            print(f"  - {f}")

    # Phase 4: write playlists
    print(f"\nWriting playlists...")
    synced = []
    for name, tracks in playlist_data:
        count = write_playlist(name, tracks, manifest)
        print(f"  {name}: {count} tracks")
        synced.append(name)

    if not no_ipod:
        sync_to_ipod(synced)

    print("\nAll done!")

if __name__ == "__main__":
    main()
