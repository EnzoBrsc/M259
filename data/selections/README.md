# Données des sélections du football réel — à collecter

Championnats : Premier League, La Liga, Bundesliga, Serie A et Ligue 1.
Modes : TOTW, TOTY, TOTS et POTM. Aucun dataset réel n'est présent dans ce dossier.
`templates/` contient seulement des en-têtes CSV, pas des observations.

Avant l'entraînement, créer un dictionnaire de sources par récompense avec :
organisme/média définissant la sélection pour chaque championnat, URL et snapshot,
licence, dates de publication, période exacte des performances, unités et source
de chaque variable, joueurs éligibles sélectionnés/non-sélectionnés, valeurs
manquantes, identifiants et règles de postes. Vérifier les données disponibles
avant la sélection et les labels publiés avant chaque pli d'entraînement.

Ne pas convertir les gagnants du Ballon d'Or en labels de ces récompenses.
Voir [le contrat et les commandes](../../docs/selections_football.md).
