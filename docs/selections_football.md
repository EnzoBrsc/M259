# Sélections expérimentales TOTW, TOTY, TOTS et POTM

Au 7 octobre 2026, les quatre modèles et classements sont opérationnels pour les cinq ligues. **Statistiques réelles ; labels calculés selon la règle scolaire M259 v1 choisie par le groupe.** Les performances ci-dessous ne mesurent pas la prévision de récompenses officielles. Les sources, droits, dictionnaire, fenêtres, exclusions et pondérations sont dans [le dossier des données](../data/selections/README.md).

## Données livrées

| Mode | Historique | Candidats actuels |
| --- | --- | --- |
| TOTS | 12 893 joueurs-saisons, huit saisons 2017/18–2024/25 | 1 589 joueurs de 2025/26, minimum 900 minutes |
| TOTY | Même historique de saison que TOTS | Même CSV 2025/26 ; pas une année civile |
| TOTW | 28 056 observations, 21 semaines | 1 287 joueurs ; dernière apparition dans la semaine du 14–20 septembre 2026 |
| POTM | 11 375 joueurs-mois, août 2024–janvier 2025 | 1 430 joueurs ; cumul septembre 2026 |

Les 153 matchs actuels viennent des feuilles ESPN marquées terminées. La recherche quotidienne jusqu'au 7 octobre donne le 20 septembre comme dernière date disponible dans les cinq ligues. L'archive des matchs d'entraînement est incomplète : les métriques sont conditionnelles à son pool observé. 3 420 doublons exacts d'apparitions historiques ont été retirés. Les candidats sans poste documenté à la coupure sont exclus : 291 pour TOTW, 442 pour POTM. Voir `data/selections/processed/quality_report.json` pour les noms et manquants ; aucun poste ni résultat sportif n'est inventé.

Les équipes sont propres à chaque championnat, avec une composition 4-3-3. POTM propose un joueur par ligue. Les dates des labels sont des coupures analytiques rétrospectives, pas des publications officielles. Les identifiants, notes de vote, notes SofaScore, attributs EA et scores composites ne sont pas les variables explicatives.

## Comparaison réellement exécutée

Neuf configurations : référence par buts, logistique C 0,1/1/10, arbres profondeur 2/4/illimitée, forêts profondeur 4/illimitée. Pipelines scikit-learn : imputation, standardisation et catégories ajustées uniquement sur l'entraînement. Les périodes restent entières et chronologiques, toutes ligues ensemble. Choix sur la précision de validation, puis rappel, avec ordre fixe en cas d'égalité.

| Mode | Modèle choisi | Validation | Test final | Groupes de test |
| --- | --- | --- | --- | --- |
| TOTS | Logistique, C=1 | 71,52 % | **53,64 %** | 10 = 2 saisons × 5 ligues |
| TOTY | Logistique, C=1 | 71,52 % | **53,64 %** | 10, même protocole TOTS |
| TOTW | Logistique, C=1 | 90,91 % | **89,09 %** | 10 = 2 semaines × 5 ligues |
| POTM | Logistique, C=0,1 | 90,00 % | **90,00 %** | 10 = 2 mois × 5 ligues |

Pour les équipes : précision/rappel à 11 après quotas, moyennés par groupe ; ils sont égaux car chaque équipe de référence comporte onze joueurs. Pour POTM : précision à 1, soit neuf joueurs de référence correctement proposés sur dix groupes de test.
Ce sont des **accords avec une règle dérivée des statistiques**, avec circularité assumée. Appliquer directement la règle reproduit sa sélection exactement. Le modèle appris est un exercice de ML, pas une amélioration démontrée de cette règle. La performance des modèles de saison reste modeste.

TOTS/TOTY : validation saisons terminées en 2021, 2022, 2023 ; test saisons 2023/24 et 2024/25. TOTW : validation semaines terminées les 29 décembre 2024, 5 et 12 janvier 2025 ; test les 19 et 26 janvier 2025. POTM : deux premiers mois pour l'apprentissage initial, validation octobre/novembre 2024, test décembre 2024/janvier 2025. Le petit historique POTM limite fortement les conclusions.

Les rapports complets [TOTS](resultats_selections/tots.json), [TOTY](resultats_selections/toty.json), [TOTW](resultats_selections/totw.json), [POTM](resultats_selections/potm.json) conservent les neuf variantes, paramètres, découpages, égalités, résultats par ligue et empreintes SHA-256. Après cette évaluation figée, le même modèle et les mêmes paramètres sont réentraînés sur tout l'historique pour la production. Les rapports distinguent les deux états ; le test ne sert jamais à choisir les paramètres.

## Lancement et export

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
# Sur un clone sans modèles locaux :
.\.venv\Scripts\python.exe -X utf8 .\src\setup_selection_models.py
.\.venv\Scripts\python.exe -m streamlit run .\app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Choisir la récompense puis la ligue. Le CSV préparé se charge automatiquement ; un CSV importé le remplace. Télécharger les statistiques d'entrée et le classement avec `predicted_selection`. Le graphique montre les vingt premiers du classement ; l'équipe respecte les quotas de postes et peut inclure des joueurs plus bas dans le classement global.

```powershell
.\.venv\Scripts\python.exe -X utf8 .\src\predict_selection.py --award TOTW --input .\data\selections\processed\totw_candidates.csv --output .\outputs\nouveau_classement_totw.csv
```

Les exports CLI existants sont refusés. Ne charger que des modèles joblib locaux de confiance, avec les versions Python/scikit-learn correspondantes. Les scores ne sont pas calibrés en probabilités.
Pour refaire la collecte : installer `requirements-data.txt`, puis `src/collect_selection_data.py --download`. Les gros snapshots et audits de scores restent hors Git ; les CSV préparés et rapports légers sont versionnés. Le setup refuse un dossier de modèles déjà rempli et ne supprime rien automatiquement.

## Vérification

Au 7 octobre 2026 : **43 tests et 14 sous-tests passent sous Python 3.13.1 Windows** ; `pip check` valide les dépendances. Tests ajoutés : regroupement des passages par club, distinction dernier match/cumul mensuel, postes antérieurs uniquement, règle et manquants, réentraînement de production distinct du test et contrats des CSV réels. Le nettoyage et le notebook de Luca restent inchangés.
Les limitations incluent couverture incomplète, jointures de noms du fournisseur, changements de schéma entre sources, simplification des gardiens/défenseurs, pondérations arbitraires et faible nombre de périodes de test. Aucun résultat sur un vote officiel n'est revendiqué.

Les quatre modes ont été exécutés avec leurs modèles réels dans le test Streamlit : aucune erreur, deux tableaux, graphique et exports par mode. Dans le navigateur, import du CSV 2025/26 en mode TOTS, affichage de l'équipe et du graphique, puis téléchargement : les 1 589 lignes et les 55 sélectionnés (11 par ligue) sont identiques à l'export de la pipeline locale. Le serveur a été redémarré pour charger les nouveaux modules.
