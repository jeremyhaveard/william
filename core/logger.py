"""
core/logger.py — Structured logging for william.

File output  : logs/william_YYYY-MM-DD.log  (daily rotation, kept 30 days)
Console      : colored, human-readable lines

Log levels used
  DEBUG    fine-grained internals (token counts, raw args)
  INFO     normal milestones (request start/end, routing, tool calls)
  WARNING  unexpected but non-fatal (empty responses, retries)
  ERROR    exceptions with full traceback
  CRITICAL unrecoverable failures

Usage
  from core.logger import get_logger, log_request_start, log_request_end, ...
  log = get_logger(__name__)
  log.info("hello")
"""

import logging
import os
import sys
import time
import traceback
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Any, Optional

# ── ANSI colour codes ────────────────────────────────────────────
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"

_GREY   = "\033[38;5;244m"
_BLUE   = "\033[38;5;75m"
_CYAN   = "\033[38;5;117m"
_GREEN  = "\033[38;5;114m"
_YELLOW = "\033[38;5;222m"
_ORANGE = "\033[38;5;215m"
_PURPLE = "\033[38;5;183m"
_RED    = "\033[38;5;203m"
_WHITE  = "\033[38;5;255m"

_LEVEL_COLORS = {
    "DEBUG":    _GREY,
    "INFO":     _BLUE,
    "WARNING":  _YELLOW,
    "ERROR":    _RED,
    "CRITICAL": _RED + _BOLD,
}

# ── Milestone tag → colour ───────────────────────────────────────
_TAG_COLORS = {
    "REQUEST":    _CYAN   + _BOLD,
    "RESPONSE":   _GREEN  + _BOLD,
    "ROUTING":    _PURPLE,
    "AGENT":      _GREEN,
    "LLM START":  _BLUE,
    "LLM END":    _CYAN,
    "TOOL CALL":  _ORANGE,
    "TOOL RESULT":_YELLOW,
    "MILESTONE":  _WHITE  + _BOLD,
    "TIMING":     _GREY,
    "ERROR":      _RED    + _BOLD,
    "WARN":       _YELLOW + _BOLD,
    "DEBUG":      _GREY,
}


# ── Formatters ───────────────────────────────────────────────────

class _ConsoleFormatter(logging.Formatter):
    """Single-line coloured format for the terminal."""

    def format(self, record: logging.LogRecord) -> str:
        ts    = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        level = record.levelname
        color = _LEVEL_COLORS.get(level, _RESET)

        # Structured extras injected via extra={} on the logger call
        tag   = getattr(record, "tag",    None)
        agent = getattr(record, "agent",  None)
        ms    = getattr(record, "ms",     None)

        tag_str   = f"  [{_TAG_COLORS.get(tag, _WHITE)}{tag}{_RESET}]" if tag   else ""
        agent_str = f"  {_GREEN}{agent}{_RESET}"                        if agent else ""
        ms_str    = f"  {_GREY}{ms}ms{_RESET}"                         if ms is not None else ""

        msg = record.getMessage()
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)

        return (
            f"{_GREY}{ts}{_RESET}  "
            f"{color}{level:<8}{_RESET}"
            f"{tag_str}{agent_str}  "
            f"{_WHITE}{msg}{_RESET}"
            f"{ms_str}"
        )


class _FileFormatter(logging.Formatter):
    """Plain structured format for the log file (no ANSI)."""

    def format(self, record: logging.LogRecord) -> str:
        ts    = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level = record.levelname
        tag   = getattr(record, "tag",    "")
        agent = getattr(record, "agent",  "")
        ms    = getattr(record, "ms",     None)
        thread= getattr(record, "thread_id", "")

        parts = [f"{ts}  {level:<8}"]
        if tag:    parts.append(f"[{tag}]")
        if agent:  parts.append(f"({agent})")
        if thread: parts.append(f"thread:{thread[:8]}")
        parts.append(" " + record.getMessage())
        if ms is not None:
            parts.append(f" [{ms}ms]")

        out = "  ".join(parts)

        if record.exc_info:
            out += "\n" + self.formatException(record.exc_info)

        return out


# ── Root william logger ──────────────────────────────────────────

_LOG_DIR   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
_ROOT_NAME = "william"
_initialized = False


def _init_logging() -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    os.makedirs(_LOG_DIR, exist_ok=True)

    root = logging.getLogger(_ROOT_NAME)
    root.setLevel(logging.DEBUG)
    root.propagate = False

    # ── Console handler ──────────────────────────────────────────
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(_ConsoleFormatter())
    root.addHandler(ch)

    # ── File handler (daily rotation, 30 days) ───────────────────
    log_path = os.path.join(_LOG_DIR, "william.log")
    fh = TimedRotatingFileHandler(
        log_path,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    fh.suffix = "%Y-%m-%d"
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_FileFormatter())
    root.addHandler(fh)


