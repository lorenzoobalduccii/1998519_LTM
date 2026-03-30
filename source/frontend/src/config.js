const trimTrailingSlash = (value) => value.replace(/\/+$/, '');

const getDefaultApiBase = () => {
  if (process.env.NODE_ENV === 'development') {
    return 'http://localhost:8001/api';
  }

  return '/api';
};

export const API_BASE = trimTrailingSlash(
  process.env.REACT_APP_API_URL || getDefaultApiBase()
);

export const LIVE_WS_URL =
  process.env.REACT_APP_WS_URL ||
  (process.env.NODE_ENV === 'development'
    ? 'ws://localhost:8001/ws/live'
    : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/live`);
