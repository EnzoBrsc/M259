"""Catalogue de portraits distants : identités vérifiées chez les fournisseurs.

Ne télécharge aucun fichier image dans le dépôt et ne recherche jamais au nom
d'un utilisateur de l'interface. À lancer après la génération des classements.
"""

import concurrent.futures
import html
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def name_key(name):
    folded = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-")


def fetch_portrait(name):
    source = f"https://www.foxsports.com/soccer/{name_key(name)}-player"
    try:
        with urlopen(Request(source, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as response:
            page = response.read().decode("utf-8")
        people = []
        for block in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
            obj = json.loads(block)
            if isinstance(obj, dict) and obj.get("@type") == "Person":
                people.append(obj.get("name", ""))
        if name_key(name) not in {name_key(p) for p in people}:
            return name, None, "Identité non confirmée sur la fiche"
        match = re.search(r'<meta property="og:image" content="([^"]+)"', page)
        if not match:
            return name, None, "Portrait absent"
        image = html.unescape(match.group(1))
        if not re.fullmatch(r"https://b\.fssta\.com/uploads/application/soccer/headshots/[1-9]\d*\.png", image):
            return name, None, "Image autre qu'un portrait identifié"
        with urlopen(Request(image, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as response:
            signature = response.read(24)
            if not response.headers.get("Content-Type", "").startswith("image/") or not signature.startswith(b"\x89PNG\r\n\x1a\n"):
                return name, None, "Portrait indisponible"
        return name, {"name": name, "image_url": image, "source_url": source,
                      "provider": "FOX Sports", "verified_on": date.today().isoformat()}, None
    except (OSError, ValueError) as exc:
        return name, None, str(exc)


def fpl_portraits(names):
    """Noms complets concordants et uniques ; aucun rapprochement par seul patronyme."""
    with urlopen("https://fantasy.premierleague.com/api/bootstrap-static/", timeout=20) as response:
        players = json.load(response)["elements"]
    found = {}
    for name in sorted(names):
        tokens = name_key(name).split("-")
        matches = [p for p in players if len(tokens) >= 2 and set(tokens).issubset(
            set(name_key(p["first_name"] + " " + p["second_name"]).split("-")))]
        if len(matches) != 1:
            continue
        p = matches[0]
        image = f"https://resources.premierleague.com/premierleague/photos/players/250x250/p{int(p['code'])}.png"
        try:
            with urlopen(image, timeout=15) as response:
                if not response.read(24).startswith(b"\x89PNG\r\n\x1a\n"):
                    continue
            found[name_key(name)] = {"name": name, "image_url": image,
                                     "source_url": "https://fantasy.premierleague.com/",
                                     "provider": "Premier League / FPL", "verified_on": date.today().isoformat(),
                                     "source_identity": p["first_name"] + " " + p["second_name"], "source_id": p["code"]}
        except OSError:
            continue
    return found


def main():
    import pandas as pd

    names = set()
    for award in ("tots", "toty", "totw", "potm"):
        path = ROOT / "outputs" / f"classement_{award}.csv"
        if path.is_file():
            frame = pd.read_csv(path)
            selected = frame.loc[frame.predicted_selection] if award != "potm" else frame.loc[frame["rank"].le(3)]
            names.update(selected.player)
    path = ROOT / "outputs/classement_test_2022_2025.csv"
    if path.is_file():
        names.update(pd.read_csv(path).query("rang <= 3").joueur)
    if not names:
        raise SystemExit("Générer les classements avant de rechercher leurs portraits.")
    target = ROOT / "assets/player_portraits.json"
    existing = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
    entries, missing = existing.get("portraits", {}), {}
    missing_names = {n for n in names if name_key(n) not in entries}
    try:
        entries.update(fpl_portraits(missing_names))
    except (OSError, ValueError, KeyError) as exc:
        print(f"FPL indisponible : {exc}")
    additions = ROOT / "assets/additional_portraits.json"
    if additions.is_file():
        for entry in json.loads(additions.read_text(encoding="utf-8")):
            entries[name_key(entry["name"])] = entry
    missing_names = {n for n in names if name_key(n) not in entries}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for name, portrait, error in pool.map(fetch_portrait, sorted(missing_names)):
            if portrait:
                entries[name_key(name)] = portrait
            else:
                missing[name] = error
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps({"retrieved_on": date.today().isoformat(),
                                 "portraits": entries, "unavailable": missing}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(entries)}/{len(names)} portraits confirmés ; {len(missing)} replis explicites. Catalogue : {target}")


if __name__ == "__main__":
    main()
