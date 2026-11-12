#!/usr/bin/env python3
"""Validate an editorial week before and after publishing."""
import argparse
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit, unquote
import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://officedetourismebeaune.github.io/agenda-rss-beaune/"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"

def event_id(url):
    m = re.search(r"-fr-(\d+)", url)
    return m.group(1) if m else url.rstrip("/")

def validate(published=False, local_images=False):
    docs = ROOT / "docs"
    feed = (docs / "feed.xml").read_bytes()
    index = (docs / "index.html").read_bytes()
    history_bytes = (docs / "history.json").read_bytes()
    history = json.loads(history_bytes)
    channel = ET.fromstring(feed).find("channel")
    items = channel.findall("item")
    assert len(items) == 7, "Le RSS doit contenir 7 événements"
    links = [i.findtext("link") for i in items]
    assert len(set(map(event_id, links))) == 7, "Événements en doublon"
    assert len({i.findtext("guid") for i in items}) == 7, "GUID en doublon"
    latest = max(history)
    assert len(history[latest]) == 7, "Historique incomplet"
    assert set(map(event_id, history[latest])) == set(map(event_id, links)), "RSS et historique incohérents"

    page = BeautifulSoup(index, "html.parser")
    heads = page.find_all("h2")
    assert len(heads) == 7, "La page doit présenter 7 événements"
    expected_titles = [i.findtext("title") for i in items]
    assert [h.get_text(strip=True) for h in heads] == expected_titles, "Titres différents entre RSS et page"

    images = []
    for item, head in zip(items, heads):
        content = item.findtext(CONTENT)
        assert content, "Bloc content:encoded manquant"
        block = BeautifulSoup(content, "html.parser")
        card = head.find_parent("table")
        assert card, "Carte HTML manquante"
        assert block.find("h2") and block.find("h2").get_text(strip=True) == item.findtext("title"), "Titre RSS incorrect"
        item_url = item.findtext("link")
        # For an event with a direct booking URL, that is the event link.
        assert any(event_id(a.get("href", "").split("?")[0]) == event_id(item_url) for a in block.find_all("a")), "Lien de l'événement incorrect"
        rss_img = block.find("img")
        page_img = card.find("img")
        assert bool(rss_img) == bool(page_img), "Image RSS/page différente"
        if rss_img:
            url = rss_img.get("src", "")
            assert page_img.get("src") == url, "Image RSS/page différente"
            assert url.startswith("https://"), "URL d'image invalide"
            if local_images or published:
                assert url.startswith(BASE + "assets/events/"), "Image non synchronisée"
                path = docs / unquote(urlsplit(url).path.removeprefix("/agenda-rss-beaune/"))
                assert path.resolve().is_relative_to(docs.resolve()), "Chemin image invalide"
                with Image.open(path) as im:
                    im.verify()
                images.append((url, path))
        else:
            assert card.find("table"), "Vignette typographique absente"
    assert b"<media:content" not in feed, "Format RSS incompatible"
    if published:
        suffix = "?verify=" + str(time.time_ns())
        for name, expected in [("feed.xml", feed), ("index.html", index), ("history.json", history_bytes)]:
            response = requests.get(BASE + name + suffix, timeout=30)
            response.raise_for_status()
            assert response.content == expected, "Version publique différente : " + name
        for url, path in images:
            response = requests.get(url + suffix, timeout=30)
            response.raise_for_status()
            assert response.headers.get("Content-Type", "").startswith("image/"), "Image publique invalide"
            assert hashlib.sha256(response.content).digest() == hashlib.sha256(path.read_bytes()).digest(), "Image publique obsolète"
    print(f"OK : {len(items)} événements, historique, cartes et {len(images) if (local_images or published) else 'images'} cohérents" + (" ; publication vérifiée" if published else ""))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--published", action="store_true")
    parser.add_argument("--local-images", action="store_true")
    a = parser.parse_args()
    for attempt in range(6 if a.published else 1):
        try:
            validate(a.published, a.local_images)
            break
        except (AssertionError, requests.RequestException):
            if not a.published or attempt == 5:
                raise
            time.sleep(10)
