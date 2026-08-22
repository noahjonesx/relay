import { useEffect, useState } from "react";
import { api } from "../api";

function AlbumCover({ album }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div className="album-cover album-cover--placeholder">
        {album.album.slice(0, 1).toUpperCase()}
      </div>
    );
  }
  return (
    <img
      className="album-cover"
      src={album.art}
      alt={`${album.artist} – ${album.album}`}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

export default function AlbumGrid() {
  const [albums, setAlbums] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.albums().then(setAlbums).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error-text">Failed to load albums: {error}</p>;
  if (!albums) return <p className="text-muted">Loading albums…</p>;

  return (
    <div className="album-grid">
      {albums.map((a) => (
        <div className="album-card" key={`${a.artist}::${a.album}`}>
          <AlbumCover album={a} />
          <div className="album-card-title">{a.album}</div>
          <div className="album-card-subtitle text-muted">{a.artist}</div>
          <div className="album-card-subtitle text-muted">
            {a.track_count} track{a.track_count === 1 ? "" : "s"}
          </div>
        </div>
      ))}
    </div>
  );
}
