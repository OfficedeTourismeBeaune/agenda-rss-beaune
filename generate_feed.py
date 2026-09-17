#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import os
import random
import re
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from xml.sax.saxutils import escape as xml_escape

SOURCE_RSS = os.getenv("SOURCE_RSS", "https://www.beaune-tourisme.fr/playlist/35902.rss")
AGENDA_URL = os.getenv("AGENDA_URL", "https://www.beaune-tourisme.fr/fr/sejourner/agenda/")
COUNT = int(os.getenv("COUNT", "6"))
AGENDA_PAGES = int(os.getenv("AGENDA_PAGES", "6"))
MAX_DISCOVERED_LINKS = int(os.getenv("MAX_DISCOVERED_LINKS", "120"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "docs"))
HISTORY_FILE = OUTPUT_DIR / "history.json"
MAX_PER_CITY = int(os.getenv("MAX_PER_CITY", "4"))
MAX_PER_CATEGORY = int(os.getenv("MAX_PER_CATEGORY", "3"))
TIMEOUT = 20
PARIS = ZoneInfo("Europe/Paris")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "BeauneAgendaRSS/2.1 (+https://www.beaune-tourisme.fr/)"
})

MONTHS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
MONTH_MAP = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12, "décembre": 12,
}
MONTH_RE = "|".join(sorted(MONTH_MAP.keys(), key=len, reverse=True))

KNOWN_CITIES = [
    "Savigny-lès-Beaune", "Chevigny-en-Valière", "Pernand-Vergelesses",
    "Ladoix-Serrigny", "Bligny-lès-Beaune", "Chorey-lès-Beaune",
    "Montagny-lès-Beaune", "Aloxe-Corton", "Saint-Romain",
    "Nuits-Saint-Georges", "Corcelles-les-Arts", "Meursault", "Santenay",
    "Pommard", "Volnay", "Vougeot", "Chagny", "Nolay", "Beaune", "Vignoles",
]

CATEGORY_KEYWORDS = {
    "musique": ("concert", "jazz", "musique", "orchestre", "festival", "chanson", "folk", "rock"),
    "patrimoine": ("patrimoine", "visite", "château", "chateau", "hôtel-dieu", "hotel-dieu", "rempart", "église", "eglise", "chapelle", "musée", "musee", "basilique", "collégiale", "collegiale"),
    "gastronomie": ("dégust", "degust", "vin", "vigne", "gastronom", "gourmand", "repas", "table", "cocktail", "gustatif"),
    "culture": ("livre", "auteur", "théâtre", "theatre", "spectacle", "exposition", "expo", "conférence", "conference", "cinéma", "cinema", "cabaret"),
    "famille": ("famille", "enfant", "jeu", "atelier", "conte"),
    "nature": ("balade", "randonnée", "randonnee", "vélo", "velo", "nature", "forêt", "foret", "promenade"),
}

# Signaux éditoriaux pour se rapprocher d'une vraie sélection humaine.
EDITORIAL_BOOSTS = {
    "concert": 6.0,
    "festival": 5.0,
    "visite guidee": 5.0,
    "atelier gustatif": 5.0,
    "livres en vignes": 5.0,
    "spectacle": 3.0,
    "orchestre": 2.5,
    "livre": 2.0,
    "conference": 1.5,
    "exposition": 1.0,
}

# Animations longues / répétitives : pas interdites, mais moins prioritaires.
EDITORIAL_PENALTIES = {
    "defiez le mcd": -12.0,
    "casino": -10.0,
    "machine": -4.0,
    "jeu de piste": -2.0,
    "chaque lundi": -4.0,
    "chaque mardi": -4.0,
    "chaque vendredi": -3.0,
    "tous les lundis": -4.0,
    "tous les mardis": -4.0,
    "tous les vendredis": -3.0,
}


