from __future__ import annotations

from pathlib import Path

from web_backend.tool_executor import execute_tool


def test_execute_tool_runs_python_script(tmp_path: Path) -> None:
    script_path = tmp_path / "echo_tool.py"
    script_path.write_text(
        "import json\n"
        "import sys\n"
        "payload = json.loads(sys.stdin.read() or '{}')\n"
        "sys.stdout.write(json.dumps({'received': payload['arguments']}))\n",
        encoding="utf-8",
    )

    result = execute_tool(
        {
            "name": "echo_tool",
            "executor_path": str(script_path),
        },
        {"value": "ok"},
    )

    assert result == {
        "status": "executed",
        "tool_name": "echo_tool",
        "output": {"received": {"value": "ok"}},
        "error": None,
    }


def test_execute_tool_reports_missing_executor_path() -> None:
    result = execute_tool({"name": "echo_tool"}, {"value": "ok"})

    assert result == {
        "status": "unsupported",
        "tool_name": "echo_tool",
        "output": None,
        "error": "Tool echo_tool has no executor_path configured",
    }