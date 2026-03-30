"""
replica.py — Seismic Signal Processing Replica Node
=====================================================
Part of a fault-tolerant, distributed seismic analysis platform.

Responsibilities:
  • Connect to the Broker via WebSocket and receive real-time ground-velocity measurements
  • Maintain a per-sensor sliding window (200 samples) and run DFT-based anomaly detection
  • Persist sensor metadata and detected events to PostgreSQL (asyncpg)
  • Forward detected events to the Gateway via HTTP POST (httpx)
  • Listen for SHUTDOWN commands from the simulator's /api/control SSE endpoint
"""

import asyncio
import json
import logging
import os
import signal
import sys
from collections import deque

import asyncpg
import httpx
import numpy as np
import websockets
import uvicorn
from fastapi import FastAPI
from httpx_sse import aconnect_sse

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("replica")

# ---------------------------------------------------------------------------
# Configuration (override via environment variables)
# ---------------------------------------------------------------------------
ALLOWED_HTTP_PORTS = {8000, 8002, 8004, 8006, 8008, 8010}

BROKER_URLS = ["ws://localhost:9000/ws/ingest"]
HTTP_HOST = "0.0.0.0"
HTTP_PORT = int(os.getenv("HTTP_PORT", "8000"))

if HTTP_PORT not in ALLOWED_HTTP_PORTS:
    raise ValueError(
        f"Unsupported HTTP_PORT '{HTTP_PORT}'. Use one of: {sorted(ALLOWED_HTTP_PORTS)}"
    )

DB_DSN = os.getenv(
    "DB_DSN",
    "postgresql://replica:replica@localhost:5432/seismic",
)

GATEWAY_URL = "http://localhost:8001/api/events"
SIMULATOR_URL = "http://localhost:8080"

# Sliding-window & analysis parameters
WINDOW_SIZE = int(os.getenv("WINDOW_SIZE", "200"))
AMPLITUDE_THRESHOLD = float(os.getenv("AMPLITUDE_THRESHOLD", "0.01"))  # mm/s

# Overlapping window parameters
STEP_SIZE = int(
    os.getenv("STEP_SIZE", "20")
)  # Run DFT every 20 new samples (1 sec at 20Hz)
COOLDOWN_SAMPLES = int(
    os.getenv("COOLDOWN_SAMPLES", "100")
)  # Wait 5 secs before next detection allowed

# ---------------------------------------------------------------------------
# Shared runtime state
# ---------------------------------------------------------------------------
db_pool: asyncpg.Pool | None = None
http_client: httpx.AsyncClient | None = None

# Per-sensor sliding windows  {sensor_id: deque[float]}
windows: dict[str, deque] = {}

# Tracking counters for the overlapping window
sample_counters: dict[str, int] = {}
cooldown_counters: dict[str, int] = {}

# Sampling-rate cache          {sensor_id: float}
sampling_rates: dict[str, float] = {}

# Sensors already inserted into DB
seen_sensors: set[str] = set()

# Asyncio event — set when we need to shut down
shutdown_event = asyncio.Event()
http_server: uvicorn.Server | None = None
resolved_http_port = HTTP_PORT
resolved_replica_id = f"replica-{resolved_http_port}"

health_app = FastAPI(title="Processing Replica Health")


@health_app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "replica_id": resolved_replica_id,
        "health_url": f"http://{HTTP_HOST}:{resolved_http_port}/health",
        "broker_urls": BROKER_URLS,
        "gateway_url": GATEWAY_URL,
    }

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


async def connect_db() -> None:
    """Connect to an already-initialised PostgreSQL database and open a pool."""
    global db_pool
    db_pool = await asyncpg.create_pool(dsn=DB_DSN, min_size=2, max_size=10)
    log.info("Connected to database.")