@dataclass
class Event:
    title: str
    link: str
    description: str
    image: str = ""
    city: str = ""
    venue: str = ""
    start: str = ""
    end: str = ""
    category: str = "autre"
    date_confidence: str = ""

    @property
    def start_dt(self):
        return parse_dt(self.start)

    @property
    def end_dt(self):
        return parse_dt(self.end) or self.start_dt


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.lower()


def parse_dt(value):
    if not value:
        return None
    try:
        dt = dateparser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=PARIS)
        return dt
    except Exception:
        return None


def next_monday(today: date) -> date:
    delta = (7 - today.weekday()) % 7
    if delta == 0:
        delta = 7
    return today + timedelta(days=delta)


def target_range(today: date):
    start = next_monday(today)
    return start, start + timedelta(days=6)


def strip_html(value: str) -> str:
    return " ".join(BeautifulSoup(value or "", "html.parser").stripped_strings)


def first_img(value: str) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    img = soup.find("img")
    return img.get("src", "") if img else ""


def safe_date(year: int, month: int | None, day: int) -> date | None:
    if not month:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def date_to_iso(d: date | None) -> str:
    if not d:
        return ""
    return datetime(d.year, d.month, d.day, 12, 0, tzinfo=PARIS).isoformat()


def distance_to_period(d: date, start: date, end: date) -> int:
    if start <= d <= end:
        return 0
    if d < start:
        return (start - d).days
    return (d - end).days


def collect_dates_from_text(text: str, target_start: date, target_end: date):
    """Récupère les dates françaises visibles sur une fiche événement."""
    raw = " ".join((text or "").split())
    low = raw.lower()
    ranges: list[tuple[date, date]] = []
    singles: list[date] = []

    # 21 juin au 20 septembre 2026
    pat_two_months = re.compile(
        rf"\b(?:du\s+)?(\d{{1,2}})\s+({MONTH_RE})\s+(?:au|à|a|-)\s+"
        rf"(\d{{1,2}})\s+({MONTH_RE})(?:\s+(20\d{{2}}))?\b",
        re.I,
    )
    for m in pat_two_months.finditer(low):
        d1, m1, d2, m2, year = m.groups()
        y = int(year or target_start.year)
        a = safe_date(y, MONTH_MAP.get(m1.lower()), int(d1))
        b = safe_date(y, MONTH_MAP.get(m2.lower()), int(d2))
        if a and b:
            if b < a and not year:
                b = safe_date(y + 1, MONTH_MAP.get(m2.lower()), int(d2))
            if b:
                ranges.append((a, b))

    # 24 au 26 septembre / 26 et 27 septembre
    pat_same_month = re.compile(
        rf"\b(?:du\s+)?(\d{{1,2}})\s+(?:au|à|a|et|-)\s+(\d{{1,2}})\s+"
        rf"({MONTH_RE})(?:\s+(20\d{{2}}))?\b",
        re.I,
    )
    for m in pat_same_month.finditer(low):
        d1, d2, mon, year = m.groups()
        y = int(year or target_start.year)
        mo = MONTH_MAP.get(mon.lower())
        a = safe_date(y, mo, int(d1))
        b = safe_date(y, mo, int(d2))
        if a and b:
            ranges.append((min(a, b), max(a, b)))

    # Dates ISO dans le HTML / data attributes.
    for y, mo, da in re.findall(r"\b(20\d{2})-(\d{2})-(\d{2})\b", raw):
        d = safe_date(int(y), int(mo), int(da))
        if d:
            singles.append(d)

    # 25 septembre 2026
    pat_single = re.compile(
        rf"\b(\d{{1,2}})\s+({MONTH_RE})(?:\s+(20\d{{2}}))?\b",
        re.I,
    )
    for d, mon, year in pat_single.findall(low):
        y = int(year or target_start.year)
        parsed = safe_date(y, MONTH_MAP.get(mon.lower()), int(d))
        if parsed:
            singles.append(parsed)

    singles = sorted(set(singles))
    ranges = sorted(set(ranges))

    # Priorité : plage qui chevauche la semaine cible.
    overlaps = [(a, b) for a, b in ranges if a <= target_end and b >= target_start]
    if overlaps:
        a, b = min(overlaps, key=lambda r: ((r[1] - r[0]).days, abs((r[0] - target_start).days)))
        return a, b, "text-range"

    # Ensuite : date ponctuelle à l'intérieur de la semaine.
    inside = [d for d in singles if target_start <= d <= target_end]
    if inside:
        return min(inside), max(inside), "text-date"

    # Si tout est hors semaine, on garde la date la plus proche : cela permet de
    # rejeter correctement les JEP du week-end précédent au lieu de les accepter.
    if ranges:
        a, b = min(
            ranges,
            key=lambda r: min(
                distance_to_period(r[0], target_start, target_end),
                distance_to_period(r[1], target_start, target_end),
            ),
        )
        return a, b, "text-range-outside"

    if singles:
        d = min(singles, key=lambda x: distance_to_period(x, target_start, target_end))
        return d, d, "text-date-outside"

    return None, None, ""


