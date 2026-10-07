# Cheminement et bilan du projet Ballon d'Or

État vérifié le **7 octobre 2026**, sur la branche `ami/modeles-interface`. Ce document décrit le travail effectivement présent ; il ne remplace pas le cadrage ou la documentation des données de Luca.

## Objectif et organisation

Le groupe veut montrer une démarche de machine learning qui classe les candidats d'une édition du Ballon d'Or avec les seules informations disponibles avant le vote. La cible prévue est binaire, gagnant/non-gagnant, sur des lignes joueur/édition. L'évaluation principale porte sur le rang du vrai gagnant parmi les candidats.

Luca est responsable du cadrage, des sources, de la collecte, du nettoyage, de la construction des variables et de l'exploration. La présente branche prend en charge les modèles, la prédiction, l'interface et le guide. Le nettoyage et le notebook n'ont pas été modifiés. Le README a été enrichi, les versions existantes des dépendances ont été conservées et joblib/Streamlit ajoutés ; ces fichiers partagés seront à relire conjointement lors de l'intégration.

## État des apports de Luca

| Fichier attendu | État observé | Conséquence |
| --- | --- | --- |
| `docs/cadrage.md` | Absent | Périmètre du prix, éditions et date de disponibilité à confirmer |
| `data/README.md` | Absent | Sources, unités, schéma et provenance temporelle à fournir |
| `src/prepare_data.py` | Absent | Nettoyage et historiques à vérifier ensemble après livraison |
| `data/processed/ballon_or.csv` | Absent | Impossible d'entraîner ou d'évaluer un modèle réel |
| `notebooks/01_exploration.ipynb` | Absent | Conclusions exploratoires et choix des variables à intégrer |

Les branches distantes disponibles au début du travail étaient `main` et `enzo` ; aucune livraison de Luca n'y était présente. Le ZIP évoqué dans un ancien échange n'a été ni trouvé, ni lu, ni utilisé. Aucun contenu ne lui est attribué.

Un exemple de configuration propose des noms de colonnes et des statistiques **fictifs**. Ils ne sont pas considérés comme validés. Le code impose des listes de variables explicites et des confirmations temporelles après audit humain. Le modèle ne peut pas déterminer à lui seul si une donnée a été réellement disponible avant le vote.

## Choix techniques effectivement implémentés

Le code utilise scikit-learn et des pipelines plutôt qu'un réseau profond, conformément aux quatre familles demandées. Une référence simple trie une statistique numérique choisie à l'avance ; elle ne lit pas la cible. Les alternatives sont une régression logistique, un arbre et une forêt aléatoire. Neuf configurations prédéfinies sont évaluées, avec une graine fixe et une forêt limitée à un processus pour un environnement scolaire sur ordinateur personnel.

Le découpage conserve les éditions entières. Les deux dernières éditions sont réservées au test final par défaut. Les trois dernières éditions de développement servent de validations successives, chacune précédée d'un entraînement sur les seules éditions antérieures. Ce protocole par défaut nécessite huit éditions au minimum. Les dates numériques sont contrôlées, les noms et l'édition sont exclus des variables et les classes doivent contenir exactement un gagnant par édition.

Les médianes, l'échelle et les catégories sont apprises sur chaque ensemble d'entraînement. La sélection maximise le top 1 puis le top 3 en validation, avec une règle fixe en cas d'égalité. Le modèle est figé et réentraîné sur le développement avant de mesurer le test final. Le test ne sert ni à choisir une famille ni à régler les paramètres.

Le classement exporte joueur, score et rang par édition. Les importations vérifient le contrat du modèle, les types, les doublons et les colonnes supplémentaires. Les candidats d'éditions déjà apprises sont refusés pour empêcher de présenter une prédiction sur l'entraînement comme une évaluation future. Les scores ne sont pas calibrés en probabilités de victoire. Les égalités utilisent un départage alphabétique arbitraire et sont signalées.

