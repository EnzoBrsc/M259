# Passation à la partie modèles

## État livré

Branche : `luca/donnees-analyse`. Les quatre étapes sont cadrage, sources,
préparation/test des données et exploration. Aucun modèle ni interface n'est
ajouté. Le brut est un snapshot de 2 095 lignes / 69 éditions ; le traité
contient 984 lignes / 30 éditions de 1995 à 2025 (2020 annulé).
Les 30 gagnants sont contrôlés contre une source UEFA indépendante.

Vérifications effectuées sous Python 3.13.15 : `pip check` sans dépendance
incohérente, 11 tests réussis, notebook exécuté avec code de sortie 0 (7 cellules
de code, 5 figures), figures contrôlées visuellement. Le snapshot exporté depuis
Git est également accepté par le contrôle SHA-256 et la préparation.

## Reproduire sous Windows / PowerShell

Ouvrir un terminal à la racine du dépôt M259 :

```powershell
python --version  # Python 3.13.x attendu
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-analysis.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe src/prepare_data.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe src/run_exploration.py
```

La préparation et les tests n'ont pas besoin du réseau. L'installation initiale
des dépendances en a besoin. L'exécution du notebook utilise explicitement le
Python qui lance `run_exploration.py` ; aucun noyau global n'est installé.
Le notebook enregistré conserve les tableaux et cinq figures de l'exécution.
Pour produire une copie plutôt que remplacer ses sorties :

```powershell
.\.venv\Scripts\python.exe src/run_exploration.py --output ..\work\exploration_verifiee.ipynb
```

Dans VS Code, ouvrir `notebooks/01_exploration.ipynb`, choisir **Select Kernel →
Python Environments → .venv**, puis **Run All**. Les extensions Python et Jupyter
doivent être installées. Les commandes ci-dessus ne nécessitent pas l'activation
PowerShell du venv.

Si un terminal restreint bloque les fichiers temporaires lors de l'installation,
rediriger TEMP et TMP vers un dossier local de travail avant les commandes :

```powershell
New-Item -ItemType Directory -Force ..\work\temp | Out-Null
$env:TEMP = (Resolve-Path ..\work\temp).Path
$env:TMP = $env:TEMP
```

## Contrat pour le binôme

- Dataset : `data/processed/ballon_or.csv`.
- Liste obligatoire des entrées : `data/processed/features.json`.
- Types, valeurs manquantes, sources et licences : `data/README.md`.
- Protocole d'évaluation : `docs/cadrage.md`.
- Contrôles et effectifs : `data/processed/quality_report.json`.
- Exploration exécutée : `notebooks/01_exploration.ipynb`.

Exemple de sélection, sans entraîner de modèle :

```python
import json
from pathlib import Path
import pandas as pd

root = Path.cwd()  # racine du dépôt
schema = json.loads((root / "data/processed/features.json").read_text(encoding="utf-8"))
df = pd.read_csv(root / "data/processed/ballon_or.csv")
columns = schema["numeric_features"]
train = df.loc[df["split"].eq("train")]
X_train = train[columns]
y_train = train["winner"]
```

Huit variables historiques seulement. Ne pas inclure le poste (disponible
uniquement en test), le nom, l'identifiant, l'année, le groupe, l'année d'audit
ou la cible. Les meilleurs/derniers rangs **antérieurs** sont autorisés ; le rang
du vote **courant** ne l'est pas. Imputer les trois colonnes historiques nullables
avec un pipeline appris sur le train. Ne pas entraîner directement depuis le brut.

Train : 1995–2015 (21 éditions, 714 lignes). Validation : 2016–2021
(5 éditions, 150 lignes). Test : 2022–2025 (4 éditions, 120 lignes).
Grouper par édition ; métriques principales top 1 et top 3 par édition.
L'historique évolue annuellement avec les résultats devenus disponibles.

## Points à transmettre explicitement

Ce dataset ne contient pas les performances sportives de la saison. Il mesure
la reconnaissance passée. Il ne contient pas nécessairement tous les nommés
officiels, notamment pour les anciennes éditions. Les noms restent une limite
d'identification malgré la correction de Luis Suárez et de l'accent de Vinícius.
Le test est petit et les périodes d'évaluation/règles varient. Aucun pourcentage
de réussite prédictive n'a encore été calculé.

375 lignes n'ont pas d'historique observé. 864 postes sont inconnus ; la présence
du poste uniquement dans les quatre années de test justifie son exclusion.
Ne pas utiliser le test pour sélectionner les variables ou les paramètres.

## Partager le travail avec Git

Les commits sont locaux jusqu'à un envoi explicite. Depuis cette branche :

```powershell
git push -u origin luca/donnees-analyse
```

Après cet envoi, le binôme peut intégrer la branche sur la sienne :

```powershell
git fetch origin
git merge origin/luca/donnees-analyse
```

Enregistrer ses changements avant la fusion et résoudre les éventuels conflits.
Une pull request permet une relecture avant intégration à `main`.
