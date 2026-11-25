"""Validate the isolated, dated image-layout test without changing the production feed."""
import argparse
import time
from pathlib import Path
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1] / "docs" / "test-affiches"
BASE = "https://officedetourismebeaune.github.io/agenda-rss-beaune/test-affiches/"
VERSIONS = ((ROOT, BASE), (ROOT / "v2", BASE + "v2/"))
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"

def validate_local_version(root):
    if not root.exists():
        return
    items = ET.parse(root / "feed.xml").findall("./channel/item")
    page = BeautifulSoup((root / "index.html").read_bytes(), "html.parser")
    assert len(items) == len(page.find_all("h2")) == 6
    assert [i.findtext("title") for i in items] == [h.get_text(strip=True) for h in page.find_all("h2")]
    images = []
    for item in items:
        assert len(item.findall(CONTENT)) == 1
        img = BeautifulSoup(item.findtext(CONTENT), "html.parser").find("img")
        assert img and "height:auto;" in img.get("style", "") and "object-fit:cover" not in img.get("style", "")
        if root.name == "v2":
            cell = img.find_parent("td")
            assert cell.get("rowspan") == "2" and cell.get("height") == "220"
            card = cell.find_parent("table")
            button = card.find("a")
            assert button and button.find_parent("td").get("valign") == "bottom"
        images.append(img["src"])
    assert images == [img["src"] for img in page.find_all("img")]
    print("OK: 6 test cards, identical RSS/HTML images, intrinsic image proportions.")

def validate_local():
    for root, _ in VERSIONS:
        validate_local_version(root)

def validate_public():
    validate_local()
    for root, base in VERSIONS:
        if not root.exists():
            continue
        for name in ("feed.xml", "index.html"):
            response = requests.get(base + name, params={"verify": time.time_ns()}, timeout=15)
            response.raise_for_status()
            assert response.content == (root / name).read_bytes(), "Test preview not yet deployed: " + base + name

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