async def upsert_sensor(payload: dict) -> None:
    """Insert static sensor metadata — once per unique sensor_id."""
    if db_pool is None:
        return

    sensor_id = payload["sensor_id"]
    if sensor_id in seen_sensors:
        return
    seen_sensors.add(sensor_id)
    coords = payload.get("coordinates", {})
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sensors
                    (sensor_id, sensor_name, category, region,
                     latitude, longitude, measurement_unit)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (sensor_id) DO NOTHING;
                """,
                sensor_id,
                payload.get("sensor_name"),
                payload.get("category"),
                payload.get("region"),
                coords.get("latitude"),
                coords.get("longitude"),
                payload.get("measurement_unit"),
            )
        log.info("Sensor registered: %s", sensor_id)
    except Exception as exc:
        log.error("DB error upserting sensor %s: %s", sensor_id, exc)
        seen_sensors.discard(sensor_id)  # retry next time


async def persist_event(event: dict) -> None:
    """Save a detected event — idempotent via ON CONFLICT DO NOTHING."""
    if db_pool is None:
        return

    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO events
                    (sensor_id, event_type, last_sample_timestamp,
                     peak_frequency, peak_amplitude, duration)
                VALUES ($1, $2, $3::timestamptz, $4, $5, $6)
                ON CONFLICT (sensor_id, last_sample_timestamp) DO NOTHING;
                """,
                event["sensor_id"],
                event["event_type"],
                event["last_sample_timestamp"],
                event["peak_frequency"],
                event["peak_amplitude"],
                event["duration"],
            )
        log.info(
            "Event persisted: sensor=%s type=%s ts=%s",
            event["sensor_id"],
            event["event_type"],
            event["last_sample_timestamp"],
        )
    except Exception as exc:
        log.error("DB error persisting event: %s", exc)


# ---------------------------------------------------------------------------
# Gateway forwarding
# ---------------------------------------------------------------------------


async def forward_to_gateway(event: dict) -> None:
    """POST the event to the Gateway — fire-and-forget style."""
    payload = {
        "sensor_id": event["sensor_id"],
        "event_type": event["event_type"],
        "last_sample_timestamp": event["last_sample_timestamp"],
        "peak_frequency": event["peak_frequency"],
        "peak_amplitude": event["peak_amplitude"],
        "duration": event["duration"],
    }
    try:
        resp = await http_client.post(GATEWAY_URL, json=payload, timeout=5.0)
        resp.raise_for_status()
        log.info("Event forwarded to Gateway (status %s).", resp.status_code)
    except Exception as exc:
        log.error("Gateway forward error: %s", exc)


# ---------------------------------------------------------------------------
# DFT / classification
# ---------------------------------------------------------------------------


def classify_frequency(freq_hz: float) -> str | None:
    """Return event type string or None if frequency is below classification bands."""
    if 0.5 <= freq_hz < 3.0:
        return "earthquake"
    if 3.0 <= freq_hz < 8.0:
        return "conventional_explosion"
    if freq_hz >= 8.0:
        return "nuclear_like"
    return None  # below 0.5 Hz — not classifiable


def analyse_window(
    samples: list[float], sampling_rate: float
) -> tuple[float, float] | None:
    """
    Run rfft on `samples`, ignore the DC component (index 0),
    and return (dominant_frequency_hz, peak_amplitude) or None
    if the peak amplitude is below the noise threshold.
    """
    arr = np.array(samples, dtype=np.float64)
    spectrum = np.fft.rfft(arr)
    freqs = np.fft.rfftfreq(len(arr), d=1.0 / sampling_rate)
    amplitudes = np.abs(spectrum)

    # Mask out the DC component and the frequencies out of range
    amplitudes[freqs < 0.5] = 0.0

    peak_idx = int(np.argmax(amplitudes))
    peak_amp = amplitudes[peak_idx]
    peak_freq = freqs[peak_idx]

    if peak_amp < AMPLITUDE_THRESHOLD:
        return None  # pure noise — do not raise an event

    return float(peak_freq), float(peak_amp)


# ---------------------------------------------------------------------------
# Per-message processing
# ---------------------------------------------------------------------------


