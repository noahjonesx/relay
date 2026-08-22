import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import StatTile from "./StatTile";
import ImportDropzone from "./ImportDropzone";

export default function Library() {
  const [data, setData] = useState(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState(null);

  const load = () => {
    api.library().then(setData).catch((e) => setError(e.message));
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

      <input
        className="text-input"
        placeholder="Search artist, title, or album…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      <div className="table-wrap">
        <table className="track-table">
          <thead>
            <tr>
              <th>Artist</th>
              <th>Title</th>
              <th>Album</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr key={t.uri}>
                <td>{t.artist}</td>
                <td>{t.title}</td>
                <td>{t.album}</td>
                <td>{t.local ? "Local import" : "Spotify"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && <p className="text-muted">No tracks match "{query}".</p>}
      </div>
    </div>
  );
}
