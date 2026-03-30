import React, { useEffect, useRef, useState } from "react";
import { API_BASE } from "../config";
import {
  formatCompactTimestamp,
  replicaLabel,
} from "../utils/platform";

export default function Health() {
  const replicaStateRef = useRef({});
  const [summary, setSummary] = useState(null);
  const [replicaRows, setReplicaRows] = useState([]);
  const [healthEvents, setHealthEvents] = useState(() => {
    const saved = sessionStorage.getItem("healthEvents");
    return saved ? JSON.parse(saved) : [];
  });

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const response = await fetch(`${API_BASE}/system/status`);
        const payload = await response.json();
        const receivedAt = new Date().toISOString();
        const nextReplicaState = {};
        const nextRows = payload.configured_replicas.map((replicaUrl, index) => {
          const isHealthy = payload.active_list.includes(replicaUrl);
          const previous = replicaStateRef.current[replicaUrl];
          const nextStatus = isHealthy ? "healthy" : "unavailable";
          const lastHeartbeat = isHealthy
            ? receivedAt
            : previous?.lastHeartbeat || null;
          const unavailableSince = isHealthy
            ? null
            : previous?.unavailableSince || receivedAt;

          nextReplicaState[replicaUrl] = {
            status: nextStatus,
            lastHeartbeat,
            unavailableSince,
          };

          return {
            id: replicaLabel(replicaUrl, index),
            status: nextStatus,
            lastHeartbeat,
            unavailableSince,
          };
        });

        const nextEvents = [];

        payload.configured_replicas.forEach((replicaUrl, index) => {
          const previous = replicaStateRef.current[replicaUrl];
          const current = nextReplicaState[replicaUrl];

          if (!previous || previous.status === current.status) {
            return;
          }

          const label = replicaLabel(replicaUrl, index);

          if (current.status === "unavailable") {
            nextEvents.unshift(
              `${formatCompactTimestamp(receivedAt)} UTC | ${label} heartbeat lost`
            );
            nextEvents.unshift(
              `${formatCompactTimestamp(receivedAt)} UTC | ${label} marked unavailable`
            );
          } else {
            nextEvents.unshift(
              `${formatCompactTimestamp(receivedAt)} UTC | ${label} rejoined cluster`
            );
          }
        });

        replicaStateRef.current = nextReplicaState;
        setSummary(payload);
        setReplicaRows(nextRows);

        if (nextEvents.length) {
          setHealthEvents((current) => {
            // Unisce i nuovi eventi ai vecchi e tiene gli ultimi 6
            const updatedEvents = [...nextEvents, ...current].slice(0, 6);
            // Salva istantaneamente nel browser per sopravvivere al cambio pagina
            sessionStorage.setItem("healthEvents", JSON.stringify(updatedEvents));
            return updatedEvents;
          });
        }
      } catch (error) {
        console.error(error);
      }
    };

    fetchHealth();
    const interval = setInterval(fetchHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!summary) {
    return (
      <div className="page-shell">
        <header className="page-header">
          <h1 className="page-title">System Health</h1>
        </header>
      </div>
    );
  }

  const totalReplicas = summary.configured_replicas.length;
  const healthyReplicas = summary.active_list.length;
  const unavailableReplicas = summary.dead_list.length;
  const liveData = healthyReplicas > 0 ? "Active" : "Unavailable";

  return (
    <div className="page-shell">
      <header className="page-header page-header--split">
        <div>
          <h1 className="page-title">System Health</h1>
        </div>

        <span className="pill">ADMIN</span>
      </header>

      <section className="page-section">
        <div className="section-label">Summary</div>

        <div className="summary-grid">
          <div className="summary-card">
            <div className="summary-card__label">Total Replicas</div>
            <div className="summary-card__value">{totalReplicas}</div>
          </div>

          <div className="summary-card">
            <div className="summary-card__label">Healthy</div>
            <div className="summary-card__value">{healthyReplicas}</div>
          </div>

          <div className="summary-card">
            <div className="summary-card__label">Unavailable</div>
            <div className="summary-card__value">{unavailableReplicas}</div>
          </div>

          <div className="summary-card">
            <div className="summary-card__label">Live Data</div>
            <div 
              className="summary-card__value" 
              style={{ color: liveData === "Active" ? "#00e676" : "#ff4444" }}
            >
              {liveData}
            </div>
          </div>
        </div>
      </section>

      <section className="page-section">
        <div className="section-label">Replica Status</div>

        <div className="table-shell">
          <table className="platform-table">
            <thead>
              <tr>
                <th>Replica ID</th>
                <th>Status</th>
                <th>Last Heartbeat</th>
                <th>Unavailable Since</th>
              </tr>
            </thead>
            <tbody>
              {replicaRows.map((row) => (
                <tr key={row.id}>
                  <td>{row.id}</td>
                  <td>
                    <span className="pill">
                      {row.status === "healthy" ? "HEALTHY" : "UNAVAILABLE"}
                    </span>
                  </td>
                  <td>
                    {row.lastHeartbeat
                      ? formatCompactTimestamp(row.lastHeartbeat)
                      : "-"}
                  </td>
                  <td>
                    {row.unavailableSince
                      ? formatCompactTimestamp(row.unavailableSince)
                      : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="page-section">
        <div className="section-label">Health Events</div>

        <div className="health-log">
          {healthEvents.length ? (
            healthEvents.map((entry) => (
              <div key={entry} className="health-log__entry">
                {entry}
              </div>
            ))
          ) : (
            <div className="health-log__entry">
              Live monitoring active. Waiting for replica state changes.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
