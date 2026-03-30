import React, { useEffect, useState } from 'react';
import { API_BASE } from '../config';

export default function Sensors() {
  const [sensors, setSensors] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE}/sensors`)
      .then(res => res.json())
      .then(data => setSensors(data.data || []))
      .catch(err => console.error(err));
  }, []);

  return (
    <div>
      <h2 className="page-title">Sensor Network</h2>
      <div className="placeholder-box map-placeholder">
        [Map Placeholder - Sensor Locations]
      </div>
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Category</th>
              <th>Region</th>
              <th>Coordinates</th>
            </tr>
          </thead>
          <tbody>
            {sensors.map(s => (
              <tr key={s.sensor_id}>
                <td>{s.sensor_id}</td>
                <td>{s.sensor_name}</td>
                <td>{s.category}</td>
                <td>{s.region}</td>
                <td>{s.latitude}, {s.longitude}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
