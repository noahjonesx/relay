import { useCallback, useState } from "react";
import { api } from "../api";

export default function ImportDropzone({ onImported }) {
  const [dragging, setDragging] = useState(false);
  const [results, setResults] = useState([]);

  const importFiles = useCallback(
    async (files) => {
      const mp3s = files.filter((f) => f.name.toLowerCase().endsWith(".mp3"));
      for (const file of mp3s) {
        const entryId = `${file.name}-${Date.now()}-${Math.random()}`;
        setResults((r) => [{ id: entryId, name: file.name, status: "uploading" }, ...r]);
        try {
          const result = await api.importMp3(file);
          setResults((r) =>
            r.map((e) => (e.id === entryId ? { ...e, status: result.status, result } : e))
          );
          if (result.status === "added") onImported?.();
        } catch (e) {
          setResults((r) =>
            r.map((e) => (e.id === entryId ? { ...e, status: "error", message: e.message } : e))
          );
        }
      }
    },
    [onImported]
  );

  return (
    <div className="import-zone-wrap">
      <div
        className={`import-zone ${dragging ? "import-zone--active" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          importFiles(Array.from(e.dataTransfer.files));
        }}
      >
        <p>Drag &amp; drop MP3 files here to add them to the library</p>
        <label className="button button--ghost">
          or choose files
          <input
            type="file"
            accept=".mp3"
            multiple
            hidden
            onChange={(e) => importFiles(Array.from(e.target.files))}
          />
        </label>
      </div>

      {results.length > 0 && (
        <ul className="import-results">
          {results.map((r) => (
            <li key={r.id} className={`import-result import-result--${r.status}`}>
              <span className="import-result-name">{r.name}</span>
              <span className="import-result-status">
                {r.status === "uploading" && "Uploading…"}
                {r.status === "added" &&
                  `Added: ${r.result.track.artist} · ${r.result.track.title}${
                    r.result.matched_spotify ? "" : " (no Spotify match, using file tags)"
                  }`}
                {r.status === "duplicate" && r.result.message}
                {r.status === "error" && (r.message || "Import failed")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
