# Processing Replica

Replica di processing che:

1. si collega al broker su `ws://localhost:9000/ws/ingest`
2. espone la health su una porta fissa scelta all'avvio
3. inoltra gli eventi al gateway su `http://localhost:8001/api/events`

## Porte supportate

Le repliche locali usano solo queste porte health:

- `8000`
- `8002`
- `8004`
- `8006`
- `8008`
- `8010`

Il gateway controlla esattamente questo insieme di porte.

## Avvio locale

Prima replica:

```bash
cd source/processing-replica
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export HTTP_PORT=8000
export DB_DSN=postgresql://replica:replica@localhost:5432/seismic
python3 replica.py
```

Seconda replica:

```bash
cd source/processing-replica
source .venv/bin/activate
export HTTP_PORT=8002
export DB_DSN=postgresql://replica:replica@localhost:5432/seismic
python3 replica.py
```

## Verifica

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8002/health
```

## Note

- Broker e gateway sono hardcoded nel file `replica.py`.
- Se il database non e disponibile, la replica continua a funzionare senza persistenza.
- Due repliche non possono usare la stessa `HTTP_PORT`.
