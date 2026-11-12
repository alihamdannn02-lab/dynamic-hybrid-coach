"""Sommeil & VFC — le laboratoire de récupération."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from ...sleep import sleep_hrv_effect
from .. import state, theme


def _clock_axis(fig: go.Figure) -> None:
    ticks = list(range(240, 961, 120))  # 22:00 → 10:00 (minutes depuis 18 h)
    fig.update_yaxes(tickvals=ticks, ticktext=[f"{(18 + t // 60) % 24:02d}:00" for t in ticks], autorange="reversed", title="")


def _sleep_section(a: state.Analytics) -> None:
    ss = a.sleep_summary
    frame = a.sleep.tail(28)
    if frame.empty:
        st.info("Aucune nuit enregistrée : synchronise ton historique Garmin ou fais tes check-ins.")
        return

    k = st.columns(4)
    k[0].metric("Sommeil moyen (7 n.)", f"{ss.avg_h:.1f} h", f"{ss.avg_h - ss.avg_h_28:+.1f} h vs 28 n.")
    k[1].metric("Dette de sommeil (7 j)", f"{ss.debt_h:.1f} h", f"besoin {ss.need_h:g} h / nuit", delta_color="off", delta_arrow="off")
    k[2].metric("Régularité du coucher", ss.regularity, f"± {ss.bed_sd:.0f} min" if ss.bed_sd is not None else None, delta_color="off", delta_arrow="off")
    k[3].metric("Score de sommeil (7 n.)", f"{ss.score:.0f}" if ss.score else "—")
    k = st.columns(4)
    k[0].metric("Sommeil profond", f"{ss.deep_pct:.0f} %" if ss.deep_pct else "—", "repère 13-23 %", delta_color="off", delta_arrow="off")
    k[1].metric("Sommeil paradoxal (REM)", f"{ss.rem_pct:.0f} %" if ss.rem_pct else "—", "repère 20-25 %", delta_color="off", delta_arrow="off")
    k[2].metric("Efficacité", f"{ss.efficiency:.0f} %" if ss.efficiency else "—", "repère > 85 %", delta_color="off", delta_arrow="off")
    k[3].metric("Jetlag social", f"{ss.social_jetlag:.0f} min" if ss.social_jetlag is not None else "—", "semaine vs week-end", delta_color="off", delta_arrow="off")

    for level, msg in ss.insights:
        getattr(st, level)(msg)

    tab_arch, tab_window = st.tabs(["Architecture des nuits", "Fenêtre de sommeil"])
    with tab_arch:
        fig = go.Figure()
        has_stages = frame["Deep"].notna().any()
        if has_stages:
            for col, name, color in (("Deep", "Profond", "#3B5BDB"), ("REM", "Paradoxal (REM)", "#B388FF"), ("Light", "Léger", "#5DADE2"), ("Awake", "Éveils", "#F4D03F")):
                fig.add_trace(go.Bar(x=frame["Date"], y=frame[col] / 60, name=name, marker_color=color))
            fig.update_layout(barmode="stack")
        else:
            fig.add_trace(go.Bar(x=frame["Date"], y=frame["Heures"], name="Durée", marker_color=theme.BLUE))
        fig.add_hline(y=ss.need_h, line_dash="dash", line_color=theme.GREEN, annotation_text=f"besoin {ss.need_h:g} h", annotation_position="top left")
        fig.update_yaxes(title="heures")
        st.plotly_chart(theme.style(fig, 330), config={"displayModeBar": False})
    with tab_window:
        w = frame.dropna(subset=["Bed", "Wake"])
        if w.empty:
            st.caption("Horaires de coucher/lever non disponibles (synchronise Garmin).")
        else:
            dur = (w["Wake"] - w["Bed"]) % 1440
            colors = [theme.SPORT_COLORS[4] if d.weekday() >= 5 else theme.ACCENT for d in w["Date"]]
            fig = go.Figure(go.Bar(x=w["Date"], y=dur, base=w["Bed"], marker_color=colors, name="Nuit", hovertemplate="%{x|%a %d/%m}<extra></extra>"))
            _clock_axis(fig)
            st.plotly_chart(theme.style(fig, 330, legend_top=False), config={"displayModeBar": False})
            st.caption(f"Coucher moyen **{ss.bedtime}** · lever moyen **{ss.waketime}** · violet = week-end. Des horaires réguliers stabilisent l'horloge biologique (Phillips et al. 2017).")


def _hrv_section(a: state.Analytics) -> None:
    hs = a.hrv_status
    tr = a.hrv.tail(90)
    if tr.empty:
        st.info("Aucune mesure de VFC.")
        return
    c1, c2 = st.columns([1, 2.2], vertical_alignment="center")
    with c1:
        st.markdown(theme.kpi("VFC moyenne 7 j", f"{hs.vfc7:.0f} ms" if hs.vfc7 else "—", hs.label, hs.color), unsafe_allow_html=True)
        st.write("")
        if hs.lower:
            st.caption(f"Plage normale : **{hs.lower:.0f} – {hs.upper:.0f} ms** (baseline 60 j {hs.baseline:.0f} ms)")
        if hs.cv7 is not None:
            trend = "" if hs.cv_trend is None else (" ↗ en hausse" if hs.cv_trend > 1 else " ↘ en baisse" if hs.cv_trend < -1 else " → stable")
            st.caption(f"Coefficient de variation 7 j : **{hs.cv7:.1f} %**{trend}")
        st.markdown(hs.advice)
    with c2:
        x = tr.index
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x, y=np.exp(tr["upper"]), line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=x, y=np.exp(tr["lower"]), fill="tonexty", fillcolor="rgba(88,214,141,0.13)", line=dict(width=0), name="Plage normale (±0,5 ET)"))
        fig.add_trace(go.Scatter(x=x, y=tr["VFC"], mode="markers", marker=dict(size=5, color="rgba(255,255,255,0.45)"), name="Mesure du matin"))
        fig.add_trace(go.Scatter(x=x, y=np.exp(tr["ln7"]), line=dict(color=theme.ACCENT, width=3), name="Moyenne 7 j"))
        fig.update_yaxes(title="rMSSD (ms)")
        st.plotly_chart(theme.style(fig, 340), config={"displayModeBar": False})
    st.caption("Méthode Plews/Buchheit : on suit la moyenne 7 j de ln(rMSSD) face à une plage normale personnelle (baseline 60 j ± 0,5 écart-type), plutôt qu'une mesure isolée, trop bruitée.")


def _link_section(a: state.Analytics) -> None:
    eff = sleep_hrv_effect(a.checkins)
    if eff.r is None:
        st.caption("Il faut au moins 10 nuits avec sommeil et VFC pour mesurer ton lien personnel.")
        return
    df = a.sleep.set_index("Date")[["Heures"]].join(a.hrv["VFC"], how="inner").dropna()
    slope, intercept = np.polyfit(df["Heures"], df["VFC"], 1)
    xs = np.linspace(df["Heures"].min(), df["Heures"].max(), 20)
    c1, c2 = st.columns([2.2, 1], vertical_alignment="center")
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["Heures"], y=df["VFC"], mode="markers", marker=dict(color=theme.ACCENT, size=8, opacity=0.7), name="Nuit"))
        fig.add_trace(go.Scatter(x=xs, y=slope * xs + intercept, line=dict(color=theme.AMBER, width=3), name="Tendance"))
        fig.update_xaxes(title="Durée de la nuit (h)")
        fig.update_yaxes(title="VFC au réveil (ms)")
        st.plotly_chart(theme.style(fig, 320, legend_top=False), config={"displayModeBar": False})
    with c2:
        st.markdown(theme.kpi("Ton effet sommeil", f"{slope:+.1f} ms", "de VFC par heure de sommeil en plus", theme.AMBER), unsafe_allow_html=True)
        st.write("")
        st.caption(f"Corrélation r = {eff.r:.2f} sur {eff.n} nuits.")
        if eff.short_ms and eff.long_ms:
            st.caption(
                f"Après une nuit < {eff.threshold:g} h : **{eff.short_ms:.0f} ms**, contre **{eff.long_ms:.0f} ms** après une nuit plus longue ({(eff.short_ms / eff.long_ms - 1) * 100:+.0f} %)."
            )
        st.caption("Corrélation ≠ causalité : la charge de la veille joue aussi. Le modèle de l'onglet 🔮 Prédictions isole chaque effet.")


def render() -> None:
    st.title("😴 Sommeil & VFC")
    st.markdown(
        "<p class='hero'>Besoin de sommeil réglable dans ton profil (barre latérale). La récupération se joue la nuit : quantité, régularité, architecture du sommeil et réponse de ton système nerveux autonome.</p>",
        unsafe_allow_html=True,
    )
    a = state.analytics()
    st.subheader("Sommeil")
    _sleep_section(a)
    st.divider()
    st.subheader("Variabilité de la fréquence cardiaque")
    _hrv_section(a)
    st.divider()
    st.subheader("Ton lien personnel sommeil → VFC")
    _link_section(a)
