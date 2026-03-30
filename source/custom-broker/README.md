# Custom Broker

Fa tre cose:

1. legge i sensori con `GET /api/devices/`
2. apre una WebSocket per ogni sensore usando `websocket_url`
3. espone una WebSocket server e fa broadcast di ogni misura a tutte le repliche connesse

Niente reconnect.

## Contratto usato

Dal simulatore:

- `GET /api/devices/` restituisce una lista di sensori
- ogni sensore contiene `websocket_url`
- ogni stream invia messaggi con:

```json
{
  "timestamp": "2026-03-25T00:00:00.000000+00:00",
  "value": 0.123456
}
```

Verso ogni replica il broker invia:

```json
{
  "sensor_id": "sensor-08",
  "sensor_name": "DC North Perimeter",
  "category": "datacenter",
  "region": "Replica Datacenter",
  "coordinates": {
    "latitude": 45.4642,
    "longitude": 9.19
  },
  "measurement_unit": "mm/s",
  "sampling_rate_hz": 20.0,
  "timestamp": "2026-03-25T00:00:00.000000+00:00",
  "value": 0.123456
}
```

## Variabili ambiente

- `SIMULATOR_BASE_URL` default `http://simulator:8080`
- `BROKER_HOST` default `0.0.0.0`
- `BROKER_PORT` default `9000`
- `REPLICA_INGEST_PATH` default `/ws/ingest`
- `BROKER_URL` solo per `esempio_replica.py`, default `ws://localhost:9000/ws/ingest`

## Avvio locale

```bash
cd source/custom-broker
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

In un altro terminale puoi provare una replica client con:

```bash
python esempio_replica.py
```

## Docker

```bash
docker build -t custom-broker ./source/custom-broker
docker run --rm -p 9000:9000 \
  -e SIMULATOR_BASE_URL=http://simulator:8080 \
  custom-broker
```

## Esempio docker-compose

```yaml
custom-broker:
  build:
    context: ./custom-broker
  ports:
    - "9000:9000"
  environment:
    SIMULATOR_BASE_URL: http://simulator:8080
    BROKER_HOST: 0.0.0.0
    BROKER_PORT: 9000
    REPLICA_INGEST_PATH: /ws/ingest
```

## Note

- I sensori non sono hardcoded.
- Le repliche devono collegarsi al broker come client WebSocket.
- L'endpoint del broker per le repliche e `ws://<broker-host>:9000/ws/ingest`.