Streamlit importe le même module de prédiction que la CLI. Il affiche les erreurs, un tableau, un graphique et un bouton d'export. En l'absence de modèle réel, il affiche cet état sans résultat de remplacement. L'environnement vérifié est Windows avec Python 3.13.1, scikit-learn 1.9.1 et Streamlit 1.65.0.

## Vérifications et résultats disponibles

Les contrôles techniques portent sur des fixtures **exclusivement fictives**, conservées dans les tests et des dossiers temporaires. Ils vérifient notamment la séparation chronologique, les statistiques apprises, les noms de variables révélant le vote, les erreurs CSV, la sauvegarde/relecture du modèle et l'accord entre le classement CLI et celui de l'interface. Le parcours complet lance l'entraînement dans un processus distinct, charge le modèle dans la CLI de prédiction, importe les candidats dans Streamlit et vérifie le tableau ainsi que le graphique.

Les **16 tests passent** dans l'environnement Windows/Python 3.13.1 et `pip check` ne signale aucun conflit. L'interface a aussi été ouverte et contrôlée dans un navigateur local : elle indique correctement le modèle manquant et désactive l'import tant qu'aucun modèle réel n'est disponible. Le contrôle final du CSV refuse les lignes dont le nombre de champs ne correspond pas à l'en-tête, pour éviter un décalage silencieux des colonnes.

**Aucun résultat sportif réel n'est disponible.** Aucune famille n'a été retenue pour les données du Ballon d'Or et aucun taux top 1/top 3 réel n'est publié. Les modèles entraînés et les métriques produits temporairement par les tests servent seulement à vérifier le logiciel.

Les commandes de reproduction et les chemins des sorties sont dans le README. Le script d'entraînement refuse de créer des artefacts si les entrées requises manquent ; les dossiers `artifacts/`, `outputs/` et `.test-artifacts/` sont ignorés par Git, tout comme `.venv` et les secrets.

## Intégration à réaliser avec Luca

1. Intégrer son cadrage, ses sources et son exploration sans écraser son nettoyage ou son notebook. Expliquer ici les choix et constats réellement documentés.
2. Définir ensemble les noms, unités, périodes, dates de disponibilité et historiques. Vérifier les décalages d'éditions et exclure les informations issues du vote courant.
3. Fixer le protocole chronologique et la référence simple avant la première évaluation. Créer `config/model_config.json` à partir du schéma réel ; ne pas utiliser les confirmations de l'exemple comme preuve.
4. Exécuter la comparaison ; conserver les paramètres, empreintes des fichiers, résultats de validation et test final dans les artefacts locaux.
5. Compléter ce bilan avec le modèle réellement retenu, les gagnants prédits, les top 1/top 3 par édition, les égalités et les erreurs concrètes. Ne pas retoucher le protocole après consultation du test sans déclarer une nouvelle étude et un nouveau test indépendant.
6. Tester l'import de candidats réels dont les statistiques sont connues avant vote et relire le guide avec le binôme avant la remise.

## Limites à discuter

Le nombre d'éditions, les différences de périodes et de postes, le choix des candidats et les critères subjectifs des votants limitent la généralisation. Un gagnant absent des candidats ne peut pas être retrouvé. Le modèle binaire pondéré ne produit pas une distribution de probabilité sur une édition et aucun travail de calibration n'a encore été réalisé. Les historiques n'apportent une information légitime que s'ils sont strictement antérieurs. Une bonne performance de classement ne prouve pas une causalité et n'est pas une garantie pour une édition future.

## Références techniques consultées

- [scikit-learn : prétraitement et fuites de données](https://scikit-learn.org/stable/common_pitfalls.html) pour la séparation des ajustements et la sélection sans consultation du test final.
- [Streamlit : AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest) pour les tests d'import et d'affichage de l'interface.

Ces références concernent le logiciel et la méthode ; elles ne sont pas des sources de données sur le Ballon d'Or.
