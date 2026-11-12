"""Prédictions — VFC de demain, forme le jour de course, temps de course."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ...forecast import FEATURE_LABELS, best_scenario, fmt_time, race_predictions, race_scenarios, today_state
from ...garmin import GarminError
from .. import state, theme


def _hrv_forecast(a: state.Analytics) -> None:
    m = a.hrv_model
    st.subheader("🔮 Ta VFC demain matin")
    if not m.ready:
        st.info(f"Le modèle personnel s'entraîne dès 28 jours de données couplées charge + VFC + sommeil ({m.n}/28). Synchronise ton historique Garmin pour l'activer immédiatement.")
        return
    ts = today_state(a.daily, a.checkins)
    if ts is None:
        st.info("Check-in du jour manquant.")
        return
    hs = a.hrv_status
    avg_load = float(a.daily.tail(28).mean())

    c1, c2 = st.columns([1, 1.5], vertical_alignment="center")
    with c1:
        st.markdown("**Et si…** règle ta journée, le modèle anticipe ta récupération.")
        load = st.slider("Charge prévue aujourd'hui (TSS)", 0, 250, int(round(max(ts.charge_jour, avg_load) / 5) * 5), step=5, help="Repère : 1 h d'endurance Z2 ≈ 50 TSS, 1 h au seuil ≈ 100 TSS.")
        sleep = st.slider("Sommeil cette nuit (h)", 4.0, 10.0, 8.0, 0.25)
        tsb = ts.tsb_tomorrow(load)
        pred = float(np.exp(ts.base_ln + m.predict_dev(load, tsb, sleep, ts.etat_j)))
        band = float(np.exp(ts.base_ln + (m.resid_sd or 0))) - float(np.exp(ts.base_ln))
        if hs.lower and pred < hs.lower:
            color, msg = theme.RED, "sous ta plage normale"
        elif hs.upper and pred > hs.upper:
            color, msg = theme.BLUE, "au-dessus de ta plage normale"
        else:
            color, msg = theme.GREEN, "dans ta plage normale"
        st.markdown(theme.kpi("VFC prédite demain", f"{pred:.0f} ms", f"± {band:.0f} ms · {msg} · aujourd'hui {ts.vfc_jour:.0f} ms", color), unsafe_allow_html=True)
    with c2:
        sleeps = np.linspace(5, 10, 21)
        fig = go.Figure()
        for lv, col in ((0, theme.GREEN), (avg_load, theme.AMBER), (min(250, avg_load * 2.2), theme.RED)):
            t = ts.tsb_tomorrow(lv)
            ys = [np.exp(ts.base_ln + m.predict_dev(lv, t, s, ts.etat_j)) for s in sleeps]
            fig.add_trace(go.Scatter(x=sleeps, y=ys, name=f"{lv:.0f} TSS", line=dict(color=col, width=3)))
        if hs.lower:
            fig.add_hrect(y0=hs.lower, y1=hs.upper, fillcolor=theme.GREEN, opacity=0.08, line_width=0, annotation_text="plage normale", annotation_position="top left")
        fig.add_trace(go.Scatter(x=[sleep], y=[pred], mode="markers", marker=dict(size=14, color="white", line=dict(color=color, width=3)), name="Ton scénario"))
        fig.update_xaxes(title="Sommeil cette nuit (h)")
        fig.update_yaxes(title="VFC prédite (ms)")
        st.plotly_chart(theme.style(fig, 330), config={"displayModeBar": False})

    with st.expander("🧪 Comment le modèle est construit et évalué", expanded=False):
        g = m.gain_pct
        k = st.columns(3)
        k[0].metric("Erreur moyenne du modèle", f"{m.mae_model:.1f} ms")
        k[1].metric("Erreur « demain = aujourd'hui »", f"{m.mae_naive:.1f} ms")
        k[2].metric("Gain vs référence naïve", f"{g:+.0f} %" if g is not None else "—")
        bt = m.backtest
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=bt.index, y=bt["Réel"], name="VFC réelle", line=dict(color="white", width=2)))
        fig.add_trace(go.Scatter(x=bt.index, y=bt["Modèle"], name="Prédiction du modèle", line=dict(color=theme.ACCENT, width=3)))
        fig.add_trace(go.Scatter(x=bt.index, y=bt["Naïf"], name="Référence naïve", line=dict(color=theme.MUTED, width=1.5, dash="dot")))
        st.plotly_chart(theme.style(fig, 300), config={"displayModeBar": False})
        eff = pd.DataFrame({"Effet": [m.effect_pct(f) for f in m.coef], "Variable": [FEATURE_LABELS[f] for f in m.coef]})
        fig = go.Figure(
            go.Bar(
                x=eff["Effet"],
                y=eff["Variable"],
                orientation="h",
                marker_color=[theme.GREEN if v > 0 else theme.RED for v in eff["Effet"]],
                text=[f"{v:+.1f} %" for v in eff["Effet"]],
                textposition="outside",
            )
        )
        fig.update_xaxes(title="effet sur la VFC du lendemain (%)")
        st.plotly_chart(theme.style(fig, 240, legend_top=False), config={"displayModeBar": False})
        st.markdown(
            f"""
