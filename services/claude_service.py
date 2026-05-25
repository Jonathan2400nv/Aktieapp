import os
import anthropic
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

_MODEL = "claude-haiku-4-5-20251001"


def get_reddit_summary(posts: list[dict]) -> str | None:
    if not posts:
        return None

    try:
        api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    except Exception:
        api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        posts_text = "\n".join(
            f"- [{p.get('subreddit', '?')}] {p['title']} | score: {p.get('score', 0)} | "
            f"kommentarer: {p.get('comments', 0)}"
            + (f" | beskrivelse: {p['beskrivelse']}" if p.get('beskrivelse') and p['beskrivelse'] != '—' else "")
            for p in posts[:30]
        )
        message = client.messages.create(
            model=_MODEL,
            max_tokens=1200,
            messages=[{
                "role": "user",
                "content": (
                    "Her er de mest populære posts fra r/wallstreetbets og r/stocks lige nu:\n\n"
                    f"{posts_text}\n\n"
                    "Analyser disse posts og svar præcist på dansk med følgende struktur:\n\n"
                    "**Nævnte aktier og hvad folk mener:**\n"
                    "List de specifikke aktier/tickers der nævnes. For hver: hvad er stemningen (bullish/bearish), "
                    "og hvad er grundlaget (earnings, news, spekulationer, teknisk analyse osv.).\n\n"
                    "**Generel markedsstemning:** (bullish/bearish/blandet — begrund med konkrete posts)\n\n"
                    "**Investeringsanbefaling:** Hvilke aktier eller tendenser er værd at holde øje med baseret på denne aktivitet, og hvorfor."
                ),
            }],
        )
        return message.content[0].text
    except Exception:
        return None
