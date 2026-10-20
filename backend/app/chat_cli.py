"""Terminal chat to test the agent graph. Run from backend/:  python -m app.chat_cli
Type 'exit' to quit. Each run starts a fresh conversation (memory lives per thread_id)."""
import time
import uuid

from app.graph import get_graph, text_of, tools_used


def ask(graph, user, config, attempts=3):
    """Retry a few times if Gemini is busy (503) or rate limited (429)."""
    for i in range(attempts):
        try:
            return graph.invoke({"messages": [("user", user)]}, config)
        except Exception as e:
            msg = str(e)
            busy = "503" in msg or "UNAVAILABLE" in msg or "429" in msg or "RESOURCE_EXHAUSTED" in msg
            if busy and i < attempts - 1:
                wait = 5 * (i + 1)
                print(f"   (Gemini busy, retrying in {wait}s...)")
                time.sleep(wait)
                continue
            print(f"   [error] {msg[:300]}")
            return None


def main():
    graph = get_graph()

    print("Loading knowledge base (first time takes a minute)...")
    from app.tools.kb_tools import _retriever
    _retriever()

    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    print("ShopEase support (type 'exit' to quit)\n")
    while True:
        user = input("You: ").strip()
        if user.lower() in ("exit", "quit"):
            break
        if not user:
            continue
        out = ask(graph, user, config)
        if out is None:
            print("Bot: Sorry, the AI service is busy right now. Please try again in a minute.\n")
            continue
        print(f"   [route: {out['route']} | tools: {tools_used(out['messages']) or '-'}]")
        print(f"Bot: {text_of(out['messages'][-1])}\n")


if __name__ == "__main__":
    main()