def find_event_jsonld(soup: BeautifulSoup):
    def walk(obj):
        if isinstance(obj, dict):
            typ = obj.get("@type")
            if typ == "Event" or (isinstance(typ, list) and "Event" in typ):
                return obj
            if "@graph" in obj:
                found = walk(obj["@graph"])
                if found:
                    return found
            for value in obj.values():
                found = walk(value)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = walk(item)
                if found:
                    return found
        return None

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or tag.get_text())
        except Exception:
            continue
        found = walk(data)
        if found:
            return found
    return None


def jsonld_image(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return jsonld_image(value[0])
    if isinstance(value, dict):
        return value.get("url") or value.get("contentUrl") or ""
    return ""


def infer_city(*values: str) -> str:
    haystack = normalize(" ".join(v for v in values if v))
    for city in KNOWN_CITIES:
        if normalize(city) in haystack:
            return city
    return ""


def page_metadata(url: str, target_start: date, target_end: date) -> dict[str, str]:
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception:
        return {}

    soup = BeautifulSoup(r.text, "html.parser")
    out: dict[str, str] = {}
    obj = find_event_jsonld(soup)

    if obj:
        out["title"] = str(obj.get("name") or "")
        out["description"] = strip_html(str(obj.get("description") or ""))
        out["image"] = jsonld_image(obj.get("image"))
        out["start"] = str(obj.get("startDate") or "")
        out["end"] = str(obj.get("endDate") or "")
        if out["start"]:
            out["date_confidence"] = "jsonld"

        loc = obj.get("location") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        if isinstance(loc, dict):
            out["venue"] = str(loc.get("name") or "")
            address = loc.get("address") or {}
            if isinstance(address, dict):
                out["city"] = str(address.get("addressLocality") or "")

    if not out.get("title"):
        h1 = soup.find("h1")
        if h1:
            out["title"] = " ".join(h1.stripped_strings)

    if not out.get("title"):
        meta = soup.find("meta", property="og:title")
        if meta:
            out["title"] = meta.get("content", "")

    if not out.get("description"):
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            out["description"] = meta.get("content", "")

    if not out.get("image"):
        meta = soup.find("meta", property="og:image")
        if meta:
            out["image"] = meta.get("content", "")

    # Beaucoup de fiches utilisent <time datetime>. Si l'une des dates tombe
    # dans la semaine, elle est prioritaire.
    if not out.get("start"):
        time_dates = []
        for tag in soup.find_all("time"):
            value = tag.get("datetime")
            dt = parse_dt(value) if value else None
            if dt:
                time_dates.append(dt.astimezone(PARIS).date())
        time_dates = sorted(set(time_dates))
        inside = [d for d in time_dates if target_start <= d <= target_end]
        if inside:
            out["start"] = date_to_iso(min(inside))
            out["end"] = date_to_iso(max(inside))
            out["date_confidence"] = "time-tag"

    # Repli robuste sur le texte visible de la fiche + HTML brut.
    if not out.get("start"):
        main = soup.find("main") or soup.find("article") or soup.body or soup
        page_text = strip_html(str(main))
        source = " ".join([
            out.get("title", ""),
            out.get("description", ""),
            page_text[:35000],
            r.text[:60000],
        ])
        a, b, confidence = collect_dates_from_text(source, target_start, target_end)
        if a:
            out["start"] = date_to_iso(a)
            out["end"] = date_to_iso(b or a)
            out["date_confidence"] = confidence

    if not out.get("city"):
        out["city"] = infer_city(
            out.get("title", ""),
            out.get("description", ""),
            url.replace("-", " "),
        )

    return out


def feed_image(entry) -> str:
    for item in getattr(entry, "media_content", []) or []:
        if isinstance(item, dict) and item.get("url"):
            return item["url"]
    for enc in getattr(entry, "enclosures", []) or []:
        if isinstance(enc, dict) and (enc.get("href") or enc.get("url")):
            return enc.get("href") or enc.get("url")
    return first_img(getattr(entry, "summary", "") or getattr(entry, "description", ""))


def clean_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


def valid_event_link(url: str) -> bool:
    try:
        path = urlparse(url).path.lower().rstrip("/")
    except Exception:
        return False
    if "/sejourner/agenda/" not in path:
        return False
    if path.endswith("/sejourner/agenda"):
        return False
    return True


def discover_agenda_links() -> list[str]:
    links = []
    seen = set()
    for page in range(1, AGENDA_PAGES + 1):
        page_url = AGENDA_URL if page == 1 else f"{AGENDA_URL}?listpage={page}"
        try:
            r = SESSION.get(page_url, timeout=TIMEOUT)
            r.raise_for_status()
        except Exception:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            absolute = clean_url(urljoin(page_url, a["href"]))
            if not valid_event_link(absolute) or absolute in seen:
                continue
            seen.add(absolute)
            links.append(absolute)
            if len(links) >= MAX_DISCOVERED_LINKS:
                return links
    return links


def classify(title: str, description: str) -> str:
    text = normalize(f"{title} {description}")
    scores = {
        cat: sum(1 for kw in kws if normalize(kw) in text)
        for cat, kws in CATEGORY_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] else "autre"


def build_events(feed, target_start: date, target_end: date) -> list[Event]:
    basics: dict[str, dict[str, str]] = {}

    for entry in getattr(feed, "entries", []) or []:
        link = clean_url((getattr(entry, "link", "") or "").strip())
        title = strip_html(getattr(entry, "title", "") or "")
        if not link or not title:
            continue
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        basics[link] = {
            "title": title,
            "description": strip_html(summary),
            "image": feed_image(entry),
        }

    # C'est ce point qui évite de dépendre des premiers résultats du RSS.
    for link in discover_agenda_links():
        basics.setdefault(link, {"title": "", "description": "", "image": ""})

    events: list[Event] = []

    def load(link: str):
        return link, page_metadata(link, target_start, target_end)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(load, link) for link in basics]
        for future in as_completed(futures):
            try:
                link, meta = future.result()
            except Exception:
                continue
            basic = basics[link]
            title = (meta.get("title") or basic.get("title") or "").strip()
            if not title:
                continue
            description = (meta.get("description") or basic.get("description") or "").strip()
            start_value = meta.get("start", "")
            end_value = meta.get("end", "")
            confidence = meta.get("date_confidence", "")

            if not start_value:
                a, b, conf = collect_dates_from_text(
                    f"{title} {description}", target_start, target_end
                )
                if a:
                    start_value = date_to_iso(a)
                    end_value = date_to_iso(b or a)
                    confidence = conf

            city = meta.get("city", "").strip() or infer_city(
                title, description, link.replace("-", " ")
            )

            ev = Event(
                title=title,
                link=link,
                description=description,
                image=meta.get("image") or basic.get("image") or "",
                city=city,
                venue=meta.get("venue", "").strip(),
                start=start_value,
                end=end_value,
                date_confidence=confidence,
            )
            ev.category = classify(ev.title, ev.description)
            events.append(ev)

    return events


