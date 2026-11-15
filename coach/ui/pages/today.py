"""Aujourd'hui — une décision, quatre indicateurs, deux actions.

Tout le reste (graphiques détaillés, méthodes) vit dans Analyses et Réglages :
cette page doit se comprendre en 10 secondes, sans jargon.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ... import schema
from ...ai import MUSCLES
from ...garmin import GarminError
from .. import state, theme
from ..i18n import lang, t
from .garmin_page import run_sync


# --- Logique de synthèse (pure, testée) -----------------------------------------
def decision_key(readiness: int | None, risk: int, tsb: float, hrv_low: bool, sleep_debt: float = 0.0) -> str:
    """→ "rest", "go", "easy" ou "easy.sleep" (séance facile imposée par la dette de sommeil)."""
    if risk >= 50 or (readiness is not None and readiness < 50) or hrv_low:
        return "rest"
    if sleep_debt >= 5:
        return "easy.sleep"
    if (readiness is None or readiness >= 75) and risk < 25 and tsb > -25:
        return "go"
    return "easy"


def freshness_key(tsb: float) -> str:
    if tsb > 10:
        return "fresh"
    if tsb >= -10:
        return "ok"
    if tsb >= -30:
        return "tired"
    return "very"


DECISION_COLOR = {"rest": theme.RED, "go": theme.GREEN, "easy": theme.AMBER}
FRESH_COLOR = {"fresh": theme.GREEN, "ok": theme.GREEN, "tired": theme.ORANGE, "very": theme.RED}


# --- Blocs d'interface ---------------------------------------------------------
def _decision(a: state.Analytics) -> None:
    if a.checkins.empty and a.realise.empty:
        st.info(t("dec.nodata"))
        return
    tsb = float(a.pmc["TSB"].iloc[-1]) if not a.pmc.empty else 0.0
    key = decision_key(a.readiness.score if a.readiness else None, a.risk.score, tsb, a.hrv_status.status == "basse", a.sleep_summary.debt_h or 0.0)
    title_key = key.split(".")[0]
    why_key = "dec.easy.sleep" if key == "easy.sleep" else f"dec.{key}.why"
    color = DECISION_COLOR[title_key]
    st.markdown(
        f"<div class='kpi' style='border-color:{color}88; padding:22px 26px'>"
        f"<div class='t'>{t('dec.title')}</div>"
        f"<div class='v' style='color:{color}; font-size:1.9rem'>{t('dec.' + title_key)}</div>"
        f"<div class='s' style='font-size:1rem'>{t(why_key)}</div></div>",
        unsafe_allow_html=True,
    )


def _cards(a: state.Analytics) -> None:
    r, ss, risk = a.readiness, a.sleep_summary, a.risk
    tsb = float(a.pmc["TSB"].iloc[-1]) if not a.pmc.empty else 0.0
    fk = freshness_key(tsb)
    rec_label = {"green": "rec.good", "amber": "rec.mid", "red": "rec.low"}[r.status] if r else None
    risk_label = {"Faible": "risk.low", "Modéré": "risk.mid", "Élevé": "risk.high"}.get(risk.level, "risk.low")
    sleep_color = theme.GREEN if (ss.avg_h or 0) >= 7.5 else theme.AMBER if (ss.avg_h or 0) >= 7 else theme.RED

    cols = st.columns(4)
    with cols[0]:
        color = {"green": theme.GREEN, "amber": theme.AMBER, "red": theme.RED}[r.status] if r else theme.MUTED
        st.markdown(theme.kpi(t("card.recovery"), f"{r.score}%" if r else "—", t(rec_label) if r else "", color), unsafe_allow_html=True)
        with st.popover(t("card.why"), width="stretch"):
            st.markdown(t("why.recovery"))
            if r:
                labels = {
                    "sommeil": t("card.sleep"),
                    "energie": "Énergie" if lang() == "FR" else "Energy",
                    "fcr": "Pouls au repos" if lang() == "FR" else "Resting HR",
                    "vfc": "VFC" if lang() == "FR" else "HRV",
                }
                for k, v in r.components.items():
                    st.progress(int(v), text=f"{labels[k]} : {v:.0f}/100")
            st.caption(t("why.more"))
    with cols[1]:
        st.markdown(theme.kpi(t("card.sleep"), f"{ss.avg_h:.1f} h" if ss.avg_h else "—", t("sleep.sub", debt=f"{ss.debt_h:.1f}") if ss.debt_h is not None else "", sleep_color), unsafe_allow_html=True)
        with st.popover(t("card.why"), width="stretch"):
            st.markdown(t("why.sleep", need=f"{ss.need_h:g}", reg=ss.regularity.lower()))
            for level, msg in ss.insights[:2]:
                theme.callout(level, msg)
            st.caption(t("why.more"))
    with cols[2]:
        top = risk.drivers[0].name if risk.drivers else ""
        st.markdown(theme.kpi(t("card.risk"), f"{risk.score}/100", t(risk_label) + (f" · {top}" if top else ""), risk.color), unsafe_allow_html=True)
        with st.popover(t("card.why"), width="stretch"):
            st.markdown(t("why.risk"))
            if risk.drivers:
                for f in risk.drivers:
                    st.markdown(f"- **{f.name}** (+{f.points:.0f}) : {f.action}")
            else:
                st.success(t("why.risk.none"))
            st.caption(t("why.more"))
    with cols[3]:
        st.markdown(theme.kpi(t("card.fresh"), t("fresh." + fk), t("fresh.sub", tsb=f"{tsb:+.0f}"), FRESH_COLOR[fk]), unsafe_allow_html=True)
        with st.popover(t("card.why"), width="stretch"):
            st.markdown(t("why.fresh"))
            st.caption(t("why.more"))


def _sync_button() -> None:
    garmin = state.garmin()
    if not garmin.connected:
        if st.button(f"⌚ {t('act.connect')}", width="stretch"):
            st.switch_page(st.session_state["_pages"]["settings"])
        return
    if st.button(f"🔄 {t('act.sync')}", type="primary", width="stretch"):
        with st.spinner("Garmin…"):
            try:
                n, a = run_sync(14)
            except GarminError as exc:
                st.error(str(exc))
                return
        st.toast(t("act.synced", n=n, a=a) if n or a else t("act.uptodate"), icon="✅")


def _row_from(base: pd.Series | None) -> list:
    """Ligne brute ``Historique_Checkin`` reconstituée depuis une ligne lue (NaN → vide)."""
    if base is None:
        return schema.pad_row(schema.CHECKIN, [])
    return ["" if pd.isna(base[c]) else base[c] for c in schema.CHECKIN_COLUMNS]


def _checkin() -> None:
    today = date.today().isoformat()
    ck = state.load(schema.CHECKIN)
    todays = ck[ck["Date"].dt.strftime("%Y-%m-%d") == today] if not ck.empty else ck
    base = todays.iloc[-1] if not todays.empty else None
    with st.popover(f"📝 {t('act.checkin')}", width="stretch"):
        energie = st.slider(t("ck.energy"), 1, 10, int(base["Niveau_Energie"]) if base is not None and pd.notna(base["Niveau_Energie"]) else 7)
        douleurs = st.multiselect(t("ck.pain"), MUSCLES, placeholder=t("ck.none"))
        has_watch = base is not None and pd.notna(base["VFC"])
        manual = st.toggle(t("ck.manual"), value=not has_watch)
        sommeil, fcr, vfc = (
            (float(base["Heures_Sommeil"]) if base is not None and pd.notna(base["Heures_Sommeil"]) else 7.5),
            (int(base["FC_Repos"]) if base is not None and pd.notna(base["FC_Repos"]) else 50),
            (int(base["VFC"]) if has_watch else 60),
        )
        if manual:
            sommeil = st.number_input(t("ck.sleep"), 0.0, 14.0, sommeil, 0.25)
            fcr = st.number_input(t("ck.rhr"), 30, 120, fcr)
            vfc = st.number_input(t("ck.hrv"), 5, 250, vfc)
        if st.button(t("ck.save"), type="primary", width="stretch"):
            # On repart de la ligne Garmin du jour (phases, horaires…) et on y ajoute le ressenti.
            row = _row_from(base)
            row[0:7] = [today, sommeil, vfc, fcr, energie, ", ".join(douleurs) if douleurs else "Aucun", state.age()]
            row[9] = "Ressenti" if not manual else "Manuel"
            state.append(schema.CHECKIN, [row])
            st.toast(t("ck.saved"), icon="✅")
            st.rerun()


def _chart(a: state.Analytics) -> None:
    start = pd.Timestamp.today().normalize() - pd.Timedelta(days=55)
    fig = go.Figure()
    load = a.daily[a.daily.index >= start]
    fig.add_trace(go.Bar(x=load.index, y=load.values, name=t("chart.load"), marker_color="rgba(255,255,255,0.14)"))
    if not a.hrv.empty:
        h = a.hrv[a.hrv.index >= start]
        fig.add_trace(go.Scatter(x=h.index, y=np.exp(h["ln7"]), name=t("chart.hrv"), yaxis="y2", line=dict(color=theme.ACCENT, width=3)))
    if not a.risk.timeline.empty:
        rk = a.risk.timeline[a.risk.timeline.index >= start]["score"]
        fig.add_trace(go.Scatter(x=rk.index, y=rk.values, name=t("chart.risk"), yaxis="y3", line=dict(color=theme.RED, width=2, dash="dot")))
    fig.update_layout(
        yaxis=dict(showgrid=False, showticklabels=False),
        yaxis2=dict(overlaying="y", side="right", showgrid=False, showticklabels=False),
        yaxis3=dict(overlaying="y", range=[0, 100], visible=False),
    )
    st.plotly_chart(theme.style(fig, 280), config={"displayModeBar": False})
    st.caption(t("chart.caption"))


def render() -> None:
    st.markdown(
        f"<div class='banner' style='padding:16px 22px'><h1 style='font-size:1.7rem'>⚡ Dynamic Hybrid Coach</h1><p>{t('app.tagline')}</p></div>",
        unsafe_allow_html=True,
    )
    if state.is_demo():
        st.caption("👋 " + t("demo.banner"))

    a = state.analytics()
    _decision(a)
    st.write("")
    if not (a.checkins.empty and a.realise.empty):
        _cards(a)
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        _sync_button()
    with c2:
        _checkin()

    if not a.daily.empty:
        st.markdown(f"#### {t('chart.title')}")
        _chart(a)
