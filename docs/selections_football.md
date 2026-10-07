# TOTW, TOTY, TOTS et POTM du football réel

Cette extension concerne **le football réel**, conformément à la demande du
groupe. Elle couvre Premier League, La Liga, Bundesliga, Serie A et Ligue 1.
Elle utilise ses propres modèles ; les historiques du Ballon d'Or ne décrivent
pas les performances d'une semaine, d'un mois ou d'une saison.

## État actuel et données à obtenir

Les quatre interfaces, la comparaison chronologique, la prédiction CSV, la
composition d'une équipe par postes et l'export sont implémentés. **Aucun
dataset ni modèle réel n'est encore disponible pour ces quatre récompenses.**
L'application affiche cette absence et désactive l'import pour la récompense
concernée. Aucun joueur ou score de remplacement n'est inventé.
Les tests techniques utilisent exclusivement des données fictives temporaires.

| Mode | Période à définir dans la source | Cible | Effectif du gabarit |
| --- | --- | --- | --- |
| TOTW | Semaine / journées exactes | Appartenance à l'équipe de référence | 11, formation 4-3-3 |
| TOTY | Fenêtre annuelle exacte | Appartenance à l'équipe annuelle de référence | 11, formation 4-3-3 |
| TOTS | Saison et date de coupure | Appartenance à l'équipe de la saison de référence | 11, formation 4-3-3 |
| POTM | Mois / période officielle | Joueur du mois de la compétition | 1 |

La formation 4-3-3 est une **proposition de protocole**, pas une règle officielle
commune à toutes les récompenses. Les quotas doivent être adaptés à la source
avant la première comparaison, et rester fixes après lecture du test.
Il faut distinguer une équipe annuelle mondiale d'une équipe annuelle par
championnat. Ne pas attribuer automatiquement des labels mondiaux aux cinq ligues.

Il reste à choisir le média ou l'organisme de référence pour chaque mode et
championnat et à documenter ses labels. Les récompenses réelles peuvent dépendre
d'un vote ou d'un jury. Exemples de sources primaires à examiner, non intégrées :

