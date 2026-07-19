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

# sync to iPod only (no downloads)
py sync.py --ipod-only
```

Watch progress live:
```powershell
Get-Content sync_log.txt -Wait -Tail 20
```

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
