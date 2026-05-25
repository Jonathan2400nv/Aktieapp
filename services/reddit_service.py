import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

_HEADERS = {"User-Agent": "aktie-app/1.0"}


@st.cache_data(ttl=900)
def fetch_hot_posts(
    subreddits: tuple[str, ...] = ("wallstreetbets", "stocks"),
    limit: int = 20,
) -> list[dict] | None:
    try:
        posts = []
        for sub in subreddits:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}"
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            resp.raise_for_status()
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
                    "subreddit": d["subreddit"],
                })
        return posts
    except Exception:
        return None
