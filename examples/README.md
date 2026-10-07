# Exemple exclusivement fictif

`candidats_fictifs.csv` contient des noms, une édition et des statistiques entièrement inventés pour illustrer le format d'import. Ce fichier ne constitue ni une collecte, ni une source sportive, ni une prédiction réelle.

Ses colonnes correspondent au **contrat provisoire** de `config/model_config.example.json`. Les adapter au schéma documenté de Luca avant de les utiliser avec un vrai modèle. Il ne suffit pas de renommer une variable : son sens, son unité et sa période doivent correspondre à ceux de l'entraînement.

Aucun modèle sportif réel n'est fourni avec cet exemple. L'import ne produira pas de classement sans un modèle entraîné et un contrat compatible. Les tests utilisent leur propre fixture synthétique dans un dossier temporaire, jamais le dataset attendu de Luca.

L'export contient `edition,joueur,score,rang`. Le rang repart à 1 pour chaque édition. Les scores ne sont pas normalisés entre joueurs et ne constituent pas des probabilités fiables de remporter le vote. En cas d'égalité, l'ordre alphabétique détermine le rang ; ce départage est arbitraire et est signalé dans l'évaluation.
