import { useEffect, useRef, useState } from "react";
import { api, connectLogSocket } from "../api";
import StatusPill from "./StatusPill";

function SpotifyAuth() {
  const [status, setStatus] = useState(null);
  const [waiting, setWaiting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const refresh = () => api.spotifyStatus().then(setStatus).catch(() => {});
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (waiting && status?.authenticated) setWaiting(false);
  }, [status, waiting]);

  const login = async () => {
    setError(null);
    setWaiting(true);
    try {
      const { url } = await api.spotifyLogin();
      window.open(url, "_blank", "noopener");
    } catch (e) {
      setError(e.message);
      setWaiting(false);
    }
  };

  if (!status) return null;

  return (
    <div className="spotify-auth-row">
      <StatusPill
        variant={status.authenticated ? "good" : "critical"}
        label={status.authenticated ? "Spotify connected" : "Spotify login required"}
      />
      {!status.authenticated && (
        <button className="button button--ghost button--tiny" onClick={login} disabled={waiting}>
          {waiting ? "Waiting for login…" : "Login to Spotify"}
        </button>
      )}
      {error && <span className="error-text">{error}</span>}
    </div>
  );
}

export default function SyncPanel() {
  const [lines, setLines] = useState([]);
  const [status, setStatus] = useState({ running: false, exit_code: null });
  const [error, setError] = useState(null);
  const logRef = useRef(null);

  useEffect(() => {
    const ws = connectLogSocket((line) => setLines((l) => [...l, line]));
    const poll = setInterval(() => api.syncStatus().then(setStatus).catch(() => {}), 1500);
    api.syncStatus().then(setStatus).catch(() => {});
    return () => {
      ws.close();
      clearInterval(poll);
    };
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight);
  }, [lines]);

  const run = async (action) => {
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e.message);
    }
  };

  const pillVariant = status.running
    ? "running"
    : status.exit_code === 0
    ? "good"
    : status.exit_code
    ? "critical"
    : "idle";

  return (
    <div className="panel-stack">
      <div className="sync-toolbar">
        <div className="sync-toolbar-header">
          <StatusPill variant={pillVariant} />
          <SpotifyAuth />
        </div>
        <div className="sync-buttons">
          <button
            className="button"
            disabled={status.running}
            onClick={() => run(() => api.startSync({}))}
          >
            Full sync
          </button>
          <button
            className="button button--ghost"
            disabled={status.running}
            onClick={() => run(() => api.startSync({ no_ipod: true }))}
          >
            Download only
          </button>
          <button
            className="button button--ghost"
            disabled={status.running}
            onClick={() => run(() => api.startSync({ ipod_only: true }))}
          >
            iPod only
          </button>
          <button
            className="button button--ghost"
            disabled={status.running}
            onClick={() => run(() => api.runDedupe())}
          >
            Run dedupe
          </button>
          <button
            className="button button--danger"
            disabled={!status.running}
            onClick={() => run(() => api.stopSync())}
          >
            Stop
          </button>
        </div>
      </div>

      {error && <p className="error-text">{error}</p>}

      <div className="log-toolbar">
        <button
          className="button button--ghost button--tiny"
          disabled={lines.length === 0}
          onClick={() => {
            setLines([]);
            api.clearLogs().catch(() => {});
          }}
        >
          Clear log
        </button>
      </div>

      <pre className="log-view mono" ref={logRef}>
        {lines.length === 0 ? "No output yet. Start a sync to see logs here." : lines.join("\n")}
      </pre>
    </div>
  );
}
