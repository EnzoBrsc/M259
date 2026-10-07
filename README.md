# M259 — Projet de machine learning

Outil scolaire qui classe les candidats au **Ballon d'Or** à partir de données disponibles **avant le vote**. Une ligne représente un joueur dans une édition ; la cible distingue le gagnant des non-gagnants.

**État au 7 octobre 2026 :** code des modèles, prédiction et interface disponibles sur `ami/modeles-interface`. Les fichiers de Luca ne sont pas encore présents. Aucun modèle entraîné sur des données réelles, aucune performance sportive et aucun classement réel ne sont fournis. Les tests et l'exemple CSV sont exclusivement fictifs.

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
git switch ami/modeles-interface
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
code .
```

Dans VS Code, installer les extensions recommandées **Python**, **Pylance** et **Jupyter**. L'interpréteur prévu est celui du dossier `.venv`. Pour un notebook, choisir **Select Kernel → Python Environments → .venv** si VS Code le demande.

Sur macOS/Linux, utiliser `.venv/bin/python` à la place de `.\.venv\Scripts\python.exe`.

L'environnement fournit NumPy, pandas, Matplotlib, seaborn, scikit-learn, joblib, Streamlit et un noyau Jupyter. Le dossier `.venv` reste local : chaque personne crée son propre environnement. Les bibliothèques directement utilisées sont versionnées dans `requirements.txt` ; les dépendances transitives sont résolues par pip. La compatibilité a été vérifiée sous Windows avec Python **3.13.1**, scikit-learn **1.9.1** et Streamlit **1.65.0**.

## Fichiers attendus et contrat des données

À obtenir de Luca avant un entraînement réel :

- `docs/cadrage.md` : objectif, périmètre du prix, éditions retenues, date limite avant vote, définition de la cible et protocole prévu ;
- `data/README.md` : sources vérifiables, licence/conditions d'utilisation, schéma, unités, périodes, valeurs manquantes et provenance temporelle des historiques ;
- `src/prepare_data.py` : nettoyage reproductible et construction des variables ;
- `data/processed/ballon_or.csv` : une ligne par joueur/édition, exactement un gagnant et au moins un non-gagnant par édition ;
- `notebooks/01_exploration.ipynb` : exploration et justifications des variables.

Le code vérifie la présence du cadrage, du dictionnaire des données et du CSV avant l'entraînement. Le nettoyage et l'exploration devront être relus avec Luca ; leur présence et le contenu des documents ne prouvent pas automatiquement l'absence de fuite temporelle. Les éditions sans prix doivent être exclues et documentées ; ne pas créer de gagnant artificiel.

Le schéma réel n'étant pas fourni, `config/model_config.example.json` est une **proposition fictive**, pas le schéma validé de Luca. Après accord sur le protocole :

```powershell
Copy-Item .\config\model_config.example.json .\config\model_config.json
code .\config\model_config.json
```

Adapter les noms des colonnes et les listes explicites `numeric_features`/`categorical_features`. Documenter la source, l'unité, la période et la date de disponibilité de **chaque variable** dans `feature_notes`. Choisir `baseline_feature`, une variable numérique dont une valeur élevée constitue une référence simple justifiée. La configuration d'exemple ne lance volontairement aucun entraînement : ses confirmations temporelles valent `false`. Les passer à `true` **uniquement après vérification conjointe** des données avant vote et des historiques calculés avec les seules éditions précédentes.

Les noms de variables évoquant le vote, le gagnant ou le classement sont refusés. L'édition, le nom et la cible restent hors des variables explicatives. L'exclusion automatique des noms est une protection partielle : elle ne détecte pas un résultat final dissimulé derrière un autre nom. Ne jamais intégrer les points du vote ou le classement final à la liste des variables. Laisser les valeurs absentes dans le CSV : l'imputation statistique destinée aux modèles est ajustée à l'intérieur de chaque pipeline, sur l'entraînement seulement.

## Entraîner et comparer

Depuis la racine du dépôt, après réception et audit des fichiers réels :

```powershell
.\.venv\Scripts\python.exe -X utf8 .\src\train.py --data .\data\processed\ballon_or.csv --config .\config\model_config.json --output .\artifacts\ballon_or
```

Le protocole par défaut nécessite **au moins 8 éditions complètes** : 3 éditions minimum pour le premier entraînement, 3 validations successives et les 2 dernières éditions réservées au test. Les validations utilisent les dernières éditions de développement, une à la fois ; chaque entraînement contient uniquement les éditions antérieures. Les paramètres du protocole doivent être fixés avant de voir les résultats, et ne pas être réduits après consultation du test pour améliorer les scores.

Quatre familles sont comparées, avec une grille volontairement modeste :

| Famille | Variantes |
| --- | --- |
| Référence simple | Tri décroissant d'une statistique numérique, médiane apprise pour les valeurs absentes |
| Régression logistique | `C` : 0.1, 1, 10 ; classes équilibrées |
| Arbre de décision | Profondeur : 2, 4, illimitée ; feuilles de 2 observations minimum |
| Forêt aléatoire | 100 arbres ; profondeur 4 ou illimitée ; feuilles de 2 observations minimum |

Les modèles apprennent des exemples joueur/édition ; la classe gagnant est rare, d'où les pondérations équilibrées. L'encodage accepte les nouvelles catégories. Imputation, standardisation et encodage sont appris dans les pipelines, jamais sur toute la table avant découpage. La sélection maximise la proportion d'éditions où le gagnant est **premier**, puis **dans les trois premiers**. Chaque édition compte autant. En cas d'égalité des performances, l'ordre de la grille tranche. En cas de scores joueurs identiques, le rang est départagé alphabétiquement et l'égalité est enregistrée ; elle n'est pas une preuve de supériorité.

Le modèle retenu est ensuite réentraîné sur toutes les éditions de développement et évalué **une seule fois** sur les dernières éditions. Aucune variante n'est choisie sur le test final. Le modèle sauvegardé conserve ce périmètre d'entraînement ; le test n'est pas automatiquement réintégré pour le déploiement.

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

La sortie contient `edition,joueur,score,rang`, avec un rang propre à chaque édition. Le fichier d'export existant est refusé pour éviter un écrasement involontaire. Le CSV d'entrée doit être préparé à partir de données réellement connues au moment de prédire.

Un [exemple explicitement fictif](examples/README.md) est fourni dans `examples/candidats_fictifs.csv`. Il illustre le contrat provisoire et devra être adapté au schéma validé. **Un score n'est pas automatiquement une probabilité de victoire** : les modèles classent des lignes indépendantes, les scores ne somment pas à 1 par édition et aucune calibration n'a été démontrée. La référence peut produire des scores supérieurs à 1.

## Interface Streamlit

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Ouvrir l'adresse locale affichée dans le terminal. Importer le CSV, sélectionner l'édition, consulter le tableau et le graphique, puis télécharger le classement. La validation et la prédiction réutilisent `src/predict_candidates.py`. Sans modèle réel à l'emplacement par défaut, l'interface signale l'absence et ne propose aucun classement inventé. Elle n'entraîne pas automatiquement un modèle et ne permet pas d'importer un fichier de modèle arbitraire.

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

Les tests utilisent uniquement des fixtures fictives et des répertoires temporaires. Ils couvrent la chronologie, les fuites par prétraitement, la sélection sans test final, les erreurs CSV, le chargement du modèle et le parcours **entraînement CLI → prédiction CLI → import Streamlit → tableau et graphique**. Les performances calculées pendant ces tests ne sont pas des résultats du projet sportif.

## Limites et bilan

Peu d'éditions signifient une forte incertitude : toujours publier le nombre d'éditions et les résultats par édition, pas seulement une moyenne. La présence du vrai gagnant parmi les candidats, les changements de règles/périodes, les différences entre postes et les critères subjectifs des votants conditionnent la validité de l'étude. Le modèle ne démontre ni une causalité ni un choix « juste » du gagnant. Le [bilan actuel](docs/cheminement_projet.md) sera complété avec les choix de Luca et les résultats réels après intégration des données et exécution du protocole.

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
