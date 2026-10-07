"""Interface locale : même validation et même pipeline que la commande CLI."""

import os
from pathlib import Path

import streamlit as st

from src.football_selections import AWARDS
from src.selection_app import render_selection

from src.predict_candidates import SCORE_NOTICE, load_model, predict_csv, predict_historical_csv
from src.schema import InputError

ROOT = Path(__file__).resolve().parent


def main():
    st.set_page_config(page_title="Football · M259", page_icon="⚽", layout="wide")
    st.caption("PROJET SCOLAIRE M259 · CLASSEMENT DES CANDIDATS")
    award = st.selectbox("Récompense", ["Ballon d'Or"] + list(AWARDS), key="award_choice")
    if award != "Ballon d'Or":
        render_selection(award, ROOT)
        return
    st.title("Qui se distingue avant le vote ?")
    st.write("Importez les variables historiques des candidats pour obtenir un classement expérimental. Cette première étude mesure la reconnaissance passée, sans statistiques sportives de la saison.")
    st.info(SCORE_NOTICE)
    model_dir = Path(os.environ.get("M259_MODEL_DIR", str(ROOT / "artifacts" / "ballon_or")))
    try:
        bundle, config = load_model(model_dir / "model.joblib")
    except InputError as exc:
        st.warning(str(exc))
        st.file_uploader("CSV des candidats", type=["csv"], max_upload_size=10, disabled=True)
        st.write("La collecte et les documents de Luca sont nécessaires avant l'entraînement. Aucun classement réel n'est disponible pour l'instant.")
        st.stop()
    st.caption(f"Modèle : {bundle.get('model_name', 'modèle local')} · Dernière édition d'entraînement : {max(bundle['trained_editions'])}")
    mode = st.radio("Type de CSV", ["Candidats à prédire", "Dataset historique de Luca (test)"], horizontal=True)
    historical = mode == "Dataset historique de Luca (test)"
    if historical:
        st.info("Importez data/processed/ballon_or.csv sans le modifier. Seules les éditions réservées au test seront affichées ; les éditions apprises sont exclues. C'est une évaluation rétrospective sur les joueurs présents dans la source, pas une prédiction future.")
    with st.expander("Quel format importer ?"):
        st.write("CSV UTF-8, séparé par des virgules ou des points-virgules, de 10 Mio maximum.")
        st.code(",".join([config.edition_column] + ([config.player_id_column] if config.player_id_column else []) + [config.player_column] + config.features))
        st.write("Une ligne par joueur et édition. Les valeurs et unités doivent correspondre à la documentation des données. Retirez la cible, les points du vote et le classement final.")
        st.write("Les valeurs numériques vides sont imputées avec les statistiques apprises sur l'entraînement. Les nouvelles catégories sont acceptées. Les éditions déjà utilisées pour entraîner le modèle sont refusées.")
    uploaded = st.file_uploader("CSV des candidats", type=["csv"], max_upload_size=10, key="candidates")
    if uploaded is None:
        st.caption("Le classement apparaîtra après l'import d'un CSV conforme.")
        return
    try:
        if historical:
            result, evaluation = predict_historical_csv(uploaded.getvalue(), bundle, config)
            metrics = evaluation["metrics"]
            st.write(f"Test historique · {metrics['editions']} éditions · gagnant premier : {metrics['top_1']:.0%} · dans le top 3 : {metrics['top_3']:.0%}")
        else:
            result = predict_csv(uploaded.getvalue(), bundle, config)
    except InputError as exc:
        st.error(str(exc))
        if not historical:
            st.caption("Pour importer le CSV complet de Luca avec sa cible et ses métadonnées, choisissez « Dataset historique de Luca (test) ».")
        return
    selected_edition = st.selectbox("Édition à afficher", options=result.edition.unique().tolist(), key="ballon_edition")
    displayed = result.loc[result.edition.eq(selected_edition)].copy()
    if displayed.score.duplicated().any():
        st.warning("Des candidats ont le même score. Le rang utilise l'identifiant déclaré (sinon le nom), un départage arbitraire.")
    st.subheader(f"Classement · {selected_edition}")
    st.caption(f"{len(displayed)} candidats · un score élevé signifie une meilleure position dans ce classement.")
    if historical:
        detail = next(d for d in evaluation["by_edition"] if d["edition"] == selected_edition)
        st.caption(f"Gagnant réel : {detail['gagnant_reel']} · rang prédit : {detail['rang_gagnant']}")
    table, chart = st.columns([3, 2])
    with table:
        st.dataframe(displayed[["rang", "joueur", "score"]], hide_index=True, width="stretch")
    with chart:
        st.bar_chart(displayed.set_index("joueur")[["score"]], horizontal=True, sort=False)
    st.download_button("Télécharger le classement CSV", data=result.to_csv(index=False).encode("utf-8-sig"),
                       file_name="classement_candidats.csv", mime="text/csv")


if __name__ == "__main__":
    main()
