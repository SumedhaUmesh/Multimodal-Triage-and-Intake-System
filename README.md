# Multimodal Triage & Intake System

Low-latency pipeline for live voice (and future vision) input: ingest audio, transcribe in real time with Deepgram, then extend toward structured extraction and backend tooling.

## Stack

| Layer | Choice |
|--------|--------|
| API | Python 3.11+, [FastAPI](https://fastapi.tiangolo.com/) (WebSockets) |
| Speech-to-text | [Deepgram](https://deepgram.com/) Live API via [`deepgram-sdk`](https://github.com/deepgram/deepgram-python-sdk) (`AsyncDeepgramClient`) |
| Client mock | `static/index.html` — microphone capture over WebSocket |

Planned later: vision-language models (Gemini / GPT-4o), Pydantic structured outputs, additional modalities.

## Phase 1 (current)

- **`GET /`** — Simple HTML page: captures microphone audio as mono **linear16 PCM**, sends raw bytes over a WebSocket.
- **`GET /health`** — Health check.
- **`WebSocket /ws/audio`** — Accepts binary PCM frames, streams them to Deepgram Live STT, returns JSON transcript events.  
  Server-side audio is decoupled with a **bounded `asyncio.Queue`** so the browser receive loop, Deepgram send path, and Deepgram receive path run concurrently without blocking the event loop.

### WebSocket query parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `sample_rate` | `48000` | Must match the client PCM rate (Hz). The demo page uses the browser `AudioContext` sample rate. |
| `model` | `nova-2` | Deepgram model (e.g. `nova-2`, `nova-2-general`, `nova-3`, `nova-3-general`). |

## Setup

1. **Python 3.11+** recommended.

2. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set your [Deepgram API key](https://console.deepgram.com/):

   ```bash
   cp .env.example .env
   # Edit .env: DEEPGRAM_API_KEY=...
   ```

## Run

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000), click **Start microphone**, allow access, and speak. Transcript lines appear in the page (interim and final events from the server).

## Project layout

```
app/main.py          # FastAPI app, /ws/audio, Deepgram live session
static/index.html    # Microphone + WebSocket client mock
requirements.txt
pyproject.toml
.env.example
```
