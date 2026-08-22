import io, json, os, re, shutil, subprocess, sys, unicodedata, urllib.request
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

# ── Duplicate detection ─────────────────────────────────────────────────────
def normalize_key(artist, title):
    """Case/punctuation/accent-insensitive key so the same song under a
    different Spotify URI (e.g. a single vs. its later album cut) is
    recognized as a duplicate. Deliberately does NOT strip things like
    '(Live)' or '(Remix)' out of the title — those are different
    recordings, not duplicates."""
    def norm(s):
        s = unicodedata.normalize("NFKD", s)
        s = "".join(c for c in s if not unicodedata.combining(c))
        s = re.sub(r"[^a-z0-9]+", " ", s.lower())
        return s.strip()
    return f"{norm(artist)}|{norm(title)}"

ALT_VERSION_RE = re.compile(r"\b(live|acoustic|unplugged|concert|session|demo)\b", re.IGNORECASE)

def is_alt_version(album, title):
    """True if this looks like a live/acoustic/etc. recording rather than
    the studio version — used to break ties when the same song shows up
    under more than one Spotify URI."""
    return bool(ALT_VERSION_RE.search(album or "") or ALT_VERSION_RE.search(title or ""))

def choose_canonical(candidates):
    """Given [(uri, info), ...] all sharing the same artist+title, prefer
    the studio recording; otherwise keep whichever came first."""
    for uri, info in candidates:
        if not is_alt_version(info.get("album", ""), info.get("title", "")):
            return uri, info
    return candidates[0]

def alias_track(track, owner_uri, manifest):
    """Point this track's URI at a file that already satisfies the same
    artist+title, instead of downloading a second copy."""
    owner = manifest[owner_uri]
    manifest[track["uri"]] = {
        "path":         owner["path"],
        "artist":       track["artists"][0]["name"],
        "title":        track["name"],
        "album":        track["album"]["name"],
        "duplicate_of": owner_uri,
    }

def resolve_duplicates(tracks, manifest):
    """Filter tracks down to the ones that actually need downloading,
    deduping by normalized artist+title (not just Spotify URI)."""
    by_key = {}
    for uri, info in manifest.items():
        if info.get("deleted"):
            continue
        if not os.path.exists(os.path.join(MUSIC_DIR, info["path"])):
            continue
        by_key.setdefault(normalize_key(info["artist"], info["title"]), []).append((uri, info))
    have_key = {key: choose_canonical(cands)[0] for key, cands in by_key.items()}

    seen_uri, groups, aliased = set(), {}, 0
    for t in tracks:
        uri = t["uri"]
        if uri in seen_uri or not needs_download(t, manifest):
            continue
        seen_uri.add(uri)

        key = normalize_key(t["artists"][0]["name"], t["name"])
        owner = have_key.get(key)
        if owner:
            alias_track(t, owner, manifest)
            aliased += 1
            continue

        groups.setdefault(key, []).append(t)

    if aliased:
        save_manifest(manifest)
        print(f"  Skipped {aliased} duplicate(s) already in the library under a different URI")

    to_download = []
    for group in groups.values():
        # Prefer the studio recording as the one that actually gets downloaded.
        group.sort(key=lambda t: is_alt_version(t["album"]["name"], t["name"]))
        primary, dupes = group[0], group[1:]
        if dupes:
            primary["_dupe_group"] = dupes
        to_download.append(primary)
    return to_download

def download_and_link(to_download, manifest):
    """Download the (deduped) queue, then alias any duplicate URIs found
    within this run onto whichever file actually got downloaded."""
    failed = download_tracks(to_download, manifest)

    linked = 0
    for t in to_download:
        dupes = t.pop("_dupe_group", None)
        if not dupes:
            continue
        entry = manifest.get(t["uri"])
        if entry and not entry.get("deleted"):
            for dupe in dupes:
                alias_track(dupe, t["uri"], manifest)
                linked += 1
    if linked:
        save_manifest(manifest)
        print(f"  Linked {linked} duplicate URI(s) to the downloaded file")

    return failed

