# Seismic Analysis Platform

## Overview
This project is a distributed, fault-tolerant seismic analysis platform designed to ingest live seismic measurements, classify suspicious activities using frequency analysis, and present real-time and historical data through a centralized web dashboard. The system is built on a microservices architecture to ensure high availability and is fully deployable via Docker Compose.

## System Architecture & Microservices

The architecture is composed of six core components acting together in a pipeline:

1. **Simulator (`seismic-simulator`)** 
   - Uses an external public image (`mattia9203/seismic-signal-simulator:multiarch_v1`).
   - Acts as the source of truth for sensor discovery, providing live time-domain seismic data streams and controlled shutdown commands used to simulate replica failures.
   
2. **Custom Broker (`custom-broker`)**
   - **Tech Stack:** Python 3.11, WebSockets
   - **Role:** Acts as the ingestion and distribution layer. It fetches metadata from the simulator, opens upstream WebSocket connections for every active sensor, normalizes incoming measurements into envelopes, and broadcasts them seamlessly to all connected processing replicas.

3. **Processing Replicas Cluster (`replica-1` to `replica-5`)**
   - **Tech Stack:** Python 3.11, FastAPI, NumPy, WebSockets
   - **Role:** Five identical replica containers handling the core computational load. They aggregate incoming measurements into independent sliding windows (200 samples window, 20 samples step size).
   - **Classification Logic:** Performs Fast Fourier Transform (FFT) analysis filtering out noise (frequencies under `0.5 Hz`), and applies a rules engine:
     - `0.5 <= f < 3.0 Hz` $\rightarrow$ `earthquake`
     - `3.0 <= f < 8.0 Hz` $\rightarrow$ `conventional_explosion`
     - `f >= 8.0 Hz` $\rightarrow$ `nuclear_like`
   - **Forwarding:** Successfully classified seismic events generate enriched alert payloads that are seamlessly forwarded to the central Gateway.

4. **Gateway (`gateway`)**
   - **Tech Stack:** Python 3.11, FastAPI, Asyncpg
   - **Role:** The synchronization and aggregation layer. Since five replicas analyze the exact same streams concurrently for fault-tolerance, the Gateway acts to unify replicated events.
   - **Deduplication:** A deterministic identifier (`sha256(sensor_id|timestamp|event_type)`) suppresses duplicate live alerts before persisting exactly one instance of a disturbance.
   - **API & Feeds:** It exposes internal REST ingest routes, historical APIs for dashboard consumption, and pushes live deduplicated events to the frontend via WebSockets. It also actively polls replicas to expose real-time system health metrics.

5. **Relational Database (`postgres`)**
   - **Tech Stack:** PostgreSQL 16
   - **Role:** Represents the persistent state storage maintaining sensor metadata records and the deduplicated history of detected seismic events mapped tightly to the UI.

6. **Frontend Dashboard (`frontend`)**
   - **Tech Stack:** React, React Router, Nginx
   - **Role:** Exposes four primary Operator and Administrator interfaces:
     - **Sensors:** Live overview of the physical network logic and components.
     - **Historical Events:** Consolidated data view combining live WebSocket events and persisted storage data, with localized frontend filtering across regions, sensors, event types, and peak amplitudes.
     - **Event Details:** Drill-down interface for exact anomaly timestamps and dominant frequencies.
     - **System Health:** Tracks exact replica availability statuses and timestamps for hardware and node failures occurring across the processing cluster.

## Deployment Details

The entire infrastructure stack is orchestrated via **Docker Compose**.
To initialize the distributed system locally:

```bash
docker compose up -d
```
All configurations, image building patterns, inter-service startup barriers, and internal database bootstrapping are automatically coordinated by the Compose `depends_on` and internal Docker network mechanics. The frontend portal maps securely to the host machine on port `3000`.

## Fault Tolerance Strategy
The platform guarantees continuous operation providing at least one processing replica container stays online. If individual nodes suffer failures (induced directly via Simulator SSE streams), the Gateway natively flags their unresponsiveness accurately on the Health Dashboard, while overall systemic detection and alerting persist uninterrupted.
