#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "docs" / "feed.xml"
INDEX = ROOT / "docs" / "index.html"
ASSET_DIR = ROOT / "docs" / "assets" / "events"
PUBLIC_BASE = "https://officedetourismebeaune.github.io/agenda-rss-beaune/assets/events/"
UA = "Mozilla/5.0 (compatible; BeauneAgendaBot/1.0; +https://www.beaune-tourisme.fr/)"

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6"})


def _walk_json(value):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from _walk_json(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk_json(v)


def _first_image(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        for v in value:
            got = _first_image(v)
            if got:
                return got
    if isinstance(value, dict):
        for key in ("url", "contentUrl", "@id"):
            if isinstance(value.get(key), str):
                return value[key]
    return None


def extract_main_image(page_url: str, title: str) -> str:
    r = session.get(page_url, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # 1. Event structured data: this is the strongest link between page and visual.
    for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = node.string or node.get_text()
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for obj in _walk_json(data):
            typ = obj.get("@type")
            types = typ if isinstance(typ, list) else [typ]
            if "Event" in types and obj.get("image"):
                img = _first_image(obj["image"])
                if img:
                    return urljoin(page_url, img)

    # 2. OpenGraph image from the exact Beaune Tourisme fiche.
    meta = soup.find("meta", attrs={"property": "og:image"})
    if meta and meta.get("content"):
        return urljoin(page_url, meta["content"])

    # 3. Main visible image, scored using the event title/alt.
    title_words = {w for w in re.findall(r"[a-zà-ÿ0-9]+", title.lower()) if len(w) >= 4}
    best = None
    best_score = -10**9
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src:
            srcset = img.get("srcset") or img.get("data-srcset")
            if srcset:
                src = srcset.split(",")[-1].strip().split(" ")[0]
        if not src:
            continue
        txt = " ".join([
            img.get("alt") or "",
            img.get("title") or "",
            img.get("class") and " ".join(img.get("class")) or "",
        ]).lower()
        s = sum(3 for w in title_words if w in txt)
        if any(x in txt for x in ("logo", "picto", "icon", "avatar", "payment")):
            s -= 20
        url = urljoin(page_url, src)
        if any(host in url for host in (
            "decibelles-data.media.tourinsoft.eu",
            "api.cloudly.space",
            "beaune-tourisme.fr",
        )):
            s += 2
        if s > best_score:
            best_score = s
            best = url
    if best:
        return best

    raise RuntimeError(f"Aucune image principale trouvée sur {page_url}")


def download_as_jpeg(image_url: str, out: Path) -> None:
    r = session.get(image_url, timeout=40)
    r.raise_for_status()
    ctype = (r.headers.get("Content-Type") or "").lower()
    if not (ctype.startswith("image/") or r.content[:4] in (b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1")):
        raise RuntimeError(f"URL non-image: {image_url} ({ctype})")
    im = Image.open(io.BytesIO(r.content))
    if getattr(im, "is_animated", False):
        im.seek(0)
    if im.mode not in ("RGB", "L"):
        bg = Image.new("RGB", im.size, "white")
        if "A" in im.getbands():
            bg.paste(im, mask=im.getchannel("A"))
        else:
            bg.paste(im)
        im = bg
    else:
        im = im.convert("RGB")
    # Keep enough definition for email while avoiding giant payloads.
    if im.width > 1400:
        h = round(im.height * 1400 / im.width)
        im = im.resize((1400, h), Image.Resampling.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=88, optimize=True, progressive=True)


def clean_page_url(url: str) -> str:
    return url.replace("&amp;", "&")


def slug_from_guid(guid: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", guid).strip("-").lower()
    return s or "event"


def main():
    feed = FEED.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")

    items = re.findall(r"<item>(.*?)</item>", feed, flags=re.S)
    if len(items) != 6:
        raise RuntimeError(f"Le flux doit contenir exactement 6 items, trouvé: {len(items)}")

    changes = []
    for item in items:
        title_m = re.search(r"<title>(.*?)</title>", item, flags=re.S)
        link_m = re.search(r"<link>(.*?)</link>", item, flags=re.S)
        guid_m = re.search(r"<guid[^>]*>(.*?)</guid>", item, flags=re.S)
        img_m = re.search(r'<img\s+[^>]*src="([^"]+)"', item, flags=re.S)
        if not all((title_m, link_m, guid_m, img_m)):
            raise RuntimeError("Item incomplet dans feed.xml")

        title = re.sub(r"\s+", " ", title_m.group(1)).strip()
        page_url = clean_page_url(link_m.group(1).strip())
        guid = re.sub(r"\s+", "-", guid_m.group(1)).strip()
        old_src = img_m.group(1).replace("&amp;", "&")

        image_url = extract_main_image(page_url, title)
        dest_name = slug_from_guid(guid) + ".jpg"
        dest = ASSET_DIR / dest_name
        download_as_jpeg(image_url, dest)

        public = PUBLIC_BASE + dest_name
        feed = feed.replace(old_src.replace("&", "&amp;"), public).replace(old_src, public)
        index = index.replace(old_src.replace("&", "&amp;"), public).replace(old_src, public)
        changes.append((title, image_url, public))
        time.sleep(0.3)

    # XML sanity checks: no media namespace/tag and exactly 6 complete content blocks.
    if "<media:content" in feed or "xmlns:media" in feed:
        raise RuntimeError("media:content ne doit pas être présent")
    if feed.count("<item>") != 6 or feed.count("<content:encoded>") != 6:
        raise RuntimeError("Structure RSS invalide après remplacement")

    FEED.write_text(feed, encoding="utf-8")
    INDEX.write_text(index, encoding="utf-8")

    print("Images synchronisées depuis les fiches Beaune Tourisme:")
    for title, source, public in changes:
        print(f"- {title}: {source} -> {public}")


if __name__ == "__main__":
    main()
