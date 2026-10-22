"""AI Analyst page: Chat with citations, NL screener, note history."""
import streamlit as st
import requests
import json
from niveshdristi.app.components import (
    page_header, render_disclaimer, analyst_note_card, empty_state, tag
)


def render(api_get):
    
    page_header("AI Analyst", "Grounded AI research with citations and natural language screening", "🤖")
    
    tab1, tab2, tab3 = st.tabs(["💬 Chat with Citations", "🔍 Natural Language Screener", "📜 Note History"])
    
    # Tab 1: Chat with Citations
    with tab1:
        st.markdown("### Ask Questions with Citations")
        st.markdown("""
        <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
            Ask questions about stocks, sectors, or market conditions. 
            Answers are grounded in annual reports and concall transcripts with citations.
        </div>
        """, unsafe_allow_html=True)
        
        # Chat input
        query = st.text_area(
            "Your question",
            placeholder="e.g., Why is RELIANCE bullish? What are the key risks for IT sector? Compare TCS vs INFY fundamentals.",
            height=100,
            label_visibility="collapsed"
        )
        
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("🔍 Ask", type="primary", use_container_width=True):
                if query:
                    with st.spinner("Searching documents and generating answer..."):
                        # This would call a RAG endpoint
                        st.info("🔧 RAG-based Q&A coming soon. Will cite annual reports and concall transcripts.")
        
        # Example questions
        st.markdown("### Example Questions")
        examples = [
            "What are the key growth drivers for RELIANCE?",
            "What are the risks for the IT sector in FY25?",
            "Compare TCS and INFY on margins and growth",
            "Why is HDFCBANK showing bullish signals?",
            "What did management say in the last concall?",
        ]
        
        cols = st.columns(len(examples))
        for i, ex in enumerate(examples):
            with cols[i]:
                if st.button(ex, key=f"ex_{i}", use_container_width=True):
                    st.toast(f"Example: {ex}")
    
    # Tab 2: Natural Language Screener
    with tab2:
        st.markdown("### Natural Language Screener")
        st.markdown("""
        <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
            Describe your screen in plain English. The AI will convert it to structured filters.
        </div>
        """, unsafe_allow_html=True)
        
        nl_query = st.text_input(
            "Screen for...",
            placeholder="e.g., low debt midcaps with RSI under 40 and ROE above 15%",
            label_visibility="collapsed"
        )
        
        if st.button("🔍 Screen", type="primary", use_container_width=True):
            if nl_query:
                with st.spinner("Converting to filters and screening..."):
                    st.info("🔧 NL → structured filter conversion coming soon. Will use LLM to parse and execute filters.")
        
        # Example NL queries
        st.markdown("### Example Queries")
        nl_examples = [
            "large caps with ROE > 20% and debt/equity < 0.5",
            "midcaps breaking out above 50-day EMA with volume surge",
            "stocks near 52-week low with improving fundamentals",
            "sectors leading in current market regime",
        ]
        
        for ex in nl_examples:
            if st.button(ex, key=f"nl_{ex[:10]}", use_container_width=True):
                st.toast(f"Example: {ex}")
    
    # Tab 3: Note History
    with tab3:
        st.markdown("### Generated Notes History")
        st.markdown("""
        <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
            Previously generated AI analyst notes for quick reference.
        </div>
        """, unsafe_allow_html=True)
        
        # Mock history
        history = [
            {"ticker": "RELIANCE", "date": "2024-10-20", "summary": "Neutral technical profile with bullish momentum...", "validated": True},
            {"ticker": "TCS", "date": "2024-10-19", "summary": "Strong fundamentals but overbought on RSI...", "validated": True},
            {"ticker": "HDFCBANK", "date": "2024-10-18", "summary": "Bullish breakout with volume confirmation...", "validated": True},
        ]
        
        for note in history:
            with st.expander(f"{note['ticker']} - {note['date']} {'✅' if note['validated'] else '⚠️'}"):
                st.markdown(f"**Summary:** {note['summary']}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔄 Regenerate", key=f"regen_{note['ticker']}"):
                        st.toast(f"Regenerating {note['ticker']}...")
                with col2:
                    if st.button("📋 Copy", key=f"copy_{note['ticker']}"):
                        st.toast("Copied!")


def render(api_get):
    # theme_toggle() is called in main.py
    render_disclaimer()