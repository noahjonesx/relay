# ipod

Automated Spotify → iPod Classic pipeline. Reads your playlists directly from the Spotify API, sources audio, tags everything with correct metadata and album art, generates Rockbox-compatible playlists, and syncs to the device — all in one command.

Built for a 5th gen iPod Classic running [Rockbox](https://www.rockbox.org/).

```
py sync.py
```

---

## what it does

1. **Reads playlists from Spotify** — no CSV exports, no third-party tools. Uses the Spotify Web API directly via OAuth.
2. **Sources audio** for any track not already in your local library
3. **Tags every file** with Spotify metadata: title, artist, album, track number, album artist
4. **Fetches real album art** from Spotify's CDN (not thumbnails) — saves as embedded APIC tag + `cover.jpg` for Rockbox display
5. **Generates `.m3u8` playlists** with correct Rockbox-relative paths (`/<HDD0>/Music/...`)
6. **Syncs to iPod** via robocopy — music to `D:\Music\`, playlists to `D:\Playlists\`
7. **Tracks deletions** — remove a folder locally, run sync, and it's gone from the manifest and iPod permanently (won't redownload)

---

## stack

- [spotipy](https://spotipy.readthedocs.io/) — Spotify Web API
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — audio sourcing
- [mutagen](https://mutagen.readthedocs.io/) — ID3 tag writing
- [Pillow](https://pillow.readthedocs.io/) — image conversion for cover art
- robocopy — iPod sync

---

## setup

**1. Clone and install dependencies**
```bash
pip install spotipy mutagen Pillow
```

**2. Create a Spotify app**

Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), create an app, and add `http://127.0.0.1:4202` as a redirect URI.

**3. Configure**
```bash
cp config.example.py config.py
# fill in your CLIENT_ID and CLIENT_SECRET
```

**4. Edit `sync.py` config block**
```python
MUSIC_DIR  = r"C:\path\to\your\music\folder"
IPOD_DRIVE = "D:"
YTDLP      = r"C:\path\to\yt-dlp.exe"
```

**5. Add your playlists to `playlists.json`**
```json
[
  { "name": "playlist_name", "url": "https://open.spotify.com/playlist/..." }
]
```

---

## usage

```bash
# full sync (download new tracks + sync to iPod)
py sync.py

# download only, skip iPod sync
py sync.py --no-ipod

# single playlist
py sync.py --playlist june26

# all Liked Songs by a given artist
py sync.py --artist "Title Fight"

# sync to iPod only (no downloads)
py sync.py --ipod-only

# scan the library for the same song under two different Spotify URIs and merge them
py sync.py --dedupe
```

Watch progress live:
```powershell
Get-Content sync_log.txt -Wait -Tail 20
```

---

## web UI

A basic local web UI lives in `backend/` (FastAPI) and `frontend/` (React + Vite). It wraps `sync.py` rather than reimplementing it — the backend shells out to `py sync.py ...` and streams its output live, and calls straight into `sync.py`'s functions for the library view, playlist toggles, and MP3 import.

**Run it (two terminals):**
```bash
# backend — http://localhost:8000
py -m uvicorn backend.app:app --port 8000

# frontend — http://localhost:5173
cd frontend
npm install   # first time only
npm run dev
```

Open `http://localhost:5173`. Current features:
- **Library** — searchable table of everything in `tracks.json`, plus track/artist/album counts. Drag-and-drop an MP3 onto the page to import it (looked up against Spotify for metadata/art, rejected if it's already a duplicate by artist+title).
- **Playlists** — toggle which playlists from `playlists.json` are included in a full sync, see per-playlist track counts, or trigger a sync for just one.
- **Sync** — start a full sync, download-only, iPod-only, or `--dedupe`, and watch the live log stream. Shows run status (idle/running/done/failed).

This is a first pass — full library visualization (artwork grid, storage stats) and playlist drag-and-drop assignment are still on the todo list.

---

## how deletion works

Remove an artist or album folder from your local music directory. On the next `sync.py` run, the script detects the missing files, marks them in the manifest as `deleted`, removes them from the iPod, and never re-downloads them — even if they're still in your Spotify playlists.

---

## file structure

```
Music/
└── Artist/
    └── Album/
        ├── 01 - Track Name.mp3
        ├── 02 - Track Name.mp3
        └── cover.jpg

Playlists/
├── june26.m3u8
└── july26.m3u8
```

---

## notes

- Tested on iPod Classic 5th gen with Rockbox 3.15
- Rockbox reads playlists from `D:\Playlists\` — **not** `.rockbox/playlists/`
- Cover art must be a real JPEG — Rockbox will not display PNG files with a `.jpg` extension
- yt-dlp should be kept updated (`yt-dlp --update`) to avoid 403 errors
