# Prédire le Ballon d’Or masculin — cadrage

## Question et unité d'observation

Peut-on classer les candidats d'une édition à partir d'informations disponibles
avant son vote ? Une ligne représente un joueur et une édition. La cible
`winner` vaut 1 pour le gagnant et 0 pour les autres joueurs observés.
Le score d'un modèle sert à ordonner les candidats d'une même édition ; il ne
constitue pas, sans étude de calibration, une probabilité fiable de victoire.

## Première base disponible

L'historique brut couvre 1956–2025 (2020 annulé). La table de travail commence
en 1995 et utilise les années précédentes pour construire des historiques.
Ce sont des joueurs présents dans les tables de résultats de la source : les
anciennes tables peuvent omettre des nommés sans points. Le terme
`previous_appearances` signifie donc apparitions observées, pas nominations
officielles exhaustives. Nous ne prédisons pas sur tous les footballeurs.

La première version contient le poste lorsqu'il est renseigné et des historiques
de participation, podium et victoire. Les buts, passes, minutes et trophées
collectifs ne sont pas disponibles dans cette source ; ils ne sont pas inventés.
Cette base mesure d'abord la capacité prédictive de l'historique de reconnaissance.
Le club et la nationalité restent des métadonnées, hors des variables autorisées
pour cette première expérience. `data/README.md` détaille leur qualité.

## Prévention des fuites de données

- Les rangs et points du vote courant servent uniquement à construire/contrôler
  les étiquettes. Ils ne figurent pas dans les variables explicatives.
- Les compteurs historiques d'une ligne d'année Y utilisent strictement les
  années < Y, et sont calculés avant d'intégrer les résultats de Y.
- Les identifiants, le nom du joueur, l'édition, les métadonnées, la cible,
  le groupe de séparation et les champs d'audit sont exclus des entrées du modèle.
- Un fichier `data/processed/features.json` fournit la liste explicite des entrées.
  Le binôme doit sélectionner cette liste, jamais toutes les colonnes sauf la cible.
- Aucune caractéristique manquante n'est reconstruite avec une édition future.
  Le poste absent devient `Unknown` ; cette absence doit faire l'objet d'une analyse.
- Les transformations apprises (imputation, encodage, mise à l'échelle) sont ajustées
  uniquement sur l'entraînement, dans un pipeline.

## Séparation et évaluation à appliquer par le binôme

Découpage fixé avant l'entraînement : entraînement 1995–2015, validation
2016–2021 (sans 2020), test final 2022–2025. Toutes les lignes d'une édition
restent ensemble. Pendant le développement, utiliser des fenêtres chronologiques
sur l'entraînement : apprendre sur le passé, valider sur les éditions suivantes.
Choisir les modèles et paramètres avec entraînement/validation, jamais le test.

L'historique des éditions de validation/test antérieures à l'année évaluée est
disponible dans un scénario de prévision annuelle après publication de ces
résultats. Le protocole simule donc des prévisions annuelles successives, pas une
prévision simultanée de quatre années faite en 2021.

Pour chaque édition, trier les scores décroissants et départager les égalités
par `player_id` (règle fixe). Mesurer :

1. **Top 1 par édition** : fraction d'éditions où le premier est le vrai gagnant.
2. **Top 3 par édition** : fraction où le vrai gagnant est parmi les trois premiers.
3. Rang du vrai gagnant et rang réciproque moyen, en complément.

Publier aussi le résultat de chaque édition et le nombre de candidats. Comparer
à une référence historique simple (par exemple nombre de victoires précédentes)
et à l'espérance aléatoire : 1/N et min(3,N)/N par édition. L'accuracy par joueur
est trompeuse : prédire toujours 0 peut donner un résultat élevé. Les métriques
de classification, si utilisées, sont secondaires. Aucun modèle n'est développé
dans cette phase de cadrage/données.

## Limites et portée

Peu d'éditions, une seule victoire par édition, dépendance entre saisons d'un
même joueur, biais de présélection et de notoriété, changement des règles et des
périodes d'évaluation, variantes de noms et erreurs possibles de la source.
Le passage à une évaluation par saison à partir de 2022 nécessite de documenter
les fenêtres exactes avant toute intégration de statistiques sportives.
Les valeurs manquantes de poste sont concentrées dans le passé : un modèle
peut apprendre un effet de période. Rapporter également une expérience sans
poste. Quatre éditions de test donnent une évaluation très incertaine.

Le vote reste subjectif. Une interface éventuelle présentera un pronostic
expérimental avec ses limites, sans promesse de résultat ni conseil de pari.
