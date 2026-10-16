"""Gedeelde testgegevens en hulpfuncties voor alle tests in deze map.

De tests draaien de ECHTE app in een headless browser en meten wat eruit komt.
Ze gaan uit van verzonnen rondes; jouw eigen gegevens staan hier bewust niet in.
Wil je tegen je eigen backup testen, zet die dan naast deze map als
'rondes_backup.json' — ijk-echt.py pakt hem dan op.
"""
import json, os, re, shutil, sys, tempfile

# Par en SI horen bij de tee (zie teePar in de app): de baan bewaart alleen holeIds.
HOLES_A = [{"par": [4,3,5,4,4,3,4,5,4][i], "si": i + 1} for i in range(9)]
HOLES_B = [{"par": [4,4,3,5,4,4,3,4,4][i], "si": i + 1} for i in range(9)]
HOLES_C = [{"par": [4,4,4,3,5,4,4,3,5][i], "si": i + 1} for i in range(9)]


# ── Pad naar de app ──────────────────────────────────────────────────────────
# Standaard: golf-score.html één map hoger. Anders: APP=... meegeven.
HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.environ.get('APP') or os.path.join(os.path.dirname(HIER), 'golf-score.html')

def zet_cachenaam(sw, naam):
    """Geeft de tekst van sw-golf-score.js terug met een vaste cachenaam, voor proeven met
    twee of meer versies. Sinds de drie apps gelijk zijn getrokken is de naam afgeleid van
    een teller (CACHE_NAME = 'golf-score-v' + CACHE_VERSION); de oude schrijfwijze met de
    naam zelf in CACHE_VERSION wordt ook herkend, zodat een proef tegen de vorige versie
    van de app kan draaien. Grijpt geen van beide aan, dan is dat een fout in de proef."""
    # Ook een naam die een eerdere aanroep al vast zette: een proef stelt vaak meerdere
    # versies na elkaar in.
    nieuw, n = re.subn(r"const CACHE_NAME = (?:'golf-score-v' \+ CACHE_VERSION|'[^']*');", f"const CACHE_NAME = '{naam}';", sw)
    if not n:
        nieuw, n = re.subn(r"const CACHE_VERSION = '[^']*';", f"const CACHE_VERSION = '{naam}';", sw)
    if not n:
        raise RuntimeError('cachenaam niet gevonden in sw-golf-score.js')
    return nieuw


def app_map():
    """De map met de app-bestanden zoals ze online komen (html, service worker, pictogrammen).

    In de werkmap is dat 'uit' naast tests_run2. In de GitHub-repository staat de map
    tests/ naast de app zelf; dan worden alleen de losse bestanden uit de hoofdmap naar een
    tijdelijke map gekopieerd (zonder tests/ en .git). Met UIT=... kies je zelf een map."""
    if os.environ.get('UIT'):
        return os.environ['UIT']
    uit = os.path.join(os.path.dirname(os.path.dirname(HIER)), 'uit')
    if os.path.isfile(os.path.join(uit, 'sw-golf-score.js')):
        return uit
    wortel = os.path.dirname(HIER)
    if os.path.isfile(os.path.join(wortel, 'sw-golf-score.js')):
        doel = tempfile.mkdtemp(prefix='golf-app-')
        for naam in os.listdir(wortel):
            pad = os.path.join(wortel, naam)
            if os.path.isfile(pad):
                shutil.copy2(pad, doel)
        return doel
    return uit

def app_url(pad=None):
    return 'file://' + os.path.abspath(pad or APP)

