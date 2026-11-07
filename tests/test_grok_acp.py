"""Grok profile seen through ask_gpt, against a fake `grok agent stdio` (tests/fixtures/fake_grok_agent.py)."""

import importlib
import json
import shlex
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from core.utils import config_utils, grok_acp
from core.utils.llm_profile import LLMAuthError, LLMProfileError, active_profile

ask_gpt_module = importlib.import_module("core.utils.ask_gpt")
FAKE = Path(__file__).parent / "fixtures" / "fake_grok_agent.py"
FAKE_COMMAND = f"{shlex.quote(sys.executable)} {shlex.quote(str(FAKE))}"

CONFIG = """
    api:
      profile: grok
      key: ''
      base_url: 'https://api.example.com'
      model: 'custom-model'
      llm_support_json: false
    max_workers: 16
    llm_profiles:
      grok:
        provider: grok
        model: grok-4.7
        reasoning_effort: low
        max_workers: 3
        command: {command}
"""


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(ask_gpt_module, "GPT_LOG_FOLDER", str(tmp_path / "gpt_log"))
    monkeypatch.setattr("core.utils.decorator.time.sleep", lambda *_: None)
    config = tmp_path / "config.yaml"
    monkeypatch.setattr(config_utils, "CONFIG_PATH", str(config))

    def write(command=FAKE_COMMAND):
        config.write_text(textwrap.dedent(CONFIG.format(command=json.dumps(command))), encoding="utf-8")

    write()
    yield write
    grok_acp.shutdown()


def complete(prompt):
    return active_profile().complete(prompt)


def test_ask_gpt_returns_the_json_of_the_agent_reply(setup):
    assert ask_gpt_module.ask_gpt('REPLY:```json\n{"1": {"direct": "xin chào"}}\n```', resp_type="json") == {
        "1": {"direct": "xin chào"}}


def test_agent_runs_the_profile_model_without_tools_or_foreign_rules(setup):
    started = json.loads(complete("how were you started?"))
    assert started["config"]["models"] == {"default": "grok-4.7", "default_reasoning_effort": "low"}
    assert started["config"]["features"] == {"title_refresh": False, "turn_summary": False, "session_recap": False}
    assert started["claude_agents"] == "false"
    assert started["backend_search"] == "false"
    assert "--always-approve" not in started["argv"]
    assert started["argv"][-1] == "stdio"


def test_agent_sees_an_empty_home_so_it_loads_none_of_the_user_skills_or_plugins(setup, monkeypatch):
    monkeypatch.delenv("GROK_HOME", raising=False)
    started = json.loads(complete("how were you started?"))
    assert started["home"] != str(Path.home())
    assert not any(Path(started["home"]).iterdir())
    assert started["grok_home"] == str(Path.home() / ".grok")


def test_a_grok_home_set_by_the_user_is_kept(setup, tmp_path, monkeypatch):
    monkeypatch.setenv("GROK_HOME", str(tmp_path / "grok-home"))
    assert json.loads(complete("how were you started?"))["grok_home"] == str(tmp_path / "grok-home")


def test_a_tool_call_cancels_the_turn_and_fails_the_request(setup):
    started = time.monotonic()
    with pytest.raises(grok_acp.GrokToolUseError):
        complete("TOOL REPLY:{}")
    assert time.monotonic() - started < 1.5  # the fake ends the turn only when it is cancelled, else after 2s


def test_a_permission_request_is_rejected_and_fails_the_request(setup):
    with pytest.raises(grok_acp.GrokToolUseError):
        complete("PERMISSION")


def test_lines_that_are_not_acp_messages_are_skipped(setup):
    assert complete("GARBAGE REPLY:ok") == "ok"


def test_an_agent_that_stops_answering_is_replaced(setup, monkeypatch):
    monkeypatch.setattr(grok_acp, "PROMPT_TIMEOUT", 1)
    first = json.loads(complete("how were you started?"))["pid"]
    with pytest.raises(grok_acp.GrokAgentError):
        complete("HANG")
    assert json.loads(complete("how were you started?"))["pid"] != first


def test_concurrent_requests_share_one_agent_and_get_their_own_reply(setup):
    results = {}
    threads = [threading.Thread(target=lambda n=n: results.__setitem__(n, complete(f"SLOW REPLY:{n}"))) for n in range(3)]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == {0: "0", 1: "1", 2: "2"}
    assert time.monotonic() - started < 2.5  # three one-second turns in parallel, not in sequence


def test_an_agent_that_exits_fails_the_request_and_the_next_request_starts_a_new_one(setup):
    with pytest.raises(grok_acp.GrokAgentError):
        complete("DIE")
    assert complete("REPLY:back") == "back"


def test_a_refused_cached_token_is_an_auth_error(setup):
    setup(FAKE_COMMAND + " --auth-fail")
    with pytest.raises(LLMAuthError):
        complete("REPLY:x")


def test_a_missing_grok_cli_is_a_profile_error(setup):
    setup("grok-cli-that-does-not-exist")
    with pytest.raises(LLMProfileError):
        complete("REPLY:x")


def test_an_empty_command_is_a_profile_error(setup):
    setup(" ")
    with pytest.raises(LLMProfileError):
        complete("REPLY:x")


def test_grok_profile_needs_no_api_key_and_keeps_its_thread_count(setup):
    from core.utils.llm_profile import llm_max_workers
    profile = active_profile()
    assert (profile.provider, profile.model) == ("grok", "grok-4.7")
    assert llm_max_workers() == 3


def test_finished_sessions_are_removed_from_the_grok_home(setup, tmp_path, monkeypatch):
    import os
    from urllib.parse import quote
    monkeypatch.setenv("GROK_HOME", str(tmp_path / "grok-home"))
    sessions = tmp_path / "grok-home" / "sessions" / quote(grok_acp.CWD, safe="")
    old, fresh = sessions / "old-session", sessions / "fresh-session"
    for folder in (old, fresh):
        folder.mkdir(parents=True)
        (folder / "updates.jsonl").write_text("{}")
    (sessions / "prompt_history.jsonl").write_text("{}")
    an_hour_ago = time.time() - 3600
    for path in (old / "updates.jsonl", old, sessions / "prompt_history.jsonl"):
        os.utime(path, (an_hour_ago, an_hour_ago))
    complete("REPLY:x")
    assert sorted(path.name for path in sessions.iterdir()) == ["fresh-session"]