def get_logger(name: str = "") -> logging.Logger:
    """Return a child logger under the 'william' namespace."""
    _init_logging()
    full = f"{_ROOT_NAME}.{name}" if name else _ROOT_NAME
    return logging.getLogger(full)


# ── Convenience helpers ──────────────────────────────────────────

def _extra(**kwargs) -> dict:
    """Build the `extra` dict for structured log fields."""
    return {"extra": {k: v for k, v in kwargs.items() if v is not None}}


_log = get_logger("core")


def log_request_start(thread_id: str, prompt: str) -> float:
    """Log a new user request. Returns start timestamp."""
    t = time.time()
    width = 62
    border = "═" * width

    # File: box header
    _log.info(
        f"\n  ╔{border}╗\n"
        f"  ║  REQUEST  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  "
        f"thread:{thread_id[:8]:<8}  ║\n"
        f"  ╚{border}╝\n"
        f"  prompt: {prompt[:200]}{'…' if len(prompt) > 200 else ''}",
        extra={"tag": "REQUEST", "thread_id": thread_id},
    )
    return t


def log_request_end(thread_id: str, start_time: float, success: bool = True) -> None:
    """Log request completion with elapsed time."""
    elapsed_ms = int((time.time() - start_time) * 1000)
    status = "OK" if success else "FAILED"
    _log.info(
        f"request complete  status={status}",
        extra={"tag": "RESPONSE", "thread_id": thread_id, "ms": elapsed_ms},
    )


def log_routing(thread_id: str, message: str) -> None:
    _log.info(message, extra={"tag": "ROUTING", "thread_id": thread_id})


def log_agent_active(thread_id: str, agent: str, label: str) -> None:
    _log.info(f"agent active → {label}", extra={"tag": "AGENT", "agent": agent, "thread_id": thread_id})


def log_llm_start(
    thread_id: str,
    agent: str,
    model: str,
    prompt_tokens: Optional[int] = None,
) -> float:
    t = time.time()
    tok_str = f"  prompt_tokens={prompt_tokens}" if prompt_tokens is not None else ""
    _log.info(
        f"model={model}{tok_str}",
        extra={"tag": "LLM START", "agent": agent, "thread_id": thread_id},
    )
    return t


def log_llm_end(
    thread_id: str,
    agent: str,
    model: str,
    start_time: float,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
) -> None:
    elapsed_ms = int((time.time() - start_time) * 1000)
    tok_parts = []
    if prompt_tokens     is not None: tok_parts.append(f"prompt={prompt_tokens}")
    if completion_tokens is not None: tok_parts.append(f"completion={completion_tokens}")
    if total_tokens      is not None: tok_parts.append(f"total={total_tokens}")
    tok_str = "  tokens: " + ", ".join(tok_parts) if tok_parts else ""
    _log.info(
        f"model={model}{tok_str}",
        extra={"tag": "LLM END", "agent": agent, "thread_id": thread_id, "ms": elapsed_ms},
    )


def log_tool_call(thread_id: str, agent: str, tool: str, args: Any) -> float:
    t = time.time()
    arg_str = str(args)[:300]
    _log.info(
        f"{tool}  args={arg_str}",
        extra={"tag": "TOOL CALL", "agent": agent, "thread_id": thread_id},
    )
    return t


def log_tool_result(
    thread_id: str,
    agent: str,
    tool: str,
    start_time: float,
    result: Any,
    error: bool = False,
) -> None:
    elapsed_ms = int((time.time() - start_time) * 1000)
    result_str = str(result)[:500]
    tag = "ERROR" if error else "TOOL RESULT"
    _log.info(
        f"{tool}  {'ERROR: ' if error else 'OK  '}{result_str}",
        extra={"tag": tag, "agent": agent, "thread_id": thread_id, "ms": elapsed_ms},
    )


def log_milestone(thread_id: str, message: str, agent: Optional[str] = None) -> None:
    _log.info(message, extra={"tag": "MILESTONE", "agent": agent, "thread_id": thread_id})


def log_error(
    thread_id: str,
    message: str,
    exc: Optional[BaseException] = None,
    agent: Optional[str] = None,
) -> None:
    _log.error(
        message,
        exc_info=exc,
        extra={"tag": "ERROR", "agent": agent, "thread_id": thread_id},
    )


def log_warning(thread_id: str, message: str, agent: Optional[str] = None) -> None:
    _log.warning(message, extra={"tag": "WARN", "agent": agent, "thread_id": thread_id})
