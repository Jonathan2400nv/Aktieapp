import requests
import streamlit as st

_REDDIT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
_STOCKTWITS_HEADERS = {"User-Agent": "aktie-app/1.0"}
_STOCKTWITS_BASE = "https://api.stocktwits.com/api/2"


@st.cache_data(ttl=900)
def fetch_reddit_posts(
    subreddits: tuple[str, ...] = ("wallstreetbets", "stocks"),
    limit: int = 20,
) -> list[dict] | None:
    try:
        posts = []
        for sub in subreddits:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}"
            resp = requests.get(url, headers=_REDDIT_HEADERS, timeout=10)
            if resp.status_code != 200:
                return None
            for child in resp.json()["data"]["children"]:
                d = child["data"]
                text = d.get("selftext", "").strip()
                if text in ("", "[removed]", "[deleted]"):
                    text = "—"
                elif len(text) > 120:
                    text = text[:120] + "…"
                posts.append({
                    "title": d["title"],
                    "beskrivelse": text,
                    "score": d["score"],
                    "comments": d["num_comments"],
                    "subreddit": f"r/{d['subreddit']}",
                    "link": f"https://reddit.com{d['permalink']}",
                })
        return posts if posts else None
    except Exception:
        return None


@st.cache_data(ttl=900)
def fetch_stocktwits_posts(limit: int = 20) -> list[dict] | None:
    try:
        resp = requests.get(
            f"{_STOCKTWITS_BASE}/streams/trending.json",
            headers=_STOCKTWITS_HEADERS,
            params={"limit": limit},
            timeout=10,
        )
        resp.raise_for_status()
        messages = resp.json().get("messages", [])
        posts = []
        for m in messages:
            syms = m.get("symbols", [])
            symbol = syms[0].get("symbol", "") if syms else ""
            sentiment = m.get("entities", {}).get("sentiment", {})
            sentiment_str = sentiment.get("basic", "—") if sentiment else "—"
            body = m.get("body", "").strip()
            posts.append({
                "title": f"${symbol}" if symbol else "Generelt",
                "beskrivelse": body[:120] + "…" if len(body) > 120 else body,
                "score": m.get("likes", {}).get("total", 0),
                "comments": 0,
                "subreddit": f"StockTwits • {sentiment_str}",
                "link": f"https://stocktwits.com/message/{m.get('id', '')}",
            })
        return posts if posts else None
    except Exception:
        return None


def fetch_hot_posts(
    subreddits: tuple[str, ...] = ("wallstreetbets", "stocks"),
    limit: int = 20,
) -> list[dict] | None:
    """Returns combined Reddit + StockTwits posts. Reddit may be unavailable."""
    reddit = fetch_reddit_posts(subreddits, limit)
    stocktwits = fetch_stocktwits_posts(limit)
    combined = []
    if reddit:
        combined.extend(reddit)
    if stocktwits:
        combined.extend(stocktwits)
    return combined if combined else None
