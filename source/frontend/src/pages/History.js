import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API_BASE, LIVE_WS_URL } from '../config';

export default function History() {
  const [events, setEvents] = useState([]);
  const [filters, setFilters] = useState({ event_type: '', region: '', sensor_id: '' });
  const navigate = useNavigate();

  useEffect(() => {
    // Build query string from filters
    const query = new URLSearchParams(
      Object.entries(filters).filter(([_, v]) => v !== '')
    ).toString();
    
    fetch(`${API_BASE}/history?${query}`)
      .then(res => res.json())
      .then(data => setEvents(data.data || []))
      .catch(err => console.error(err));
  }, [filters]);

  const handleFilterChange = (e) => {
    setFilters({ ...filters, [e.target.name]: e.target.value });
  };
  
  useEffect(() => {
  const ws = new WebSocket(LIVE_WS_URL);

  ws.onmessage = (message) => {
    const newEvent = JSON.parse(message.data);
    
    // Aggiorna lo stato aggiungendo il nuovo evento in cima all'array esistente
    setEvents(prevEvents => {
      // Evita duplicati se l'evento è già stato caricato dalla fetch storica
      if (prevEvents.some(e => e.event_id === newEvent.event_id)) {
        return prevEvents;
      }
      return [newEvent, ...prevEvents];
    });
  };

  // Termina la connessione al disinnesto del componente
  return () => ws.close(); 
}, []);

  return (
    <div>
      <h2 className="page-title">Event History</h2>
      
      <div className="filters-bar">
        <input name="event_type" placeholder="Event Type" className="filter-input" onChange={handleFilterChange} />
        <input name="region" placeholder="Region" className="filter-input" onChange={handleFilterChange} />
        <input name="sensor_id" placeholder="Sensor ID" className="filter-input" onChange={handleFilterChange} />
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Event ID</th>
              <th>Type</th>
              <th>Sensor</th>
              <th>Region</th>
              <th>Amplitude</th>
            </tr>
          </thead>
          <tbody>
            {events.map(ev => (
              <tr key={ev.event_id} className="clickable" onClick={() => navigate(`/event/${ev.event_id}`)}>
                <td>{new Date(ev.last_sample_timestamp).toLocaleString()}</td>
                <td>{ev.event_id}</td>
                <td>{ev.event_type}</td>
                <td>{ev.sensor_id}</td>
                <td>{ev.region}</td>
                <td>{ev.peak_amplitude.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
