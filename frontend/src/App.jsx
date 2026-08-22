import { useEffect, useState } from "react";
import { api } from "./api";
import Library from "./components/Library";
import Playlists from "./components/Playlists";
import SyncPanel from "./components/SyncPanel";
import "./App.css";

const TABS = [
  { id: "library", label: "Library" },
  { id: "playlists", label: "Playlists" },
  { id: "sync", label: "Sync" },
];

export default function App() {
  const [tab, setTab] = useState("library");
  const [ipodConnected, setIpodConnected] = useState(null);

  useEffect(() => {
    const check = () => api.ipodStatus().then((r) => setIpodConnected(r.connected)).catch(() => {});
    check();
    const id = setInterval(check, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>relay</h1>
        <div className={`ipod-badge ${ipodConnected ? "ipod-badge--on" : ""}`}>
          <span aria-hidden="true">{ipodConnected ? "●" : "○"}</span>
          {ipodConnected === null ? "Checking iPod…" : ipodConnected ? "iPod connected" : "iPod not connected"}
        </div>
      </header>

      <nav className="app-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`app-tab ${tab === t.id ? "app-tab--active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="app-main">
        {tab === "library" && <Library />}
        {tab === "playlists" && <Playlists onSyncStarted={() => setTab("sync")} />}
        {tab === "sync" && <SyncPanel />}
      </main>
    </div>
  );
}
