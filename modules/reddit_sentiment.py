import streamlit as st
import pandas as pd
from services.reddit_service import fetch_reddit_posts, fetch_stocktwits_posts
from services.claude_service import get_reddit_summary


def _render_table(posts: list[dict]) -> None:
    df = pd.DataFrame(posts)[["title", "beskrivelse", "score", "comments", "subreddit", "link"]]
    df.columns = ["Aktie/Titel", "Besked", "Score", "Kommentarer", "Kilde", "Link"]
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Besked": st.column_config.TextColumn(width="large"),
            "Link": st.column_config.LinkColumn(display_text="Åbn"),
        },
        hide_index=True,
    )


def render() -> None:
    st.header("Marked Sentiment")

    # --- Reddit ---
    st.subheader("Reddit — r/wallstreetbets & r/stocks")
    with st.spinner("Henter Reddit-posts..."):
        reddit_posts = fetch_reddit_posts(subreddits=("wallstreetbets", "stocks"), limit=20)

    if reddit_posts:
        _render_table(reddit_posts)
    else:
        st.warning("Reddit er ikke tilgængeligt lige nu — de blokerer ind imellem uden API-nøgle. Prøv igen senere.")

    # --- StockTwits ---
    st.subheader("StockTwits — Trending")
    with st.spinner("Henter StockTwits..."):
        st_posts = fetch_stocktwits_posts(limit=20)

    if st_posts:
        _render_table(st_posts)
    else:
        st.warning("Kunne ikke hente data fra StockTwits — prøv igen om et øjeblik.")

    # --- AI-resumé ---
    all_posts = (reddit_posts or []) + (st_posts or [])
    if not all_posts:
        return

    st.subheader("AI-resumé")
    with st.spinner("Genererer dansk resumé..."):
        summary = get_reddit_summary(all_posts)

    if summary:
        st.info(summary)
    else:
        st.caption("Resumé ikke tilgængeligt — tjek at ANTHROPIC_API_KEY er konfigureret.")
