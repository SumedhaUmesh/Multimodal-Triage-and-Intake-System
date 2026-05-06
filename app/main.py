"""
Phase 1: WebSocket audio ingress + Deepgram Live STT.

Audio bytes from the browser are buffered in asyncio.Queue producers/consumers so
receive/send loops never block each other on the event loop.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from deepgram import AsyncDeepgramClient
from deepgram.listen.v1.types.listen_v1results import ListenV1Results

load_dotenv()

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Multimodal Triage — Phase 1 Audio")

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


ListenModel = Literal[
    "nova-2",
    "nova-2-general",
    "nova-3",
    "nova-3-general",
]


@app.websocket("/ws/audio")
async def audio_stream(
    websocket: WebSocket,
    sample_rate: int = Query(48000, ge=8000, le=48000),
    model: ListenModel = Query("nova-2"),
) -> None:
    await websocket.accept()

    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        await websocket.close(code=1011, reason="DEEPGRAM_API_KEY is not set")
        return

    # Bounded queue applies backpressure if Deepgram ingest is slower than realtime audio.
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=128)
    deepgram = AsyncDeepgramClient(api_key=api_key)

    async def browser_to_queue() -> None:
        try:
            while True:
                msg = await websocket.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if "bytes" in msg and msg["bytes"] is not None:
                    await audio_queue.put(msg["bytes"])
        except WebSocketDisconnect:
            pass
        finally:
            await audio_queue.put(None)

    async def run_session() -> None:
        async with deepgram.listen.v1.connect(
            model=model,
            encoding="linear16",
            sample_rate=sample_rate,
            channels=1,
            interim_results=True,
            punctuate=True,
            smart_format=True,
        ) as dg_socket:

            async def queue_to_deepgram() -> None:
                while True:
                    chunk = await audio_queue.get()
                    if chunk is None:
                        await dg_socket.send_finalize()
                        break
                    await dg_socket.send_media(chunk)

            async def deepgram_to_browser() -> None:
                try:
                    async for message in dg_socket:
                        if not isinstance(message, ListenV1Results):
                            continue
                        alts = message.channel.alternatives
                        text = alts[0].transcript.strip() if alts else ""
                        await websocket.send_json(
                            {
                                "type": "transcript",
                                "text": text,
                                "is_final": bool(message.is_final),
                                "speech_final": bool(message.speech_final),
                            }
                        )
                except WebSocketDisconnect:
                    pass

            await asyncio.gather(
                browser_to_queue(),
                queue_to_deepgram(),
                deepgram_to_browser(),
            )

    await run_session()

