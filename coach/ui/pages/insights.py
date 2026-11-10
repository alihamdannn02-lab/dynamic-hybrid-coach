"""Page 3 — Cockpit Performance : readiness, charge, Banister, ACWR, PPG, zones."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ... import schema
from ...readiness import readiness_from_history
from ...training_load import acwr_status, daily_load, performance_manager, sessions_from_history, tsb_label
from .. import state, theme

COMP_LABELS = {"sommeil": "Sommeil", "energie": "Énergie", "fcr": "FC repos", "vfc": "VFC"}


def _readiness_card(checkins: pd.DataFrame) -> None:
    r = readiness_from_history(checkins)
    if r is None:
        st.info("Aucun check-in pour le moment : commence par **Morning Readiness**.")
        return
    last_date = checkins["Date"].max().strftime("%d/%m")
    with st.container(border=True):
        g, t = st.columns([1, 1.2], vertical_alignment="center")
        g.plotly_chart(theme.gauge(r.score, f"Readiness · {last_date}"), config={"displayModeBar": False})
        with t:
            st.markdown(r.advice)
            for key, label in COMP_LABELS.items():
                v = r.components[key]
                st.progress(int(v), text=f"{label} — {v:.0f}/100")
            st.caption("Baseline personnelle" if r.baseline.personal else "Normes de référence (baseline en construction)")


def _recovery_trends(checkins: pd.DataFrame) -> None:
    if len(checkins) < 3:
        return
    df = checkins.sort_values("Date").tail(60).copy()
    df["VFC_7j"] = df["VFC"].rolling(7, min_periods=3).mean()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Date"], y=df["VFC"], name="VFC (ms)", marker_color="rgba(0,209,255,0.35)"))
    fig.add_trace(go.Scatter(x=df["Date"], y=df["VFC_7j"], name="VFC moyenne 7 j", line=dict(color=theme.ACCENT, width=3)))
    fig.add_trace(go.Scatter(x=df["Date"], y=df["FC_Repos"], name="FC repos (bpm)", yaxis="y2", line=dict(color=theme.RED, width=2, dash="dot")))
    fig.update_layout(yaxis=dict(title="VFC (ms)"), yaxis2=dict(title="FCR (bpm)", overlaying="y", side="right", showgrid=False))
    st.plotly_chart(theme.style(fig, 300))


def render() -> None:
    st.title("📊 Cockpit Performance")
    realise = state.load(schema.REALISE)
    checkins = state.load(schema.CHECKIN)

    _readiness_card(checkins)

    if realise.empty:
        st.info("Aucune séance enregistrée pour le moment.")
        return

    sessions = sessions_from_history(realise)
    daily = daily_load(sessions)
    pmc = performance_manager(daily)
    load = acwr_status(daily)

    today = pd.Timestamp.today().normalize()
    week_start = today - pd.Timedelta(days=today.weekday())
    this_week = sessions[(sessions["Date"] >= week_start) & (sessions["Sport_Discipline"] != "Repos")]
    prev_week = sessions[(sessions["Date"] >= week_start - pd.Timedelta(days=7)) & (sessions["Date"] < week_start) & (sessions["Sport_Discipline"] != "Repos")]

    st.subheader("📌 Cette semaine")
    k = st.columns(5)
    vol, vol_prev = this_week["Duree"].sum() / 60, prev_week["Duree"].sum() / 60
    k[0].metric("Séances", len(this_week), len(this_week) - len(prev_week))
    k[1].metric("Volume", f"{vol:.1f} h", f"{vol - vol_prev:+.1f} h")
    k[2].metric("Distance", f"{this_week['Distance'].sum():.0f} km")
    k[3].metric("D+", f"{int(this_week['Denivele'].sum())} m")
    k[4].metric("Charge", f"{this_week['TSS'].sum():.0f} TSS", f"{this_week['TSS'].sum() - prev_week['TSS'].sum():+.0f}")

    tab_load, tab_sport, tab_ppg, tab_zones, tab_recov = st.tabs(["🧬 Forme & charge", "🏊🚴🏃 Disciplines", "🏋️ PPG", "❤️ Intensité", "💤 Récupération"])

    with tab_load:
        if len(pmc) < 7:
            st.info("Le modèle de Banister s'active après une semaine d'historique.")
        else:
            last = pmc.iloc[-1]
            c = st.columns(4)
            c[0].metric("Fitness (CTL)", f"{last.CTL:.0f}", f"{last.CTL - pmc.CTL.iloc[-8]:+.1f} / 7 j")
            c[1].metric("Fatigue (ATL)", f"{last.ATL:.0f}")
            c[2].metric("Forme (TSB)", f"{last.TSB:+.0f}", tsb_label(last.TSB), delta_color="off")
            c[3].metric("ACWR", f"{load.acwr:.2f}" if load.acwr else "—", load.label, delta_color="off")

            view = pmc.tail(120)
            fig = go.Figure()
            fig.add_trace(go.Bar(x=view.index, y=view.TSS, name="TSS du jour", marker_color="rgba(255,255,255,0.12)", yaxis="y"))
            fig.add_trace(go.Scatter(x=view.index, y=view.CTL, name="Fitness (CTL)", line=dict(color=theme.ACCENT, width=3), fill="tozeroy", fillcolor="rgba(0,209,255,0.10)"))
            fig.add_trace(go.Scatter(x=view.index, y=view.ATL, name="Fatigue (ATL)", line=dict(color=theme.RED, width=2, dash="dot")))
            fig.add_trace(go.Scatter(x=view.index, y=view.TSB, name="Forme (TSB)", line=dict(color=theme.AMBER, width=2.5), yaxis="y2"))
            for y0, y1, color in [(-10, 10, "#58D68D"), (-30, -10, "#E67E22"), (-80, -30, "#E74C3C")]:
                fig.add_hrect(y0=y0, y1=y1, fillcolor=color, opacity=0.06, line_width=0, yref="y2")
            fig.update_layout(
                yaxis=dict(title="Charge"), yaxis2=dict(title="TSB", overlaying="y", side="right", showgrid=False, tickformat=".0f", zeroline=True, zerolinecolor="rgba(255,255,255,0.2)")
            )
            st.plotly_chart(theme.style(fig, 380))
            st.markdown(
                theme.pill("TSB > 10 : frais", theme.GREEN) + theme.pill("-10 à -30 : surcharge productive", theme.ORANGE) + theme.pill("< -30 : risque", theme.RED),
                unsafe_allow_html=True,
            )
            with st.container(border=True):
                st.markdown(f"**Ratio charge aiguë / chronique :** <span style='color:{load.color}'>{load.label}</span>", unsafe_allow_html=True)
                st.caption(load.advice)
                if load.monotony:
                    mono = "élevée ⚠️ — varie les intensités" if load.monotony > 2 else "correcte"
                    st.caption(f"Monotonie de Foster (7 j) : {load.monotony:.2f} ({mono})")
            st.caption("TSS estimé via sRPE (durée × RPE) — CTL 42 j, ATL 7 j, moyennes exponentielles journalières.")

    with tab_sport:
        last4 = sessions[(sessions["Date"] >= today - pd.Timedelta(days=27)) & (sessions["Sport_Discipline"] != "Repos")].copy()
        if last4.empty:
            st.caption("Aucun volume sur les 4 dernières semaines.")
        else:
            last4["Semaine_ISO"] = last4["Date"].dt.to_period("W-SUN").dt.start_time
            agg = last4.groupby(["Semaine_ISO", "Sport_Discipline"])["Duree"].sum().reset_index()
            agg["Heures"] = agg["Duree"] / 60
            fig = px.bar(agg, x="Semaine_ISO", y="Heures", color="Sport_Discipline", color_discrete_sequence=theme.SPORT_COLORS, labels={"Semaine_ISO": "Semaine", "Sport_Discipline": ""})
            fig.update_xaxes(tickformat="%d %b")
            st.plotly_chart(theme.style(fig, 340))
            tot = (
                last4.groupby("Sport_Discipline")
                .agg(Heures=("Duree", lambda x: round(x.sum() / 60, 1)), Séances=("Duree", "size"), Km=("Distance", "sum"), TSS=("TSS", "sum"))
                .sort_values("Heures", ascending=False)
            )
            st.dataframe(tot.round(0), width="stretch")

    with tab_ppg:
        ppg = realise[realise["Poids_Reel_Kg"] > 0].copy()
        if ppg.empty:
            st.caption("Aucune série de musculation enregistrée.")
        else:
            ppg["Mouvement"] = ppg["Exercice"].astype(str).str.split(" (Série", regex=False).str[0]
            # 1RM estimé (Epley) en tenant compte des répétitions en réserve
            ppg["e1RM"] = ppg["Poids_Reel_Kg"] * (1 + (ppg["Reps_Reelles"].fillna(0) + ppg["RIR"].fillna(0)) / 30)
            ppg["Tonnage"] = ppg["Poids_Reel_Kg"] * ppg["Reps_Reelles"].fillna(0)
            mvt = st.selectbox("Mouvement", sorted(ppg["Mouvement"].unique()))
            d = ppg[ppg["Mouvement"] == mvt].groupby("Date").agg(e1RM=("e1RM", "max"), Charge=("Poids_Reel_Kg", "max"), Tonnage=("Tonnage", "sum")).reset_index()
            fig = go.Figure()
            fig.add_trace(go.Bar(x=d["Date"], y=d["Tonnage"], name="Tonnage (kg)", marker_color="rgba(255,255,255,0.12)", yaxis="y2"))
            fig.add_trace(go.Scatter(x=d["Date"], y=d["e1RM"], name="1RM estimé", mode="lines+markers", line=dict(color=theme.RED, width=3, shape="spline")))
            fig.add_trace(go.Scatter(x=d["Date"], y=d["Charge"], name="Charge max", mode="lines+markers", line=dict(color=theme.ACCENT, width=2, dash="dot")))
            fig.update_layout(yaxis=dict(title="kg"), yaxis2=dict(overlaying="y", side="right", showgrid=False, title="Tonnage"))
            st.plotly_chart(theme.style(fig, 340))
            if len(d) >= 2:
                gain = d["e1RM"].iloc[-1] - d["e1RM"].iloc[0]
                st.caption(f"Progression du 1RM estimé : **{gain:+.1f} kg** sur {len(d)} séances (formule d'Epley + RIR).")

    with tab_zones:
        zcols = ["Z1_Min", "Z2_Min", "Z3_Min", "Z4_Min", "Z5_Min"]
        recent = realise[realise["Date"] >= today - pd.Timedelta(days=27)]
        totals = recent[zcols].fillna(0).sum()
        if totals.sum() <= 0:
            st.caption("Aucune donnée de zone cardiaque sur 4 semaines.")
        else:
            labels = ["Z1 Récup", "Z2 Endurance", "Z3 Tempo", "Z4 Seuil", "Z5 VO2max"]
            colors = [theme.BLUE, theme.GREEN, theme.AMBER, theme.ORANGE, theme.RED]
            c1, c2 = st.columns([1.2, 1], vertical_alignment="center")
            fig = go.Figure(go.Pie(labels=labels, values=totals.values, hole=0.62, marker=dict(colors=colors, line=dict(color="#0E1117", width=2)), sort=False, textinfo="percent"))
            fig.update_layout(annotations=[dict(text="4 sem.", x=0.5, y=0.5, showarrow=False, font_size=15)])
            c1.plotly_chart(theme.style(fig, 300, legend_top=False))
            low, mid, high = totals.iloc[:2].sum(), totals.iloc[2], totals.iloc[3:].sum()
            tot = totals.sum()
            with c2:
                st.markdown("**Distribution d'intensité**")
                st.markdown(f"- Basse (Z1-Z2) : **{low / tot:.0%}**\n- Modérée (Z3) : **{mid / tot:.0%}**\n- Haute (Z4-Z5) : **{high / tot:.0%}**")
                if low / tot >= 0.75 and mid / tot <= 0.10:
                    st.success("Modèle **polarisé** (≈ 80/20) — la référence chez les athlètes d'endurance.")
                elif mid / tot > 0.20:
                    st.warning("Beaucoup de Z3 (« zone grise ») : facilite tes séances faciles, durcis les dures.")
                else:
                    st.info("Modèle **pyramidal** : volume bas dominant, peu de haute intensité.")

    with tab_recov:
        if len(checkins) < 3:
            st.caption("Il faut au moins 3 check-ins pour afficher les tendances.")
        else:
            _recovery_trends(checkins)
            c = checkins.sort_values("Date").tail(7)
            k = st.columns(3)
            k[0].metric("Sommeil moyen (7 j)", f"{c['Heures_Sommeil'].mean():.1f} h")
            k[1].metric("VFC moyenne (7 j)", f"{c['VFC'].mean():.0f} ms")
            k[2].metric("FCR moyenne (7 j)", f"{c['FC_Repos'].mean():.0f} bpm")
