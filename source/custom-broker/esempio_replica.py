import asyncio
import os

import websockets


BROKER_URL = os.getenv("BROKER_URL", "ws://localhost:9000/ws/ingest")


async def main() -> None:
    async with websockets.connect(BROKER_URL) as websocket:
        print(f"Connected to broker at {BROKER_URL}")
        async for message in websocket:
            print(message)


if __name__ == "__main__":
    asyncio.run(main())