def overlaps(ev: Event, start: date, end: date) -> bool:
    # Correctif critique : sans date vérifiée, l'événement est exclu.
    if not ev.start_dt:
        return False
    sd = ev.start_dt.astimezone(PARIS).date()
    ed = (ev.end_dt or ev.start_dt).astimezone(PARIS).date()
    return sd <= end and ed >= start


def duration_days(ev: Event) -> int:
    if not ev.start_dt:
        return 999
    sd = ev.start_dt.astimezone(PARIS).date()
    ed = (ev.end_dt or ev.start_dt).astimezone(PARIS).date()
    return max(0, (ed - sd).days)


def load_history():
    try:
        obj = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def recent_links(history, weeks=2):
    keys = sorted(history.keys())[-weeks:]
    return {link for key in keys for link in history.get(key, [])}


def editorial_score(ev: Event, previous: set[str], rng: random.Random) -> float:
    text = normalize(f"{ev.title} {ev.description}")
    score = 0.0

    if ev.date_confidence == "jsonld":
        score += 8.0
    elif ev.date_confidence == "time-tag":
        score += 7.0
    elif ev.date_confidence:
        score += 6.0

    if ev.image:
        score += 2.0
    if ev.city:
        score += 1.0

    days = duration_days(ev)
    if days <= 1:
        score += 8.0
    elif days <= 3:
        score += 7.0
    elif days <= 7:
        score += 3.0
    elif days >= 14:
        score -= 8.0

    for term, value in EDITORIAL_BOOSTS.items():
        if normalize(term) in text:
            score += value
    for term, value in EDITORIAL_PENALTIES.items():
        if normalize(term) in text:
            score += value

    # Léger avantage aux sorties du vendredi au dimanche.
    sd = ev.start_dt.astimezone(PARIS).date()
    ed = (ev.end_dt or ev.start_dt).astimezone(PARIS).date()
    if any((sd + timedelta(days=i)).weekday() >= 4 for i in range((ed - sd).days + 1)):
        score += 2.0

    if ev.link in previous:
        score -= 10.0

    # Juste assez d'aléa pour faire tourner des événements de score proche,
    # mais stable pour toute la semaine.
    score += rng.random() * 0.5
    return score


