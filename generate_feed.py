#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

OUTPUT_DIR = Path("docs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EVENTS = [
    {
        "title": "Festival d’Automne Jazz O’Verre Beaune",
        "date": "24 au 26 septembre",
        "city": "Beaune",
        "description": "Trois jours de concerts aux Ateliers du Cinéma à Beaune.",
        "url": "https://www.beaune-tourisme.fr/sejourner/agenda/festival-dautomne-jazz-overre-beaune-3-jours-de-concerts-beaune-fr-4322650/",
        "image": "https://api.cloudly.space/resize/cropratio/640/640/75/aHR0cHM6Ly9kZWNpYmVsbGVzLWRhdGEubWVkaWEudG91cmluc29mdC5ldS91cGxvYWQvZWRpdGlvbi0xMC1hbnMtbm9pci5wbmc%3D/image.webp",
    },
    {
        "title": "Concert de la Virade de l’Espoir",
        "date": "25 septembre",
        "city": "Chagny",
        "description": "Un concert au Théâtre des Copiaus au profit de Vaincre la mucoviscidose.",
        "url": "https://www.beaune-tourism.com/fr/sejourner/agenda/concert-de-la-virade-de-lespoir-chagny-fr-6789236/",
        "image": "https://api.cloudly.space/resize/cropratio/640/640/75/aHR0cHM6Ly9kZWNpYmVsbGVzLWRhdGEubWVkaWEudG91cmluc29mdC5ldS91cGxvYWQvMjUuMDktY29uY2VydC12aXJhZGVzLUNoYWdueS5qcGc%3D/image.webp",
    },
    {
        "title": "Concert de Tibz & Loé",
        "date": "25 septembre",
        "city": "Beaune",
        "description": "Tibz en concert à la Lanterne Magique, avec Loé en première partie.",
        "url": "https://www.beaune-tourisme.fr/sejourner/agenda/concert-de-tibz-loe-en-premiere-partie-beaune-fr-6727666/",
        "image": "https://api.cloudly.space/resize/cropratio/640/640/75/aHR0cHM6Ly9kZWNpYmVsbGVzLWRhdGEubWVkaWEudG91cmluc29mdC5ldS91cGxvYWQvQ29uY2VydC1kZS1UaWJ6LmpwZw%3D%3D/image.webp",
    },
    {
        "title": "Hôtel-Dieu – Atelier gustatif « Saveurs du soin »",
        "date": "26 septembre",
        "city": "Beaune",
        "description": "Un atelier gustatif proposé à l’Hôtel-Dieu des Hospices de Beaune.",
        "url": "https://www.beaune-tourisme.fr/sejourner/agenda/hotel-dieu-hospices-de-beaune2026-mouvementsatelier-gustatif-saveurs-du-soin-beaune-fr-5326104/",
        "image": "https://api.cloudly.space/resize/cropratio/640/640/75/aHR0cHM6Ly9kZWNpYmVsbGVzLWRhdGEubWVkaWEudG91cmluc29mdC5ldS91cGxvYWQvSG90ZWwtRGlldS1kZXMtSG9zcGljZXMtQ2l2aWxzLWRlLUJlYXVuZS0tLUF0ZWxpZXItZ3VzdGF0aWYtLS1KdWxpZW4tUGlmZmF1dC5wbmc%3D/image.webp",
    },
    {
        "title": "Livres en Vignes",
        "date": "26 au 27 septembre",
        "city": "Vougeot",
        "description": "Le rendez-vous littéraire et viticole organisé au Château du Clos de Vougeot.",
        "url": "https://www.beaune-tourisme.fr/sejourner/agenda/livres-en-vignes-a-vougeot-vougeot-fr-4146278/",
        "image": "https://api.cloudly.space/resize/cropratio/640/640/75/aHR0cHM6Ly9kZWNpYmVsbGVzLWRhdGEubWVkaWEudG91cmluc29mdC5ldS91cGxvYWQvQ2hhdGVhdS0tcmV0b3VjaGUtLkpQRw%3D%3D/image.webp",
    },
    {
        "title": "Visite guidée des remparts",
        "date": "27 septembre",
        "city": "Beaune",
        "description": "Une visite guidée pour parcourir et comprendre les remparts de Beaune.",
        "url": "https://www.beaune-tourisme.fr/sejourner/agenda/visite-guidee-des-remparts-beaune-fr-6552682/",
        "image": "https://api.cloudly.space/resize/cropratio/640/640/75/aHR0cHM6Ly9kZWNpYmVsbGVzLWRhdGEubWVkaWEudG91cmluc29mdC5ldS91cGxvYWQvVmlzaXRlLWd1aWRlZS1kZXMtcmVtcGFydHMtLTUuanBn/image.webp",
    },
]

