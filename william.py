import asyncio
import os
import re
import sys
import uuid
from typing import Literal
from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command
from pydantic import Field, create_model
from core.db import db_path

from agents.scout.agent import scout_agent
from agents.karen.agent import karen_agent
from core.llm import get_llm

# ── Supervisor prompt ──────────────────────────────────────────────────────────
WILLIAM_PROMPT = """You are William, a government contract management supervisor.

Agents:
- scout: Government contract researcher and pipeline manager. Route here for searching contract opportunities on SAM.gov, Florida VBS, Bonfire, OpenGov, and municipal portals. Also handles bid pipeline management, deadline tracking, and generating contract reports.
- karen: Document and presentation creator. Route here for Word (.docx), Excel (.xlsx), and PowerPoint (.pptx) files and written reports.

Routing rules:
- Route contract research, opportunity discovery, pipeline, and reporting tasks to scout.
- Route document, spreadsheet, and presentation creation to karen.
- A task may require both agents in sequence (e.g. scout finds opportunities, karen formats a report) — that is fine.
- Once an agent has returned a clear, complete answer, route to FINISH immediately.
- If the last agent message contains a direct answer or saved file confirmation, the task is complete — route to FINISH.
- Only route to another agent if a genuinely different skill is needed."""

# ── Dynamic Route model ────────────────────────────────────────────────────────
Route = create_model(
    "Route",
    next=(Literal["scout", "karen", "FINISH"], Field(..., description="Next agent or FINISH")),
    reason=(str, Field(..., description="Why this route was chosen")),
)

_llm = get_llm()

_AGENT_NAMES = {"scout", "karen"}


def supervisor(state: MessagesState) -> Command:
    # Hard loop guard: if scout has responded twice in a row, finish immediately.
    agent_msgs = [
        m for m in state["messages"]
        if isinstance(m, HumanMessage) and getattr(m, "name", None) in _AGENT_NAMES
    ]
    if len(agent_msgs) >= 2 and agent_msgs[-1].name == agent_msgs[-2].name:
        return Command(goto=END)

    messages = [{"role": "system", "content": WILLIAM_PROMPT}] + state["messages"]
    result = _llm.with_structured_output(Route).invoke(messages)
    if result.next == "FINISH":
        return Command(goto=END)
    return Command(goto=result.next)


_THINKING_RE = re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    """Remove <thinking>...</thinking> blocks emitted by Nova Pro."""
    return _THINKING_RE.sub("", text).strip()


def _last_content(result: dict) -> str:
    """Extract the last non-empty text from an agent result, stripping thinking blocks."""
    for msg in reversed(result["messages"]):
        content = getattr(msg, "content", "")
        if isinstance(content, str):
            clean = _strip_thinking(content)
            if clean:
                return clean
        if isinstance(content, list):
            text = " ".join(
                b.get("text", "") if isinstance(b, dict) else str(b) for b in content
            ).strip()
            clean = _strip_thinking(text)
            if clean:
                return clean
    return "(no response)"


# ── Agent nodes ────────────────────────────────────────────────────────────────
def karen_node(state: MessagesState) -> Command:
    result = karen_agent.invoke(state)
    return Command(
        update={"messages": [HumanMessage(content=_last_content(result), name="karen")]},
        goto="supervisor",
    )


def scout_node(state: MessagesState) -> Command:
    result = scout_agent.invoke(state)
    return Command(
        update={"messages": [HumanMessage(content=_last_content(result), name="scout")]},
        goto="supervisor",
    )


# ── Build graph ────────────────────────────────────────────────────────────────
_builder = StateGraph(MessagesState)
_builder.add_node("supervisor", supervisor)
_builder.add_node("scout", scout_node)
_builder.add_node("karen", karen_node)
_builder.add_edge(START, "supervisor")

# ── Persistent checkpointer ────────────────────────────────────────────────────
# Uses SqliteSaver locally (data/checkpoints.db).
# On AWS: set DATABASE_URL=postgresql://... to get PostgresSaver automatically.
_DATABASE_URL = os.getenv("DATABASE_URL", "")


def _make_checkpointer():
    if _DATABASE_URL.startswith("postgresql"):
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            import psycopg
            conn = psycopg.connect(_DATABASE_URL, autocommit=True)
            cp = PostgresSaver(conn)
            cp.setup()
            return cp
        except Exception as exc:
            print(f"[william] PostgresSaver failed ({exc}), falling back to SQLite", file=sys.stderr)

    from langgraph.checkpoint.sqlite import SqliteSaver
    import sqlite3
    conn = sqlite3.connect(db_path("checkpoints.db"), check_same_thread=False)
    cp = SqliteSaver(conn)
    cp.setup()
    return cp


graph = _builder.compile(checkpointer=_make_checkpointer())

# ── Streaming labels ───────────────────────────────────────────────────────────
_LABELS: dict[str, str] = {
    "scout": "Scout (research)",
    "karen": "Karen (documents)",
}


def run(prompt: str, thread_id: str) -> None:
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 30}
    active_agent = None
    final_content = None

    for event in graph.stream(
        {"messages": [HumanMessage(content=prompt)]},
        config=config,
        stream_mode="updates",
    ):
        for node_name, node_data in event.items():
            if node_name in ("supervisor", "__end__"):
                continue
            label = _LABELS.get(node_name, node_name)
            if node_name != active_agent:
                print(f"\n[{label}]", flush=True)
                active_agent = node_name
            for msg in node_data.get("messages", []):
                content = getattr(msg, "content", "")
                if isinstance(content, str) and content.strip():
                    final_content = content
                elif isinstance(content, list):
                    text = " ".join(
                        b.get("text", "") if isinstance(b, dict) else str(b)
                        for b in content
                    ).strip()
                    if text:
                        final_content = text

    if final_content:
        print(final_content)


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    thread_id = str(uuid.uuid4())

    if len(sys.argv) > 1:
        run(" ".join(sys.argv[1:]), thread_id)
        return

    print(f"William ready  |  session {thread_id[:8]}  |  type 'exit' to quit\n")
    while True:
        try:
            prompt = input("william> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not prompt:
            continue
        if prompt.lower() in ("exit", "quit", "q"):
            break
        run(prompt, thread_id)
        print()


if __name__ == "__main__":
    main()
