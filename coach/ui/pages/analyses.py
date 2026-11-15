"""Analyses — toutes les analyses détaillées, en onglets, chacune précédée d'un résumé simple."""

from __future__ import annotations

import re

import numpy as np
import streamlit as st

from ...forecast import today_state
from .. import state
from ..i18n import lang, t
from . import insights, predictions, risk_page, sleep_page
from .today import freshness_key


def _brief(text: str) -> None:
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)  # gras Markdown → HTML (on est dans une div)
    st.markdown(
        f"<div class='kpi' style='padding:12px 16px; margin-bottom:10px'><div class='t'>{t('an.brief')}</div><div class='s' style='font-size:1rem'>{text}</div></div>",
        unsafe_allow_html=True,
    )


def brief_load(a: state.Analytics) -> str:
    if a.pmc.empty:
        return "Pas encore de séances." if lang() == "FR" else "No sessions yet."
    last = a.pmc.iloc[-1]
    fresh = t("fresh." + freshness_key(float(last.TSB))).lower()
    acwr = a.load_status.acwr
    if lang() == "FR":
        spike = (
            ""
            if acwr is None
            else (" Attention, ta charge augmente trop vite." if acwr > 1.3 else " Ta charge progresse à un rythme sain." if acwr >= 0.8 else " Ta charge récente est plus basse que d'habitude.")
        )
        return f"Forme de fond : **{last.CTL:.0f}** (sur 6 semaines). Aujourd'hui tu es **{fresh}**.{spike}"
    spike = (
        "" if acwr is None else (" Careful, your load is rising too fast." if acwr > 1.3 else " Your load is building at a healthy rate." if acwr >= 0.8 else " Your recent load is lower than usual.")
    )
    return f"Baseline fitness: **{last.CTL:.0f}** (6 weeks). Today you are **{fresh}**.{spike}"


def brief_sleep(a: state.Analytics) -> str:
    ss, hs = a.sleep_summary, a.hrv_status
    if not ss.avg_h:
        return "Pas encore de nuits enregistrées." if lang() == "FR" else "No nights recorded yet."
    if lang() == "FR":
        hrv = {
            "stable": "ta VFC est normale",
            "basse": "ta VFC est **sous ta normale** (fatigue)",
            "haute": "ta VFC est au-dessus de ta normale",
            "insuffisant": "ta VFC n'a pas encore assez d'historique",
        }[hs.status]
        return f"Tu dors **{ss.avg_h:.1f} h** par nuit cette semaine (il te manque {ss.debt_h:.1f} h) et {hrv}."
    hrv = {"stable": "your HRV is normal", "basse": "your HRV is **below your normal** (fatigue)", "haute": "your HRV is above your normal", "insuffisant": "your HRV needs more history"}[hs.status]
    return f"You sleep **{ss.avg_h:.1f} h** a night this week ({ss.debt_h:.1f} h short) and {hrv}."


def brief_risk(a: state.Analytics) -> str:
    r = a.risk
    level = t({"Faible": "risk.low", "Modéré": "risk.mid", "Élevé": "risk.high"}.get(r.level, "risk.low")).lower()
    if lang() == "FR":
        cause = f" Principal facteur : {r.drivers[0].name.lower()}." if r.drivers else " Aucun signal d'alerte."
        return f"Risque **{level}** ({r.score}/100).{cause}"
    cause = f" Main factor: {r.drivers[0].name.lower()}." if r.drivers else " No warning signal."
    return f"**{level.capitalize()}** risk ({r.score}/100).{cause}"


def brief_predict(a: state.Analytics) -> str:
    m = a.hrv_model
    ts = today_state(a.daily, a.checkins)
    if not m.ready or ts is None:
        return "Le modèle personnel s'active après 4 semaines de données." if lang() == "FR" else "The personal model activates after 4 weeks of data."
    load = float(a.daily.tail(28).mean())
    good = float(np.exp(ts.base_ln + m.predict_dev(load, ts.tsb_tomorrow(load), 8.0, ts.etat_j)))
    bad = float(np.exp(ts.base_ln + m.predict_dev(load, ts.tsb_tomorrow(load), 6.0, ts.etat_j)))
    if lang() == "FR":
        return f"Avec une séance habituelle ce soir, ta VFC demain serait d'environ **{good:.0f} ms** si tu dors 8 h, contre **{bad:.0f} ms** si tu dors 6 h."
    return f"After a typical session today, your HRV tomorrow would be about **{good:.0f} ms** with 8 h of sleep, versus **{bad:.0f} ms** with 6 h."


def render() -> None:
    a = state.analytics()
    if lang() == "EN":
        st.caption(t("detail.fr_only"))
    tabs = st.tabs([f"📈 {t('an.load')}", f"😴 {t('an.sleep')}", f"🛡️ {t('an.risk')}", f"🔮 {t('an.predict')}"])
    sections = [(brief_load, insights), (brief_sleep, sleep_page), (brief_risk, risk_page), (brief_predict, predictions)]
    for tab, (brief, module) in zip(tabs, sections):
        with tab:
            _brief(brief(a))
            module.render(embedded=True)