def card_html(ev: dict) -> str:
    eyebrow = f'{ev["date"].upper()} · {ev["city"].upper()}'
    title = html.escape(ev["title"])
    desc = html.escape(ev["description"])
    image = html.escape(ev["image"], quote=True)
    sep = "&" if "?" in ev["url"] else "?"
    link = html.escape(
        ev["url"] + sep + "utm_source=newsletter&utm_medium=email&utm_campaign=agenda_hebdomadaire",
        quote=True,
    )
    return (
        '<table border="0" cellpadding="0" cellspacing="0" width="100%" '
        'style="margin-bottom:22px;border-collapse:separate;background-color:#fbf8f5;border-radius:8px;">'
        '<tbody><tr>'
        f'<td width="36%" valign="top" style="padding:14px 8px 14px 14px;">'
        f'<img src="{image}" alt="{title}" width="100%" '
        'style="display:block;width:100%;max-width:100%;height:auto;border-radius:6px;border:0;"></td>'
        '<td width="64%" valign="top" style="padding:14px 14px 14px 10px;">'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;line-height:16px;letter-spacing:0.8px;'
        f'text-transform:uppercase;color:#8b7770;font-weight:bold;margin-bottom:5px;">{html.escape(eyebrow)}</div>'
        f'<h3 style="margin:0 0 8px 0;font-family:Arial,Helvetica,sans-serif;font-size:17px;line-height:22px;'
        f'color:#432f32;font-weight:bold;">{title}</h3>'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:20px;color:#55504e;'
        f'margin-bottom:13px;">{desc}</div>'
        '<table border="0" cellpadding="0" cellspacing="0"><tbody><tr>'
        '<td bgcolor="#bd3d00" style="border-radius:4px;">'
        f'<a href="{link}" target="_blank" style="display:inline-block;padding:10px 16px;'
        'font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:bold;color:#ffffff;'
        'text-decoration:none;">Découvrir</a>'
        '</td></tr></tbody></table>'
        '</td></tr></tbody></table>'
    )

def cdata(text: str) -> str:
    return text.replace("]]>", "]]]]><![CDATA[>")

def rfc2822(dt: datetime) -> str:
    from email.utils import format_datetime
    return format_datetime(dt)

def build_rss() -> str:
    now = datetime.now(timezone.utc)
    items = []
    for ev in EVENTS:
        guid = hashlib.sha1(ev["url"].encode("utf-8")).hexdigest()
        items.append(
            f'<item>'
            f'<title>{xml_escape(ev["title"])}</title>'
            f'<link>{xml_escape(ev["url"])}</link>'
            f'<guid isPermaLink="false">{guid}</guid>'
            f'<pubDate>{rfc2822(now)}</pubDate>'
            f'<description><![CDATA[{cdata(ev["description"])}]]></description>'
            f'<content:encoded><![CDATA[{cdata(card_html(ev))}]]></content:encoded>'
            f'<media:content url="{xml_escape(ev["image"])}" medium="image" />'
            f'</item>'
        )
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:media="http://search.yahoo.com/mrss/">
<channel>
<title>Agenda du 21 au 27 septembre 2026</title>
<link>https://www.beaune-tourisme.fr/fr/sejourner/agenda/</link>
<description>Sélection éditoriale validée de six événements.</description>
<language>fr-FR</language>
<lastBuildDate>{rfc2822(now)}</lastBuildDate>
{''.join(items)}
</channel>
</rss>'''

def build_preview() -> str:
    cards = "\n".join(card_html(ev) for ev in EVENTS)
    return f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agenda du 21 au 27 septembre 2026</title>
</head>
<body style="margin:0;background:#fff;font-family:Arial,Helvetica,sans-serif;">
<div style="max-width:600px;margin:35px auto;padding:0 15px;">
<h1 style="font-size:22px;color:#432f32;">Agenda du 21 au 27 septembre 2026</h1>
<p style="font-size:13px;color:#666;">Test statique : aucune donnée n'est lue sur le site pendant la génération.</p>
{cards}
<p style="font-size:12px;color:#888;margin-top:30px;"><a href="feed.xml">Ouvrir le flux RSS</a></p>
</div>
</body>
</html>'''

def main():
    (OUTPUT_DIR / "feed.xml").write_text(build_rss(), encoding="utf-8")
    (OUTPUT_DIR / "index.html").write_text(build_preview(), encoding="utf-8")
    (OUTPUT_DIR / "history.json").write_text(
        json.dumps(
            {"2026-09-21": [ev["url"] for ev in EVENTS]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("TEST STATIQUE OK")
    print("Aucun appel au site Beaune Tourisme n'a été effectué.")
    print("6 événements écrits dans docs/feed.xml et docs/index.html.")
    for ev in EVENTS:
        print(f'- {ev["title"]} | {ev["date"]} | {ev["city"]}')

if __name__ == "__main__":
    main()
