# Cheminement et bilan du projet Ballon d'Or

État vérifié le **7 octobre 2026**, branche `integration-donnees`. Le cadrage,
les données et l'exploration de Luca sont maintenant intégrés. Le nettoyage
et le notebook de Luca n'ont pas été modifiés.

## Données et exploration livrées par Luca

Le snapshot communautaire attribué dans `data/README.md` couvre 69 éditions
1956–2025, sans 2020, soit 2 095 lignes brutes. Le script de préparation retient
984 lignes sur 30 éditions à partir de 1995 ; les éditions antérieures alimentent
uniquement les historiques. Les 30 gagnants sont contrôlés dans la livraison
contre une source UEFA indépendante. La régénération locale produit un CSV
traité identique octet par octet. Le manifeste et les tests vérifient la provenance,
les homonymes, les valeurs manquantes et l'absence d'utilisation du vote courant
ou des données futures dans les variables présentes.

Le notebook livré et le rapport montrent 375 lignes sans historique et 864 postes
inconnus. Seul le test dispose de postes renseignés : cette variable reste exclue.
Club et nationalité restent des métadonnées. Aucune donnée de buts, passes,
minutes ou trophées collectifs n'est disponible, ni inventée. Les joueurs présents
dans les tables historiques ne constituent pas nécessairement des listes
exhaustives de nommés connus avant vote. L'étude est rétrospective et mesure
la reconnaissance passée, avec un biais de sélection et de notoriété.

## Corrections d'intégration

L'ancienne configuration fictive ne correspondait pas au schéma de Luca.
`config/model_config.json` sélectionne exactement ses huit historiques :
apparitions, podiums, victoires, meilleur/dernier rang antérieur, délai depuis
la dernière apparition, présence à l'édition précédente et présence d'historique.
Les deux noms de rangs historiques sont autorisés explicitement ; les champs de
vote courant restent refusés. L'année d'audit doit être strictement antérieure.
Les homonymes et les égalités sont traités par `player_id`, conformément au cadrage.
Ni l'identifiant, ni le nom, ni l'année, ni la cible, ni les métadonnées n'entrent dans X.

Le mode candidats refuse toujours la cible et les colonnes supplémentaires.
Un mode historique distinct accepte le CSV complet et ne classe que les quatre
éditions du test réservé. Il vérifie le SHA-256 du snapshot entraîné. L'interface
signale clairement le caractère rétrospectif, le gagnant réel et son rang prédit.
Il n'y a ni nouveau choix de modèle ni réentraînement lors de l'import.

## Protocole fixé avant le test

Le premier entraînement porte sur 1995–2015 (21 éditions). La validation comporte
2016, 2017, 2018, 2019 et 2021 : chaque pipeline est apprise uniquement sur les
éditions antérieures à son année de validation. Les labels `split` du CSV sont
contrôlés. Les quatre éditions 2022–2025 restent hors de la sélection.
L'historique d'une année peut utiliser les résultats des années déjà publiées,
comme prévu par le scénario de prévisions annuelles successives du cadrage.

La référence trie `previous_wins`. Neuf variantes prédéfinies comparent cette
référence, la régression logistique, l'arbre et la forêt. Imputation, standardisation
et encodage sont appris sur chaque entraînement. Le choix maximise le top 1,
puis le top 3 en validation ; l'ordre fixe de la grille tranche les égalités.
Le modèle sélectionné est réentraîné sur le développement 1995–2021 (sans 2020),
puis évalué sur le test. Les performances du test ne servent pas à changer les
variables, le protocole ou la famille retenue.

## Comparaison réelle sur les cinq validations

| Modèle | Paramètres | Top 1 | Top 3 |
| --- | --- | --- | --- |
| reference | `{}` | 20% | 80% |
| regression_logistique | `{"C": 0.1}` | 40% | 80% |
| regression_logistique | `{"C": 1.0}` | 20% | 80% |
| regression_logistique | `{"C": 10.0}` | 20% | 80% |
| arbre_decision | `{"max_depth": 2, "min_samples_leaf": 2}` | 40% | 100% |
| arbre_decision | `{"max_depth": 4, "min_samples_leaf": 2}` | 60% | 60% |
| arbre_decision | `{"max_depth": null, "min_samples_leaf": 2}` | 40% | 40% |
| foret_aleatoire | `{"n_estimators": 100, "max_depth": 4, "min_samples_leaf": 2}` | 20% | 80% |
| foret_aleatoire | `{"n_estimators": 100, "max_depth": null, "min_samples_leaf": 2}` | 40% | 80% |

Le modèle retenu est l'**arbre de décision**, profondeur 4, minimum 2 lignes par
feuille, classes équilibrées, graine 42. Il obtient 3/5 gagnants premiers et 3/5
dans le top 3 en validation. La référence historique obtient 1/5 et 4/5.
L'arbre de profondeur 2 a un meilleur top 3, mais la règle fixée donne priorité
au top 1 : il n'a donc pas été retenu. Cette règle n'a pas été changée après le test.

