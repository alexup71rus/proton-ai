from __future__ import annotations

import argparse
import json
from pathlib import Path

from protonx.schemas import ToolDefinition
from protonx.training.dataset_builder import build_synthetic_dataset


def _load_tools(path: Path) -> list[ToolDefinition]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Tools file must contain a JSON list.")
    return [ToolDefinition.model_validate(tool) for tool in payload]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a mixed routing dataset from tools and phrase seeds.")
    parser.add_argument("--tools", default="data/tools/tools.json", help="Path to tools registry JSON.")
    parser.add_argument("--output", default="data/train/routing/routing.jsonl", help="Output JSONL path.")
    parser.add_argument("--target-rows", type=int, default=None, help="Approximate target row count.")
    args = parser.parse_args()

    rows_written = build_synthetic_dataset(
        tools=_load_tools(Path(args.tools)),
        output_path=Path(args.output),
        target_rows=args.target_rows,
    )
    print(json.dumps({"rows_written": rows_written, "output_path": args.output}, ensure_ascii=False))


if __name__ == "__main__":
    main()