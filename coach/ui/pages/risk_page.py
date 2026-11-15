"""Risque de blessure — indice multifactoriel, explicable et historisé."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from .. import state, theme

FACTOR_STYLE = {
    "acwr": ("Pic de charge (ACWR)", "#E74C3C"),
    "monotonie": ("Monotonie", "#E67E22"),
    "vfc": ("VFC basse", "#00D1FF"),
    "fcr": ("FC repos élevée", "#FF6B9D"),
    "sommeil": ("Manque de sommeil", "#B388FF"),
    "douleur": ("Douleurs", "#F4D03F"),
}

METHOD = """
| Facteur | Points max | Déclenchement | Référence |
|---|---|---|---|
| ACWR (EWMA 7 j / 28 j) | 30 | > 1,3 : 18 pts · > 1,5 : 30 pts · < 0,8 : 6 pts | Gabbett 2016 ; Williams et al. 2017 |
| Monotonie de Foster | 12 | moyenne / écart-type de la charge 7 j > 2 | Foster 1998 |
| VFC | 20 | moyenne 7 j de ln rMSSD sous baseline − 0,5 ET | Plews et al. 2013 |
| FC de repos | 15 | moyenne 7 j ≥ baseline + 3 bpm (8 pts) / + 5 bpm (15 pts) | Buchheit 2014 |
| Sommeil | 15 | moyenne 7 j < 7 h (8 pts) / < 6,5 h (15 pts) | Milewski et al. 2014 |
| Douleurs | 20 | douleur ≤ 3 j (8 pts) · même zone ≥ 3 j sur 7 (20 pts) | Clarsen et al. 2013 |

Score = somme des points, plafonnée à 100 : **< 25 faible · 25-49 modéré · ≥ 50 élevé**.

**Limites assumées.** L'ACWR fait débat : couplage mathématique entre charges aiguë et
chronique, causalité non démontrée (Impellizzeri et al. 2020). Les seuils sont issus de
populations différentes (sports collectifs, coureurs). Cet indice est une **aide à la
décision heuristique** : il dit *quand regarder de plus près*, pas *qui va se blesser*.
Un modèle prédictif validé exigerait un historique de blessures réelles, ce que
l'application pourra apprendre à terme en enregistrant les blessures déclarées.
"""


def render() -> None:
    st.title("🛡️ Risque de blessure")
    st.markdown("<p class='hero'>Six signaux issus de la littérature, combinés en un indice où chaque point est traçable jusqu'à sa cause.</p>", unsafe_allow_html=True)
    a = state.analytics()
    rep = a.risk
    if rep.timeline.empty:
        st.info("Pas encore assez de données : enregistre tes séances et check-ins, ou synchronise Garmin.")
        return

    c1, c2 = st.columns([1, 1.4], vertical_alignment="center")
    with c1:
        fig = theme.gauge(rep.score, "Indice de risque")
        fig.update_traces(number={"suffix": "/100", "font": {"size": 40}}, gauge={"bar": {"color": rep.color}})
        st.plotly_chart(fig, config={"displayModeBar": False})
    with c2:
        st.markdown(f"### Niveau <span style='color:{rep.color}'>{rep.level.lower()}</span>", unsafe_allow_html=True)
        if rep.drivers:
            st.markdown("**Ce qui fait monter ton risque aujourd'hui :**")
            for f in rep.drivers:
                st.markdown(f"- **{f.name}** (+{f.points:.0f}) : {f.value}. {f.action}")
        else:
            st.success("Aucun facteur de risque actif : charge, récupération et sommeil sont alignés.")
        for note in rep.coverage:
            st.caption(f"ℹ️ {note}")

    st.subheader("Détail des facteurs")
    for f in rep.factors:
        label, color = FACTOR_STYLE[f.key]
        with st.container(border=True):
            left, mid, right = st.columns([1.3, 1, 2.2], vertical_alignment="center")
            left.markdown(f"**{f.name}**  \n<span style='color:#8B949E'>{f.value}</span>", unsafe_allow_html=True)
            mid.progress(min(1.0, f.points / f.max_points), text=f"{f.points:.0f} / {f.max_points:.0f} pts")
            right.caption(f.why)

    st.subheader("Historique : d'où vient le risque, jour après jour")
    tl = rep.timeline.tail(90)
    fig = go.Figure()
    for key, (label, color) in FACTOR_STYLE.items():
        fig.add_trace(go.Scatter(x=tl.index, y=tl[key], name=label, stackgroup="risk", mode="none", fillcolor=color + "B3"))
    for y0, y1, c in [(25, 50, theme.ORANGE), (50, 100, theme.RED)]:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=c, opacity=0.05, line_width=0)
    fig.update_yaxes(title="points de risque", range=[0, max(60, float(tl["score"].max()) + 5)])
    st.plotly_chart(theme.style(fig, 360), config={"displayModeBar": False})
    peak_day = tl["score"].idxmax()
    if tl["score"].max() >= 25:
        top = tl.loc[peak_day, list(FACTOR_STYLE)].sort_values(ascending=False)
        causes = ", ".join(FACTOR_STYLE[k][0].lower() for k, v in top.items() if v > 0)
        st.caption(f"Pic à **{tl['score'].max():.0f}/100** le {peak_day:%d/%m} : {causes}. Les aires montrent la contribution de chaque facteur.")

    with st.expander("📐 Méthode, seuils et limites"):
        st.markdown(METHOD)