- **Modèle** : régression ridge (λ = 1) sur variables standardisées, entraînée sur **{m.n} jours** de ton historique.
- **Cible** : écart de ln(rMSSD) du lendemain à ta baseline 60 j (ce qui neutralise ton niveau propre).
- **Variables** : charge du jour, fraîcheur (TSB de Banister), durée de la nuit, état VFC du jour.
- **Évaluation walk-forward** : chaque jour des 30 derniers est prédit avec un modèle entraîné **uniquement sur les jours précédents**, aucune fuite d'information du futur. On compare à la prévision naïve « demain = aujourd'hui ».
- **Limites** : modèle linéaire et individuel, non causal ; il apprend tes régularités, il ne connaît pas l'alcool, le stress pro ou une maladie qui démarre.
"""
        )


def _race_planner(a: state.Analytics) -> None:
    st.subheader("🏁 Planificateur de forme pour ta course")
    if len(a.pmc) < 14:
        st.info("Il faut au moins 2 semaines d'historique de charge.")
        return
    c1, c2 = st.columns([1, 2.2])
    with c1:
        race = st.date_input("Date de la course", value=date.today() + timedelta(days=28), min_value=date.today() + timedelta(days=3), format="DD/MM/YYYY")
        target = st.select_slider("Fraîcheur visée le jour J (TSB)", options=list(range(-10, 31, 5)), value=(5, 25))
    sc = race_scenarios(a.pmc, pd.Timestamp(race))
    best = best_scenario(sc, target)
    colors = {"Maintien": theme.MUTED, "Progression +8 %/sem.": theme.ORANGE, "Affûtage 10 j": theme.GREEN}
    with c2:
        fig = go.Figure()
        hist = a.pmc.tail(42)
        fig.add_trace(go.Scatter(x=hist.index, y=hist["TSB"], name="TSB réalisé", line=dict(color="white", width=2)))
        for name, df in sc.items():
            fig.add_trace(go.Scatter(x=df.index, y=df["TSB"], name=name, line=dict(color=colors[name], width=4 if name == best else 2, dash=None if name == best else "dot")))
        fig.add_hrect(y0=target[0], y1=target[1], fillcolor=theme.GREEN, opacity=0.08, line_width=0, annotation_text="zone de fraîcheur visée", annotation_position="top left")
        fig.add_vline(x=pd.Timestamp(race), line_color=theme.ACCENT, line_dash="dash")
        fig.update_yaxes(title="Forme (TSB)")
        st.plotly_chart(theme.style(fig, 340), config={"displayModeBar": False})
    rows = [
        {
            "Scénario": ("⭐ " if n == best else "") + n,
            "Charge moy. (TSS/j)": round(df["TSS"].mean()),
            "Fitness CTL jour J": round(df["CTL"].iloc[-1], 1),
            "Fraîcheur TSB jour J": round(df["TSB"].iloc[-1], 1),
        }
        for n, df in sc.items()
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    b = sc[best].iloc[-1]
    st.success(f"Recommandation : **{best}**. Tu arrives le {race:%d/%m} avec une fitness de **{b.CTL:.0f}** et une fraîcheur de **{b.TSB:+.0f}**.")
    st.caption("Projection du modèle impulsion-réponse de Banister. L'affûtage réduit le volume de 55 % sur 10 jours en conservant l'intensité (Bosquet et al. 2007).")


def _race_times(a: state.Analytics) -> None:
    st.subheader("⏱️ Tes temps de course estimés")
    rp = race_predictions(a.realise)
    garmin = state.garmin()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Modèle de Riegel** (à partir de ta meilleure sortie des 90 derniers jours)")
        if rp is None:
            st.caption("Aucune sortie de course ≥ 3 km récente.")
        else:
            src = rp["source"]
            for name, minutes in rp["predictions"].items():
                dist = {"5 km": 5, "10 km": 10, "Semi-marathon": 21.0975, "Marathon": 42.195}[name]
                pace = minutes / dist
                st.markdown(f"- **{name}** : {fmt_time(minutes)}  <span style='color:#8B949E'>({int(pace)}:{int(pace % 1 * 60):02d} /km)</span>", unsafe_allow_html=True)
            st.caption(
                f"Base : {src['Type_Seance']} du {src['Date']:%d/%m} ({src['Distance_Km']:.1f} km en {fmt_time(src['Duree_Min'])}). T₂ = T₁ × (D₂/D₁)^1,06. Le marathon est souvent surestimé sans sorties longues spécifiques."
            )
    with c2:
        st.markdown("**Prédicteur Garmin** (basé sur ta VO2max)")
        if not garmin.connected:
            st.caption("Connecte ta montre dans l'onglet ⌚ Garmin pour comparer.")
        elif st.button("Récupérer les prédictions Garmin"):
            try:
                st.session_state["garmin_race"] = garmin.fetch_race_predictions()
            except GarminError as exc:
                st.error(str(exc))
        preds = st.session_state.get("garmin_race")
        if preds:
            for name, minutes in preds.items():
                delta = ""
                if rp and name in rp["predictions"]:
                    delta = f"  <span style='color:#8B949E'>({minutes - rp['predictions'][name]:+.1f} min vs Riegel)</span>"
                st.markdown(f"- **{name}** : {fmt_time(minutes)}{delta}", unsafe_allow_html=True)
        elif preds == {}:
            st.caption("Pas de prédiction disponible sur ce modèle de montre.")


def render() -> None:
    st.title("🔮 Prédictions")
    st.markdown("<p class='hero'>Anticiper plutôt que constater : ta récupération de demain, ta forme le jour J, ton potentiel en course.</p>", unsafe_allow_html=True)
    a = state.analytics()
    _hrv_forecast(a)
    st.divider()
    _race_planner(a)
    st.divider()
    _race_times(a)
