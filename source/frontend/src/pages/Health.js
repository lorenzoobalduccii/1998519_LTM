import React, { useEffect, useState } from 'react';
import { API_BASE } from '../config';

export default function Health() {
  const [healthData, setHealthData] = useState(null);

  useEffect(() => {
    // Poll the health status every 5 seconds
    const fetchHealth = () => {
      fetch(`${API_BASE}/system/status`)
        .then(res => res.json())
        .then(data => setHealthData(data))
        .catch(err => console.error(err));
    };
    
    fetchHealth();
    const interval = setInterval(fetchHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!healthData) return <div style={{color: 'white', fontSize: '2vh'}}>Loading System Status...</div>;

  return (
    <div>
      <h2 className="page-title">System Health Check</h2>
      
      <div className="grid-container">
        {healthData.configured_replicas.map(replicaUrl => {
          const isActive = healthData.active_list.includes(replicaUrl);
          
          return (
            <div key={replicaUrl} className="card">
              <div className="card-label">Replica Node</div>
              <div className="card-value" style={{ marginBottom: '2vh', fontSize: '2vh' }}>
                {replicaUrl}
              </div>
              <span className={`status-badge ${isActive ? 'status-active' : 'status-inactive'}`}>
                {isActive ? 'ACTIVE' : 'INACTIVE'}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
