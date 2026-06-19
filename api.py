"""
FastAPI backend for William UI.
Streams LangGraph events to the browser via Server-Sent Events.

Event types emitted:
  thinking     — initial "William is thinking…" indicator
  routing      — supervisor chose an agent
  agent        — agent node is active
  tool_call    — agent is calling a tool
  tool_result  — tool finished (ms elapsed, result preview)
  llm_start    — LLM invocation began (model name)
  llm_end      — LLM invocation finished (model, ms, token counts)
  milestone    — internal progress note
  message      — final message from an agent
  done         — stream complete
  error        — something went wrong (message + optional traceback)
"""
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from dotenv import load_dotenv
load_dotenv()

import httpx
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from jose import jwt, JWTError
from langchain_core.messages import HumanMessage

# Import the compiled graph and labels from william
from william import graph, _LABELS

# Import structured logging helpers
from core.logger import (
    get_logger,
    log_request_start,
    log_request_end,
    log_routing,
    log_agent_active,
    log_error,
    log_milestone,
)
from core.callbacks import WilliamCallbackHandler
from core.db import get_db

_log = get_logger("api")


app = FastAPI(title="William API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Cognito JWT verification ───────────────────────────────────────
_COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
_COGNITO_CLIENT_ID    = os.getenv("COGNITO_CLIENT_ID", "")
_AWS_REGION           = os.getenv("AWS_REGION", "us-east-1")
_AUTH_ENABLED         = bool(_COGNITO_USER_POOL_ID and _COGNITO_CLIENT_ID)

_jwks_cache: Optional[dict] = None

async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    url = (
        f"https://cognito-idp.{_AWS_REGION}.amazonaws.com"
        f"/{_COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    )
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache

_bearer = HTTPBearer(auto_error=False)

async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
):
    """FastAPI dependency — validates Cognito JWT when auth is enabled."""
    if not _AUTH_ENABLED:
        return None   # dev mode: no auth required

    if not credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        jwks   = await _get_jwks()
        key    = next((k for k in jwks["keys"] if k["kid"] == header["kid"]), None)
        if not key:
            raise HTTPException(status_code=401, detail="Unknown token key")

        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=_COGNITO_CLIENT_ID,
        )
        return claims
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ── Thread metadata (stored in platform.db) ───────────────────────
def _init_threads_table() -> None:
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS threads (
                thread_id    TEXT PRIMARY KEY,
                title        TEXT NOT NULL DEFAULT 'New session',
                created_at   TEXT NOT NULL,
                last_active  TEXT NOT NULL,
                message_count INTEGER NOT NULL DEFAULT 0
            )
        """)

_init_threads_table()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_thread(thread_id: str) -> None:
    now = _now_iso()
    with get_db() as db:
        db.execute(
            "INSERT OR IGNORE INTO threads (thread_id, title, created_at, last_active) VALUES (?,?,?,?)",
            (thread_id, "New session", now, now),
        )


def _update_thread(thread_id: str, prompt: str) -> None:
    """Set title from first message and bump last_active + count."""
    now = _now_iso()
    with get_db() as db:
        row = db.execute(
            "SELECT message_count FROM threads WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        if row is None:
            _record_thread(thread_id)
            row = {"message_count": 0}
        count = row["message_count"] + 1
        # Use the first user message as the title (trimmed to 80 chars)
        if count == 1:
            title = prompt[:80] + ("…" if len(prompt) > 80 else "")
        else:
            title = None  # keep existing
        if title:
            db.execute(
                "UPDATE threads SET title=?, last_active=?, message_count=? WHERE thread_id=?",
                (title, now, count, thread_id),
            )
        else:
            db.execute(
                "UPDATE threads SET last_active=?, message_count=? WHERE thread_id=?",
                (now, count, thread_id),
            )


# Top-level William nodes — anything else is an internal subgraph step and should be ignored
_TOP_LEVEL_NODES = {"supervisor", "scout", "karen"} | set(_LABELS.keys())


def _process_event(
    event: dict,
    active_agent: list,
    thread_id: str,
    request_start: float,
) -> list[str]:
    """Convert a single LangGraph update event into SSE strings."""
    out = []
    for node_name, node_data in event.items():
        # Skip internal subgraph nodes (e.g. "agent"/"tools" from create_react_agent)
        if node_name not in _TOP_LEVEL_NODES or not node_data:
            continue

        if node_name == "supervisor":
            msgs = node_data.get("messages", []) if isinstance(node_data, dict) else []
            for msg in reversed(msgs):
                content = getattr(msg, "content", "")
                if content:
                    log_routing(thread_id, str(content))
                    out.append(_sse("routing", {"message": str(content)}))
                    break
            continue

        if not isinstance(node_data, dict):
            continue

        label = _LABELS.get(node_name, node_name)

        if node_name != active_agent[0]:
            active_agent[0] = node_name
            log_agent_active(thread_id, node_name, label)
            elapsed_ms = int((time.time() - request_start) * 1000)
            out.append(_sse("agent", {"agent": node_name, "label": label}))
            out.append(_sse("milestone", {
                "agent":   node_name,
                "message": f"{label} started",
                "ms":      elapsed_ms,
            }))

        for msg in node_data.get("messages", []):
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                for tc in tool_calls:
                    name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                    args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                    out.append(_sse("tool_call", {"agent": node_name, "tool": name, "args": args}))

            content = getattr(msg, "content", "")
            if isinstance(content, str) and content.strip():
                out.append(_sse("message", {"agent": node_name, "label": label, "content": content}))
            elif isinstance(content, list):
                text = " ".join(
                    b.get("text", "") if isinstance(b, dict) else str(b)
                    for b in content
                ).strip()
                if text:
                    out.append(_sse("message", {"agent": node_name, "label": label, "content": text}))
    return out


async def _stream_william(prompt: str, thread_id: str) -> AsyncIterator[str]:
    """Stream William events as SSE using a queue to bridge sync graph.stream()."""
    request_start = log_request_start(thread_id, prompt)

    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 30}
    loop = asyncio.get_running_loop()   # must use get_running_loop() inside async context
    queue: asyncio.Queue = asyncio.Queue()
    _DONE = object()

    # Emit thinking right away so the UI shows activity immediately
    yield _sse("thinking", {"message": "William is thinking…"})

    def _run_sync():
        active_agent    = [None]
        message_emitted = [False]

        # Create one callback handler shared across all agents
        cb = WilliamCallbackHandler(
            queue=queue,
            loop=loop,
            thread_id=thread_id,
            agent_name="william",
        )

        try:
            log_milestone(thread_id, "graph.stream() started")
            for event in graph.stream(
                {"messages": [HumanMessage(content=prompt)]},
                config={**config, "callbacks": [cb]},
                stream_mode="updates",
            ):
                for sse_str in _process_event(event, active_agent, thread_id, request_start):
                    if sse_str.startswith('event: message'):
                        message_emitted[0] = True
                    loop.call_soon_threadsafe(queue.put_nowait, sse_str)

        except Exception as exc:
            log_error(thread_id, f"graph.stream() failed: {exc}", exc=exc)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                _sse("error", {"message": str(exc)}),
            )
        finally:
            success = message_emitted[0]

            # If no agent responded (e.g. supervisor routed straight to FINISH),
            # emit a fallback so the chat bubble isn't left empty.
            if not message_emitted[0]:
                fallback = _sse("message", {
                    "agent":   "william",
                    "label":   "William",
                    "content": "Done.",
                })
                loop.call_soon_threadsafe(queue.put_nowait, fallback)

            # Emit timing summary
            elapsed_ms = int((time.time() - request_start) * 1000)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                _sse("timing", {"total_ms": elapsed_ms, "thread_id": thread_id}),
            )

            log_request_end(thread_id, request_start, success=success)
            loop.call_soon_threadsafe(queue.put_nowait, _DONE)

    loop.run_in_executor(None, _run_sync)

    while True:
        item = await queue.get()
        if item is _DONE:
            yield _sse("done", {})
            break
        yield item


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat/{thread_id}")
async def chat(thread_id: str, request: Request, _claims=Depends(require_auth)):
    body   = await request.json()
    prompt = body.get("message", "").strip()
    if not prompt:
        return {"error": "empty message"}

    _log.info(
        f"POST /chat/{thread_id[:8]}…  prompt_len={len(prompt)}",
        extra={"tag": "REQUEST", "thread_id": thread_id},
    )
    _update_thread(thread_id, prompt)

    return StreamingResponse(
        _stream_william(prompt, thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/thread")
async def new_thread(_claims=Depends(require_auth)):
    tid = str(uuid.uuid4())
    _record_thread(tid)
    _log.info(f"new thread created  id={tid[:8]}", extra={"tag": "MILESTONE"})
    return {"thread_id": tid}


@app.get("/history")
async def get_history(_claims=Depends(require_auth), limit: int = 50):
    """Return the most recent threads ordered by last activity."""
    with get_db() as db:
        rows = db.execute(
            """SELECT thread_id, title, created_at, last_active, message_count
               FROM threads
               ORDER BY last_active DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Serve React UI ────────────────────────────────────────────────
_UI_DIR = os.path.join(os.path.dirname(__file__), "ui", "dist")
if os.path.isdir(_UI_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(_UI_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_ui(full_path: str):
        return FileResponse(os.path.join(_UI_DIR, "index.html"))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
