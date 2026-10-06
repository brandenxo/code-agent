import json
from types import SimpleNamespace

import pytest

from app.main import run_turn
from app.tools import BASH_TIMEOUT_SECONDS, execute_tool


def test_tool_call_limit_stops_before_executing_extra_calls():
    tool_calls = [
        SimpleNamespace(
            id=f"call-{index}",
            function=SimpleNamespace(name="Read", arguments='{"file_path": "x"}'),
        )
        for index in range(2)
    ]
    message = SimpleNamespace(content=None, tool_calls=tool_calls)
    response = SimpleNamespace(
        usage=SimpleNamespace(total_tokens=5),
        choices=[SimpleNamespace(message=message)],
        model="test/model",
    )
    completions = SimpleNamespace(create=lambda **kwargs: response)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    history = [{"role": "user", "content": "work"}]

    reply, model, tokens, tool_count, steps = run_turn(
        client, history, "test/model", max_tool_calls=1
    )

    assert "tool-call limit" in reply
    assert model == "test/model"
    assert tokens == 5
    assert tool_count == 0
    assert steps == []


def test_normal_bash_uses_argument_list_and_timeout(monkeypatch):
    captured = {}

    def fake_run(arguments, **kwargs):
        captured["arguments"] = arguments
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("app.tools.subprocess.run", fake_run)
    tool_call = SimpleNamespace(
        function=SimpleNamespace(
            name="Bash", arguments=json.dumps({"command": "python --version"})
        )
    )

    result = execute_tool(tool_call)

    assert captured["arguments"] == ["python", "--version"]
    assert captured["kwargs"]["timeout"] == BASH_TIMEOUT_SECONDS
    assert "shell" not in captured["kwargs"]
    assert "Exit code: 0" in result


def test_delete_removes_a_file(tmp_path):
    target = tmp_path / "remove-me.txt"
    target.write_text("temporary", encoding="utf-8")
    tool_call = SimpleNamespace(
        function=SimpleNamespace(
            name="Delete", arguments=json.dumps({"file_path": str(target)})
        )
    )

    assert execute_tool(tool_call) == "File deleted successfully."
    assert not target.exists()


def test_benchmark_delete_cannot_escape_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "keep-me.txt"
    outside.write_text("important", encoding="utf-8")
    tool_call = SimpleNamespace(
        function=SimpleNamespace(
            name="Delete", arguments=json.dumps({"file_path": "../keep-me.txt"})
        )
    )

    with pytest.raises(PermissionError, match="benchmark workspace"):
        execute_tool(tool_call, workspace_root=workspace)
    assert outside.exists()
