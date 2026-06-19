"""
core/callbacks.py — LangChain callback handler for william.

williamCallbackHandler bridges LangChain/LangGraph events to:
  1. The SSE queue  (so the browser console sees real-time detail)
  2. The log file   (via core.logger helpers)

SSE event types emitted:
  llm_start    — LLM invocation begins  { agent, model, prompt_tokens? }
  llm_end      — LLM invocation ends    { agent, model, ms, tokens: {...} }
  tool_result  — Tool finished          { agent, tool, ms, result_preview, error? }
  milestone    — Arbitrary note         { agent, message }
  error        — Exception captured     { agent, message, traceback }
"""

import json
import time
import traceback
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from core.logger import (
    log_llm_start,
    log_llm_end,
    log_tool_call,
    log_tool_result,
    log_milestone,
    log_error,
    get_logger,
)

_log = get_logger("callbacks")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class williamCallbackHandler(BaseCallbackHandler):
    """
    Captures fine-grained LangChain events and routes them to the SSE queue
    and structured log file.

    Parameters
    ----------
    queue   : asyncio.Queue  — the same queue that _stream_william() drains
    loop    : asyncio loop   — needed for thread-safe queue puts
    thread_id : str          — conversation thread for log correlation
    agent_name : str         — which agent owns this callback instance
    """

    raise_error = False   # Don't let callback errors crash the graph

    def __init__(
        self,
        queue,
        loop,
        thread_id: str,
        agent_name: str = "unknown",
    ):
        super().__init__()
        self._queue     = queue
        self._loop      = loop
        self._thread_id = thread_id
        self._agent     = agent_name

        # Timing state keyed by run_id (UUID → float)
        self._llm_starts:  Dict[str, float] = {}
        self._tool_starts: Dict[str, float] = {}

    # ── Helpers ──────────────────────────────────────────────────

    def _emit(self, event: str, data: dict) -> None:
        """Thread-safe push to the SSE queue."""
        try:
            self._loop.call_soon_threadsafe(
                self._queue.put_nowait,
                _sse(event, data),
            )
        except Exception as exc:
            _log.warning(f"Failed to emit SSE event {event}: {exc}")

    def _run_id(self, run_id: UUID) -> str:
        return str(run_id)

    # ── LLM events ───────────────────────────────────────────────

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid   = self._run_id(run_id)
        model = (
            serialized.get("kwargs", {}).get("model_id")
            or serialized.get("kwargs", {}).get("model")
            or serialized.get("name", "unknown")
        )
        self._llm_starts[rid] = log_llm_start(
            thread_id=self._thread_id,
            agent=self._agent,
            model=model,
        )
        self._emit("llm_start", {
            "agent": self._agent,
            "model": model,
        })

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        # Treat chat model start the same as LLM start
        rid   = self._run_id(run_id)
        model = (
            serialized.get("kwargs", {}).get("model_id")
            or serialized.get("kwargs", {}).get("model")
            or serialized.get("name", "unknown")
        )
        # Count input tokens roughly (chars / 4)
        prompt_chars = sum(
            len(getattr(m, "content", "") or "")
            for batch in messages
            for m in batch
        )
        approx_tokens = prompt_chars // 4

        self._llm_starts[rid] = log_llm_start(
            thread_id=self._thread_id,
            agent=self._agent,
            model=model,
            prompt_tokens=approx_tokens if approx_tokens else None,
        )
        self._emit("llm_start", {
            "agent":         self._agent,
            "model":         model,
            "prompt_tokens": approx_tokens or None,
        })

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid        = self._run_id(run_id)
        start_time = self._llm_starts.pop(rid, time.time())

        # Extract token usage if available
        usage = {}
        if response.llm_output:
            usage = response.llm_output.get("usage", {}) or response.llm_output.get("token_usage", {}) or {}

        prompt_tokens     = usage.get("inputTokens")  or usage.get("prompt_tokens")
        completion_tokens = usage.get("outputTokens") or usage.get("completion_tokens")
        total_tokens      = usage.get("totalTokens")  or usage.get("total_tokens")

        # Also check per-generation metadata (Bedrock puts it here)
        if not prompt_tokens and response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    meta = getattr(gen, "generation_info", {}) or {}
                    if not usage:
                        usage = meta.get("usage", {}) or {}
                        prompt_tokens     = usage.get("inputTokens")
                        completion_tokens = usage.get("outputTokens")
                        total_tokens      = usage.get("totalTokens")

        elapsed_ms = int((time.time() - start_time) * 1000)
        model = "unknown"
        if response.llm_output:
            model = (
                response.llm_output.get("model_id")
                or response.llm_output.get("model")
                or "unknown"
            )

        log_llm_end(
            thread_id=self._thread_id,
            agent=self._agent,
            model=model,
            start_time=start_time,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

        tokens = {}
        if prompt_tokens     is not None: tokens["prompt"]     = prompt_tokens
        if completion_tokens is not None: tokens["completion"] = completion_tokens
        if total_tokens      is not None: tokens["total"]      = total_tokens

        self._emit("llm_end", {
            "agent":  self._agent,
            "model":  model,
            "ms":     elapsed_ms,
            "tokens": tokens,
        })

    def on_llm_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid = self._run_id(run_id)
        self._llm_starts.pop(rid, None)
        tb = traceback.format_exc()
        log_error(self._thread_id, f"LLM error: {error}", exc=error if isinstance(error, Exception) else None, agent=self._agent)
        self._emit("error", {
            "agent":     self._agent,
            "message":   str(error),
            "traceback": tb,
        })

    # ── Tool events ───────────────────────────────────────────────

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid       = self._run_id(run_id)
        tool_name = serialized.get("name", "unknown")
        # Try to parse as JSON for nicer args display
        try:
            args = json.loads(input_str)
        except Exception:
            args = {"input": input_str}

        self._tool_starts[rid] = log_tool_call(
            thread_id=self._thread_id,
            agent=self._agent,
            tool=tool_name,
            args=args,
        )
        # Note: tool_call SSE is already emitted by _process_event from graph messages
        # We don't re-emit here to avoid duplicates.

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid        = self._run_id(run_id)
        start_time = self._tool_starts.pop(rid, time.time())
        tool_name  = kwargs.get("name", "tool")
        elapsed_ms = int((time.time() - start_time) * 1000)

        log_tool_result(
            thread_id=self._thread_id,
            agent=self._agent,
            tool=tool_name,
            start_time=start_time,
            result=output,
        )

        preview = str(output)[:300]
        self._emit("tool_result", {
            "agent":   self._agent,
            "tool":    tool_name,
            "ms":      elapsed_ms,
            "preview": preview,
        })

    def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid        = self._run_id(run_id)
        start_time = self._tool_starts.pop(rid, time.time())
        tool_name  = kwargs.get("name", "tool")
        elapsed_ms = int((time.time() - start_time) * 1000)
        tb         = traceback.format_exc()

        log_tool_result(
            thread_id=self._thread_id,
            agent=self._agent,
            tool=tool_name,
            start_time=start_time,
            result=str(error),
            error=True,
        )
        self._emit("tool_result", {
            "agent":     self._agent,
            "tool":      tool_name,
            "ms":        elapsed_ms,
            "preview":   str(error)[:300],
            "error":     True,
            "traceback": tb,
        })

    # ── Chain / agent events ─────────────────────────────────────

    def on_chain_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        tb = traceback.format_exc()
        log_error(
            self._thread_id,
            f"Chain error in {self._agent}: {error}",
            exc=error if isinstance(error, Exception) else None,
            agent=self._agent,
        )
        self._emit("error", {
            "agent":     self._agent,
            "message":   str(error),
            "traceback": tb,
        })
