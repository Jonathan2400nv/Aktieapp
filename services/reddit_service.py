import os
import praw
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def _get_credentials() -> tuple[str, str, str]:
    client_id = st.secrets.get("REDDIT_CLIENT_ID") or os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = st.secrets.get("REDDIT_CLIENT_SECRET") or os.getenv("REDDIT_CLIENT_SECRET", "")
    user_agent = st.secrets.get("REDDIT_USER_AGENT") or os.getenv("REDDIT_USER_AGENT", "aktie-app/1.0")
    return client_id, client_secret, user_agent


@st.cache_data(ttl=900)
def fetch_hot_posts(
    subreddits: tuple[str, ...] = ("wallstreetbets", "stocks"),
    limit: int = 20,
) -> list[dict] | None:
    try:
        client_id, client_secret, user_agent = _get_credentials()
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        posts = []
        for sub in subreddits:
            for post in reddit.subreddit(sub).hot(limit=limit):
                posts.append({
                    "title": post.title,
                    "score": post.score,
                    "comments": post.num_comments,
                    "subreddit": post.subreddit.display_name,
                })
        return posts
    except Exception:
        return None
