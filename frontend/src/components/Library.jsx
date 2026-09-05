import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import StatTile from "./StatTile";
import ImportDropzone from "./ImportDropzone";
import AlbumGrid from "./AlbumGrid";

function albumArtUrl(path) {
  const dir = path.split("/").slice(0, -1).join("/");
  return `/api/art?path=${encodeURIComponent(dir)}`;
}

function TrackThumb({ track }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return <div className="track-thumb track-thumb--placeholder">{track.album.slice(0, 1).toUpperCase()}</div>;
  }
  return (
    <img
      className="track-thumb"
      src={albumArtUrl(track.path)}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

function AddToPlaylist({ track, playlists, onAdded }) {
  const [busy, setBusy] = useState(false);

  if (!playlists || playlists.length === 0) return null;

  const handleChange = async (e) => {
    const name = e.target.value;
    e.target.value = "";
    if (!name) return;
    setBusy(true);
    try {
      await api.addTrackToPlaylist(name, track.uri);
      onAdded?.(name);
    } finally {
      setBusy(false);
    }
  };

  return (
    <select className="mini-select" defaultValue="" onChange={handleChange} disabled={busy}>
      <option value="" disabled>
        {busy ? "Adding…" : "+ Add to playlist"}
      </option>
      {playlists.map((p) => (
        <option key={p.name} value={p.name}>
          {p.name}
        </option>
      ))}
    </select>
  );
}

export default function Library() {
  const [data, setData] = useState(null);
  const [playlists, setPlaylists] = useState(null);
  const [query, setQuery] = useState("");
  const [view, setView] = useState("table");
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  const load = () => {
    api.library().then(setData).catch((e) => setError(e.message));
    api.playlists().then(setPlaylists).catch(() => {});
  };

  useEffect(load, []);

  const deleteTrack = async (t) => {
    if (!window.confirm(`Delete "${t.artist} – ${t.title}"? This removes the file from your library and the iPod.`)) {
      return;
    }
    try {
      const result = await api.deleteTrack(t.uri);
      setToast(
        result.shared_file_retained
          ? `Removed "${t.title}" (file kept, still used by a duplicate)`
          : `Deleted "${t.title}" from the library and iPod`
      );
      load();
    } catch (e) {
      setToast(`Failed to delete "${t.title}": ${e.message}`);
    }
  };

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    return data.tracks
      .filter((t) => !t.deleted)
      .filter(
        (t) =>
          !q ||
          t.artist.toLowerCase().includes(q) ||
          t.title.toLowerCase().includes(q) ||
          t.album.toLowerCase().includes(q)
      )
      .sort((a, b) => a.artist.localeCompare(b.artist) || a.album.localeCompare(b.album));
  }, [data, query]);

  if (error) return <p className="error-text">Failed to load library: {error}</p>;
  if (!data) return <p className="text-muted">Loading library…</p>;

  return (
    <div className="panel-stack">
      <div className="stat-row">
        <StatTile label="Tracks" value={data.stats.active} />
        <StatTile label="Artists" value={data.stats.artists} />
        <StatTile label="Albums" value={data.stats.albums} />
      </div>

      <ImportDropzone onImported={load} />

      <div className="library-toolbar">
        <input
          className="text-input"
          placeholder="Search artist, title, or album…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="view-toggle">
          <button
            className={`view-toggle-btn ${view === "table" ? "view-toggle-btn--active" : ""}`}
            onClick={() => setView("table")}
          >
            Table
          </button>
          <button
            className={`view-toggle-btn ${view === "albums" ? "view-toggle-btn--active" : ""}`}
            onClick={() => setView("albums")}
          >
            Albums
          </button>
        </div>
      </div>

      {toast && <p className="text-muted">{toast}</p>}

      {view === "albums" ? (
        <AlbumGrid />
      ) : (
        <div className="table-wrap">
          <table className="track-table">
            <thead>
              <tr>
                <th></th>
                <th>Artist</th>
                <th>Title</th>
                <th>Album</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr key={t.uri}>
                  <td className="track-thumb-cell">
                    <TrackThumb track={t} />
                  </td>
                  <td>{t.artist}</td>
                  <td>{t.title}</td>
                  <td>{t.album}</td>
                  <td className="track-actions">
                    {t.local && (
                      <AddToPlaylist
                        track={t}
                        playlists={playlists}
                        onAdded={(name) => setToast(`Added "${t.title}" to ${name}`)}
                      />
                    )}
                    <button
                      className="button button--danger button--tiny"
                      onClick={() => deleteTrack(t)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && <p className="text-muted">No tracks match "{query}".</p>}
        </div>
      )}
    </div>
  );
}
