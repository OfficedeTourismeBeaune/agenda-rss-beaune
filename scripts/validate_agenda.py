#!/usr/bin/env python3
"""Block deployment of partial or inconsistent weekly editions."""
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
    match = re.search(r"-fr-(\d+)", url)
    return match.group(1) if match else url.rstrip("/")


def validate(published=False, local_images=False):
    docs = ROOT / "docs"
    feed = (docs / "feed.xml").read_bytes()
    index = (docs / "index.html").read_bytes()
    history = json.loads((docs / "history.json").read_text())
    channel = ET.fromstring(feed).find("channel")
    items = channel.findall("item")
    assert len(items) == 6, "Le RSS doit contenir 6 événements"
    links = [item.findtext("link") for item in items]
    assert len(set(map(event_id, links))) == 6, "Événements en doublon"
    assert len({item.findtext("guid") for item in items}) == 6, "GUID en doublon"
    latest = max(history)
    assert len(history[latest]) == 6, "Historique incomplet"
    assert set(map(event_id, history[latest])) == set(map(event_id, links)), "RSS et historique incohérents"
    cards = BeautifulSoup(index, "html.parser")
    preview_images = cards.find_all("img")
    assert len(preview_images) == 6, "La page doit contenir 6 cartes"
    preview_titles = [h.get_text(strip=True) for h in cards.find_all("h3")]
    assert preview_titles == [item.findtext("title") for item in items], "Titres différents entre RSS et page"
    images = []
    for item, preview in zip(items, preview_images):
        content = item.findtext(CONTENT)
        assert content, "Bloc content:encoded manquant"
        soup = BeautifulSoup(content, "html.parser")
        img = soup.find_all("img")
        assert len(img) == 1, "Chaque carte doit contenir une image"
        url = img[0].get("src", "")
        assert preview.get("src") == url, "Images différentes entre RSS et page"
        assert any(event_id(a.get("href", "")) == event_id(item.findtext("link")) for a in soup.find_all("a")), "Lien du bouton incorrect"
        assert url.startswith("https://"), "URL d'image invalide"
        if local_images or published:
            assert url.startswith(BASE + "assets/events/"), "Image non synchronisée"
            path = docs / unquote(urlsplit(url).path.removeprefix("/agenda-rss-beaune/"))
            assert path.resolve().is_relative_to(docs.resolve()), "Chemin image invalide"
            with Image.open(path) as image:
                image.verify()
            images.append((url, path))
    assert b"<media:content" not in feed, "Format Mailchimp non conforme"
    if published:
        # Cache-busting avoids accepting an earlier cached edition.
        suffix = "?verify=" + str(time.time_ns())
        for name, expected in [("feed.xml", feed), ("index.html", index), ("history.json", (docs / "history.json").read_bytes())]:
            response = requests.get(BASE + name + suffix, timeout=30)
            response.raise_for_status()
            assert response.content == expected, "Version publique différente : " + name
        for url, path in images:
            response = requests.get(url + suffix, timeout=30)
            response.raise_for_status()
            assert response.headers.get("Content-Type", "").startswith("image/"), "Image publique invalide"
            assert hashlib.sha256(response.content).digest() == hashlib.sha256(path.read_bytes()).digest(), "Image publique obsolète"
    print("OK : 6 événements, historique, cartes et images cohérents" + (" ; publication vérifiée" if published else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--published", action="store_true")
    parser.add_argument("--local-images", action="store_true")
    args = parser.parse_args()
    for attempt in range(6 if args.published else 1):
        try:
            validate(args.published, args.local_images)
            break
        except (AssertionError, requests.RequestException):
            if not args.published or attempt == 5:
                raise
            time.sleep(10)
