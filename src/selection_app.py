"""Interface des récompenses du football réel, indépendante du modèle Ballon d'Or."""

import os
from pathlib import Path

import streamlit as st

from src.football_selections import AWARDS, LEAGUES, load_selection_model, predict_selection_csv, select_squad
from src.schema import InputError


def render_selection(award, root):
    st.title(f"Candidats {award}")
    st.write(AWARDS[award])
    st.caption("Championnat : " + " · ".join(LEAGUES))
    st.info("Le score classe les candidats ; il n'est pas une probabilité fiable de sélection. La source de référence, les votes ou le jury et le championnat doivent être précisés pour chaque récompense.")
    model_root = Path(os.environ.get("M259_SELECTION_MODELS_DIR", str(root / "artifacts" / "selections")))
    try:
        bundle, config = load_selection_model(model_root / award.lower() / "model.joblib", award)
    except InputError as exc:
        st.warning(str(exc))
        st.file_uploader(f"CSV {award}", type=["csv"], max_upload_size=10, disabled=True, key=f"csv_{award}")
        st.write("Aucune prédiction disponible pour cette récompense : le dépôt ne fournit pas encore ses statistiques et labels historiques validés.")
        with st.expander("Données nécessaires"):
            st.write("Une ligne par joueur, période et compétition ; des sélectionnés et des non-sélectionnés dans l'historique, ainsi que des statistiques connues avant la sélection.")
            st.write("Le modèle Ballon d'Or ne sera pas utilisé à la place. Voir docs/selections_football.md et les gabarits data/selections/templates.")
        return
    st.caption(f"Modèle {award} : {bundle['model_name']} · appris jusqu'au {max(bundle['trained_periods'])}")
    st.caption(f"Référence des labels : {config.authority}")
    with st.expander("Format CSV"):
        st.code(",".join(["period_end", "competition", "player_id", "player"] + config.features))
        st.write("period_end : YYYY-MM-DD. Même fenêtre de statistiques et même compétition que dans la documentation d'entraînement. Retirer selected et tout résultat de la sélection courante.")
    uploaded = st.file_uploader(f"CSV {award}", type=["csv"], max_upload_size=10, key=f"csv_{award}")
    if uploaded is None:
        return
    try:
        result = predict_selection_csv(uploaded.getvalue(), bundle, config)
    except (InputError, OSError) as exc:
        st.error(str(exc))
        return
    groups = sorted(set(zip(result.period_end, result.competition)))
    period, competition = st.selectbox("Période et compétition", groups, format_func=lambda v: f"{v[0]} · {v[1]}", key=f"group_{award}")
    shown = result.loc[result.period_end.eq(period) & result.competition.eq(competition)]
    squad = select_squad(shown, config)
    st.subheader("Joueur proposé" if award == "POTM" else "Équipe proposée")
    st.caption(f"{len(shown)} candidats · {len(squad)} sélectionnés selon les quotas documentés du protocole.")
    st.dataframe(squad[["player", "score"] + (["position"] if "position" in squad else [])], hide_index=True, width="stretch")
    if shown.score.duplicated().any():
        st.warning("Scores identiques : départage arbitraire par player_id.")
    table, chart = st.columns([3, 2])
    with table:
        st.dataframe(shown[["rank", "player", "score"]], hide_index=True, width="stretch")
    with chart:
        st.bar_chart(shown.set_index("player")[["score"]], horizontal=True, sort=False)
    selected_ids = {(r.period_end, r.competition, r.player_id) for _, g in result.groupby(["period_end", "competition"]) for r in select_squad(g, config).itertuples()}
    result["predicted_selection"] = [(r.period_end, r.competition, r.player_id) in selected_ids for r in result.itertuples()]
    st.download_button(f"Télécharger {award}", result.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"classement_{award.lower()}.csv", mime="text/csv")
