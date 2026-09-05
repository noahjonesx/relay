import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import Library from "./components/Library";
import Playlists from "./components/Playlists";
import SyncPanel from "./components/SyncPanel";
import "./App.css";

export default function App() {
  const [ipodConnected, setIpodConnected] = useState(null);
  const syncRef = useRef(null);

  useEffect(() => {
    const check = () => api.ipodStatus().then((r) => setIpodConnected(r.connected)).catch(() => {});
    check();
    const id = setInterval(check, 5000);
    return () => clearInterval(id);
  }, []);

  const scrollToSync = () => {
    syncRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>relay</h1>
        <div className={`ipod-badge ${ipodConnected ? "ipod-badge--on" : ""}`}>
          <span aria-hidden="true">{ipodConnected ? "●" : "○"}</span>
          {ipodConnected === null ? "Checking iPod…" : ipodConnected ? "iPod connected" : "iPod not connected"}
        </div>
      </header>

      <main className="dashboard-grid">
        <div className="dashboard-col dashboard-col--side">
          <section className="dashboard-section" ref={syncRef}>
            <h2 className="dashboard-section-title">Sync</h2>
            <SyncPanel />
          </section>

          <section className="dashboard-section">
            <h2 className="dashboard-section-title">Playlists</h2>
            <Playlists onSyncStarted={scrollToSync} />
          </section>
        </div>

        <div className="dashboard-col dashboard-col--main">
          <section className="dashboard-section">
            <h2 className="dashboard-section-title">Library</h2>
            <Library />
          </section>
        </div>
      </main>
    </div>
  );
}
