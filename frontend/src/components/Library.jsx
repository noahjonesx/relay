import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import StatTile from "./StatTile";
import ImportDropzone from "./ImportDropzone";
import AlbumGrid from "./AlbumGrid";

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
                <th>Artist</th>
                <th>Title</th>
                <th>Album</th>
                <th>Source</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr key={t.uri}>
                  <td>{t.artist}</td>
                  <td>{t.title}</td>
                  <td>{t.album}</td>
                  <td>{t.local ? "Local import" : "Spotify"}</td>
                  <td>
                    {t.local && (
                      <AddToPlaylist
                        track={t}
                        playlists={playlists}
                        onAdded={(name) => setToast(`Added "${t.title}" to ${name}`)}
                      />
                    )}
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
