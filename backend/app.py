"""
FastAPI backend for the iPod sync UI.

Thin wrapper around sync.py: it shells out to `py sync.py ...` for actual
sync runs (streaming its stdout live over a WebSocket) and calls sync.py's
functions directly for read-only/library-editing operations (library list,
playlist toggles, manual MP3 import). No sync logic is duplicated here.
"""
import asyncio
import http.server
import os
import sys
import threading
import urllib.parse
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from spotipy.oauth2 import SpotifyOAuth

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))
import sync  # noqa: E402  (must come after sys.path insert)

app = FastAPI(title="ipod sync")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Spotify login (no terminal needed) ──────────────────────────────────────
# sync.py's normal CLI flow prompts for a pasted-in redirect URL, which can't
# work from a headless subprocess (no stdin). Instead, we spin up a one-shot
# local HTTP server matching REDIRECT_URI to catch Spotify's OAuth redirect
# automatically, so login can happen entirely by clicking a button and
# finishing the flow in a browser tab.
OAUTH_SCOPE = "playlist-read-private playlist-read-collaborative user-library-read"

def _make_oauth():
    return SpotifyOAuth(
        client_id=sync.CLIENT_ID,
        client_secret=sync.CLIENT_SECRET,
        redirect_uri=sync.REDIRECT_URI,
        scope=OAUTH_SCOPE,
        cache_path=os.path.join(sync.REPO_DIR, ".spotify_cache"),
        open_browser=False,
    )

class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        self.server.oauth_params = params
        ok = "code" in params
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        msg = (
            "Logged in to Spotify — you can close this tab."
            if ok
            else "Spotify login failed — you can close this tab and try again."
        )
        self.wfile.write(f"<html><body style='font-family:sans-serif;padding:40px'>{msg}</body></html>".encode())

    def log_message(self, *args):
        pass  # silence default request logging to stderr

def _run_oauth_callback_server(oauth, timeout=180):
    parsed = urllib.parse.urlparse(sync.REDIRECT_URI)
    try:
        server = http.server.HTTPServer((parsed.hostname, parsed.port), _OAuthCallbackHandler)
    except OSError as e:
        print(f"Couldn't start the Spotify login listener on {sync.REDIRECT_URI}: {e}")
        return
    server.timeout = timeout
    server.oauth_params = None
    try:
        server.handle_request()  # blocks for exactly one request, or until timeout
    finally:
        server.server_close()

    params = server.oauth_params or {}
    if "code" in params:
        try:
            oauth.get_access_token(params["code"][0], as_dict=False)
        except Exception as e:
            print(f"Spotify token exchange failed: {e}")
    elif "error" in params:
        print(f"Spotify login failed: {params['error'][0]}")

@app.get("/api/spotify/status")
def spotify_status():
    return {"authenticated": bool(_make_oauth().get_cached_token())}

@app.post("/api/spotify/login")
def spotify_login():
    oauth = _make_oauth()
    url = oauth.get_authorize_url()
    threading.Thread(target=_run_oauth_callback_server, args=(oauth,), daemon=True).start()
    return {"url": url}

# ── Live sync run state ─────────────────────────────────────────────────────
LOG_BUFFER = deque(maxlen=4000)
CLIENTS: set[WebSocket] = set()
_proc: Optional[asyncio.subprocess.Process] = None
_proc_lock = asyncio.Lock()

sync_state = {
    "running": False,
    "args": None,
    "started_at": None,
    "finished_at": None,
    "exit_code": None,
}

def _now():
    return datetime.now(timezone.utc).isoformat()

async def _broadcast(line):
    LOG_BUFFER.append(line)
    dead = []
    for ws in CLIENTS:
        try:
            await ws.send_text(line)
        except Exception:
            dead.append(ws)
    for ws in dead:
        CLIENTS.discard(ws)

async def _run_sync(args):
    global _proc
    sync_state.update(running=True, args=args, started_at=_now(), finished_at=None, exit_code=None)
    await _broadcast(f"$ py sync.py {' '.join(args)}")

    # sync.py's interactive login can't work headlessly (no stdin) — catch
    # this up front instead of letting the subprocess crash on input().
    needs_auth = "--ipod-only" not in args and "--dedupe" not in args
    if needs_auth and not _make_oauth().get_cached_token():
        await _broadcast('Spotify login required — click "Login to Spotify" above, then try again.')
        sync_state.update(running=False, finished_at=_now(), exit_code=1)
        return

    try:
        _proc = await asyncio.create_subprocess_exec(
            sys.executable, str(REPO_DIR / "sync.py"), *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.DEVNULL,
            cwd=str(REPO_DIR),
        )
        async for raw in _proc.stdout:
            await _broadcast(raw.decode(errors="replace").rstrip("\r\n"))
        code = await _proc.wait()
    except Exception as e:
        await _broadcast(f"[backend error launching sync.py: {e}]")
        code = -1
    sync_state.update(running=False, finished_at=_now(), exit_code=code)
    await _broadcast(f"[process exited with code {code}]")
    _proc = None

