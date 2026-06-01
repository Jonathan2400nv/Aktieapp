import html as _html
import streamlit as st
from services.reddit_service import fetch_reddit_posts, fetch_stocktwits_posts
from services.claude_service import get_reddit_summary


def _render_cards(posts: list[dict]) -> None:
    html = ""
    for p in posts:
        score = p.get("score", 0)
        comments = p.get("comments", 0)
        source = _html.escape(str(p.get("subreddit", "")))
        title = _html.escape(p.get("title", "")[:120])
        desc = _html.escape(p.get("beskrivelse", "")[:160])
        link = p.get("link", "#")

        score_color = "#4caf50" if score > 100 else ("#ffc107" if score > 10 else "#888")

        html += f"""
        <a href="{link}" target="_blank" style="text-decoration:none;color:inherit">
          <div style="padding:14px 16px;border-radius:10px;border:1px solid rgba(128,128,128,0.15);
                      margin-bottom:8px;transition:border-color 0.15s;cursor:pointer">
            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px">
              <div style="flex:1;min-width:0">
                <div style="font-weight:600;font-size:13px;line-height:1.4;margin-bottom:4px">{title}</div>
                <div style="font-size:12px;color:#888;line-height:1.4">{desc}</div>
              </div>
              <div style="flex-shrink:0;text-align:right">
                <div style="font-size:11px;color:#888;margin-bottom:4px">{source}</div>
                <div style="font-size:11px">
                  <span style="color:{score_color};font-weight:500">▲ {score:,}</span>
                  <span style="color:#888;margin-left:8px">💬 {comments:,}</span>
                </div>
              </div>
            </div>
          </div>
        </a>"""

    st.markdown(html, unsafe_allow_html=True)


def render() -> None:
    st.header("💬 Marked Sentiment")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Reddit")
        st.caption("r/wallstreetbets · r/stocks")
        with st.spinner("Henter..."):
            reddit_posts = fetch_reddit_posts(subreddits=("wallstreetbets", "stocks"), limit=15)
        if reddit_posts:
            _render_cards(reddit_posts)
        else:
            st.warning("Reddit utilgængeligt — prøv igen om et øjeblik.")

    with col2:
        st.markdown("#### StockTwits")
        st.caption("Trending")
        with st.spinner("Henter..."):
            st_posts = fetch_stocktwits_posts(limit=15)
        if st_posts:
            _render_cards(st_posts)
        else:
            st.warning("StockTwits utilgængeligt — prøv igen om et øjeblik.")

    all_posts = (reddit_posts or []) + (st_posts or [])
    if not all_posts:
        return

    st.divider()
    st.markdown("#### 🤖 AI-resumé")
    with st.spinner("Genererer resumé..."):
        summary = get_reddit_summary(all_posts)
    if summary:
        st.info(summary)
    else:
        st.caption("Resumé ikke tilgængeligt — tjek at ANTHROPIC_API_KEY er konfigureret.")
