# M259 — Projet de machine learning

Outil scolaire qui classe les candidats au **Ballon d'Or** à partir de données disponibles **avant le vote**. Une ligne représente un joueur dans une édition ; la cible distingue le gagnant des non-gagnants.

**État au 7 octobre 2026 :** données et exploration de Luca intégrées sur `integration-donnees`, modèle entraîné localement et import du CSV historique disponible. 984 lignes / 30 éditions (1995–2025, sans 2020). L'étude utilise huit historiques de reconnaissance, aucune statistique sportive de saison. L'arbre choisi sur la validation obtient sur le test 2022–2025 **0/4 gagnant premier et 1/4 dans le top 3**. Ce résultat modeste est conservé sans changer le modèle après lecture du test. Voir le [bilan réel](docs/cheminement_projet.md).

## Répartition et coordination

| Responsable | Travail |
| --- | --- |
| Luca | Cadrage, sources, nettoyage, variables et notebook d'exploration |
| Branche `ami/modeles-interface` | Pipelines, comparaison, prédiction, Streamlit et guide |

La partie modèles ne modifie ni `src/prepare_data.py` ni le notebook de Luca. Le README a été complété et `joblib`/`streamlit` ont été ajoutés aux dépendances existantes. Relire ensemble ces deux fichiers partagés lors de la pull request ; aucune coordination effective avec Luca n'est présumée. Le [cheminement du projet](docs/cheminement_projet.md) distingue les réalisations et les éléments en attente.

## Installation sur un nouvel ordinateur

Installer Git, Python 3.13 et VS Code, puis exécuter dans un terminal :

```powershell
git clone https://github.com/EnzoBrsc/M259.git
cd M259
git switch integration-donnees
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
code .
```

Dans VS Code, installer les extensions recommandées **Python**, **Pylance** et **Jupyter**. L'interpréteur prévu est celui du dossier `.venv`. Pour un notebook, choisir **Select Kernel → Python Environments → .venv** si VS Code le demande.

Sur macOS/Linux, utiliser `.venv/bin/python` à la place de `.\.venv\Scripts\python.exe`.

L'environnement fournit NumPy, pandas, Matplotlib, seaborn, scikit-learn, joblib, Streamlit et un noyau Jupyter. Le dossier `.venv` reste local : chaque personne crée son propre environnement. Les bibliothèques directement utilisées sont versionnées dans `requirements.txt` ; les dépendances transitives sont résolues par pip. La compatibilité a été vérifiée sous Windows avec Python **3.13.1**, scikit-learn **1.9.1** et Streamlit **1.65.0**.

## Fichiers attendus et contrat des données

Livrés par Luca et présents dans cette branche :

- `docs/cadrage.md` : objectif, périmètre du prix, éditions retenues, date limite avant vote, définition de la cible et protocole prévu ;
- `data/README.md` : sources vérifiables, licence/conditions d'utilisation, schéma, unités, périodes, valeurs manquantes et provenance temporelle des historiques ;
- `src/prepare_data.py` : nettoyage reproductible et construction des variables ;
- `data/processed/ballon_or.csv` : une ligne par joueur/édition, exactement un gagnant et au moins un non-gagnant par édition ;
- `notebooks/01_exploration.ipynb` : exploration et justifications des variables.

Le code vérifie la présence du cadrage, du dictionnaire des données et du CSV avant l'entraînement. Le nettoyage et l'exploration devront être relus avec Luca ; leur présence et le contenu des documents ne prouvent pas automatiquement l'absence de fuite temporelle. Les éditions sans prix doivent être exclues et documentées ; ne pas créer de gagnant artificiel.

Le contrat réel est fourni dans `config/model_config.json` et correspond à `data/processed/features.json`. `config/model_config.example.json` reste une **proposition fictive ancienne**, utile seulement pour expliquer la configuration ; ne pas la copier sur le contrat réel.

```powershell
code .\config\model_config.json
```

Les huit entrées sont les apparitions, podiums et victoires précédents, meilleur/dernier rang antérieur, délai depuis la dernière apparition, présence à l'édition précédente et présence d'un historique. La référence fixée est `previous_wins`. Les notes et confirmations temporelles du contrat réel reposent sur la documentation et la vérification du script de Luca, sans présumer une relecture humaine conjointe. Le nettoyage régénère exactement son CSV traité. Club, nationalité, poste, identifiants, `winner`, `split` et année d'audit restent hors de X. Les candidats du snapshot sont connus rétrospectivement : cela ne démontre pas qu'ils constituent une liste exhaustive de nommés disponible avant vote.

