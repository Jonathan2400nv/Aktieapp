import os
import requests


def _get_secret(key: str) -> str | None:
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return None


def _credentials() -> tuple[str, str] | None:
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_KEY")
    if url and key:
        return url.rstrip("/"), key
    return None


def load_from_supabase() -> dict | None:
    creds = _credentials()
    if not creds:
        return None
    url, key = creds
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    r = requests.get(
        f"{url}/rest/v1/portfolio",
        headers=headers,
        params={"id": "eq.1", "select": "data"},
        timeout=10,
    )
    r.raise_for_status()
    rows = r.json()
    return rows[0]["data"] if rows else None


def save_to_supabase(portfolio: dict) -> bool:
    creds = _credentials()
    if not creds:
        return False
    url, key = creds
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    r = requests.post(
        f"{url}/rest/v1/portfolio",
        headers=headers,
        json={"id": 1, "data": portfolio},
        timeout=10,
    )
    r.raise_for_status()
    return True
