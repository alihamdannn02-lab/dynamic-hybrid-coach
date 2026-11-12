"""Accueil — tableau de bord du jour : tous les signaux réunis en une décision."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ...training_load import tsb_label
from .. import state, theme

STEPS = [
    ("⌚", "Collecte", "Garmin : sommeil, VFC, FC repos, activités"),
    ("🧬", "Modèles", "Banister, ACWR, VFC (Plews), sommeil"),
    ("🛡️", "Risque", "Indice multifactoriel explicable"),
    ("🔮", "Prédiction", "ML personnel validé en walk-forward"),
    ("🧠", "Coach IA", "Séance adaptée générée par Gemini"),
]


def decision(a: state.Analytics) -> tuple[str, str, list[str]]:
    """Synthèse des signaux → (titre, couleur, raisons)."""
    r = a.readiness.score if a.readiness else None
    risk = a.risk.score
    tsb = float(a.pmc["TSB"].iloc[-1]) if not a.pmc.empty else 0.0
    hs = a.hrv_status
    reasons = []
    if r is not None:
        reasons.append(f"Readiness {r} %")
    reasons.append(f"Risque de blessure {risk}/100 ({a.risk.level.lower()})")
    reasons.append(f"Forme TSB {tsb:+.0f} ({tsb_label(tsb).lower()})")
    if hs.status != "insuffisant":
        reasons.append(f"VFC 7 j {hs.label.lower()}")
    if a.sleep_summary.avg_h:
        reasons.append(f"Sommeil {a.sleep_summary.avg_h:.1f} h / nuit")

    if risk >= 50 or (r is not None and r < 50) or hs.status == "basse":
        return "Récupération active aujourd'hui", theme.RED, reasons
    if (r is None or r >= 75) and risk < 25 and tsb > -25:
        return "Feu vert pour une séance de qualité", theme.GREEN, reasons
    return "Endurance fondamentale (Z2), sans intensité", theme.AMBER, reasons


def _overview_chart(a: state.Analytics) -> go.Figure:
    end = pd.Timestamp.today().normalize()
    start = end - pd.Timedelta(days=55)
    fig = go.Figure()
    load = a.daily[a.daily.index >= start]
    fig.add_trace(go.Bar(x=load.index, y=load.values, name="Charge (TSS)", marker_color="rgba(255,255,255,0.14)"))
    if not a.hrv.empty:
        h = a.hrv[a.hrv.index >= start]
        fig.add_trace(go.Scatter(x=h.index, y=np.exp(h["ln7"]), name="VFC 7 j (ms)", yaxis="y2", line=dict(color=theme.ACCENT, width=3)))
    risk = a.risk.timeline
    if not risk.empty:
        rk = risk[risk.index >= start]["score"]
        fig.add_trace(go.Scatter(x=rk.index, y=rk.values, name="Risque de blessure", yaxis="y3", line=dict(color=theme.RED, width=2, dash="dot")))
    fig.update_layout(
        yaxis=dict(title="TSS", showgrid=False),
        yaxis2=dict(title="VFC (ms)", overlaying="y", side="right", showgrid=False, tickformat=".0f"),
        yaxis3=dict(overlaying="y", side="right", range=[0, 100], visible=False),
    )
    return theme.style(fig, 300)


def render() -> None:
    st.markdown(
        "<div class='banner'><h1>⚡ Dynamic Hybrid Coach</h1>"
        "<p>De la montre à la décision du jour : modèles de charge, VFC, sommeil, risque de blessure et prédictions personnelles.</p>"
        "<div style='margin-top:12px'>"
        + theme.pill("Garmin Connect", theme.ACCENT)
        + theme.pill("Sciences du sport", theme.GREEN)
        + theme.pill("Machine learning personnel", theme.AMBER)
        + theme.pill("IA générative", "#B388FF")
        + "</div></div>",
        unsafe_allow_html=True,
    )
    if state.is_demo():
        st.info(
            "👋 Tu explores un **athlète simulé** (12 semaines, dont un stage de surcharge). Connecte **ta** montre dans l'onglet ⌚ Garmin pour analyser tes propres données : elles restent dans ta session."
        )

    a = state.analytics()
    if a.realise.empty and a.checkins.empty:
        st.warning("Aucune donnée pour l'instant : fais ton premier check-in ou synchronise ton historique Garmin.")
        st.page_link(st.session_state["_pages"]["garmin"], label="Synchroniser Garmin", icon="⌚")
        return

    title, color, reasons = decision(a)
    st.markdown(
        f"<div class='kpi' style='border-color:{color}66'><div class='t'>Décision du jour</div>"
        f"<div class='v' style='color:{color}; font-size:1.6rem'>{title}</div>"
        f"<div class='s'>{' · '.join(reasons)}</div></div>",
        unsafe_allow_html=True,
    )
    st.write("")

    r = a.readiness
    hs = a.hrv_status
    ss = a.sleep_summary
    tsb = float(a.pmc["TSB"].iloc[-1]) if not a.pmc.empty else 0.0
    cards = [
        theme.kpi(
            "Readiness",
            f"{r.score}%" if r else "—",
            "vs ta baseline perso" if r and r.baseline.personal else "normes de référence",
            {"green": theme.GREEN, "amber": theme.AMBER, "red": theme.RED}[r.status] if r else theme.MUTED,
        ),
        theme.kpi("Risque de blessure", f"{a.risk.score}", f"{a.risk.level} · {a.risk.drivers[0].name if a.risk.drivers else 'aucun facteur actif'}", a.risk.color),
        theme.kpi("Forme (TSB)", f"{tsb:+.0f}", tsb_label(tsb), theme.GREEN if tsb > -10 else theme.ORANGE if tsb > -30 else theme.RED),
        theme.kpi("VFC 7 jours", f"{hs.vfc7:.0f} ms" if hs.vfc7 else "—", hs.label, hs.color),
        theme.kpi(
            "Sommeil 7 nuits",
            f"{ss.avg_h:.1f} h" if ss.avg_h else "—",
            f"dette {ss.debt_h:.1f} h" if ss.debt_h is not None else "",
            theme.GREEN if (ss.avg_h or 0) >= 7.5 else theme.AMBER if (ss.avg_h or 0) >= 7 else theme.RED,
        ),
    ]
    for col, html in zip(st.columns(5), cards):
        col.markdown(html, unsafe_allow_html=True)

    st.subheader("8 dernières semaines en un coup d'œil")
    st.plotly_chart(_overview_chart(a), config={"displayModeBar": False})
    st.caption("Barres : charge quotidienne · Ligne bleue : VFC moyenne 7 j · Pointillés rouges : indice de risque. On voit la VFC chuter et le risque monter quand la charge s'emballe.")

    st.subheader("Comment ça marche")
    for col, (icon, name, desc) in zip(st.columns(len(STEPS)), STEPS):
        col.markdown(f"<div class='step'><div class='i'>{icon}</div><div class='n'>{name}</div><div class='d'>{desc}</div></div>", unsafe_allow_html=True)

    st.subheader("Explorer")
    pages = st.session_state["_pages"]
    c = st.columns(4)
    c[0].page_link(pages["sleep"], label="Sommeil & VFC", icon="😴")
    c[1].page_link(pages["risk"], label="Risque de blessure", icon="🛡️")
    c[2].page_link(pages["predict"], label="Prédictions", icon="🔮")
    c[3].page_link(pages["method"], label="Méthodologie & sources", icon="📚")
