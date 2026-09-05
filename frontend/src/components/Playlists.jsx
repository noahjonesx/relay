import { useEffect, useState } from "react";
import { api } from "../api";

function extractPlaylistUrl(raw) {
  const httpMatch = raw.match(/https?:\/\/open\.spotify\.com\/playlist\/[A-Za-z0-9]+(\?[^\s"]*)?/);
  if (httpMatch) return httpMatch[0];
  const uriMatch = raw.match(/spotify:playlist:([A-Za-z0-9]+)/);
  if (uriMatch) return `https://open.spotify.com/playlist/${uriMatch[1]}`;
  return null;
}

function slugify(s) {
  return s.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function AddPlaylistForm({ onAdded }) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [lookingUp, setLookingUp] = useState(false);
  const [dragging, setDragging] = useState(false);

  const applyDroppedText = async (raw) => {
    const found = extractPlaylistUrl(raw);
    if (!found) {
      setError("That doesn't look like a Spotify playlist link");
      return;
    }
    setError(null);
    setUrl(found);
    setLookingUp(true);
    try {
      const info = await api.lookupPlaylist(found);
      if (info.name) setName(slugify(info.name));
    } catch {
      // Private playlist or lookup failure — leave the name for manual entry.
    } finally {
      setLookingUp(false);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.addPlaylist(name.trim(), url.trim());
      setName("");
      setUrl("");
      onAdded();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      className={`add-playlist-form ${dragging ? "add-playlist-form--dragging" : ""}`}
      onSubmit={submit}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const raw = e.dataTransfer.getData("text/uri-list") || e.dataTransfer.getData("text/plain");
        if (raw) applyDroppedText(raw);
      }}
    >
      <input
        className="text-input"
        placeholder={lookingUp ? "Looking up name…" : "Name (e.g. september24)"}
        value={name}
        onChange={(e) => setName(e.target.value)}
        disabled={lookingUp}
        required
      />
      <input
        className="text-input"
        placeholder="Spotify playlist URL, or drop a link here"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        required
      />
      <button className="button" disabled={busy || lookingUp} type="submit">
        {busy ? "Adding…" : "Add playlist"}
      </button>
      {error && <p className="error-text">{error}</p>}
    </form>
  );
}

export default function Playlists({ onSyncStarted }) {
  const [playlists, setPlaylists] = useState(null);
  const [error, setError] = useState(null);

  const load = () => {
    api.playlists().then(setPlaylists).catch((e) => setError(e.message));
  };

  useEffect(load, []);

  const toggle = async (p) => {
    const updated = await api.togglePlaylist(p.name, !p.enabled);
    setPlaylists((all) => all.map((x) => (x.name === p.name ? updated : x)));
  };

  const removePlaylist = async (p) => {
    if (!window.confirm(`Remove "${p.name}" from your synced playlists? This won't delete any tracks.`)) {
      return;
    }
    await api.removePlaylist(p.name);
    setPlaylists((all) => all.filter((x) => x.name !== p.name));
  };

  const removeTrack = async (p, uri) => {
    const updated = await api.removeTrackFromPlaylist(p.name, uri);
    setPlaylists((all) => all.map((x) => (x.name === p.name ? updated : x)));
  };

  const syncOne = async (name) => {
    try {
      await api.startSync({ playlist: name });
      onSyncStarted?.();
    } catch (e) {
      setError(e.message);
    }
  };

  if (error) return <p className="error-text">{error}</p>;
  if (!playlists) return <p className="text-muted">Loading playlists…</p>;

  return (
    <div className="panel-stack">
      <AddPlaylistForm onAdded={load} />

      <ul className="playlist-list">
        {playlists.map((p) => (
          <li key={p.name} className="playlist-row">
            <div className="playlist-row-main">
              <label className="switch">
                <input type="checkbox" checked={p.enabled} onChange={() => toggle(p)} />
                <span className="switch-track" />
              </label>
              <div className="playlist-info">
                <div className="playlist-name">{p.name}</div>
                <div className="text-muted">{p.track_count} tracks synced</div>
              </div>
              <button className="button button--ghost" onClick={() => syncOne(p.name)}>
                Sync now
              </button>
              <button className="button button--danger" onClick={() => removePlaylist(p)}>
                Remove
              </button>
            </div>

            {p.extra_tracks.length > 0 && (
              <ul className="extra-track-list">
                {p.extra_tracks.map((t) => (
                  <li key={t.uri} className="extra-track-row">
                    <span>
                      {t.artist} – {t.title}
                    </span>
                    <span className="text-muted">local import</span>
                    <button
                      className="button button--ghost button--tiny"
                      onClick={() => removeTrack(p, t.uri)}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
      <p className="text-muted">
        Disabled playlists are skipped on the next full sync but aren't removed from your library.
        Local imports added to a playlist show up here. Assign them from the Library tab.
      </p>
    </div>
  );
}
