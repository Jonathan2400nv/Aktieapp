import streamlit as st


def render() -> None:
    st.header("Saxo Bank Integration")

    st.markdown("""
    ### :orange[Kommer snart]

    Denne fane vil give adgang til automatisk paper trading på din Saxo Bank demo-konto.

    **Planlagte features:**
    - Automatisk ordreafgivelse baseret på swing trading-signaler
    - Live porteføljeoverblik og åbne positioner
    - Trade-log med historik og performance
    - Risikostyring: stop-loss og position sizing

    ---
    *Saxo Bank API-integration er under udvikling.*
    """)