async def process_message(raw: str) -> None:
    """Parse one WebSocket message, update state, and trigger event pipeline."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("Malformed JSON received: %s", exc)
        return

    sensor_id = payload.get("sensor_id")
    timestamp = payload.get("timestamp")
    value = payload.get("value")
    sampling_rate = payload.get("sampling_rate_hz", 20.0)

    if sensor_id is None or timestamp is None or value is None:
        log.warning("Incomplete payload — skipping: %s", payload)
        return

    # ---- Sensor metadata (static, persisted once) --------------------------
    asyncio.create_task(upsert_sensor(payload))

    # ---- Update per-sensor sliding window & counters -----------------------
    sampling_rates[sensor_id] = sampling_rate

    # print(sensor_id, timestamp, value, sampling_rate)
    # Initialize state for new sensors
    if sensor_id not in windows:
        windows[sensor_id] = deque(maxlen=WINDOW_SIZE)
        sample_counters[sensor_id] = 0
        cooldown_counters[sensor_id] = 0

    # Append new data
    win = windows[sensor_id]
    win.append(float(value))
    sample_counters[sensor_id] += 1

    # Decrement cooldown if active
    if cooldown_counters[sensor_id] > 0:
        cooldown_counters[sensor_id] -= 1

    # ---- Check if we are ready to analyze ----------------------------------
    # 1. Ensure the window is fully populated initially
    if len(win) < WINDOW_SIZE:
        return

    # 2. Ensure enough new samples have arrived (the slide/stride)
    if sample_counters[sensor_id] < STEP_SIZE:
        return

    # Ready to analyze — reset the step counter
    sample_counters[sensor_id] = 0

    # 3. Skip analysis if we are in a cooldown period from a recent event
    if cooldown_counters[sensor_id] > 0:
        return

    # ---- Run DFT -----------------------------------------------------------
    result = analyse_window(list(win), sampling_rate)
    if result is None:
        return  # below amplitude threshold

    peak_freq, peak_amp = result
    event_type = classify_frequency(peak_freq)
    if event_type is None:
        return  # frequency below detectable bands

    # ---- Event detected! ---------------------------------------------------
    duration = WINDOW_SIZE / sampling_rate  # seconds covered by the window

    event = {
        "sensor_id": sensor_id,
        "event_type": event_type,
        "last_sample_timestamp": timestamp,
        "peak_frequency": round(peak_freq, 4),
        "peak_amplitude": round(peak_amp, 6),
        "duration": round(duration, 3),
    }

    log.info(
        "EVENT DETECTED — sensor=%s type=%s freq=%.3f Hz amp=%.4f",
        sensor_id,
        event_type,
        peak_freq,
        peak_amp,
    )

    # The historical data stays in the buffer.
    # Trigger cooldown to prevent spamming the same event over and over.
    cooldown_counters[sensor_id] = COOLDOWN_SAMPLES

    # Persist + forward concurrently
    await asyncio.gather(
        persist_event(event),
        forward_to_gateway(event),
        return_exceptions=True,
    )


# ---------------------------------------------------------------------------
# Broker WebSocket client
# ---------------------------------------------------------------------------


async def consume_broker_stream() -> None:
    """
    Connect to the broker as a WebSocket client and keep retrying until shutdown.
    Consumes the broker stream until shutdown.
    """
    if not BROKER_URLS:
        raise RuntimeError("No broker URL configured. Set BROKER_URL or BROKER_URLS.")

    while not shutdown_event.is_set():
        for broker_url in BROKER_URLS:
            if shutdown_event.is_set():
                return

            try:
                log.info("Connecting to broker at %s", broker_url)
                async with websockets.connect(
                    broker_url,
                    ping_interval=20,
                    ping_timeout=10,
                ) as websocket:
                    log.info("Connected to broker at %s", broker_url)

                    async for message in websocket:
                        if shutdown_event.is_set():
                            return
                        await process_message(message)
            except asyncio.CancelledError:
                raise
            except websockets.ConnectionClosedError as exc:
                log.warning("Broker stream closed from %s: %s", broker_url, exc)
            except OSError as exc:
                log.warning("Broker connection failed for %s: %s", broker_url, exc)
            except Exception as exc:
                log.error("Unexpected broker client error for %s: %s", broker_url, exc)
        await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# SSE control stream — SHUTDOWN listener
# ---------------------------------------------------------------------------


async def listen_control_stream() -> None:
    """
    Connects to the simulator's /api/control SSE endpoint.
    When {"command": "SHUTDOWN"} is received, sets the global shutdown_event.
    Retries on transient connection errors.
    """
    control_url = f"{SIMULATOR_URL}/api/control"
    backoff = 1.0

    while not shutdown_event.is_set():
        try:
            async with aconnect_sse(http_client, "GET", control_url) as event_source:
                log.info("SSE control stream connected: %s", control_url)
                backoff = 1.0  # reset on success
                async for sse in event_source.aiter_sse():
                    if shutdown_event.is_set():
                        return
                    if sse.event == "command":
                        try:
                            data = json.loads(sse.data)
                        except json.JSONDecodeError:
                            continue
                        if data.get("command") == "SHUTDOWN":
                            log.warning(
                                "SHUTDOWN command received — initiating graceful shutdown."
                            )
                            shutdown_event.set()
                            return
        except asyncio.CancelledError:
            raise
        except (httpx.ReadError, httpx.RemoteProtocolError, httpx.ReadTimeout) as exc:
            if shutdown_event.is_set():
                return
            # Quietly retry common SSE disconnects; they are expected in practice.
            pass
        except Exception as exc:
            if shutdown_event.is_set():
                return
            error_name = exc.__class__.__name__
            error_detail = str(exc).strip() or "no details"
            log.error(
                "SSE control stream error (%s: %s) — retrying in %.1fs",
                error_name,
                error_detail,
                backoff,
            )
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 30.0)


# ---------------------------------------------------------------------------
# Replica health server
# ---------------------------------------------------------------------------


async def run_health_server() -> None:
    global http_server
    global resolved_http_port
    global resolved_replica_id

    resolved_http_port = HTTP_PORT
    resolved_replica_id = f"replica-{resolved_http_port}"

    config = uvicorn.Config(
        health_app,
        host=HTTP_HOST,
        port=resolved_http_port,
        log_level="warning",
    )
    http_server = uvicorn.Server(config)
    log.info(
        "Replica health server listening on http://%s:%d/health",
        HTTP_HOST,
        resolved_http_port,
    )
    await http_server.serve()


# ---------------------------------------------------------------------------
# Graceful shutdown helper
# ---------------------------------------------------------------------------


async def graceful_shutdown() -> None:
    """Wait for shutdown signal, then tear down DB pool and HTTP client."""
    await shutdown_event.wait()
    log.info("Shutting down — closing resources …")

    if db_pool:
        await db_pool.close()
        log.info("Database pool closed.")

    if http_client:
        await http_client.aclose()
        log.info("HTTP client closed.")

    if http_server is not None:
        http_server.should_exit = True

    log.info("Replica shut down cleanly.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def _keyboard_interrupt_watcher() -> None:
    """
    Cross-platform Ctrl-C handler.
    On Windows, loop.add_signal_handler() raises NotImplementedError, so we
    install a plain signal.signal handler that simply sets the shutdown event
    from the main thread instead.  asyncio.run() will propagate KeyboardInterrupt
    out of the event loop, which is caught in __main__.
    """
    await shutdown_event.wait()


def _install_signal_handlers() -> None:
    """Register SIGINT / SIGTERM in a platform-safe way."""

    def _handler(signum, frame):  # noqa: ANN001
        log.info("Signal %s received — requesting shutdown.", signum)
        # set() is thread-safe and can be called from a signal handler
        shutdown_event.set()

    signal.signal(signal.SIGINT, _handler)
    # SIGTERM is not available on Windows; guard accordingly
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handler)


async def main() -> None:
    global http_client

    # Initialise shared resources
    http_client = httpx.AsyncClient()
    log.info(
        "Replica starting with health=http://%s:%d/health broker=%s gateway=%s",
        HTTP_HOST,
        HTTP_PORT,
        BROKER_URLS[0],
        GATEWAY_URL,
    )
    try:
        await connect_db()
    except Exception as exc:
        db_pool = None
        log.warning("Database unavailable, continuing without persistence: %s", exc)

    # Launch all background tasks
    await asyncio.gather(
        run_health_server(),
        consume_broker_stream(),
        listen_control_stream(),
        graceful_shutdown(),
    )


if __name__ == "__main__":
    _install_signal_handlers()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Ctrl-C pressed before the event loop caught the signal
        shutdown_event.set()
        sys.exit(0)
