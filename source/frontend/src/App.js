import React from 'react';
import { HashRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Sensors from './pages/Sensors';
import History from './pages/History';
import EventDetail from './pages/EventDetail';
import Health from './pages/Health';
import './styles.css';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/sensors" />} />
          <Route path="/sensors" element={<Sensors />} />
          <Route path="/history" element={<History />} />
          <Route path="/event/:id" element={<EventDetail />} />
          <Route path="/health" element={<Health />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