- [UNFP : joueur du mois](https://www.unfp.org/ce-que-nous-faisons/les-trophees-unfp-du-joueur-du-mois/) pour les récompenses françaises.
- [Premier League : Player of the Month](https://www.premierleague.com/en/news/4106380) pour les nommés et le principe de vote/panel.
- [FIFPRO World 11](https://www.fifpro.org/en/world-11) pour une équipe annuelle mondiale votée par les joueurs, distincte d'une sélection par championnat.

Ces pages ne constituent pas un dataset de statistiques. Ne pas inventer leurs
labels, leurs nommés ni leurs dates. Prévoir aussi des statistiques sportives
documentées, leurs unités, leur licence et les dates de disponibilité : le dépôt
actuel de Luca fournit uniquement les historiques de reconnaissance du Ballon d'Or.

## Contrat proposé

Les CSV dans `data/selections/templates/` contiennent uniquement des en-têtes.
Ils ne contiennent aucune donnée. Les configurations dans `config/selections/`
sont des exemples non validés ; `authority` est vide et les confirmations sont
désactivées. Ne pas les activer sans avoir documenté et vérifié les données.

Colonnes communes :

- `period_end` : date ISO `YYYY-MM-DD`, fin de la fenêtre de statistiques,
  identique pour une période commune aux cinq championnats ;
- `competition` : exactement `Premier League`, `La Liga`, `Bundesliga`, `Serie A`
  ou `Ligue 1` ;
- `player_id`, `player` : identifiant stable et nom d'affichage ;
- variables proposées : `goals`, `assists`, `minutes`, `matches`, `team_wins`,
  `clean_sheets`, `saves`, agrégées sur la fenêtre documentée ;
- `position` : `GK`, `DEF`, `MID`, `FWD`, poste documenté, sans reconstruction
  depuis une sélection future ;
- historique seulement : `selected` (0/1), sélection de la source de référence,
  et `label_available_on`, date ISO de publication des labels du groupe.

La liste des variables est à adapter aux données réellement disponibles, pas à
remplir avec des nombres inventés. Les cellules numériques vides peuvent être
imputées par la pipeline ; une colonne entièrement absente doit être traitée dans
le cadrage avant validation du contrat.

Une ligne représente un joueur dans une période/compétition. Les doublons sont
refusés. Chaque groupe historique contient des sélectionnés et des
non-sélectionnés éligibles documentés. POTM exige exactement un gagnant par
groupe ; les équipes permettent plusieurs sélectionnés. Les dates de publication
des labels doivent être connues avant l'utilisation de ceux-ci dans un entraînement.
Ne pas utiliser le vote final, la sélection courante ou une note publiée après
l'annonce comme variable. La présence parmi les nommés doit être connue à la
date du scénario choisi, et ses biais de présélection documentés.

## Entraînement et évaluation

Neuf variantes comparent la référence numérique, la régression logistique,
l'arbre et la forêt avec les pipelines du projet. Les périodes restent entières,
tous championnats ensemble dans un pli. Imputation et standardisation sont
apprises sur l'entraînement seulement. La sélection maximise la précision de
l'équipe proposée puis son rappel en validation, avec ordre fixe en cas d'égalité.
Pour POTM, la précision à 1 mesure le gagnant correctement proposé.

Les quotas sont appliqués avant les métriques et lors de la prédiction :
un gardien, quatre défenseurs, trois milieux et trois attaquants dans les gabarits
d'équipe. Une réserve de candidats insuffisante à un poste provoque une erreur.
Les scores identiques sont départagés par identifiant, sans preuve de supériorité.
Les modèles par récompense peuvent apprendre sur plusieurs ligues ; chaque
classement et sélection reste propre à une période et une ligue.

Par défaut, trois périodes minimum pour le premier apprentissage, trois
validations successives et deux périodes finales de test nécessitent au moins
huit périodes. Le modèle choisi est réentraîné sur le développement puis testé
sans changer les paramètres sur le test. Les dates de publication des labels
d'entraînement doivent précéder la date de la période évaluée. Le rapport JSON
conserve le découpage, les neuf variantes, les résultats par groupe et les
empreintes des entrées. Les scores ne sont pas calibrés en probabilités.

## Commandes PowerShell après collecte et validation

Exemple TOTW (remplacer les chemins par des fichiers réellement collectés) :

```powershell
Copy-Item .\config\selections\totw.example.json .\config\selections\totw.json
code .\config\selections\totw.json
# Documenter authority, variables, sources, fenêtres, candidats, quotas et protocole.
# Activer les confirmations seulement après vérification effective.
.\.venv\Scripts\python.exe -X utf8 .\src\train_selection.py --data .\data\selections\totw_history.csv --config .\config\selections\totw.json --data-readme .\data\selections\TOTW_sources.md --output .\artifacts\selections\totw
.\.venv\Scripts\python.exe -X utf8 .\src\predict_selection.py --award TOTW --input .\data\selections\totw_candidates.csv --output .\outputs\classement_totw.csv
.\.venv\Scripts\python.exe -m streamlit run .\app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

La commande de prédiction accepte `--model` pour un autre artefact local.
Le CSV de candidats exclut `selected` et `label_available_on`. Sa période doit
être postérieure aux données apprises et aux labels utilisés. L'export contient
le classement et `predicted_selection`, marquant l'équipe ou le joueur proposé.
Les fichiers d'export existants sont refusés. Adapter les noms TOTW en TOTY,
TOTS ou POTM pour les autres modèles. L'interface refuse un artefact d'une autre
récompense. Charger seulement des modèles joblib locaux de confiance.

## Vérifications

Les tests couvrent les cibles multiples et POTM, les cinq ligues, les quotas,
la chronologie et les dates de publication, le choix sans test, les erreurs CSV,
la sauvegarde, la CLI, l'interface et l'absence de prédictions sans modèle.
Les métriques calculées pendant ces tests sont fictives et ne constituent pas
des résultats sur les récompenses réelles. Le travail de Luca reste inchangé.

Au 7 octobre 2026, **38 tests passent** sous Windows avec Python 3.13.1,
dont six tests de cette extension ; `pip check` ne signale aucun conflit.
Le navigateur vérifie les cinq modes et l'état sans modèle du mode TOTW.
Les modèles utilisés dans les tests restent fictifs et temporaires.
