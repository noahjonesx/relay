# todo

## in progress / bugs
- [ ] 7 tracks still failing (yt-dlp can't find a working source) — add retry logic to try up to 3 YouTube results before marking failed

## features

### high priority
- [ ] **Rich CLI** — replace plain print with `rich` library: colored output, spinners, live progress table. Quick win, looks great
- [ ] **Retry logic** — try up to 3 `ytsearch` results before marking a track failed. Would fix most current failures
- [ ] **GUI** — live progress window: current track downloading, album art thumbnail, overall progress bar, failed tracks list. Options: tkinter (simple) or Flask + htmx (web-based, looks more modern)

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
