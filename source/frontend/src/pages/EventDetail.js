import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { API_BASE } from '../config';

export default function EventDetail() {
  const { id } = useParams();
  const [event, setEvent] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/events/${id}`)
      .then(res => res.json())
      .then(data => setEvent(data.data))
      .catch(err => console.error(err));
  }, [id]);

  if (!event) return <div style={{color: 'white', fontSize: '2vh'}}>Loading...</div>;

  return (
    <div>
      <h2 className="page-title">Event Details: {event.event_id}</h2>
      
      <div className="grid-container" style={{ marginBottom: '3vh' }}>
        <div className="card">
          <div className="card-label">Timestamp</div>
          <div className="card-value">{new Date(event.last_sample_timestamp).toLocaleString()}</div>
        </div>
        <div className="card">
          <div className="card-label">Event Type</div>
          <div className="card-value">{event.event_type}</div>
        </div>
        <div className="card">
          <div className="card-label">Sensor & Region</div>
          <div className="card-value">{event.sensor_id} ({event.region})</div>
        </div>
        <div className="card">
          <div className="card-label">Peak Amplitude</div>
          <div className="card-value">{event.peak_amplitude.toFixed(3)} {event.measurement_unit}</div>
        </div>
        <div className="card">
          <div className="card-label">Peak Frequency</div>
          <div className="card-value">{event.peak_frequency.toFixed(2)} Hz</div>
        </div>
        <div className="card">
          <div className="card-label">Duration</div>
          <div className="card-value">{event.duration.toFixed(2)}s</div>
        </div>
      </div>

      <div className="placeholder-box chart-placeholder">
        [Waveform / Chart Placeholder]
      </div>
      <div className="placeholder-box map-placeholder">
        [Map Placeholder - Pin at Lat: {event.latitude}, Lng: {event.longitude}]
      </div>
    </div>
  );
}
