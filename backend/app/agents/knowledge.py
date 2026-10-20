"""Knowledge Agent: answers policy/FAQ questions using RAG (search_knowledge_base)."""
from langchain.agents import create_agent

from app.agents.llm import get_llm
from app.tools import KNOWLEDGE_TOOLS

PROMPT = """You are the Knowledge Agent of ShopEase customer support.
- Answer ONLY using information returned by the search_knowledge_base tool. Always call it first.
- If the knowledge base has no answer, say you are not sure and offer to connect the customer to a human agent. Never invent policies, prices or deadlines.
- Be short, friendly and clear.
- Reply in the same language/style the customer uses (English, Urdu, or Roman Urdu)."""


def build_knowledge_agent():
    return create_agent(get_llm(), tools=KNOWLEDGE_TOOLS, system_prompt=PROMPT)
