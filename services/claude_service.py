import os
import anthropic
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

_MODEL = "claude-haiku-4-5-20251001"


def get_reddit_summary(posts: list[dict]) -> str | None:
    if not posts:
        return None

    api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        titles = "\n".join(
            f"- {p['title']} (score: {p.get('score', 0)}, r/{p.get('subreddit', '?')})"
            for p in posts[:20]
        )
        message = client.messages.create(
            model=_MODEL,
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": (
                    "Her er de mest populære posts fra r/wallstreetbets og r/stocks:\n\n"
                    f"{titles}\n\n"
                    "Lav et kort resumé på dansk (3-5 sætninger) af de vigtigste tendenser "
                    "og stemninger i markedet baseret på disse posts."
                ),
            }],
        )
        return message.content[0].text
    except Exception:
        return None