# ── Sync control ─────────────────────────────────────────────────────────────
class SyncRequest(BaseModel):
    playlist: Optional[str] = None
    artist: Optional[str] = None
    no_ipod: bool = False
    ipod_only: bool = False

@app.post("/api/sync/start")
async def start_sync(req: SyncRequest):
    async with _proc_lock:
        if sync_state["running"]:
            raise HTTPException(409, "A sync is already running")
        args = []
        if req.ipod_only:
            args.append("--ipod-only")
        if req.playlist:
            args += ["--playlist", req.playlist]
        if req.artist:
            args += ["--artist", req.artist]
        if req.no_ipod:
            args.append("--no-ipod")
        asyncio.create_task(_run_sync(args))
    return {"status": "started", "args": args}

@app.post("/api/sync/dedupe")
async def start_dedupe():
    async with _proc_lock:
        if sync_state["running"]:
            raise HTTPException(409, "A sync is already running")
        asyncio.create_task(_run_sync(["--dedupe"]))
    return {"status": "started", "args": ["--dedupe"]}

@app.post("/api/sync/stop")
async def stop_sync():
    if not _proc or not sync_state["running"]:
        raise HTTPException(400, "No sync is running")
    _proc.terminate()
    return {"status": "stopping"}

@app.get("/api/sync/status")
def get_status():
    return sync_state

@app.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket):
    await websocket.accept()
    CLIENTS.add(websocket)
    for line in LOG_BUFFER:
        await websocket.send_text(line)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        CLIENTS.discard(websocket)

# ── Library ──────────────────────────────────────────────────────────────────
@app.get("/api/library")
def get_library():
    manifest = sync.load_manifest()
    tracks, artists, albums, active = [], set(), set(), 0

    for uri, info in manifest.items():
        deleted = bool(info.get("deleted", False))
        if not deleted:
            active += 1
            artists.add(info["artist"])
            albums.add((info["artist"], info["album"]))
        tracks.append({
            "uri":          uri,
            "artist":       info["artist"],
            "title":        info["title"],
            "album":        info["album"],
            "path":         info["path"],
            "deleted":      deleted,
            "duplicate_of": info.get("duplicate_of"),
            "local":        uri.startswith("local:"),
        })

    return {
        "tracks": tracks,
        "stats": {
            "total":   len(tracks),
            "active":  active,
            "artists": len(artists),
            "albums":  len(albums),
        },
    }

@app.get("/api/albums")
def get_albums():
    manifest = sync.load_manifest()
    albums = {}
    for info in manifest.values():
        if info.get("deleted"):
            continue
        key = (info["artist"], info["album"])
        album = albums.get(key)
        if not album:
            art_dir = str(Path(info["path"]).parent).replace("\\", "/")
            album = albums[key] = {
                "artist":      info["artist"],
                "album":       info["album"],
                "track_count": 0,
                "art":         f"/api/art?path={quote(art_dir)}",
            }
        album["track_count"] += 1
    return sorted(albums.values(), key=lambda a: (a["artist"].lower(), a["album"].lower()))

@app.delete("/api/library/{uri:path}")
def delete_track(uri: str):
    manifest = sync.load_manifest()
    result = sync.delete_track(uri, manifest)
    if result["status"] == "error":
        raise HTTPException(404, result["message"])
    return result

@app.get("/api/art")
def get_art(path: str):
    """Serve an album's cover.jpg. `path` is the album's folder relative to
    MUSIC_DIR (e.g. 'Artist/Album'), as returned by /api/albums."""
    music_root = Path(sync.MUSIC_DIR).resolve()
    album_dir = (music_root / path).resolve()
    if music_root != album_dir and music_root not in album_dir.parents:
        raise HTTPException(400, "Invalid path")
    cover = album_dir / "cover.jpg"
    if not cover.is_file():
        raise HTTPException(404, "No cover art")
    return FileResponse(cover, media_type="image/jpeg")

# ── Playlists ────────────────────────────────────────────────────────────────
def _playlist_track_count(name):
    m3u8 = Path(sync.MUSIC_DIR) / "Playlists" / f"{name}.m3u8"
    if not m3u8.exists():
        return 0
    return sum(1 for line in m3u8.read_text(encoding="utf-8").splitlines() if line.strip())

def _serialize_playlist(p, manifest):
    extra = []
    for uri in p.get("extra_tracks", []):
        info = manifest.get(uri)
        if info and not info.get("deleted"):
            extra.append({"uri": uri, "artist": info["artist"], "title": info["title"]})
    return {**p, "track_count": _playlist_track_count(p["name"]), "extra_tracks": extra}

