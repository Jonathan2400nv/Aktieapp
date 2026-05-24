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
            max_tokens=900,
            messages=[{
                "role": "user",
                "content": (
                    "Her er de mest populære posts fra r/wallstreetbets og r/stocks lige nu:\n\n"
                    f"{titles}\n\n"
                    "Analyser disse posts og svar på dansk med følgende struktur:\n\n"
                    "**Generel stemning:** (bullish/bearish/blandet og hvorfor)\n\n"
                    "**Hvad er optimistisk:** (hvilke aktier, sektorer eller tendenser er folk positive omkring)\n\n"
                    "**Investeringsanbefaling:** (baseret på stemningen — hvad bør man holde øje med eller overveje)"
                ),
            }],
        )
        return message.content[0].text
    except Exception:
        return None
