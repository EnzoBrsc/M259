# Données du Ballon d’Or masculin

## Sources et attribution

Le fichier brut `raw/ballon_dor_all_years.csv` est conservé **sans modification**
depuis [SpoicyCurri/ballon-d-ata](https://github.com/SpoicyCurri/ballon-d-ata),
commit `f566a8efca758ec27b3c4d53a4f8f4aeb20e4803`, téléchargé le 7 octobre 2026.
Le dépôt indique une collecte des tables annuelles de Wikipédia. Il s'agit d'une
source secondaire communautaire, pas d'un export officiel de France Football.
`raw/provenance.json` donne l'URL immuable, le SHA-256, les pages originales
par édition, les effectifs et les valeurs manquantes.

La notice MIT du dépôt source (Fergus Walden, 2025) est conservée dans
`raw/LICENSE.upstream.txt`. Les contenus dérivés de Wikipédia sont attribués
à leurs contributeurs ; voir les pages et historiques liés dans le manifeste,
ainsi que [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
La licence MIT du code source ne remplace pas les droits des contenus d'origine.
Les transformations locales sont décrites ci-dessous et les données dérivées
sont proposées sous CC BY-SA 4.0 dans la mesure applicable. L'amont ne fournit
pas les identifiants de révision Wikipédia : le CSV figé est reproductible,
mais pas nécessairement une nouvelle extraction des pages actuelles.

`raw/winner_checks.csv` contient une vérification indépendante des **30 gagnants
de 1995–2025**, transcrits depuis [l'historique UEFA](https://www.uefa.com/news-media/news/0287-195e642735da-0594342b9554-1000--history-of-the-ballon-d-or/),
consulté le 7 octobre 2026. Ils concordent (accent différent pour Zidane).
Cette vérification n'atteste pas tous les rangs, clubs ou postes.
L'UEFA conserve les droits de sa publication ; seules les données factuelles
nécessaires au contrôle sont reprises, pas le texte de l'article.

## Couverture et limites de qualité

Le brut contient 2 095 lignes, 69 éditions de 1956 à 2025, sans 2020 (annulé),
aucun doublon exact joueur/édition, un gagnant par édition. La table traitée
retient 984 lignes sur 30 éditions de 1995–2025 ; 1956–1994 servent uniquement
à initialiser les historiques. Train : 714 lignes/21 éditions ; validation :
150 lignes/5 éditions ; test : 120 lignes/4 éditions.
Le nombre de lignes varie selon les années. Certaines tables anciennes ne
contiennent que les joueurs ayant reçu des points ; ne pas appeler les lignes
des « nominations exhaustives ». Le jeu est rétrospectif et sélectionné par les
résultats publiés, ce qui limite sa validité pour une prévision sur les nommés.

Poste absent sur 1 975 lignes : seuls 2022–2025 ont des postes. Nationalité
absente sur les 150 lignes de 2016–2021 (hors 2020). 146 points et 31 pourcentages
sont absents. Ces manques restent visibles et ne sont pas remplis depuis le futur.
Les noms de clubs sont historiques, peuvent changer et peuvent contenir `~~~`
pour plusieurs clubs. Aucun enrichissement de buts, passes ou trophées n'est fait.

## Colonnes brutes (valeurs textuelles du CSV)

| Colonne | Sens | Utilisation |
|---|---|---|
| year | Année de l'édition | Groupement chronologique |
| rank | Rang final, égalités possibles, encodé en décimal | Cible et historique décalé seulement |
| player | Nom publié | Identité après normalisation |
| club | Club(s) indiqué(s) | Métadonnée, pas une entrée ML |
| nationality | Nationalité, parfois absente | Métadonnée, pas une entrée ML |
| points | Points du vote, systèmes variables | Brut seulement, jamais entrée ML |
| percent | Pourcentage fourni/calculé par l'amont | Brut seulement, jamais entrée ML |
| position | Poste lorsqu'il existe | Exploration seulement |

## Nettoyage et contrat avec le binôme

Commande : `python src/prepare_data.py` (bibliothèque standard, Python 3.13).
Le script contrôle le SHA-256 du snapshot, les colonnes, années, rangs entiers
positifs. `.gitattributes` protège les octets du brut contre la conversion
automatique des fins de ligne par Git, notamment sous Windows. Il vérifie les
doublons, gagnants et valeurs numériques optionnelles. Il retire les
espaces superflus et normalise les chaînes en Unicode NFC. Les clubs multiples
deviennent ` | `. Les valeurs absentes de club/nationalité/poste deviennent
`Unknown`, sans reconstruction. Les dates et points ne sont pas exportés.

Les identifiants sont dérivés des noms normalisés ; les homonymes Luis Suárez
sont séparés par leur période (1958–1965 : joueur espagnol ; 2011–2021 : joueur
uruguayen). Les plages sont explicites et toute autre occurrence de cet homonyme
déclenche une erreur. Références : [Luis Suárez espagnol](https://www.uefa.com/news-media/news/0283-187370f4166c-84a2b286587c-1000--remembering-spain-s-football-icon-luis-suarez/)
et [Luis Suárez à Barcelone en 2015](https://www.uefa.com/uefachampionsleague/news/0252-0d043e270c4f-0d9b8ac77738-1000--best-player-reporters-view-luis-suarez/).
La variante d'accent `Vinicius Junior` / `Vinícius Júnior` partage explicitement
le même identifiant, sans modifier le nom d'affichage d'origine.
Les autres variations d'identité restent une limite ; le script ne fait pas de
rapprochement flou automatique. L'ordre final est édition puis identifiant,
jamais rang final. Les ex æquo au rang 3 comptent tous comme top 3 historique.

Le schéma exact de `processed/ballon_or.csv` est le suivant :

| Colonne | Type | Règle / rôle |
|---|---|---|
| edition | int | 1995–2025 sauf 2020 ; groupe, pas entrée ML |
| player_id | str | Identité stable ; pas entrée ML |
| player | str | Nom d'affichage ; pas entrée ML |
| club | str | Métadonnée, `Unknown` si absent |
| nationality | str | Métadonnée, `Unknown` si absent |
| position | str | Forward/Midfielder/Defender/Goalkeeper/Unknown ; exploration |
| previous_appearances | int | Nombre d'apparitions observées avant l'édition |
| previous_top3 | int | Nombre de rangs ≤ 3 avant l'édition |
| previous_wins | int | Nombre de rangs = 1 avant l'édition |
| previous_best_rank | int nullable | Meilleur rang antérieur ; vide si aucun |
| previous_last_rank | int nullable | Rang de la dernière apparition antérieure ; vide si aucune |
| years_since_previous | int nullable | Écart en années calendaires ; vide si aucune apparition |
| appeared_previous_edition | int 0/1 | Présent à l'édition attribuée précédente (2019 pour 2021) |
| has_history | int 0/1 | Au moins une apparition antérieure observée |
| history_last_edition | int nullable | Année de la dernière apparition ; audit, pas entrée ML |
| winner | int 0/1 | Cible, issue du rang final courant |
| split | str | train 1995–2015 / validation 2016–2021 / test 2022–2025 |

**Sélectionner exclusivement `features.json["numeric_features"]` pour X**,
et `winner` pour y. Le poste est exclu de X : il est absent de toutes les lignes
d'entraînement/validation et renseigné uniquement dans le test. Les trois
historiques nullables doivent être imputés dans un pipeline ajusté sur le train,
ou traités par un modèle compatible avec les valeurs manquantes. Un historique
nul signifie aucune apparition observée, pas aucune performance sportive.

Les compteurs avancent seulement après avoir produit toutes les lignes d'une
édition. Les résultats des éditions déjà passées peuvent alimenter l'historique
de l'année suivante, même en validation/test : voir le scénario annuel dans
`docs/cadrage.md`. `quality_report.json` conserve les contrôles et manques.
Le CSV, le manifeste des entrées et le rapport sont régénérés sans réseau.

Tests : `python -m unittest discover -s tests -v`. Ils vérifient notamment que
le vote courant ou des données futures ne changent pas les entrées présentes.
Ne pas utiliser le brut comme table d'entraînement.
