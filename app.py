"""Interface locale : même validation et même pipeline que la commande CLI."""

import os
from pathlib import Path

import streamlit as st

from src.predict_candidates import SCORE_NOTICE, load_model, predict_csv
from src.schema import InputError

ROOT = Path(__file__).resolve().parent


def main():
    st.set_page_config(page_title="Ballon d'Or · M259", page_icon="⚽", layout="wide")
    st.caption("PROJET SCOLAIRE M259 · CLASSEMENT DES CANDIDATS")
    st.title("Qui se distingue avant le vote ?")
    st.write("Importez les statistiques des candidats d'une même édition pour obtenir un classement avec le modèle entraîné.")
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
    with st.expander("Quel format importer ?"):
        st.write("CSV UTF-8, séparé par des virgules ou des points-virgules, de 10 Mio maximum.")
        st.code(",".join([config.edition_column, config.player_column] + config.features))
        st.write("Une ligne par joueur et édition. Les valeurs et unités doivent correspondre à la documentation des données. Retirez la cible, les points du vote et le classement final.")
        st.write("Les valeurs numériques vides sont imputées avec les statistiques apprises sur l'entraînement. Les nouvelles catégories sont acceptées. Les éditions déjà utilisées pour entraîner le modèle sont refusées.")
    uploaded = st.file_uploader("CSV des candidats", type=["csv"], max_upload_size=10, key="candidates")
    if uploaded is None:
        st.caption("Le classement apparaîtra après l'import d'un CSV conforme.")
        return
    try:
        result = predict_csv(uploaded.getvalue(), bundle, config)
    except InputError as exc:
        st.error(str(exc))
        return
    selected_edition = st.selectbox("Édition à afficher", options=result.edition.unique().tolist())
    displayed = result.loc[result.edition.eq(selected_edition)].copy()
    if displayed.score.duplicated().any():
        st.warning("Des candidats ont le même score. Le rang utilise un départage alphabétique arbitraire.")
    st.subheader(f"Classement · {selected_edition}")
    st.caption(f"{len(displayed)} candidats · un score élevé signifie une meilleure position dans ce classement.")
    table, chart = st.columns([3, 2])
    with table:
        st.dataframe(displayed[["rang", "joueur", "score"]], hide_index=True, width="stretch")
    with chart:
        st.bar_chart(displayed.set_index("joueur")[["score"]], horizontal=True, sort=False)
    st.download_button("Télécharger le classement CSV", data=result.to_csv(index=False).encode("utf-8-sig"),
                       file_name="classement_candidats.csv", mime="text/csv")


if __name__ == "__main__":
    main()
