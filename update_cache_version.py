#!/usr/bin/env python3
"""
Werkt CACHE_VERSION in sw-golf-score.js bij op basis van een hash van de app-bestanden
zelf. Verandert een van de bestanden en je draait dit script, dan verandert
de hash, dan verandert sw-golf-score.js van byte-inhoud, en dán detecteert de browser
dat er een nieuwe service worker geïnstalleerd moet worden (dat is het
enige signaal dat browsers gebruiken om een SW-update te starten).

Gebruik: python3 update_cache_version.py

LET OP: dit hoeft NIET na elke wijziging te draaien. De fetch-handler van de
service worker
ververst de cache toch al op de achtergrond bij elk bezoek, ongeacht de
versie — gebruikers krijgen dus sowieso vanzelf de nieuwste versie, met
hoogstens één bezoek vertraging. Draai dit script alleen wanneer:
  - er een bestand is toegevoegd/verwijderd uit APP_FILES, of
  - je een directe, volledige refresh wilt forceren i.p.v. de geleidelijke
    achtergrond-verversing.
"""
import hashlib
import re
import sys
from pathlib import Path

DIR = Path(__file__).parent
APP_FILES = ['index.html', 'golf-score.html', 'manifest.json', 'icon.svg', 'icon-180.png', 'icon-192.png', 'icon-512.png']
SW_FILE = DIR / 'sw-golf-score.js'

def compute_hash():
    h = hashlib.sha256()
    for name in APP_FILES:
        path = DIR / name
        if not path.exists():
            print(f'WAARSCHUWING: {name} niet gevonden, wordt overgeslagen in de hash', file=sys.stderr)
            continue
        h.update(path.read_bytes())
        h.update(b'\x00')  # scheidingsteken tussen bestanden
    return h.hexdigest()[:12]  # 12 hex-tekens is ruim voldoende om botsingen te voorkomen

def main():
    new_hash = compute_hash()
    new_version = f'golf-score-{new_hash}'
    if not SW_FILE.exists():
        print(f'FOUT: {SW_FILE.name} niet gevonden in {DIR}', file=sys.stderr)
        sys.exit(1)
    sw_content = SW_FILE.read_text()

    m = re.search(r"const CACHE_VERSION = '([^']*)';", sw_content)
    if not m:
        print(f'FOUT: CACHE_VERSION niet gevonden in {SW_FILE.name}', file=sys.stderr)
        sys.exit(1)
    old_version = m.group(1)

    if old_version == new_version:
        print(f'Geen wijziging: CACHE_VERSION is al actueel ({old_version})')
        return

    updated = sw_content.replace(
        f"const CACHE_VERSION = '{old_version}';",
        f"const CACHE_VERSION = '{new_version}';",
    )
    SW_FILE.write_text(updated)
    print(f'CACHE_VERSION bijgewerkt: {old_version}  ->  {new_version}')

if __name__ == '__main__':
    main()