## Test final 2022–2025

| Édition | Gagnant réel | Premier prédit | Rang du gagnant | Top 3 |
| --- | --- | --- | --- | --- |
| 2022 | Karim Benzema | Sadio Mané | 24 | Non |
| 2023 | Lionel Messi | Mohamed Salah | 27 | Non |
| 2024 | Rodri | Erling Haaland | 2 | Oui |
| 2025 | Ousmane Dembélé | Erling Haaland | 20 | Non |

Le test donne **0/4 gagnant premier (0 %) et 1/4 dans le top 3 (25 %)** ; le rang
réciproque moyen vaut environ 0,157. Chaque édition contient 30 candidats :
l'espérance d'un classement aléatoire est 3,33 % pour le top 1 et 10 % pour le
top 3. Ces espérances ne sont pas un test de significativité. Avec seulement
quatre éditions, le résultat est très incertain et ne démontre pas une prédiction
fiable. Les premiers scores sont ex aequo en 2022, 2024 et 2025, et celui du
vrai gagnant est ex aequo dans les quatre éditions : les rangs dépendent alors
du départage fixe par identifiant. Ne pas interpréter ce départage comme une
supériorité sportive.

Les scores ne sont pas calibrés et ne forment pas une distribution de probabilité
par édition. Le mauvais top 1 du test est un résultat de l'étude, pas un défaut
à masquer en choisissant une autre famille sur ce test. Une amélioration future
nécessiterait des variables sportives documentées disponibles avant vote et
un nouveau protocole déclaré avec une évaluation indépendante.

## Vérifications du parcours

Windows, Python 3.13.1, scikit-learn 1.9.1 et Streamlit 1.65.0 : **32 tests réussis**,
`pip check` sans conflit. Les tests comprennent les 11 contrôles de Luca et cinq
régressions d'intégration : schéma réel/découpage, exceptions des rangs historiques,
homonymes/égalités, audit temporel et import historique sans éditions apprises.
Les autres tests vérifient les pipelines et le parcours CLI/Streamlit sur fixtures
fictives. Ces fixtures ne sont pas les données de l'étude.

Le parcours réel entraîne depuis le snapshot, sauvegarde la pipeline, exporte
les 120 lignes du test par la CLI, puis importe le CSV de Luca dans le navigateur
Streamlit. Les quatre éditions réservées, le tableau, le graphique et l'export
sont disponibles. Le fichier CLI et l'export de l'interface sont comparés.

Le rapport détaillé avec paramètres, versions, empreintes SHA-256, résultats de
validation et résultats par édition est archivé dans `docs/resultats_modeles.json`.
Les artefacts locaux restent dans `artifacts/ballon_or` et les exports dans
`outputs/`, ignorés par Git. Un nouveau clone doit reproduire l'entraînement
avec les commandes du README ; le modèle n'est pas téléversé dans le dépôt.

## Extension du 7 octobre 2026 : statistiques et sélections expérimentales

Après le choix explicite du groupe de produire des sélections expérimentales sur des statistiques réelles, trois sources ont été intégrées séparément du dataset Ballon d'Or : archives FBref/worldfootballR pour l'historique, snapshot FBref/SofaScore 2025/26 pour les candidats de saison, et feuilles ESPN de septembre 2026 pour les dernières apparitions et le mois. Sources et SHA-256, fenêtres, identifiants, manquants et exclusions sont dans `data/selections/README.md` et son rapport de qualité.

Les labels sont calculés par une règle M259 de performance, avec une équipe 4-3-3 par ligue ou un joueur du mois. Ils ne sont pas officiels. TOTY reprend volontairement la saison 2025/26 comme TOTS, conformément à la demande, sans prétendre être une récompense annuelle mondiale. Les statistiques sportives ne sont pas simulées et les valeurs manquantes ne sont pas inventées.

La comparaison chronologique de neuf configurations retient la logistique : C=1 pour TOTS/TOTY/TOTW, C=0,1 pour POTM. Sur dix groupes de test par mode, accord avec la règle : 53,64 % TOTS/TOTY, 89,09 % TOTW, 90 % POTM. Ces métriques évaluent l'imitation d'une règle construite à partir des variables ; elles ne démontrent pas la prédiction d'un jury. Le modèle de saison reste faible et le protocole POTM n'a que six mois historiques. Les modèles de production sont ensuite réentraînés sur tout l'historique, avec paramètres figés ; le test conserve son évaluation antérieure.

Les modèles et classements locaux sont utilisables dans Streamlit ; les CSV préparés, configurations et rapports sont versionnés pour permettre au binôme de réentraîner sur son ordinateur. La collecte facultative lit des snapshots RDS avec pyreadr 0.5.3, dont la roue Windows/Python 3.13 a été installée et vérifiée. Le travail de collecte/nettoyage/notebook de Luca n'a pas été modifié.