Les noms évoquant le vote, le gagnant ou le classement sont refusés, avec deux exceptions exactes documentées : `previous_best_rank` et `previous_last_rank`, strictement antérieurs. L'année d'audit doit précéder l'édition. L'exclusion par nom est une protection partielle ; ne jamais intégrer le vote courant. Les valeurs numériques absentes sont imputées dans chaque pipeline, sur l'entraînement seulement.

## Entraîner et comparer

Depuis la racine du dépôt, après réception et audit des fichiers réels :

```powershell
.\.venv\Scripts\python.exe -X utf8 .\src\train.py --data .\data\processed\ballon_or.csv --config .\config\model_config.json --output .\artifacts\ballon_or
```

Le contrat réel applique le cadrage de Luca : premier entraînement **1995–2015 (21 éditions)**, validation annuelle successive **2016, 2017, 2018, 2019, 2021 (5 éditions)**, test final **2022–2025 (4 éditions)**. Les groupes `split` du CSV sont vérifiés. Les entraînements de validation s'étendent avec les éditions antérieures ; le modèle retenu est réentraîné sur 1995–2021, hors 2020, avant le test. Les historiques des résultats déjà publiés évoluent chaque année, conformément au scénario annuel du cadrage. Ne pas réduire le protocole après consultation du test pour améliorer les scores.

Quatre familles sont comparées, avec une grille volontairement modeste :

| Famille | Variantes |
| --- | --- |
| Référence simple | Tri décroissant d'une statistique numérique, médiane apprise pour les valeurs absentes |
| Régression logistique | `C` : 0.1, 1, 10 ; classes équilibrées |
| Arbre de décision | Profondeur : 2, 4, illimitée ; feuilles de 2 observations minimum |
| Forêt aléatoire | 100 arbres ; profondeur 4 ou illimitée ; feuilles de 2 observations minimum |

Les modèles apprennent des exemples joueur/édition ; la classe gagnant est rare, d'où les pondérations équilibrées. L'encodage accepte les nouvelles catégories. Imputation, standardisation et encodage sont appris dans les pipelines, jamais sur toute la table avant découpage. La sélection maximise la proportion d'éditions où le gagnant est **premier**, puis **dans les trois premiers**. Chaque édition compte autant. En cas d'égalité des performances, l'ordre de la grille tranche. En cas de scores joueurs identiques, le rang est départagé par l'identifiant déclaré (sinon par le nom) et l'égalité est enregistrée ; elle n'est pas une preuve de supériorité.

Le modèle retenu est ensuite réentraîné sur les éditions de développement avant le test. Aucune variante n'est choisie sur le test final. Le modèle sauvegardé conserve ce périmètre d'entraînement ; l'interface peut rejouer ce test figé sans nouvelle sélection ni réentraînement. Le départage des scores identiques utilise `player_id` conformément au cadrage (nom pour les contrats sans identifiant). Le rang réciproque moyen et l'espérance aléatoire complètent le top 1/top 3.

Les sorties locales sont :

- `model.joblib` : pipeline, contrat, versions, éditions apprises et paramètres retenus ;
- `results.json` : configuration, empreintes SHA-256 des entrées, dates, découpages, sélection et résultats par édition ;
- `validation.csv` : comparaison des 9 variantes sur les validations ;
- `final_test.csv` : gagnant réel, premier prédit, top 3, rang du gagnant et égalités sur le test.

Un dossier de résultats non vide est refusé : utiliser un nouveau nom pour conserver la trace des essais. Ces sorties sont ignorées par Git. Tant que les données manquent, la commande retourne une erreur explicite et ne crée pas de modèle ni de résultats.

## Classer de nouveaux candidats

Le CSV doit contenir les deux identifiants et **exactement** les variables du contrat du modèle, sans la cible ni les résultats du vote. Il doit être UTF-8, avec virgules ou points-virgules, 10 Mio maximum. Les colonnes absentes, doublons de joueurs, noms vides, éditions non entières et valeurs numériques invalides sont refusés. Une cellule numérique vide est acceptée puis imputée avec la médiane apprise. Les éditions doivent être postérieures à celles utilisées pour entraîner le modèle.

```powershell
.\.venv\Scripts\python.exe -X utf8 .\src\predict_candidates.py --model .\artifacts\ballon_or\model.joblib --input .\data\candidats_a_classer.csv --output .\outputs\classement.csv
```

