"""Custom: the grok provider, answered by the official Grok CLI over ACP (`grok agent stdio`) on the SuperGrok plan.

See docs/adr/0003-grok-acp.md. One long-lived agent process per AgentSpec, one ACP session per request.
"""

import atexit
import collections
import itertools
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
from concurrent.futures import Future, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote

from core.utils.llm_profile import LLMAuthError, LLMProfileError

PROFILE_FILE = Path(__file__).with_name("grok_agent_profile.md")
SYSTEM_PROMPT = PROFILE_FILE.read_text(encoding="utf-8").split("---", 2)[2].strip()
CWD = os.path.join(tempfile.gettempdir(), "videolingo-grok")  # kept empty: nothing for the agent to read
# HOME the agent sees, kept empty: under the real one it loads the user's skills and Claude plugins' MCP servers
AGENT_HOME = os.path.join(tempfile.gettempdir(), "videolingo-grok-home")
PROMPT_TIMEOUT = 300
SESSION_KEEP_SECONDS = 60  # the CLI writes a session's summary after the turn ends
# Grok reads the user's Claude/Cursor rules and offers web and session search unless told not to
LEAN_ENV = {name: "false" for name in (
    "GROK_CLAUDE_AGENTS_ENABLED", "GROK_CLAUDE_RULES_ENABLED", "GROK_CLAUDE_SKILLS_ENABLED",
    "GROK_CLAUDE_MCPS_ENABLED", "GROK_CLAUDE_HOOKS_ENABLED", "GROK_CURSOR_AGENTS_ENABLED",
    "GROK_CURSOR_RULES_ENABLED", "GROK_CURSOR_SKILLS_ENABLED", "GROK_CURSOR_MCPS_ENABLED",
    "GROK_CURSOR_HOOKS_ENABLED", "GROK_BACKEND_SEARCH", "GROK_WEB_FETCH", "GROK_SESSION_SEARCH",
)}
# background model calls that only serve the interactive UI
LEAN_FEATURES = {"title_refresh": False, "turn_summary": False, "session_recap": False}


def grok_home():
    """Where the CLI keeps its login and sessions; resolved here because the agent runs with another HOME."""
    return Path(os.environ.get("GROK_HOME") or Path.home() / ".grok")


class GrokAgentError(RuntimeError):
    """The agent exited, timed out, or ended the turn without an answer."""


class GrokToolUseError(GrokAgentError):
    """The agent tried to use a tool, which spends quota on work the prompt never asked for."""


class _RpcError(GrokAgentError):
    """The agent answered a request with a JSON-RPC error."""


@dataclass(frozen=True)
class AgentSpec:
    command: tuple
    model: str
    reasoning_effort: Optional[str]

    def argv(self):
        # --model has no effect on this route; the model goes through GROK_CONFIG
        return [*self.command, "agent", "--no-leader", "--agent-profile", str(PROFILE_FILE), "stdio"]

    def env(self):
        models = {"default": self.model}
        if self.reasoning_effort:
            models["default_reasoning_effort"] = self.reasoning_effort
        return {**os.environ, **LEAN_ENV, "HOME": AGENT_HOME, "GROK_HOME": str(grok_home()),
                "GROK_CONFIG": json.dumps({"models": models, "features": LEAN_FEATURES})}


@dataclass
class _Turn:
    chunks: list = field(default_factory=list)
    tool: Optional[str] = None  # title of the first tool the agent tried


