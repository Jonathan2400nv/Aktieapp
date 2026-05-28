import streamlit as st
import pandas as pd
from services.reddit_service import fetch_hot_posts
from services.claude_service import get_reddit_summary


def render() -> None:
    st.header("Marked Sentiment")

    with st.spinner("Henter trending fra StockTwits..."):
        posts = fetch_hot_posts(subreddits=("wallstreetbets", "stocks"), limit=20)

    if posts is None:
        st.warning("Kunne ikke hente data fra StockTwits — prøv igen om et øjeblik.")
        return

    df = pd.DataFrame(posts)[['title', 'beskrivelse', 'score', 'comments', 'subreddit', 'link']]
    df.columns = ['Aktie', 'Besked', 'Likes', 'Kommentarer', 'Kilde', 'Link']
    st.dataframe(df, use_container_width=True, column_config={
        "Beskrivelse": st.column_config.TextColumn(width="large"),
        "Link": st.column_config.LinkColumn(display_text="Åbn"),
    })

    st.subheader("AI-resumé")
    with st.spinner("Genererer dansk resumé..."):
        summary = get_reddit_summary(posts)

    if summary:
        st.info(summary)
    else:
        st.caption(
            "Resumé ikke tilgængeligt — tjek at ANTHROPIC_API_KEY er konfigureret. "
            "Data vises ovenfor uden resumé."
        )