La sortie contient `edition,joueur,score,player_id,rang` avec le contrat réel (sans `player_id` pour les contrats sans identifiant), avec un rang propre à chaque édition. Le fichier d'export existant est refusé pour éviter un écrasement involontaire. Le CSV d'entrée doit être préparé à partir de données réellement connues au moment de prédire.

Un [exemple explicitement fictif](examples/README.md) est fourni dans `examples/candidats_fictifs.csv`, conforme aux huit historiques du contrat réel ; ses joueurs et valeurs ne sont pas des données sportives. **Un score n'est pas automatiquement une probabilité de victoire** : les scores ne somment pas à 1 par édition et aucune calibration n'a été démontrée. La référence peut produire des scores supérieurs à 1.

Pour rejouer le test historique depuis le CSV complet, sans classer les éditions apprises :

```powershell
.\.venv\Scripts\python.exe -X utf8 .\src\predict_candidates.py --input .\data\processed\ballon_or.csv --historical-test --output .\outputs\classement_test_2022_2025.csv
```

Ce mode exige le snapshot exact utilisé pour l'entraînement (empreinte SHA-256). Pour de nouveaux candidats, le schéma exact est `edition,player_id,player` et les huit variables de `features.json`, sans cible ni métadonnées. Ne pas inventer les historiques d'une édition future.

## Interface Streamlit

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Ouvrir l'adresse locale affichée. Pour vérifier la livraison, sélectionner **Dataset historique de Luca (test)** et importer `data/processed/ballon_or.csv` tel quel. Seules 2022–2025 sont proposées, avec gagnant réel, rang prédit, tableau, graphique et export. Le mode **Candidats à prédire** exige un CSV sans cible ni métadonnées. La validation et la prédiction réutilisent `src/predict_candidates.py`. Sans artefact local, entraîner d'abord avec la commande ci-dessus ; les modèles ne sont pas stockés dans Git. L'interface n'entraîne pas automatiquement et ne charge aucun modèle téléversé arbitraire.

Pour utiliser un autre dossier d'entraînement local :

```powershell
$env:M259_MODEL_DIR = (Resolve-Path .\artifacts\autre_essai).Path
.\.venv\Scripts\python.exe -m streamlit run .\app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
Remove-Item Env:M259_MODEL_DIR
```

Charger seulement vos propres artefacts de confiance : le format joblib peut exécuter du code lors du chargement. Les versions Python majeure/mineure et scikit-learn doivent correspondre à celles du modèle sauvegardé.

## Vérifications reproductibles

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

Les tests couvrent la chronologie, les fuites, la sélection sans test final, les erreurs CSV et le parcours **entraînement CLI → prédiction CLI → import Streamlit → tableau et graphique**. Les tests de Luca vérifient le snapshot réel et la préparation ; les tests d'intégration contrôlent aussi le schéma et le découpage de son CSV. Les fixtures fictives servent uniquement aux contrôles logiciels. Les résultats réels sont archivés dans `docs/resultats_modeles.json`, séparément des tests.

## Limites et bilan

Peu d'éditions signifient une forte incertitude : toujours publier les effectifs et les résultats par édition. La liste rétrospective des candidats, les changements de règles/périodes et les critères subjectifs conditionnent la validité de l'étude. Le modèle ne démontre ni une causalité ni un choix « juste » du gagnant. Le [bilan actuel](docs/cheminement_projet.md) intègre les choix de Luca, la comparaison et le test réel, avec les égalités et les limites. Aucune amélioration n'a été choisie sur le test déjà consulté.

## Travailler ensemble

1. Le propriétaire invite son binôme depuis [Settings → Collaborators → Add people](https://github.com/EnzoBrsc/M259/settings/access) sur GitHub. L'ami doit accepter l'invitation pour pouvoir envoyer ses modifications.
2. Chaque personne clone le dépôt sur son ordinateur et ouvre le dossier dans Codex ou son éditeur.
3. Avant une nouvelle tâche, revenir sur `main` avec `git switch main`, puis récupérer les dernières modifications avec `git pull --ff-only` (enregistrer d'abord les changements en cours).
4. Pour une nouvelle tâche, créer une branche : `git switch -c nom-de-la-tache`.
5. Enregistrer et envoyer les modifications :

```bash
git add .
git commit -m "Description des modifications"
git push -u origin HEAD
```

6. Ouvrir une pull request sur GitHub pour relire et fusionner les changements. Éviter de modifier le même notebook en même temps.

## Fichiers à conserver localement

Les environnements Python, les caches et les fichiers `.env` sont ignorés. Ne pas ajouter de mots de passe, de clés API ou de données personnelles au dépôt.
