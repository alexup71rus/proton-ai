from __future__ import annotations

from typing import Any

import requests
from fastapi import HTTPException

from web_backend.config import get_service_base_url


def _build_url(path: str) -> str:
    return f"{get_service_base_url()}{path}"


def _raise_for_response(response: requests.Response) -> None:
    if response.ok:
        return
    detail: str | dict[str, Any]
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and "detail" in payload:
        detail = payload["detail"]
    else:
        detail = response.text or "Service request failed"
    raise HTTPException(status_code=response.status_code, detail=detail)


def get_json(path: str) -> dict[str, Any]:
    response = requests.get(_build_url(path), timeout=30)
    _raise_for_response(response)
    return response.json()


def post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(_build_url(path), json=payload, timeout=30)
    _raise_for_response(response)
    return response.json()