def dedupe_existing(manifest):
    """One-off maintenance pass: find tracks already downloaded under
    different URIs that are actually the same song, keep one file, and
    remove the rest (locally and from the iPod if connected)."""
    groups = {}
    for uri, info in manifest.items():
        if info.get("deleted"):
            continue
        key = normalize_key(info["artist"], info["title"])
        groups.setdefault(key, []).append((uri, info))

    ipod_music = f"{IPOD_DRIVE}\\Music"
    ipod_connected = os.path.isdir(ipod_music)
    removed = 0

    for entries in groups.values():
        by_path = {}
        for uri, info in entries:
            by_path.setdefault(info["path"], []).append(uri)
        if len(by_path) <= 1:
            continue  # only one real file backs this song already

        canonical_uri, canonical_info = choose_canonical(entries)
        canonical_path = canonical_info["path"]
        sample = entries[0][1]
        print(f"\nDuplicate found: {sample['artist']} - {sample['title']}")
        print(f"  Keeping:  {canonical_path}")

        for path, uris in by_path.items():
            if path == canonical_path:
                continue
            print(f"  Removing: {path}")
            full = os.path.join(MUSIC_DIR, path.replace("/", os.sep))
            if os.path.exists(full):
                os.remove(full)
            if ipod_connected:
                remove_from_ipod(ipod_music, path)
            for uri in uris:
                manifest[uri] = {
                    "path":         canonical_path,
                    "artist":       manifest[uri]["artist"],
                    "title":        manifest[uri]["title"],
                    "album":        manifest[uri]["album"],
                    "duplicate_of": canonical_uri,
                }
            removed += 1

    if removed:
        save_manifest(manifest)
        print(f"\nRemoved {removed} duplicate file(s).")
        if not ipod_connected:
            print("  (iPod not connected — stale copies will be removed automatically next sync)")
    else:
        print("\nNo duplicates found.")

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
    disc         = track.get("disc_number", 1)
    album_artist = track["album"]["artists"][0]["name"]

    out_dir = os.path.join(MUSIC_DIR, sanitize(artist), sanitize(album))
    os.makedirs(out_dir, exist_ok=True)

    # Disc number in the filename prefix so multi-disc albums don't collide
    # on track number alone (disc 1 track 1 vs. disc 2 track 1).
    track_prefix = f"{disc}-{tnum:02d}" if disc and disc > 1 else f"{tnum:02d}"
    stem = os.path.join(out_dir, f"{track_prefix} - {sanitize(title)}")

    # Guard against two genuinely different songs colliding on the same
    # filename (e.g. sanitize() reducing two different titles to the same
    # string). If a different, still-live URI already owns this exact path,
    # disambiguate instead of silently overwriting it.
    rel_path = (stem + ".mp3").replace(MUSIC_DIR + os.sep, "").replace("\\", "/")
    my_key = normalize_key(artist, title)
    for other_uri, info in manifest.items():
        if other_uri == uri or info.get("deleted"):
            continue
        if info.get("path") == rel_path and normalize_key(info["artist"], info["title"]) != my_key:
            stem += f" [{uri.split(':')[-1][:6]}]"
            break

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

# ── Fetch Liked Songs by a given artist ────────────────────────────────────────
def fetch_saved_tracks_by_artist(sp, artist_name):
    tracks = []
    page = sp.current_user_saved_tracks(limit=50)
    while page:
        for item in page["items"]:
            t = item.get("track")
            if t and t.get("id") and any(a["name"].lower() == artist_name.lower() for a in t["artists"]):
                tracks.append(t)
        page = sp.next(page) if page["next"] else None
    return tracks

# ── Download queue helpers ─────────────────────────────────────────────────────
def needs_download(t, manifest):
    entry = manifest.get(t["uri"])
    return (
        not entry
        or (not entry.get("deleted")
            and not os.path.exists(os.path.join(MUSIC_DIR, entry["path"])))
    )

def download_tracks(to_download, manifest):
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
    return failed

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

# ── iPod file removal ───────────────────────────────────────────────────────
def remove_from_ipod(ipod_music, rel_path):
    """Best-effort removal of a track (and now-empty album/artist dirs) from
    the iPod. Safe to call even if the file isn't actually there."""
    ipod_path = os.path.join(ipod_music, rel_path.replace("/", os.sep))
    if not os.path.exists(ipod_path):
        return
    try:
        os.remove(ipod_path)
    except Exception:
        return
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
            remove_from_ipod(ipod_music, info["path"])
        manifest[uri]["deleted"] = True

    save_manifest(manifest)
    if not ipod_connected:
        print("  (iPod not connected — stale copies will be removed automatically next time it's plugged in)")

