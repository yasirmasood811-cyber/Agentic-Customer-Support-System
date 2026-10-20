"""Runs the LangGraph and turns each step into Server-Sent Events (SSE) for the React UI.

Events:  start | route | agent | tool | escalation | status | message | error | done
Retries (503 / 429) resume the same conversation from the last checkpoint.
"""
import json
import re
import time
import uuid
from typing import Iterator, Optional

from langchain_core.messages import AIMessage, ToolMessage

from app.graph import text_of

MAX_ATTEMPTS = 3
TICKET_RE = re.compile(r"Ticket #(\d+)")
BUSY_MARKERS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "rate limit", "Rate limit")


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def is_busy(error: Exception) -> bool:
    msg = str(error)
    return any(marker in msg for marker in BUSY_MARKERS)


def chat_events(graph, message: str, thread_id: Optional[str]) -> Iterator[str]:
    thread_id = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    yield sse({"type": "start", "thread_id": thread_id})

    graph_input = {"messages": [("user", message)]}
    final_text = None

    for attempt in range(MAX_ATTEMPTS):
        try:
            for chunk in graph.stream(graph_input, config, stream_mode="updates"):
                for node, update in chunk.items():
                    if not update:
                        continue
                    if node == "router":
                        yield sse({"type": "route", "route": update["route"]})
                        continue

                    yield sse({"type": "agent", "name": node})
                    for m in update.get("messages", []):
                        if isinstance(m, ToolMessage):
                            result = text_of(m)
                            yield sse({"type": "tool", "name": m.name, "result": result})
                            if m.name == "escalate_to_human":
                                found = TICKET_RE.search(result)
                                if found:
                                    yield sse({"type": "escalation", "ticket_id": int(found.group(1))})
                        elif isinstance(m, AIMessage) and not m.tool_calls and text_of(m).strip():
                            final_text = text_of(m)
            break  # finished without error
        except Exception as e:
            if is_busy(e) and attempt < MAX_ATTEMPTS - 1:
                wait = 5 * (attempt + 1)
                yield sse({"type": "status", "message": f"AI service is busy, retrying in {wait}s..."})
                time.sleep(wait)
                # Resume from the last checkpoint if the run already started; otherwise resend the input.
                if graph.get_state(config).next:
                    graph_input = None
                continue
            friendly = ("The AI service is busy or its free limit is reached. Please try again in a minute."
                        if is_busy(e) else "Something went wrong while processing your request.")
            yield sse({"type": "error", "message": friendly, "detail": str(e)[:300]})
            yield sse({"type": "done"})
            return

    yield sse({"type": "message", "text": final_text or "Sorry, I could not generate a reply."})
    yield sse({"type": "done"})
