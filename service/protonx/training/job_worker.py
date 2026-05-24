from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from protonx.training.trainer import run_training


def _load_config(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Training job config must be a JSON object")
    return payload


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        raise SystemExit("Usage: python -m protonx.training.job_worker <config.json>")

    config = _load_config(Path(args[0]))
    training_device = config.pop("training_device", None)
    if training_device:
        os.environ["PROTONX_TRAIN_DEVICE"] = str(training_device)

    config["dataset_path"] = Path(config["dataset_path"])
    status = run_training(**config)
    if status.get("status") == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
