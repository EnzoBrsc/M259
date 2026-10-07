# Terrain et podiums — interface M259

## Présentation et fidélité au modèle

Le terrain et les cartes s'inspirent de la présentation d'une équipe dans
Ultimate Team. Le dessin, les lignes et les cartes sont du HTML/CSS propre au
projet, sans copie d'assets EA et sans notes de joueurs inventées.

`src/football_visuals.py` reçoit directement les classements existants.
Pour TOTW/TOTS/TOTY, `select_squad` conserve les quotas documentés : un gardien,
quatre défenseurs, trois milieux, trois attaquants. Les lignes suivent l'ordre
FWD, MID, DEF, GK de haut en bas ; à l'intérieur d'une ligne, le rang détermine
l'ordre. Les données ne permettent pas de distinguer précisément arrière gauche,
arrière droit, ailier ou avant-centre : ces rôles ne sont pas ajoutés. Si le poste
est absent ou inconnu, aucun terrain trompeur n'est dessiné ; le tableau subsiste.

Le podium respecte `rank` (ou `rang` pour le Ballon d'Or), avec le deuxième à
gauche, le premier au centre et le troisième à droite. Il accepte aussi un ou
deux candidats. Pour POTM, les deuxième et troisième sont des candidats au podium,
pas des gagnants supplémentaires. Les scores restent affichés sans pourcentage,
sous le libellé « SCORE DU MODÈLE ». L'arrondi d'affichage à six décimales peut
masquer de faibles écarts ; les valeurs complètes sont dans les tableaux et CSV.
Les égalités sont départagées selon le protocole existant, sans preuve de
supériorité sportive. Tous les avertissements sur les sélections expérimentales
et l'évaluation rétrospective sont conservés.

## Photos et provenance

`assets/player_portraits.json` contient uniquement des URL, noms, fournisseurs,
dates de vérification et liens de provenance. Il couvre les joueurs recherchés
dans les équipes courantes des cinq ligues et les podiums de test du Ballon d'Or.
La collecte ne constitue pas un catalogue de tous les footballeurs.

- [FOX Sports, fiche Harry Kane](https://www.foxsports.com/soccer/harry-kane-player) :
  la collecte lit le nom de la personne dans les métadonnées de la fiche et son
  portrait `og:image`, puis vérifie la signature PNG de l'image distante.
- [Premier League / FPL](https://fantasy.premierleague.com/) : noms complets et
  identifiants du [bootstrap officiel](https://fantasy.premierleague.com/api/bootstrap-static/),
  rapprochement par noms concordants uniquement s'il est unique, portrait vérifié.
  Les noms originaux et l'identifiant du fournisseur sont conservés.
- [FC Bayern, Luis Díaz](https://fcbayern.com/en/teams/first-team/luis-diaz),
  [FC Bayern, Tom Bischof](https://fcbayern.com/fcbayerntv/de/video/portraitvideos/herren/tom-bischof),
  [FC Köln, Said El Mala](https://fc.de/mannschaften/maenner/kader/said-el-mala),
  [worldfootball.net, Janis Blaswich](https://www.worldfootball.net/player_summary/janis-blaswich/),
  [Playmakerstats, Lukas Kübler](https://www.playmakerstats.com/player/lukas-kubler/215722?epoca_id=153),
  [FC Barcelona, Lamine Yamal](https://www.fcbarcelona.com/en/football/first-team/players/129404/lamine-yamal-nasraoui-ebana),
  [ogol, Sadio Mané](https://www.ogol.com.br/jogador/sadio-mane/240701?epoca_id=151),
  [Liverpool FC, Virgil van Dijk](https://www.liverpoolfc.com/news/virgil-van-dijk-receives-special-honour-willem-ii) :
  compléments trouvés par recherche d'images et associés à leurs fiches nominatives,
  conservés dans `assets/additional_portraits.json`.

Rodri est relié explicitement à l'entrée FPL « Rodrigo 'Rodri' Hernandez Cascante »,
identifiant 220566 : cet alias vérifié figure aussi dans les compléments.

Les photos sont affichées depuis les serveurs des fournisseurs. Elles ne sont
pas copiées dans Git et aucune licence libre n'est présumée : les droits restent
ceux des photographes/fournisseurs. Les sources sont créditées sous la vue, dans
le titre du portrait et par le lien de chaque carte. Les tenues peuvent être
anciennes et ne constituent pas une affirmation sur le club actuel ni sur la
saison des données. Les portraits n'entrent jamais dans les variables du modèle.

Un nom sans portrait confirmé affiche ses initiales et « Photo indisponible ».
Les portraits distants nécessitent Internet et restent dépendants de leurs
serveurs. Les noms importés sont échappés ; seules les URL HTTPS de fournisseurs
autorisés peuvent être affichées. L'interface n'effectue aucune recherche réseau
au nom d'un joueur importé et n'exécute pas de JavaScript personnalisé.

## Reproduction

Les modèles et classements sont générés avec les commandes du README. Le
catalogue de portraits est versionné ; son renouvellement est facultatif :

```powershell
.\.venv\Scripts\python.exe -X utf8 -m src.collect_player_portraits
.\.venv\Scripts\python.exe -m streamlit run .\app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
.\.venv\Scripts\python.exe -m pytest -q
```

Aucune dépendance supplémentaire : la collecte utilise la bibliothèque standard
Python et pandas déjà installé. Le CSS est limité aux classes `fv-*`, avec une
adaptation aux écrans de moins de 600 px et aux préférences de mouvement réduit.

## Vérification du 7 octobre 2026

49 tests et 14 sous-tests passent sous Python 3.13.1 Windows. Les contrôles ajoutés
vérifient les quotas et l'identité des joueurs sur le terrain, le podium basé sur
le rang, les petits effectifs, l'échappement des noms importés, les fournisseurs
autorisés et le parcours Streamlit réel des cinq modes. Le catalogue contient
68 portraits pour 118 joueurs recherchés ; les 50 autres restent explicitement
sans photo. Aucun portrait n'est inventé.
