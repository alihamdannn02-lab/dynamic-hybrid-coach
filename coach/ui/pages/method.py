"""Méthodologie & sources — ce qu'il y a sous le capot, et ses limites."""

from __future__ import annotations

import streamlit as st

MODELS = """
| Module | Méthode | Pourquoi |
|---|---|---|
| **Charge** | TSS estimé par sRPE (durée × RPE, Foster 2001) ramené à l'échelle TSS | Une unité commune à la course, au vélo, à la natation et à la musculation |
| **Forme** | Modèle impulsion-réponse de Banister : CTL (τ 42 j), ATL (τ 7 j), TSB | Standard du Performance Manager (Coggan), calculé jour par jour depuis 0 |
| **Pic de charge** | ACWR par moyennes exponentielles 7/28 j | Version EWMA, plus sensible que les moyennes glissantes (Williams 2017) |
| **VFC** | ln(rMSSD), moyenne 7 j, plage normale = baseline 60 j ± 0,5 ET, CV 7 j | Méthode Plews/Buchheit, référence en sports d'endurance |
| **Readiness** | Sommeil, énergie perçue, FC repos et VFC comparées à la baseline perso | Une VFC « basse » n'a de sens que rapportée à l'individu |
| **Sommeil** | Dette vs besoin, régularité (ET du coucher), architecture, jetlag social | La régularité pèse autant que la durée (Phillips 2017) |
| **Risque de blessure** | Indice additif explicable à 6 facteurs | Chaque point est traçable jusqu'à sa cause |
| **Prédiction VFC** | Régression ridge personnelle, validation walk-forward vs référence naïve | Mesurer le gain réel plutôt que l'affirmer |
| **Jour J** | Projection Banister de 3 scénarios dont affûtage −55 % / 10 j | Bosquet et al. 2007 (méta-analyse sur l'affûtage) |
| **Temps de course** | Formule de Riegel (exposant 1,06), comparée au prédicteur Garmin | Simple, robuste, connue de tous les coachs |
"""

REFS = """
- Banister E.W. et al. (1975). *A systems model of training for athletic performance.*
- Bosquet L. et al. (2007). *Effects of tapering on performance: a meta-analysis.* Med Sci Sports Exerc.
- Buchheit M. (2014). *Monitoring training status with HR measures: do all roads lead to Rome?* Front Physiol.
- Clarsen B. et al. (2013). *Development and validation of the OSTRC overuse injury questionnaire.* Br J Sports Med.
- Foster C. (1998). *Monitoring training in athletes with reference to overtraining syndrome.* Med Sci Sports Exerc.
- Gabbett T. (2016). *The training–injury prevention paradox.* Br J Sports Med.
- Impellizzeri F. et al. (2020). *Acute:Chronic Workload Ratio: conceptual issues and fundamental pitfalls.* Int J Sports Physiol Perform.
- Mah C. et al. (2011). *The effects of sleep extension on the athletic performance of collegiate basketball players.* Sleep.
- Milewski M. et al. (2014). *Chronic lack of sleep is associated with increased sports injuries in adolescent athletes.* J Pediatr Orthop.
- Phillips A. et al. (2017). *Irregular sleep/wake patterns are associated with poorer academic performance.* Sci Rep.
- Plews D. et al. (2013). *Training adaptation and heart rate variability in elite endurance athletes.* Int J Sports Physiol Perform.
- Riegel P. (1981). *Athletic records and human endurance.* American Scientist.
- Williams S. et al. (2017). *Better way to determine the acute:chronic workload ratio?* Br J Sports Med.
"""

STACK = """
- **Python** · Streamlit · pandas / NumPy · Plotly
- **Données** : Garmin Connect (lecture seule) · Google Sheets ou CSV
- **IA** : Google Gemini (sorties JSON contrôlées, vision pour lire les tableaux de WOD), repli sur règles physiologiques
- **Qualité** : tests automatisés (modèles, parseurs Garmin, flux de connexion simulé, chaque page), lint, intégration continue GitHub Actions
"""

PRIVACY = """
- **Lecture seule sur Garmin** : l'application ne modifie jamais tes activités, titres ou descriptions (un test automatisé le garantit).
- **Aucun mot de passe stocké** : seul un jeton de session vit dans ton navigateur, le temps de ta visite.
- **Mode démo isolé** : les visiteurs explorent un athlète simulé ; s'ils connectent leur montre, leurs données restent dans leur session et ne sont écrites nulle part.
"""


def render() -> None:
    st.title("📚 Méthodologie & sources")
    st.markdown("<p class='hero'>Chaque chiffre affiché repose sur une méthode publiée. Voici lesquelles, et où elles s'arrêtent.</p>", unsafe_allow_html=True)
    st.subheader("Les modèles")
    st.markdown(MODELS)
    st.subheader("Données & confidentialité")
    st.markdown(PRIVACY)
    st.subheader("Ce que l'application ne prétend pas faire")
    st.markdown(
        "- Elle **ne diagnostique pas** de blessure : l'indice de risque est une aide à la décision, pas un modèle clinique validé.\n"
        "- Les seuils (ACWR, sommeil) viennent de populations précises et se discutent (Impellizzeri 2020).\n"
        "- Le TSS par sRPE est une approximation : avec un capteur de puissance, le TSS « vrai » est plus précis.\n"
        "- Les prédictions sont **personnelles** et s'améliorent avec l'historique ; leur erreur est toujours affichée."
    )
    st.subheader("Stack technique")
    st.markdown(STACK)
    st.subheader("Références")
    st.markdown(REFS)
