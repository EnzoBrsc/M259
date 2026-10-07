# Statistiques réelles et sélections expérimentales M259

Le 7 octobre 2026, le groupe a choisi des sélections expérimentales sur des statistiques réelles. Aucun joueur, match, but ou passe n'est simulé. **Les labels ne sont pas des récompenses officielles** : ils sont calculés par la règle M259 ci-dessous. Le test mesure la reproduction de cette règle, pas la prévision d'un vote.

## Sources et snapshots

- [Jase Ziv — worldfootballR_data](https://github.com/JaseZiv/worldfootballR_data) : releases `fb_big5_advanced_season_stats` (FBref standard, défense et gardiens, mises à jour en septembre 2025) et `fb_advanced_match_stats` (résumés joueurs des cinq ligues, septembre 2025). Historique retenu : saisons terminées en **2018–2025**, apparitions du **1 août 2024 au 31 janvier 2025**. Les saisons 2025/26 incomplètes de cette archive, le mois partiel de février 2025 et les apparitions 2025/26 clairsemées sont exclus.
- [Mahadi — top5-football-dataset](https://github.com/m-mahadi/top5-football-dataset) : `data/master/player_seasons.csv`, commit `8940299c2c56c2c0932d3caf292336f5e1689893` du 18 août 2026. Saison **2025/26** uniquement pour les nouveaux candidats. Buts/passes/minutes/matchs/postes : bloc FBref ; défense et gardiens : bloc SofaScore. Les données EA/SoFIFA, notes SofaScore, valeurs marchandes et sélections TOTW sont exclues.
- **ESPN** : API publique `https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates=YYYYMMDD` et `.../{league}/summary?event={id}`. Codes `eng.1`, `esp.1`, `ger.1`, `ita.1`, `fra.1`. Recherche quotidienne du **1 septembre au 7 octobre 2026** ; seulement matchs marqués terminés. Statistiques des apparitions et résultats d'équipe de la même feuille de match. Dernières apparitions disponibles : **20 septembre 2026** dans les cinq ligues consultées ; 153 matchs terminés collectés.

`sources_manifest.json` enregistre URL, taille et SHA-256 de chaque snapshot lu. Au rejeu, une empreinte modifiée provoque une erreur. Les gros originaux restent locaux dans `artifacts/source_cache/`, ignoré par Git. Les endpoints directs SofaScore et Transfermarkt ayant répondu 403 n'ont pas été contournés ni utilisés.
Les droits des fournisseurs restent applicables : une licence de code d'un collecteur ne donne pas une licence générale sur ses données. Utilisation scolaire ; statistiques non vérifiées indépendamment match par match. Le CSV Mahadi comporte des jointures de noms entre fournisseurs, avec des manquants et des erreurs d'identité possibles.

## Périodes et population

| Mode | Historique | Nouveaux candidats |
| --- | --- | --- |
| TOTS | 2017/18–2024/25, coupure au 30 juin | Saison 2025/26 : `2026-06-30` |
| TOTY | **Même protocole de saison que TOTS**, demandé par le groupe | Même CSV 2025/26 ; pas une année civile ni le FIFPRO World 11 |
| TOTW | Semaines lundi–dimanche ; dernier match du joueur dans chaque semaine | Dernière apparition disponible dans la semaine du 14–20 septembre 2026 |
| POTM | Mois août 2024–janvier 2025 | Cumul de septembre 2026 |

Classement séparé par ligue. Les CSV de saison incluent tous les joueurs observés ayant **900 minutes minimum**, dont les grands joueurs et les non-sélectionnés nécessaires à l'apprentissage. Aucun filtrage selon une récompense future. Les totaux de saison ne sont jamais découpés artificiellement en matchs/mois.
Pour les matchs, seuls les joueurs ayant une apparition observée sont inclus. Poste `SUB` ou absent : dernier poste connu d'une apparition **antérieure** du même joueur, jamais un match futur. POTM utilise le dernier poste documenté à la fin du mois, et cumule aussi les performances des apparitions sans poste. Un joueur sans aucun poste connu à la coupure est exclu et listé dans `processed/quality_report.json`.
L'historique couvre le **pool observé dans l'archive**, avec une collecte incomplète : ce n'est pas la preuve d'une couverture exhaustive des candidats de chaque ligue. Les métriques restent conditionnelles à ce pool.

## Colonnes et unités

Une ligne = joueur/période/ligue. `period_end` est ISO ; `competition` appartient aux cinq ligues ; `player_id` est préfixé `fbref:`, `sofascore:` ou `espn:`. Sans ID SofaScore, `name-birth:` est un hash déterministe du nom et de l'année de naissance. Aucune jointure d'identité entre fournisseurs n'est supposée. ID et nom ne sont pas des variables explicatives.
`position` : `GK`, `DEF`, `MID`, `FWD`, premier poste déclaré ; ailes = FWD, latéraux/pistons = DEF. L'ID sert aussi à départager les égalités.

- Saison : comptes `goals`, `assists`, `minutes`, `matches`, `tackles`, `interceptions`, `saves`, `goals_conceded`, `clean_sheets`. Les trois dernières variables sont **réservées au gardien** et valent zéro par définition pour les joueurs de champ, dans les deux sources. Manquants des gardiens conservés vides.
- Match/mois : comptes `goals`, `assists`, `matches`, `shots_on_goal` (tirs cadrés), `yellow_cards`, `red_cards`, `team_wins`, `clean_sheets`, `goals_conceded`. Les trois dernières décrivent le **résultat de l'équipe entière lors de l'apparition**, pas uniquement les minutes du joueur. Même approximation dans les deux sources. TOTW garde le dernier match ; POTM additionne les comptes. ESPN ne fournit pas les minutes individuelles dans ces données : elles ne sont pas inventées et n'entrent pas dans ces modèles.

Les manquants numériques restent vides ; l'imputation du modèle est apprise uniquement sur l'entraînement. Passages par plusieurs clubs : comptes FBref par club additionnés, totaux SofaScore saisonniers répétés pris au maximum. Doublons exacts d'apparitions retirés ; doublons contradictoires refusés. Deux lignes historiques sans poste (1 et 5 minutes) sont exclues, sous le seuil de 900 minutes. Le rapport de qualité donne les doublons, exclusions et manquants.

## Règle M259 v1, fixée avant comparaison

Équipes : **GK 1 / DEF 4 / MID 3 / FWD 3** ; POTM : un joueur tous postes confondus. Égalités départagées par ID alphabétique. Les semaines/ligues sans pool suffisant sont exclues et documentées.
Avec `n = minutes / 90`, scores de saison :

- FWD : `(4 × buts + 3 × passes) / n`.
- MID : `(4 × buts + 3 × passes + 0,5 × tacles + 0,5 × interceptions) / n`.
- DEF : `(4 × buts + 3 × passes + tacles + interceptions) / n`.
- GK : `4 × clean_sheets / matchs + arrêts / n − buts_concédés / n`.

TOTW/POTM : `4 × buts + 3 × passes + 0,25 × tirs_cadrés + victoires − 0,5 × jaunes − 2 × rouges`, plus `2 × clean_sheets − 0,5 × buts_concédés` pour GK/DEF. Le cumul mensuel favorise les joueurs avec plus de matchs.
Pondérations **arbitraires et scolaires**, pas une mesure validée du talent. Contexte, adversaires, influence tactique et arrêts match par match manquent. Un manquant contribue zéro à la **règle**, sans être remplacé par zéro dans les observations du modèle : un joueur mal documenté peut être pénalisé.
Le score composite reste dans `*_rule_audit.csv`, exclu des variables du modèle. Les labels sont déterminés par les statistiques utilisées : **imitation d'une règle avec circularité assumée**, pas découverte des préférences d'un jury. Appliquer directement cette règle fournit la référence exacte et peut être préférable au modèle appris.

Historique : `selected` (0/1) et `label_available_on=period_end`. Cette dernière est une **coupure analytique de disponibilité potentielle**, pas une annonce officielle ni une date de collecte historique. Les labels sont reconstruits le 7 octobre 2026. Configuration : `label_kind=derived_statistical`, `availability_kind=retrospective_reconstruction`. Les périodes sont séparées chronologiquement ; les archives ne prouvent pas que chaque valeur exacte existait avant un vote historique. Aucune métrique n'est présentée comme une prévision réellement effectuée à l'époque.

## Fichiers et reproduction PowerShell

`processed/season_history.csv`, `season_candidates.csv`, `season_rule_audit.csv` sont communs à TOTS/TOTY. `totw_*`, `potm_*` sont séparés. Configurations : `config/selections/{award}.json`, distinctes des gabarits `.example.json`. Modèles : `artifacts/selections/` ; exports : `outputs/` ; rapports légers : `docs/resultats_selections/`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements-data.txt
.\.venv\Scripts\python.exe -X utf8 .\src\collect_selection_data.py --download
.\.venv\Scripts\python.exe -X utf8 .\src\setup_selection_models.py
.\.venv\Scripts\python.exe -m streamlit run .\app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Sans `--download`, le collecteur rejoue le cache vérifié. Un snapshot modifié nécessite un nouvel audit. Le setup refuse les dossiers de modèles déjà remplis : conserver le run précédent ailleurs avant un nouvel entraînement. Aucun modèle n'est supprimé automatiquement.
L'ami peut utiliser les CSV nettoyés versionnés et exécuter directement `setup_selection_models.py` avec les dépendances principales, sans pyreadr ni téléchargement.
Le modèle est choisi sur validation seulement. Après le test figé, le même modèle et les mêmes paramètres sont réentraînés sur tout l'historique pour la production. Le rapport distingue le modèle évalué de l'artefact réentraîné ; aucune nouvelle métrique de test n'est calculée sur ce dernier.
