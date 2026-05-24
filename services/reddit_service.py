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
                posts.append({
                    "title": d["title"],
                    "score": d["score"],
                    "comments": d["num_comments"],
                    "subreddit": d["subreddit"],
                })
        return posts
    except Exception:
        return None