def select_events(events: list[Event], start: date, end: date, count: int) -> list[Event]:
    candidates = [ev for ev in events if overlaps(ev, start, end)]

    history = load_history()
    previous = recent_links(history)
    rng = random.Random(start.isoformat())
    scores = {ev.link: editorial_score(ev, previous, rng) for ev in candidates}

    selected: list[Event] = []
    cities = Counter()
    categories = Counter()
    remaining = candidates[:]

    while remaining and len(selected) < count:
        best = None
        best_score = float("-inf")

        for ev in remaining:
            city_key = normalize(ev.city or "inconnu")
            cat_key = ev.category or "autre"

            if city_key != "inconnu" and cities[city_key] >= MAX_PER_CITY:
                continue
            if categories[cat_key] >= MAX_PER_CATEGORY:
                continue

            score = scores[ev.link]

            # Diversité sans empêcher une forte présence de Beaune si les événements sont bons.
            if categories[cat_key] == 0:
                score += 2.5
            elif categories[cat_key] == 1:
                score += 0.7

            if city_key != "inconnu":
                if cities[city_key] == 0:
                    score += 1.8
                elif cities[city_key] >= 2:
                    score -= 1.0 * (cities[city_key] - 1)

            if score > best_score:
                best = ev
                best_score = score

        if not best:
            break

        selected.append(best)
        remaining.remove(best)
        cities[normalize(best.city or "inconnu")] += 1
        categories[best.category or "autre"] += 1

    # Si les plafonds bloquent, on complète uniquement avec des événements
    # toujours valides sur la semaine. Jamais de JEP du week-end précédent.
    if len(selected) < count:
        already = {ev.link for ev in selected}
        fallback = sorted(
            [ev for ev in candidates if ev.link not in already],
            key=lambda ev: scores[ev.link],
            reverse=True,
        )
        for ev in fallback:
            selected.append(ev)
            if len(selected) >= count:
                break

    # Dans le mail, ordre chronologique après la sélection éditoriale.
    selected.sort(key=lambda ev: (ev.start_dt.astimezone(PARIS), ev.title.lower()))
    return selected[:count]


