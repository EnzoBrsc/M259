"""Terrain et podium : présentation des scores, sans modifier les prédictions."""

import html
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st

from src.collect_player_portraits import name_key

ASSETS = Path(__file__).resolve().parents[1] / "assets"
POSITIONS = {"GK": "GAR", "DEF": "DÉF", "MID": "MIL", "FWD": "ATT"}
THEMES = {"TOTW": "totw", "TOTS": "tots", "TOTY": "toty", "POTM": "potm", "Ballon d'Or": "ballon"}
PHOTO_SOURCES = {"b.fssta.com": {"www.foxsports.com"},
                 "resources.premierleague.com": {"fantasy.premierleague.com"},
                 "img.fcbayern.com": {"fcbayern.com"},
                 "images.ctfassets.net": {"fc.de"},
                 "s.hs-data.com": {"www.worldfootball.net"},
                 "cdn-img.zerozero.pt": {"www.playmakerstats.com", "www.ogol.com.br"},
                 "backend.liverpoolfc.com": {"www.liverpoolfc.com"},
                 "www.fcbarcelona.com": {"www.fcbarcelona.com"}}


@lru_cache(maxsize=1)
def _read_catalog(modified_ns):
    try:
        return json.loads((ASSETS / "player_portraits.json").read_text(encoding="utf-8"))["portraits"]
    except (OSError, ValueError, KeyError):
        return {}


def portrait_catalog():
    try:
        return _read_catalog((ASSETS / "player_portraits.json").stat().st_mtime_ns)
    except OSError:
        return {}


def portrait_for(name):
    entry = portrait_catalog().get(name_key(name))
    if not entry or name_key(entry.get("name", "")) != name_key(name):
        return None
    image, source = (urlsplit(entry.get(key, "")) for key in ("image_url", "source_url"))
    if (image.scheme != "https" or image.netloc not in PHOTO_SOURCES
            or source.scheme != "https" or source.netloc not in PHOTO_SOURCES[image.netloc]):
        return None
    return entry


def player_card(row, *, rank=None):
    name = str(row["player"])
    safe_name = html.escape(name, quote=True)
    initials = html.escape("".join(part[0] for part in name.split()[:2]) or "?", quote=True)
    position = POSITIONS.get(str(row.get("position", "")), "")
    badge = f"#{rank}" if rank is not None else position
    portrait = portrait_for(name)
    image = (f'<img src="{html.escape(portrait["image_url"], quote=True)}" '
             f'alt="Portrait de {safe_name}" loading="lazy" referrerpolicy="no-referrer">') if portrait else ""
    photo_note = html.escape("Portrait : " + portrait["provider"], quote=True) if portrait else "Portrait indisponible · initiales"
    content = f'''<article class="fv-card" aria-label="{safe_name}, {html.escape(badge)}, score {float(row['score']):.6f}">
        <div class="fv-card-top"><span>{html.escape(badge)}</span><span>{'TOP 3' if rank else 'M259'}</span></div>
        <div class="fv-photo" title="{photo_note}">{image if portrait else f'<span class="fv-initials" aria-hidden="true">{initials}</span>'}</div>
        <div class="fv-name" title="{safe_name}">{safe_name}</div>
        <div class="fv-score"><span>SCORE DU MODÈLE</span><strong>{float(row['score']):.6f}</strong></div>
        {'<div class="fv-no-photo">Photo indisponible</div>' if not portrait else ''}
    </article>'''
    if portrait:
        return f'<a class="fv-profile" href="{html.escape(portrait["source_url"], quote=True)}" target="_blank" rel="noopener noreferrer" title="Fiche et crédit photo · {safe_name}">{content}</a>'
    return content


def pitch_html(squad, award, competition, period):
    if "position" not in squad or not squad.position.isin(POSITIONS).all():
        return ""
    formation = "–".join(str(int(squad.position.eq(p).sum())) for p in ("DEF", "MID", "FWD"))
    rows = []
    for position in ("FWD", "MID", "DEF", "GK"):
        players = squad.loc[squad.position.eq(position)].sort_values("rank")
        cards = "".join(player_card(row) for _, row in players.iterrows())
        rows.append(f'<div class="fv-line fv-{position.lower()}" data-position="{position}">{cards}</div>')
    return f'''<section class="fv-board fv-{THEMES[award]}" aria-label="Terrain {award}">
        <header class="fv-header"><div><span class="fv-eyebrow">M259 · SÉLECTION EXPÉRIMENTALE</span><h2>{award} <span>XI</span></h2></div>
        <div class="fv-context">{html.escape(str(competition))}<br><span>{html.escape(str(period))} · {formation}</span></div></header>
        <div class="fv-pitch">
        <div class="fv-markings" aria-hidden="true"><div class="fv-halfway"></div><div class="fv-circle"></div>
        <div class="fv-area fv-area-top"><div></div></div><div class="fv-area fv-area-bottom"><div></div></div></div>
        {''.join(rows)}</div>
        <footer class="fv-footer"><span>ATTAQUE ↑ · GARDIEN ↓</span><span>Classement du modèle · aucune note EA</span></footer>
    </section>'''


def podium_html(ranking, award, context):
    ranked = ranking.sort_values("rank").head(3)
    if ranked.empty:
        return ""
    blocks = []
    # Ordre visuel du podium : deuxième, premier, troisième. Le rang vient du modèle.
    for place in (2, 1, 3):
        match = ranked.loc[ranked["rank"].eq(place)]
        if match.empty:
            continue
        row = match.iloc[0]
        blocks.append(f'<div class="fv-podium-place fv-place-{place}">{player_card(row, rank=place)}<div class="fv-step"><span>{place:02d}</span></div></div>')
    return f'''<section class="fv-board fv-{THEMES[award]}" aria-label="Podium {html.escape(award)}">
        <header class="fv-header"><div><span class="fv-eyebrow">M259 · CLASSEMENT PRÉDIT</span><h2>{html.escape(award)} <span>TOP 3</span></h2></div>
        <div class="fv-context">{html.escape(str(context))}</div></header>
        <div class="fv-podium">{''.join(blocks)}</div>
        <footer class="fv-footer"><span>PODIUM DU MODÈLE</span><span>Scores de classement · aucun résultat officiel</span></footer>
    </section>'''


def render_visual(markup, *, pitch=False):
    if not markup:
        return
    css = (ASSETS / "football_visuals.css").read_text(encoding="utf-8")
    st.html(f"<style>{css}</style>{markup}")
    if pitch:
        st.caption("Postes documentés : GAR = gardien, DÉF = défenseur, MIL = milieu, ATT = attaquant. Dans chaque ligne, les cartes suivent le classement ; gauche/droite ne représente pas un poste précis.")
    st.caption("Portraits : FOX Sports, Premier League et sources indiquées sur les cartes · cliquer ouvre la source photo. Les tenues peuvent dater d'une autre saison. Portrait inconnu : initiales ; connexion Internet nécessaire pour les photos.")