@app.get("/api/playlists")
def get_playlists():
    manifest = sync.load_manifest()
    return [_serialize_playlist(p, manifest) for p in sync.load_playlists()]

@app.get("/api/spotify/lookup")
def lookup_playlist(url: str):
    """Resolve a Spotify playlist URL to its display name, via app-only auth
    (no login) — used to auto-fill the name field when a link is dropped in.
    Only works for public playlists; private ones just won't resolve."""
    if "/playlist/" not in url:
        raise HTTPException(400, "That doesn't look like a Spotify playlist URL")
    pid = url.split("/playlist/")[1].split("?")[0]
    try:
        info = sync.spotify_public_client().playlist(pid, fields="name")
    except Exception as e:
        raise HTTPException(404, f"Couldn't look up that playlist: {e}")
    return {"name": info.get("name", "")}

class AddPlaylistRequest(BaseModel):
    name: str
    url: str

@app.post("/api/playlists")
def add_playlist(req: AddPlaylistRequest):
    name, url = req.name.strip(), req.url.strip()
    if not name or not url:
        raise HTTPException(400, "Name and URL are required")
    if "/playlist/" not in url:
        raise HTTPException(400, "That doesn't look like a Spotify playlist URL")

    playlists = sync.load_playlists()
    if any(p["name"] == name for p in playlists):
        raise HTTPException(409, f"Playlist '{name}' already exists")

    playlists.append({"name": name, "url": url, "enabled": True})
    sync.save_playlists(playlists)
    return _serialize_playlist(playlists[-1], sync.load_manifest())

@app.delete("/api/playlists/{name}")
def remove_playlist(name: str):
    playlists = sync.load_playlists()
    remaining = [p for p in playlists if p["name"] != name]
    if len(remaining) == len(playlists):
        raise HTTPException(404, f"Playlist '{name}' not found")
    sync.save_playlists(remaining)
    return {"status": "removed"}

class ToggleRequest(BaseModel):
    enabled: Optional[bool] = None  # omit to flip the current value

@app.post("/api/playlists/{name}/toggle")
def toggle_playlist(name: str, req: ToggleRequest = ToggleRequest()):
    playlists = sync.load_playlists()
    for p in playlists:
        if p["name"] == name:
            p["enabled"] = req.enabled if req.enabled is not None else not p["enabled"]
            sync.save_playlists(playlists)
            return _serialize_playlist(p, sync.load_manifest())
    raise HTTPException(404, f"Playlist '{name}' not found")

class AddTrackRequest(BaseModel):
    uri: str

@app.post("/api/playlists/{name}/tracks")
def add_playlist_track(name: str, req: AddTrackRequest):
    manifest = sync.load_manifest()
    entry = manifest.get(req.uri)
    if not entry or entry.get("deleted"):
        raise HTTPException(404, "Track not found in library")

    playlists = sync.load_playlists()
    for p in playlists:
        if p["name"] == name:
            extra = p.setdefault("extra_tracks", [])
            if req.uri not in extra:
                extra.append(req.uri)
            sync.save_playlists(playlists)
            return _serialize_playlist(p, manifest)
    raise HTTPException(404, f"Playlist '{name}' not found")

@app.delete("/api/playlists/{name}/tracks/{uri:path}")
def remove_playlist_track(name: str, uri: str):
    playlists = sync.load_playlists()
    for p in playlists:
        if p["name"] == name:
            extra = p.get("extra_tracks", [])
            if uri in extra:
                extra.remove(uri)
                sync.save_playlists(playlists)
            return _serialize_playlist(p, sync.load_manifest())
    raise HTTPException(404, f"Playlist '{name}' not found")

# ── iPod status ──────────────────────────────────────────────────────────────
@app.get("/api/ipod")
def ipod_status():
    return {"connected": os.path.isdir(f"{sync.IPOD_DRIVE}\\Music")}

# ── Manual MP3 import (drag-and-drop) ───────────────────────────────────────
@app.post("/api/import")
async def import_mp3(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".mp3"):
        raise HTTPException(400, "Only .mp3 files are supported")

    tmp_dir = REPO_DIR / ".import_tmp"
    tmp_dir.mkdir(exist_ok=True)
    tmp_path = tmp_dir / f"{uuid.uuid4().hex}.mp3"
    tmp_path.write_bytes(await file.read())

    manifest = sync.load_manifest()
    try:
        result = sync.import_local_mp3(str(tmp_path), file.filename, manifest)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    if result["status"] == "error":
        raise HTTPException(422, result["message"])
    return result

@app.get("/")
def health():
    return {"status": "ok"}
