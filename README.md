# M259 — Projet de machine learning

Espace de travail commun pour notre projet du module M259.

Le dépôt contient la configuration de départ pour Python et les notebooks Jupyter dans VS Code. Les scripts, notebooks et données du projet seront ajoutés au fur et à mesure.

## Installation sur un nouvel ordinateur

Installer Git, Python 3.13 et VS Code, puis exécuter dans un terminal :

```powershell
git clone https://github.com/EnzoBrsc/M259.git
cd M259
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
code .
```

Dans VS Code, installer les extensions recommandées **Python**, **Pylance** et **Jupyter**. L'interpréteur prévu est celui du dossier `.venv`. Pour un notebook, choisir **Select Kernel → Python Environments → .venv** si VS Code le demande.

Sur macOS/Linux, utiliser `.venv/bin/python` à la place de `.\.venv\Scripts\python.exe`.

L'environnement fournit NumPy, pandas, Matplotlib, seaborn, scikit-learn et un noyau Jupyter. Le dossier `.venv` reste local : chaque personne crée son propre environnement.

## Travailler ensemble

1. Le propriétaire invite son binôme depuis [Settings → Collaborators → Add people](https://github.com/EnzoBrsc/M259/settings/access) sur GitHub. L'ami doit accepter l'invitation pour pouvoir envoyer ses modifications.
2. Chaque personne clone le dépôt sur son ordinateur et ouvre le dossier dans Codex ou son éditeur.
3. Avant une nouvelle tâche, revenir sur `main` avec `git switch main`, puis récupérer les dernières modifications avec `git pull --ff-only` (enregistrer d'abord les changements en cours).
4. Pour une nouvelle tâche, créer une branche : `git switch -c nom-de-la-tache`.
5. Enregistrer et envoyer les modifications :

```bash
git add .
git commit -m "Description des modifications"
git push -u origin HEAD
```

6. Ouvrir une pull request sur GitHub pour relire et fusionner les changements. Éviter de modifier le même notebook en même temps.

## Fichiers à conserver localement

Les environnements Python, les caches et les fichiers `.env` sont ignorés. Ne pas ajouter de mots de passe, de clés API ou de données personnelles au dépôt.
