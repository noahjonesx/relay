# todo

## in progress / bugs
- [ ] 7 tracks still failing (yt-dlp can't find a working source) — add retry logic to try up to 3 YouTube results before marking failed

## features

### high priority
- [ ] **Rich CLI** — replace plain print with `rich` library: colored output, spinners, live progress table. Quick win, looks great
- [ ] **Retry logic** — try up to 3 `ytsearch` results before marking a track failed. Would fix most current failures
- [x] **GUI (v1)** — React + FastAPI web UI (`frontend/`, `backend/`). Library view + search, playlist enable/disable + per-playlist sync, live sync log streaming, drag-and-drop MP3 import with dedup check. See README "web UI" section.
  - [ ] v2: album art grid / real library visualization, storage stats
  - [ ] v2: drag tracks onto a playlist to assign them (currently playlists are Spotify-sourced only; local imports aren't assignable to a playlist yet)
  - [ ] v2: surface per-track failure reasons in the UI (currently just shows raw log lines)
  - [ ] v2: package as a desktop app (Tauri/Electron) instead of two dev servers

### medium priority
- [ ] **`--stats` command** — total tracks, artists, albums, storage used, last sync time, most-represented artists
- [ ] **Playlist diff view** — on each sync, show what's new vs removed from Spotify since last run
- [ ] **`--health` command** — scan library for tracks with missing tags, bad/missing cover art, or broken files

### polish
- [ ] **Demo GIF in README** — screen recording of a sync running, embedded at the top
- [ ] **`requirements.txt`** — so anyone can clone and run it

## notes
- Rockbox path format: `/<HDD0>/Music/Artist/Album/track.mp3`
- Playlists live at `D:\Playlists\` (not `.rockbox/playlists/`)
- Cover art must be real JPEG — Rockbox won't display PNG renamed to .jpg
- yt-dlp needs occasional `--update` to avoid 403 errors
- Spotify API now returns track data under `item` key, not `track` (updated June 2026)
- Deleted tracks are marked `deleted: true` in `tracks.json` so they never redownload
