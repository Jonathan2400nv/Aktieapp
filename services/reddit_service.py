import requests
import streamlit as st

_HEADERS = {"User-Agent": "aktie-app/1.0"}
_STOCKTWITS_BASE = "https://api.stocktwits.com/api/2"


@st.cache_data(ttl=900)
def fetch_hot_posts(
    subreddits: tuple[str, ...] = ("wallstreetbets", "stocks"),
    limit: int = 20,
) -> list[dict] | None:
    """Fetches trending messages from StockTwits (Reddit API is now blocked)."""
    try:
        posts = []

        # Trending stream
        resp = requests.get(
            f"{_STOCKTWITS_BASE}/streams/trending.json",
            headers=_HEADERS,
            params={"limit": limit},
            timeout=10,
        )
        resp.raise_for_status()
        messages = resp.json().get("messages", [])

        for m in messages:
            symbol = ""
            syms = m.get("symbols", [])
            if syms:
                symbol = syms[0].get("symbol", "")

            sentiment = m.get("entities", {}).get("sentiment", {})
            sentiment_str = sentiment.get("basic", "—") if sentiment else "—"

            body = m.get("body", "").strip()
            beskrivelse = body[:120] + "…" if len(body) > 120 else body

            posts.append({
                "title": f"${symbol}" if symbol else "Generelt",
                "beskrivelse": beskrivelse,
                "score": m.get("likes", {}).get("total", 0),
                "comments": 0,
                "subreddit": f"StockTwits • {sentiment_str}",
                "link": f"https://stocktwits.com/message/{m.get('id', '')}",
            })

        return posts if posts else None
    except Exception:
        return None
