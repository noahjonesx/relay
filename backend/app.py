"""
FastAPI backend for the iPod sync UI.

Thin wrapper around sync.py: it shells out to `py sync.py ...` for actual
sync runs (streaming its stdout live over a WebSocket) and calls sync.py's
functions directly for read-only/library-editing operations (library list,
playlist toggles, manual MP3 import). No sync logic is duplicated here.
"""
import asyncio
import os
import sys
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

# ── Playlists ────────────────────────────────────────────────────────────────
def _playlist_track_count(name):
    m3u8 = Path(sync.MUSIC_DIR) / "Playlists" / f"{name}.m3u8"
    if not m3u8.exists():
        return 0
    return sum(1 for line in m3u8.read_text(encoding="utf-8").splitlines() if line.strip())

@app.get("/api/playlists")
def get_playlists():
    return [{**p, "track_count": _playlist_track_count(p["name"])} for p in sync.load_playlists()]

class ToggleRequest(BaseModel):
    enabled: Optional[bool] = None  # omit to flip the current value

@app.post("/api/playlists/{name}/toggle")
def toggle_playlist(name: str, req: ToggleRequest = ToggleRequest()):
    playlists = sync.load_playlists()
    for p in playlists:
        if p["name"] == name:
            p["enabled"] = req.enabled if req.enabled is not None else not p["enabled"]
            sync.save_playlists(playlists)
            return {**p, "track_count": _playlist_track_count(name)}
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
