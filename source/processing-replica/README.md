# Processing Replica

Replica di processing che:

1. si collega al broker come client WebSocket
2. espone `/health` via HTTP
3. inoltra gli eventi al gateway
4. opzionalmente persiste su PostgreSQL

## Event ID

`event_id` e deterministico ed e derivato da:

- `sensor_id`
- `last_sample_timestamp`
- `event_type`

In questo modo:

- tutte le repliche generano lo stesso `event_id` per lo stesso evento
- i restart non resettano piu gli ID logici
- il database puo mantenere `UNIQUE(event_id)` senza collisioni dovute ai contatori locali

## Variabili ambiente

- `BROKER_URL` default `ws://localhost:9000/ws/ingest`
- `BROKER_URLS` opzionale lista separata da virgole
- `GATEWAY_URL` default `http://localhost:8001/api/events`
- `HTTP_HOST` default `0.0.0.0`
- `HTTP_PORT` default `8000`
- `DB_DSN` default `postgresql://replica:replica@localhost:5432/seismic`
- `SIMULATOR_URL` default `http://localhost:8080`

## Avvio locale

Prima replica:

```bash
cd source/processing-replica
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export HTTP_PORT=8000
export BROKER_URL=ws://localhost:9000/ws/ingest
export GATEWAY_URL=http://localhost:8001/api/events
export DB_DSN=postgresql://replica:replica@localhost:5432/seismic
python3 replica.py
```

Seconda replica:

```bash
cd source/processing-replica
source .venv/bin/activate
export HTTP_PORT=8002
export BROKER_URL=ws://localhost:9000/ws/ingest
export GATEWAY_URL=http://localhost:8001/api/events
export DB_DSN=postgresql://replica:replica@localhost:5432/seismic
python3 replica.py
```

## Docker Compose

Nel `docker-compose.yml` ogni replica gira nel proprio container e puo usare la stessa `HTTP_PORT=8000`, perche il gateway la raggiunge tramite nome servizio (`replica-1`, `replica-2`, ...).

## Note

- Se il database non e disponibile, la replica continua a funzionare senza persistenza.
- La barriera di startup e nel broker, non nella replica.
- Il database persistente puo usare `UNIQUE(event_id)` come chiave di deduplica applicativa.
