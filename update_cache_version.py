#!/usr/bin/env python3
"""Verhoogt de cacheteller van Golf Score.

Twee stempels, met een eigen taak -- en maar een ervan hoort in een script:

  Versie <HEX(yyyymmdd)-NNN>      onderaan Instellingen in golf-score.html.
                                  Hieraan ziet de app dat er een nieuwe versie
                                  in de offline-kopie staat. Dit stempel gaat
                                  met de HAND omhoog, bij elke wijziging aan de
                                  app. Zo schrijven de gedeelde conventies het
                                  voor: een script verhoogt het ook bij een
                                  wijziging die niemand hoeft te zien, en dan
                                  staat er een melding tegenover niets.
  CACHE_VERSION  in sw-golf-score.js
                                  de naam van de cache ('golf-score-v' + dit
                                  getal). Die gaat omhoog zodra sw-golf-score.js
                                  zelf wijzigt, of als er een bestand bij komt of
                                  af gaat in APP_FILES. Doe je dat niet, dan vult
                                  de nieuwe service worker tijdens zijn
                                  installatie dezelfde cache waaruit de oude nog
                                  bedient.

Dezelfde werkwijze als bij Trends en Events. Tot 16-10-2026 rekende dit script een
hash uit over de appbestanden; daar zat de service worker zelf niet in, dus juist
bij een wijziging daaraan bleef de naam gelijk.

    python3 update_cache_version.py          verhoogt CACHE_VERSION
"""

import re
import sys
from pathlib import Path

DIR = Path(__file__).parent
SW_FILE = DIR / 'sw-golf-score.js'
PATROON = re.compile(r"(const CACHE_VERSION\s*=\s*)(\d+)(\s*;)")


def main() -> int:
    if not SW_FILE.exists():
        print(f"Niet gevonden: {SW_FILE}", file=sys.stderr)
        return 1
    tekst = SW_FILE.read_text(encoding="utf-8")
    treffer = PATROON.search(tekst)
    if not treffer:
        print(f"CACHE_VERSION niet gevonden in {SW_FILE.name}", file=sys.stderr)
        return 1
    oud = int(treffer.group(2))
    SW_FILE.write_text(PATROON.sub(rf"\g<1>{oud + 1}\g<3>", tekst, count=1), encoding="utf-8")
    print(f"{SW_FILE.name}: CACHE_VERSION {oud} -> {oud + 1}")
    print("Het versiestempel in golf-score.html is NIET aangeraakt: dat gaat met de hand.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
