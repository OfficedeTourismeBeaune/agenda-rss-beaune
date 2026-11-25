"""Validate the isolated, dated image-layout test without changing the production feed."""
import argparse
import time
from pathlib import Path
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1] / "docs" / "test-affiches"
BASE = "https://officedetourismebeaune.github.io/agenda-rss-beaune/test-affiches/"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"

def validate_local():
    if not ROOT.exists():
        return
    items = ET.parse(ROOT / "feed.xml").findall("./channel/item")
    page = BeautifulSoup((ROOT / "index.html").read_bytes(), "html.parser")
    assert len(items) == len(page.find_all("h2")) == 6
    assert [i.findtext("title") for i in items] == [h.get_text(strip=True) for h in page.find_all("h2")]
    images = []
    for item in items:
        assert len(item.findall(CONTENT)) == 1
        img = BeautifulSoup(item.findtext(CONTENT), "html.parser").find("img")
        assert img and "height:auto;" in img.get("style", "") and "object-fit:cover" not in img.get("style", "")
        images.append(img["src"])
    assert images == [img["src"] for img in page.find_all("img")]
    print("OK: 6 test cards, identical RSS/HTML images, intrinsic image proportions.")

def validate_public():
    if not ROOT.exists():
        return
    validate_local()
    for name in ("feed.xml", "index.html"):
        response = requests.get(BASE + name, params={"verify": time.time_ns()}, timeout=15)
        response.raise_for_status()
        assert response.content == (ROOT / name).read_bytes(), "Test preview not yet deployed: " + name

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--published", action="store_true")
    args = parser.parse_args()
    if args.published:
        for attempt in range(6):
            try:
                validate_public()
                break
            except (AssertionError, requests.RequestException):
                if attempt == 5:
                    raise
                time.sleep(10)
    else:
        validate_local()
