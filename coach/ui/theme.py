"""Identité visuelle : CSS global et gabarit Plotly commun."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

ACCENT = "#00D1FF"
GREEN = "#58D68D"
AMBER = "#F4D03F"
ORANGE = "#E67E22"
RED = "#E74C3C"
BLUE = "#5DADE2"
MUTED = "#8B949E"
SPORT_COLORS = ["#00D1FF", "#FF6B6B", "#58D68D", "#F4D03F", "#B388FF", "#FF9F43", "#8B949E"]

CSS = """
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 2rem; max-width: 1100px;}
div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    padding: 12px 16px; border-radius: 12px;
}
div[data-testid="stMetricLabel"] p {color: #8B949E; font-size: 0.8rem;}
.zone-title {text-align:center; font-weight:700; margin-bottom:0;}
.zone-sub {font-size:0.75em; color:#8B949E; text-align:center; display:block; margin-bottom:6px;}
.pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.75rem; font-weight:600;
       border:1px solid rgba(255,255,255,0.15); margin-right:6px;}
.hero {font-size: 0.95rem; color:#8B949E; margin-top:-0.6rem;}
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def pill(text: str, color: str = ACCENT) -> str:
    return f"<span class='pill' style='color:{color}; border-color:{color}55'>{text}</span>"


def style(fig: go.Figure, height: int = 340, legend_top: bool = True) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=0, r=0, t=30, b=0),
        hovermode="x unified",
        font=dict(family="Inter, system-ui, sans-serif"),
    )
    if legend_top:
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)")
    return fig


def gauge(score: int, title: str = "Readiness") -> go.Figure:
    color = GREEN if score >= 75 else AMBER if score >= 50 else RED
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "%", "font": {"size": 46}},
            title={"text": title, "font": {"size": 16, "color": MUTED}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 0, "tickcolor": "rgba(0,0,0,0)"},
                "bar": {"color": color, "thickness": 0.28},
                "bgcolor": "rgba(255,255,255,0.04)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 50], "color": "rgba(231,76,60,0.12)"},
                    {"range": [50, 75], "color": "rgba(244,208,63,0.12)"},
                    {"range": [75, 100], "color": "rgba(88,214,141,0.12)"},
                ],
            },
        )
    )
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(t=40, b=0, l=20, r=20))
    return fig