def fmt_day_month(d: date) -> str:
    return f"{d.day} {MONTHS_FR[d.month]}"


def fmt_event_date(ev: Event) -> str:
    if not ev.start_dt:
        return ""
    sd = ev.start_dt.astimezone(PARIS).date()
    ed = (ev.end_dt or ev.start_dt).astimezone(PARIS).date()
    if sd == ed:
        return fmt_day_month(sd)
    if sd.month == ed.month:
        return f"{sd.day} au {ed.day} {MONTHS_FR[sd.month]}"
    return f"{fmt_day_month(sd)} au {fmt_day_month(ed)}"


def truncate(text: str, n=230):
    text = " ".join((text or "").split())
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"


def card_html(ev: Event) -> str:
    eyebrow = " · ".join(x.upper() for x in (fmt_event_date(ev), ev.city or ev.venue) if x)
    title = html.escape(ev.title)
    desc = html.escape(truncate(ev.description))
    image = html.escape(ev.image, quote=True)
    sep = "&" if "?" in ev.link else "?"
    link = html.escape(
        ev.link + sep + "utm_source=newsletter&utm_medium=email&utm_campaign=agenda_hebdomadaire",
        quote=True,
    )

    image_cell = ""
    if image:
        image_cell = (
            f'<td width="36%" valign="top" style="padding:14px 8px 14px 14px;">'
            f'<img src="{image}" alt="{title}" width="100%" '
            f'style="display:block;width:100%;max-width:100%;height:auto;border-radius:6px;border:0;"></td>'
        )

    width = "64%" if image else "100%"
    pad = "10px" if image else "14px"

    return (
        '<table border="0" cellpadding="0" cellspacing="0" width="100%" '
        'style="margin-bottom:22px;border-collapse:separate;background-color:#fbf8f5;border-radius:8px;">'
        f'<tbody><tr>{image_cell}'
        f'<td width="{width}" valign="top" style="padding:14px 14px 14px {pad};">'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;line-height:16px;letter-spacing:0.8px;text-transform:uppercase;color:#8b7770;font-weight:bold;margin-bottom:5px;">{html.escape(eyebrow)}</div>'
        f'<h3 style="margin:0 0 8px 0;font-family:Arial,Helvetica,sans-serif;font-size:17px;line-height:22px;color:#432f32;font-weight:bold;">{title}</h3>'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:20px;color:#55504e;margin-bottom:13px;">{desc}</div>'
        '<table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td bgcolor="#bd3d00" style="border-radius:4px;">'
        f'<a href="{link}" target="_blank" style="display:inline-block;padding:10px 16px;font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:bold;color:#ffffff;text-decoration:none;">Découvrir</a>'
        '</td></tr></tbody></table></td></tr></tbody></table>'
    )


def cdata(text: str) -> str:
    return text.replace("]]>", "]]]]><![CDATA[>")


def rfc2822(dt: datetime) -> str:
    from email.utils import format_datetime
    return format_datetime(dt)