# ── Sync to iPod ──────────────────────────────────────────────────────────────
def sync_to_ipod(manifest, synced_names):
    ipod_music = f"{IPOD_DRIVE}\\Music"
    ipod_pl    = f"{IPOD_DRIVE}\\Playlists"

    if not os.path.isdir(ipod_music):
        print(f"\niPod not connected at {IPOD_DRIVE} — skipping sync.")
        print("Plug in and run:  py sync.py --ipod-only")
        return

    # Catch up on any removals that happened while the iPod was unplugged —
    # robocopy below only adds/updates, it never deletes, so this is the
    # only place stale (deleted) tracks actually get purged from the device.
    stale = [info for info in manifest.values() if info.get("deleted")]
    if stale:
        print(f"\nRemoving {len(stale)} stale track(s) from iPod (if present)...")
        for info in stale:
            remove_from_ipod(ipod_music, info["path"])

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

# ── Auth ────────────────────────────────────────────────────────────────────
def authenticate():
    sp_oauth = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope="playlist-read-private playlist-read-collaborative user-library-read",
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
    return sp

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args      = sys.argv[1:]
    no_ipod   = "--no-ipod"   in args
    ipod_only = "--ipod-only" in args
    dedupe    = "--dedupe"    in args
    target    = args[args.index("--playlist") + 1] if "--playlist" in args else None
    artist    = args[args.index("--artist") + 1] if "--artist" in args else None

    if dedupe:
        manifest = load_manifest()
        dedupe_existing(manifest)
        return

    if ipod_only:
        with open(PLAYLISTS_FILE, encoding="utf-8") as f:
            playlists = json.load(f)
        if target:
            playlists = [p for p in playlists if p["name"] == target]
        manifest = load_manifest()
        sync_to_ipod(manifest, [p["name"] for p in playlists])
        return

    if artist:
        sp = authenticate()
        manifest = load_manifest()
        clean_deleted(manifest)

        print(f"\nFetching Liked Songs by '{artist}'...")
        tracks = fetch_saved_tracks_by_artist(sp, artist)
        print(f"  Found {len(tracks)} liked track(s) by {artist}")

        to_download = resolve_duplicates(tracks, manifest)
        print(f"\n{len(tracks)} tracks  |  {len(to_download)} to download")

        failed = download_and_link(to_download, manifest)
        if failed:
            print(f"\nFailed ({len(failed)}):")
            for f in failed:
                print(f"  - {f}")

        if not no_ipod:
            sync_to_ipod(manifest, [])

        print("\nAll done!")
        return

    with open(PLAYLISTS_FILE, encoding="utf-8") as f:
        playlists = json.load(f)

    if target:
        playlists = [p for p in playlists if p["name"] == target]
        if not playlists:
            print(f"Playlist '{target}' not found in playlists.json")
            sys.exit(1)

    # Authenticate
    sp = authenticate()

    manifest = load_manifest()
    clean_deleted(manifest)

    # Phase 1: fetch all playlists from Spotify
    print(f"\nFetching {len(playlists)} playlist(s) from Spotify...")
    playlist_data = []
    for pl in playlists:
        tracks = fetch_playlist_tracks(sp, pl)
        playlist_data.append((pl["name"], tracks))
        print(f"  {pl['name']}: {len(tracks)} tracks")

    # Phase 2: collect unique tracks that need downloading (deduped by
    # artist+title as well as by URI — see resolve_duplicates)
    seen, unique_tracks = set(), []
    for _, tracks in playlist_data:
        for t in tracks:
            if t["uri"] in seen:
                continue
            seen.add(t["uri"])
            unique_tracks.append(t)

    to_download = resolve_duplicates(unique_tracks, manifest)

    total_tracks = sum(len(t) for _, t in playlist_data)
    print(f"\n{len(playlists)} playlists  |  {total_tracks} total tracks  |  {len(to_download)} to download")

    # Phase 3: download
    failed = download_and_link(to_download, manifest)

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
        sync_to_ipod(manifest, synced)

    print("\nAll done!")

if __name__ == "__main__":
    main()