class _Agent:
    def __init__(self, spec):
        try:
            self.proc = subprocess.Popen(spec.argv(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
                                         env=spec.env(), cwd=CWD)
        except OSError as error:
            raise LLMProfileError(f"cannot run Grok CLI '{spec.command[0]}' ({error.strerror}): install it "
                                  f"(https://docs.x.ai/build/cli) or set llm_profiles.<name>.command") from error
        self.ids = itertools.count(1)
        self.state_lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.pending = {}
        self.turns = {}
        self.exited = False
        self.last_prune = 0.0
        self.stderr_tail = collections.deque(maxlen=20)
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=lambda: self.stderr_tail.extend(self.proc.stderr), daemon=True).start()
        try:
            self._request("initialize", {"protocolVersion": 1, "clientCapabilities": {
                "fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False}})
            try:
                self._request("authenticate", {"methodId": "cached_token", "_meta": {"headless": True}})
            except _RpcError as error:
                raise LLMAuthError(f"{error}; run `grok` once and sign in with grok.com") from error
        except BaseException:
            self.close()
            raise

    def alive(self):
        return not self.exited and self.proc.poll() is None

    def complete(self, prompt):
        if time.monotonic() - self.last_prune > SESSION_KEEP_SECONDS:
            self.last_prune = time.monotonic()
            prune_sessions(active={session for agent in list(_AGENTS.values()) for session in list(agent.turns)})
        session_id = self._request("session/new", {"cwd": CWD, "mcpServers": [],
                                                   "_meta": {"systemPromptOverride": SYSTEM_PROMPT}})["sessionId"]
        turn = self.turns[session_id] = _Turn()
        try:
            result = self._request("session/prompt", {"sessionId": session_id,
                                                      "prompt": [{"type": "text", "text": prompt}]},
                                   timeout=PROMPT_TIMEOUT)
        except GrokAgentError as error:
            if turn.tool:  # the tool is the cause; the cancel only turned it into an error
                raise GrokToolUseError(f"the Grok agent tried to use a tool ({turn.tool})") from error
            raise
        finally:
            del self.turns[session_id]
            self._send_quietly({"jsonrpc": "2.0", "id": next(self.ids), "method": "session/close",
                                "params": {"sessionId": session_id}})
        if turn.tool:
            raise GrokToolUseError(f"the Grok agent tried to use a tool ({turn.tool})")
        if result.get("stopReason") != "end_turn":
            raise GrokAgentError(f"the Grok agent stopped the turn: {result.get('stopReason')}")
        return "".join(turn.chunks)

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()
            self.proc.wait()

    def _request(self, method, params, timeout=60):
        request_id = next(self.ids)
        reply = Future()
        with self.state_lock:
            if self.exited:
                raise self._exit_error()
            self.pending[request_id] = reply
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        try:
            message = reply.result(timeout=timeout)
        except FutureTimeout:
            # a hung agent would hang every later request too: retire it, and the next request starts a new one
            self.close()
            raise GrokAgentError(f"the Grok agent did not answer {method} within {timeout}s") from None
        if "error" in message:
            raise _RpcError(f"Grok agent refused {method}: {message['error'].get('message')}")
        return message.get("result") or {}

    def _send(self, message):
        try:
            with self.write_lock:
                self.proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
                self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as error:
            raise self._exit_error() from error

    def _send_quietly(self, message):
        try:
            self._send(message)
        except GrokAgentError:
            pass

    def _exit_error(self):
        tail = "".join(self.stderr_tail).strip()[-500:]
        return GrokAgentError(f"the Grok agent exited (code {self.proc.poll()}){': ' + tail if tail else ''}")

    def _read_stdout(self):
        try:
            for line in self.proc.stdout:
                try:
                    message = json.loads(line)
                except ValueError:
                    continue  # banners and update notices
                if not isinstance(message, dict):
                    continue
                if "method" in message and "id" in message:
                    self._answer(message)
                elif message.get("method") == "session/update":
                    self._on_update(message.get("params") or {})
                elif "id" in message:
                    with self.state_lock:
                        reply = self.pending.pop(message["id"], None)
                    if reply:
                        reply.set_result(message)
        finally:
            with self.state_lock:
                self.exited = True
                waiting, self.pending = list(self.pending.values()), {}
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.close()
            for reply in waiting:
                reply.set_exception(self._exit_error())

    def _on_update(self, params):
        turn = self.turns.get(params.get("sessionId"))
        update = params.get("update") or {}
        if turn is None:
            return
        kind = update.get("sessionUpdate")
        if kind == "agent_message_chunk" and (update.get("content") or {}).get("type") == "text":
            turn.chunks.append(update["content"].get("text", ""))
        elif kind == "tool_call" and turn.tool is None:
            turn.tool = update.get("title") or update.get("kind") or "?"
            self._send_quietly({"jsonrpc": "2.0", "method": "session/cancel", "params": {"sessionId": params["sessionId"]}})

    def _answer(self, message):
        """The client offers no file system or terminal, and rejects every permission request."""
        if message["method"] == "session/request_permission":
            params = message.get("params") or {}
            turn = self.turns.get(params.get("sessionId"))
            if turn is not None and turn.tool is None:
                turn.tool = (params.get("toolCall") or {}).get("title") or "?"
                self._send_quietly({"jsonrpc": "2.0", "method": "session/cancel", "params": {"sessionId": params["sessionId"]}})
            options = params.get("options") or []
            reject = next((option for option in options if str(option.get("kind", "")).startswith("reject")), None)
            outcome = {"outcome": "selected", "optionId": reject["optionId"]} if reject else {"outcome": "cancelled"}
            self._send_quietly({"jsonrpc": "2.0", "id": message["id"], "result": {"outcome": outcome}})
        else:
            self._send_quietly({"jsonrpc": "2.0", "id": message["id"],
                                "error": {"code": -32601, "message": f"client does not support {message['method']}"}})


def prune_sessions(active=()):
    """Delete what the CLI stored for this CWD and has not written to for SESSION_KEEP_SECONDS.

    The CLI keeps every ACP session (about 80 KB) even after session/close. CWD is VideoLingo's own,
    so everything stored under it is a finished request once it goes quiet, whichever run made it."""
    root = grok_home() / "sessions" / quote(CWD, safe="")
    if not root.is_dir():
        return
    cutoff = time.time() - SESSION_KEEP_SECONDS
    for entry in root.iterdir():
        if entry.name in active:
            continue
        try:
            files = [entry, *entry.rglob("*")] if entry.is_dir() else [entry]
            if max(path.stat().st_mtime for path in files) > cutoff:
                continue
            shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
        except OSError:
            pass  # written to or removed while we looked: the next prune decides


_AGENTS = {}
_AGENTS_LOCK = threading.Lock()


def _agent(spec):
    """The live agent of `spec`, started on first use and again after it exits."""
    with _AGENTS_LOCK:
        agent = _AGENTS.get(spec)
        if agent is None or not agent.alive():
            os.makedirs(CWD, exist_ok=True)
            os.makedirs(AGENT_HOME, exist_ok=True)
            agent = _AGENTS[spec] = _Agent(spec)
        return agent


def completer(command, model, reasoning_effort) -> Callable[[str], str]:
    argv = tuple(shlex.split(command))
    if not argv:
        raise LLMProfileError("llm_profiles.<name>.command is empty: set it to the Grok CLI, usually 'grok'")
    spec = AgentSpec(argv, model, reasoning_effort)
    return lambda prompt: _agent(spec).complete(prompt)


def shutdown():
    with _AGENTS_LOCK:
        for agent in _AGENTS.values():
            agent.close()
        _AGENTS.clear()


atexit.register(shutdown)
