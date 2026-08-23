const BASE = "/api";

async function request(path, opts) {
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = body.detail || message;
    } catch {
      // ignore — not JSON
    }
    throw new Error(message);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  library: () => request("/library"),
  deleteTrack: (uri) => request(`/library/${encodeURIComponent(uri)}`, { method: "DELETE" }),
  albums: () => request("/albums"),
  playlists: () => request("/playlists"),
  addPlaylist: (name, url) =>
    request("/playlists", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, url }),
    }),
  removePlaylist: (name) => request(`/playlists/${encodeURIComponent(name)}`, { method: "DELETE" }),
  lookupPlaylist: (url) => request(`/spotify/lookup?url=${encodeURIComponent(url)}`),
  togglePlaylist: (name, enabled) =>
    request(`/playlists/${encodeURIComponent(name)}/toggle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    }),
  addTrackToPlaylist: (name, uri) =>
    request(`/playlists/${encodeURIComponent(name)}/tracks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uri }),
    }),
  removeTrackFromPlaylist: (name, uri) =>
    request(`/playlists/${encodeURIComponent(name)}/tracks/${encodeURIComponent(uri)}`, {
      method: "DELETE",
    }),
  ipodStatus: () => request("/ipod"),
  spotifyStatus: () => request("/spotify/status"),
  spotifyLogin: () => request("/spotify/login", { method: "POST" }),
  syncStatus: () => request("/sync/status"),
  startSync: (opts) =>
    request("/sync/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opts),
    }),
  stopSync: () => request("/sync/stop", { method: "POST" }),
  runDedupe: () => request("/sync/dedupe", { method: "POST" }),
  importMp3: async (file) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/import`, { method: "POST", body: form });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || "Import failed");
    return body;
  },
};

export function connectLogSocket(onLine) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${window.location.host}/ws/logs`);
  ws.onmessage = (evt) => onLine(evt.data);
  return ws;
}