# ── Verzonnen banen ──────────────────────────────────────────────────────────
CLUBS = {
    "Golfclub Heelsum": {
        "club": "Golfclub Heelsum", "shortName": "Heelsum",
        "courses": {
            "Airborne": {
                "tees": {"Heren": {"Blauw": {"CR": 34.5, "SR": 120, "holes": HOLES_A},
                                    "Geel":  {"CR": 33.8, "SR": 116, "holes": HOLES_A}},
                          "Dames": {"Rood": {"CR": 36.0, "SR": 124, "holes": HOLES_A}}},
                "holeIds": [i + 1 for i in range(9)],
            },
            "Sandr": {
                "tees": {"Heren": {"Blauw": {"CR": 34.2, "SR": 118, "holes": HOLES_B}}},
                "holeIds": [i + 1 for i in range(9)],
            },
        },
    },
    "Papendal": {
        "club": "Papendal", "shortName": "Pap",
        "courses": {
            "Noord": {
                "tees": {"Heren": {"Wit": {"CR": 35.1, "SR": 121, "holes": HOLES_C}}},
                "holeIds": [i + 1 for i in range(9)],
            },
        },
    },
}

def ronde(rid, datum, baan="Airborne", club="Golfclub Heelsum", kort="Heelsum",
          tee="Blauw", speler="Mark", played=9, scores=None, putts=True, qual=True):
    """Eén ronde in het opslagformaat van de app."""
    pars = ([4,3,5,4,4,3,4,5,4] if baan == "Airborne"
            else [4,4,3,5,4,4,3,4,4] if baan == "Sandr" else [4,4,4,3,5,4,4,3,5])
    sc = scores or [p + (rid % 3) - 1 for p in pars]
    holes = [{"id": i + 1, "par": pars[i], "si": i + 1, "phcp": 1, "ppar": pars[i] + 1,
              "score": (sc[i] if i < played else None)} for i in range(9)]
    if putts:
        for i, h in enumerate(holes):
            if h["score"] is not None:
                h["putts"] = 2 if i % 4 else 1
    return {"id": rid, "date": datum, "time": "09:30", "player": speler, "hcp": 30.7,
            "club": club, "clubShort": kort, "track": baan, "gender": "Heren", "tee": tee,
            "CR": 34.5, "SR": 120, "PAR": sum(pars), "chcp": 11, "qualifying": qual,
            "total": sum(x for x in sc[:played]), "totalStb": 15,
            "holesCount": 9, "currentHole": 0, "started": True,
            "sd": 30.0 + (rid % 9), "sdFinal": 30.0 + (rid % 9), "pcc": 0, "holes": holes}

# Een gevarieerde set: twee jaar, drie banen, twee clubs, halve/geplande/andere-speler rondes
RONDES = []
for i in range(1, 41):
    RONDES.append(ronde(i, f'2026-{(i % 12) + 1:02d}-{(i % 27) + 1:02d}'))
for i in range(41, 61):
    RONDES.append(ronde(i, f'2025-{(i % 12) + 1:02d}-{(i % 27) + 1:02d}', baan="Sandr"))
for i in range(61, 71):
    RONDES.append(ronde(i, f'2025-0{(i % 8) + 1}-1{i % 9}', baan="Noord", club="Papendal", kort="Pap", tee="Wit"))
RONDES.append(ronde(80, '2026-08-01', played=5))                    # half gespeeld
RONDES.append(ronde(81, '2026-08-02', qual=False))                  # niet-qualifying
RONDES.append(ronde(82, '2026-08-03', putts=False))                 # zonder putts
RONDES.append(ronde(83, '2026-09-20', played=0))                    # gepland
RONDES.append(ronde(84, '2026-08-04', speler='Speler 2'))           # tweede speler

# ── Standaard opslag klaarzetten in de browser ───────────────────────────────
SEED = """([clubs, rondes]) => {
    localStorage.clear();
    localStorage.setItem('golf_clubs', JSON.stringify(clubs));
    localStorage.setItem('golf_rounds', JSON.stringify(rondes));
    localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
    localStorage.setItem('golf_home_club', 'Golfclub Heelsum');
    localStorage.setItem('golf_profile_name', 'Mark');
    localStorage.setItem('golf_profile_hcp', '30.7');
    localStorage.setItem('golf_track_putts', 'on');
    localStorage.setItem('golf_putts_stats', 'on');
    ['handicap','prestaties','banen'].forEach(g => localStorage.setItem('golf_stats_grp_' + g, 'open'));
}"""
