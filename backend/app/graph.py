"""LangGraph orchestration.

START -> router -> knowledge ------------------------------> END
                -> action -> (email | escalate | END)
                -> escalate -----------------------------> END
Memory: MemorySaver keeps each conversation by thread_id.
Key used: GOOGLE_API_KEY (router + agents).
"""
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import BaseModel
from typing_extensions import TypedDict
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.agents.action import build_action_agent
from app.agents.email_agent import build_email_agent
from app.agents.escalation import build_escalation_agent
from app.agents.knowledge import build_knowledge_agent
from app import verification
from app.agents.llm import get_llm


# ---------------- State ----------------
class State(TypedDict):
    messages: Annotated[list, add_messages]
    route: str


# ---------------- Helpers ----------------
def text_of(message) -> str:
    """Message text as a plain string (Gemini can return a list of parts)."""
    content = message.content
    if isinstance(content, str):
        return content
    parts = []
    for p in content:
        if isinstance(p, str):
            parts.append(p)
        elif isinstance(p, dict) and p.get("type") == "text":
            parts.append(p.get("text", ""))
    return "".join(parts)


def plain_history(messages, limit: int = 12) -> list:
    """Only the human messages and final AI replies. Tool-call details of other agents are hidden
    so every agent sees a clean conversation."""
    keep = [m for m in messages
            if isinstance(m, HumanMessage)
            or (isinstance(m, AIMessage) and not m.tool_calls and text_of(m).strip())]
    return keep[-limit:]


def turn_messages(messages) -> list:
    """All messages since the customer's latest message (this turn only)."""
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            return messages[i + 1:]
    return list(messages)


def turn_tool_results(messages) -> list[tuple[str, str]]:
    return [(m.name or "", text_of(m)) for m in turn_messages(messages) if isinstance(m, ToolMessage)]


def tools_used(messages) -> list[str]:
    return [name for name, _ in turn_tool_results(messages)]


# ---------------- Router ----------------
class RouteDecision(BaseModel):
    route: Literal["knowledge", "action", "escalate"]


ROUTER_PROMPT = """Classify the customer's latest message for a support system. Answer with one route:
- knowledge: general questions about policies, shipping, warranty, FAQs, support hours.
- action: needs something DONE or looked up on a specific order/account: order status, tracking, refund, cancel, change address/phone, or the status of a support ticket (ticket number + email). Short replies like "yes, refund it", an order number, a 6-digit verification code, or a ticket number/email that continue an earlier action request are also action (for example when the assistant just asked the customer to type the code that was emailed to them).
- escalate: angry/abusive customer, legal threats, fraud, payment dispute, asks for a human/manager, or a very sensitive complaint. Also escalate when the assistant has just asked the customer for their email so a human can contact them and the customer now replies with an email address or details."""


def classify(messages) -> str:
    decision = get_llm().with_structured_output(RouteDecision).invoke(
        [SystemMessage(content=ROUTER_PROMPT)] + plain_history(messages)
    )
    return decision.route


def router_node(state: State):
    return {"route": classify(state["messages"])}


def pick_route(state: State) -> str:
    return state["route"]


# ---------------- Conditional logic after the Action Agent (decided by code, not LLM) ----------------
def after_action(state: State) -> str:
    results = turn_tool_results(state["messages"])
    if any("REFUND_NEEDS_APPROVAL" in content for _, content in results):
        return "escalate"
    for name, content in results:
        if (name == "process_refund" and content.startswith("Refund of")) or \
           (name == "update_record" and "updated to" in content):
            return "email"
    return "end"


# ---------------- Agent nodes ----------------
def make_node(build_agent, with_context: bool = False, include_verified_email: bool = False):
    agent = None  # built on first use

    def node(state: State, config: RunnableConfig):
        nonlocal agent
        if agent is None:
            agent = build_agent()
        msgs = plain_history(state["messages"])
        if with_context:
            results = turn_tool_results(state["messages"])
            if results:
                ctx = "[Internal context: results of actions in this conversation turn]\n" + \
                      "\n".join(f"- {name}: {content}" for name, content in results)
                if include_verified_email:
                    # From the server, not from the LLM: the one address a confirmation email may go to.
                    # (Not every action result contains the email, e.g. update_record does not.)
                    email = verification.verified_email(config)
                    ctx += f"\nVerified customer email (the only allowed recipient): {email or 'not available'}"
                msgs = msgs + [HumanMessage(content=ctx)]
        # The agent only needs the conversation id (tools use it to look up who is verified) and the tracing callbacks.
        child_config = {"configurable": {"thread_id": config.get("configurable", {}).get("thread_id")},
                        "callbacks": config.get("callbacks")}
        result = agent.invoke({"messages": msgs}, child_config)
        return {"messages": result["messages"][len(msgs):]}  # only the new messages

    return node


# ---------------- Graph ----------------
def build_graph(checkpointer=None):
    builder = StateGraph(State)
    builder.add_node("router", router_node)
    builder.add_node("knowledge", make_node(build_knowledge_agent))
    builder.add_node("action", make_node(build_action_agent))
    builder.add_node("email", make_node(build_email_agent, with_context=True, include_verified_email=True))
    builder.add_node("escalate", make_node(build_escalation_agent, with_context=True))

    builder.add_edge(START, "router")
    builder.add_conditional_edges("router", pick_route,
                                  {"knowledge": "knowledge", "action": "action", "escalate": "escalate"})
    builder.add_edge("knowledge", END)
    builder.add_conditional_edges("action", after_action,
                                  {"email": "email", "escalate": "escalate", "end": END})
    builder.add_edge("email", END)
    builder.add_edge("escalate", END)
    return builder.compile(checkpointer=checkpointer or MemorySaver())


@lru_cache(maxsize=1)
def get_graph():
    return build_graph()