def build_rss(selected: list[Event], start: date, end: date) -> str:
    now = datetime.now(timezone.utc)
    channel_title = f"Agenda du {fmt_day_month(start)} au {fmt_day_month(end)} {end.year}"
    items = []

    for ev in selected:
        guid = hashlib.sha1(f"{start.isoformat()}::{ev.link}".encode()).hexdigest()
        media = ""
        if ev.image:
            media = f'<media:content url="{xml_escape(ev.image)}" medium="image" />'
        items.append(
            f'<item><title>{xml_escape(ev.title)}</title><link>{xml_escape(ev.link)}</link>'
            f'<guid isPermaLink="false">{guid}</guid><pubDate>{rfc2822(now)}</pubDate>'
            f'<description><![CDATA[{cdata(truncate(ev.description, 500))}]]></description>'
            f'<content:encoded><![CDATA[{cdata(card_html(ev))}]]></content:encoded>{media}</item>'
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:media="http://search.yahoo.com/mrss/">\n'
        '<channel>\n'
        f'<title>{xml_escape(channel_title)}</title>\n'
        '<link>https://www.beaune-tourisme.fr/fr/sejourner/agenda/</link>\n'
        '<description>Sélection automatique de six événements de l\'agenda Beaune &amp; Pays Beaunois.</description>\n'
        '<language>fr-FR</language>\n'
        f'<lastBuildDate>{rfc2822(now)}</lastBuildDate>\n'
        f'{"".join(items)}\n'
        '</channel></rss>'
    )


def build_preview(selected: list[Event], start: date, end: date) -> str:
    title = f"Agenda du {fmt_day_month(start)} au {fmt_day_month(end)} {end.year}"
    cards = "\n".join(card_html(ev) for ev in selected)
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(title)}</title></head>'
        '<body style="margin:0;background:#fff;font-family:Arial,Helvetica,sans-serif;">'
        '<div style="max-width:600px;margin:35px auto;padding:0 15px;">'
        f'<h1 style="font-size:22px;color:#432f32;">{html.escape(title)}</h1>'
        '<p style="font-size:13px;color:#666;">Aperçu automatique du flux destiné à Mailchimp.</p>'
        f'{cards}'
        '<p style="font-size:12px;color:#888;margin-top:30px;"><a href="feed.xml">Ouvrir le flux RSS</a></p>'
        '</div></body></html>'
    )


def save_history(start: date, selected: list[Event]):
    history = load_history()
    history[start.isoformat()] = [ev.link for ev in selected]
    keys = sorted(history.keys())[-12:]
    HISTORY_FILE.write_text(
        json.dumps({key: history[key] for key in keys}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(PARIS).date()
    start, end = target_range(today)

    try:
        r = SESSION.get(SOURCE_RSS, timeout=TIMEOUT)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
    except Exception:
        feed = feedparser.FeedParserDict()
        feed.entries = []

    events = build_events(feed, start, end)
    selected = select_events(events, start, end, COUNT)

    if len(selected) < COUNT:
        dated = sum(1 for ev in events if ev.start_dt)
        raise RuntimeError(
            f"Seulement {len(selected)} événement(s) valide(s) pour {start} -> {end}. "
            f"{len(events)} fiches analysées, {dated} avec date détectée."
        )

    (OUTPUT_DIR / "feed.xml").write_text(build_rss(selected, start, end), encoding="utf-8")
    (OUTPUT_DIR / "index.html").write_text(build_preview(selected, start, end), encoding="utf-8")
    save_history(start, selected)

    print(f"Agenda généré pour {start} -> {end}")
    print(f"{len(events)} fiches analysées.")
    print("Sélection éditoriale :")
    for ev in selected:
        print(
            f"- {ev.title} | {fmt_event_date(ev)} | {ev.city or '?'} | "
            f"{ev.category} | date={ev.date_confidence or '?'}"
        )


if __name__ == "__main__":
    main()
