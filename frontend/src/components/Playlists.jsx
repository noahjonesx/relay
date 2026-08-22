import { useEffect, useState } from "react";
import { api } from "../api";

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
        Local imports added to a playlist show up here — assign them from the Library tab.
      </p>
    </div>
  );
}
