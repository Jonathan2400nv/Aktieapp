import os
import urllib.parse
import requests
from dotenv import load_dotenv

load_dotenv()

_SIM_BASE = "https://gateway.saxobank.com/sim/openapi"
_AUTH_URL = "https://sim.logonvalidation.net/authorize"
_TOKEN_URL = "https://sim.logonvalidation.net/token"
_REDIRECT_URI = os.getenv("SAXO_REDIRECT_URI", "http://localhost:8501")


def _app_key() -> str:
    return os.getenv("SAXO_APP_KEY", "")


def _app_secret() -> str:
    return os.getenv("SAXO_APP_SECRET", "")


def get_auth_url() -> str:
    params = {
        "response_type": "code",
        "client_id": _app_key(),
        "redirect_uri": _REDIRECT_URI,
        "state": "saxo_auth",
    }
    return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str) -> dict | None:
    try:
        resp = requests.post(
            _TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": _REDIRECT_URI,
                "client_id": _app_key(),
                "client_secret": _app_secret(),
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def refresh_access_token(refresh_token: str) -> dict | None:
    try:
        resp = requests.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": _app_key(),
                "client_secret": _app_secret(),
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def get_accounts(access_token: str) -> list[dict]:
    try:
        resp = requests.get(
            f"{_SIM_BASE}/port/v1/accounts/me",
            headers=_headers(access_token),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("Data", [])
    except Exception:
        return []


def get_positions(access_token: str, client_key: str) -> list[dict]:
    try:
        resp = requests.get(
            f"{_SIM_BASE}/port/v1/positions",
            headers=_headers(access_token),
            params={"ClientKey": client_key, "FieldGroups": "DisplayAndFormat,PositionBase,PositionView"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("Data", [])
    except Exception:
        return []


def get_balance(access_token: str, client_key: str) -> dict | None:
    try:
        resp = requests.get(
            f"{_SIM_BASE}/port/v1/balances",
            headers=_headers(access_token),
            params={"ClientKey": client_key},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def find_uic(access_token: str, symbol: str) -> int | None:
    """Look up Saxo UIC for a US stock symbol."""
    try:
        resp = requests.get(
            f"{_SIM_BASE}/ref/v1/instruments",
            headers=_headers(access_token),
            params={"Keywords": symbol, "AssetTypes": "Stock", "ExchangeId": "XNAS,XNYS"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("Data", [])
        if data:
            return data[0]["Identifier"]
        return None
    except Exception:
        return None


def place_order(
    access_token: str,
    account_key: str,
    uic: int,
    buy: bool,
    amount: int,
    stop_loss_price: float,
    take_profit_price: float,
) -> dict | None:
    try:
        order = {
            "Uic": uic,
            "AssetType": "Stock",
            "BuySell": "Buy" if buy else "Sell",
            "Amount": amount,
            "OrderType": "Market",
            "ManualOrder": True,
            "AccountKey": account_key,
            "OrderDuration": {"DurationType": "DayOrder"},
            "Orders": [
                {
                    "Uic": uic,
                    "AssetType": "Stock",
                    "BuySell": "Sell" if buy else "Buy",
                    "Amount": amount,
                    "OrderType": "StopIfTraded",
                    "StopLimitPrice": stop_loss_price,
                    "OrderDuration": {"DurationType": "GoodTillCancel"},
                    "ManualOrder": False,
                },
                {
                    "Uic": uic,
                    "AssetType": "Stock",
                    "BuySell": "Sell" if buy else "Buy",
                    "Amount": amount,
                    "OrderType": "Limit",
                    "Price": take_profit_price,
                    "OrderDuration": {"DurationType": "GoodTillCancel"},
                    "ManualOrder": False,
                },
            ],
        }
        resp = requests.post(
            f"{_SIM_BASE}/trade/v2/orders",
            headers={**_headers(access_token), "Content-Type": "application/json"},
            json=order,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}
