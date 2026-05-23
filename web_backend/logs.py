from __future__ import annotations

import json
import textwrap
from typing import Any

from web_backend.config import get_log_file


def load_human_logs(limit: int = 100) -> list[dict[str, Any]]:
    path = get_log_file()
    if not path.exists():
        return []

    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    result: list[dict[str, Any]] = []
    for row in rows[-limit:][::-1]:
        raw_output = row.get("model_output", "")
        result.append(
            {
                "user": row.get("user_text", ""),
                "candidates": row.get("candidate_tools", []),
                "raw_output_summary": textwrap.shorten(raw_output, width=120, placeholder="..."),
                "raw_output": raw_output,
                "error": row.get("validation_error") or "none",
                "result": row.get("final_action") or "unknown",
            }
        )
    return result
