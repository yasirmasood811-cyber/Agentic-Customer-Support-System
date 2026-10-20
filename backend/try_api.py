"""Quick test of the chat API (server must be running).  Usage:  python try_api.py "refund policy kya hai?" """
import json
import sys
import requests

message = sys.argv[1] if len(sys.argv) > 1 else "refund policy kya hai?"
resp = requests.post("http://localhost:8000/api/chat", json={"message": message}, stream=True, timeout=180)
for line in resp.iter_lines(decode_unicode=True):
    if line and line.startswith("data: "):
        event = json.loads(line[6:])
        print(event)
