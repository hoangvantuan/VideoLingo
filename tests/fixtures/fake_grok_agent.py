"""Stands in for `grok agent stdio`: speaks ACP JSON-RPC on stdin/stdout.

The reply to a prompt is the text after "REPLY:" in it, else a JSON report of how the agent was started.
Words in the prompt choose a behaviour: TOOL (reports a tool call and stops the turn once cancelled),
PERMISSION (asks the client), DIE (exits mid-turn), SLOW (answers after one second), HANG (never answers),
GARBAGE (writes lines that are not ACP messages first). `--auth-fail` refuses the cached token.
"""

import itertools
import json
import os
import sys
import threading
import time
from concurrent.futures import Future

write_lock = threading.Lock()
client_replies = {}
ids = itertools.count(1000)
sessions = itertools.count(1)
cancelled = {}


def send(message):
    with write_lock:
        sys.stdout.write(json.dumps(message) + "\n")
        sys.stdout.flush()


def update(session_id, payload):
    send({"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": session_id, "update": payload}})


def ask_client(method, params):
    request_id = next(ids)
    client_replies[request_id] = Future()
    send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
    return client_replies[request_id].result(timeout=10)


def started_with():
    return json.dumps({
        "argv": sys.argv[1:],
        "config": json.loads(os.environ.get("GROK_CONFIG") or "{}"),
        "pid": os.getpid(),
        "home": os.environ.get("HOME"),
        "grok_home": os.environ.get("GROK_HOME"),
        "claude_agents": os.environ.get("GROK_CLAUDE_AGENTS_ENABLED"),
        "backend_search": os.environ.get("GROK_BACKEND_SEARCH"),
    })


def prompt_turn(request_id, params):
    session_id = params["sessionId"]
    text = params["prompt"][0]["text"]
    if "HANG" in text:
        return
    if "GARBAGE" in text:
        for line in ("42", "[1, 2]", '{"jsonrpc": "2.0", "method": "session/update"}', "not json"):
            with write_lock:
                sys.stdout.write(line + "\n")
                sys.stdout.flush()
    if "SLOW" in text:
        time.sleep(1)
    if "DIE" in text:
        os._exit(3)
    if "TOOL" in text:
        cancelled[session_id] = threading.Event()
        update(session_id, {"sessionUpdate": "tool_call", "toolCallId": "t1", "title": "Web search", "kind": "search"})
        if cancelled[session_id].wait(timeout=2):
            send({"jsonrpc": "2.0", "id": request_id, "result": {"stopReason": "cancelled"}})
            return
    reply = text.split("REPLY:", 1)[1] if "REPLY:" in text else started_with()
    if "PERMISSION" in text:
        answer = ask_client("session/request_permission", {
            "sessionId": session_id,
            "toolCall": {"toolCallId": "t2", "title": "Run ls"},
            "options": [{"optionId": "yes", "name": "Allow", "kind": "allow_once"},
                        {"optionId": "no", "name": "Reject", "kind": "reject_once"}],
        })
        reply = json.dumps(answer.get("result"))
    for start in range(0, len(reply), 7):
        update(session_id, {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": reply[start:start + 7]}})
    send({"jsonrpc": "2.0", "id": request_id, "result": {"stopReason": "end_turn"}})


def main():
    for line in sys.stdin:
        message = json.loads(line)
        method, request_id, params = message.get("method"), message.get("id"), message.get("params") or {}
        if method is None:
            client_replies.pop(request_id).set_result(message)
        elif method == "initialize":
            send({"jsonrpc": "2.0", "id": request_id, "result": {"protocolVersion": 1, "authMethods": [{"id": "cached_token"}]}})
        elif method == "authenticate":
            if "--auth-fail" in sys.argv:
                send({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": "Authentication required"}})
            else:
                send({"jsonrpc": "2.0", "id": request_id, "result": {}})
        elif method == "session/new":
            send({"jsonrpc": "2.0", "id": request_id, "result": {"sessionId": f"s{next(sessions)}"}})
        elif method == "session/cancel":
            cancelled.get(params.get("sessionId"), threading.Event()).set()
        elif method == "session/prompt":
            threading.Thread(target=prompt_turn, args=(request_id, params), daemon=True).start()
        elif request_id is not None:
            send({"jsonrpc": "2.0", "id": request_id, "result": None})


if __name__ == "__main__":
    main()
