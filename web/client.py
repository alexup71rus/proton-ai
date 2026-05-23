import requests


BASE_URL = "http://localhost:8000"


def post(path: str, payload: dict) -> dict:
    response = requests.post(f"{BASE_URL}{path}", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def get(path: str) -> dict:
    response = requests.get(f"{BASE_URL}{path}", timeout=30)
    response.raise_for_status()
    return response.json()
