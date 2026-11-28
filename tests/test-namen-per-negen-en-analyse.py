"""Hole- en baannamen blijven tekst in 'Per negen' en in de aanbevelingen van de spelanalyse.

Gevonden in de onafhankelijke review van 13527DA-13D: op twee plekken kwam een naam
onbewerkt in het scherm:
  * het kopje 'Per negen' in het rondeoverzicht (de holenamen van de eerste en laatste
    hole, bij een ronde van 18 holes);
  * de aanbeveling 'hole … levert je in … van de … keer 0 punten op' in de spelanalyse
    (de baannaam).
Een clubbestand van een ander met zo'n naam liet daar code draaien.

De regel: een naam is tekst, ook daar. Er draait niets, en de naam staat er letterlijk.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

def naam(tag): return f'<img src=x onerror="__x.push(\'{tag}\')">'
BAAN = naam('baan'); HOLES = [naam(f'h{i + 1}') if i in (0, 8, 9, 17) else f'H{i + 1}' for i in range(18)]
TEE = {"CR": 72.0, "SR": 130, "holes": [{"par": 4, "si": i + 1} for i in range(18)]}
CLUBS = {"Club": {"club": "Club", "shortName": "Club", "courses": {BAAN: {"holeIds": HOLES, "tees": {"Heren": {"Geel": TEE}}}}}}
def ronde(k, actief=False):
    holes = [{"id": HOLES[i], "par": 4, "si": i + 1, "phcp": 1, "ppar": 5, "score": None if actief and i > 12 else (8 if i == 0 else 5), "putts": 2} for i in range(18)]
    return {"id": 1700000000000 + k, "date": f"2026-0{1 + k % 9}-{10 + k % 18}", "time": "10:00", "player": "Testspeler", "hcp": 18.0, "gender": "Heren",
            "track": BAAN, "tee": "Geel", "club": "Club", "clubShort": "Club", "CR": 72.0, "SR": 130, "PAR": 72, "chcp": 18, "qualifying": True, "holes": holes}

async def main():
    rondes = [ronde(k) for k in range(12)] + [ronde(99, actief=True)]
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.add_init_script("window.__x = [];")
        await pg.goto(app_url())
        await pg.evaluate("""([c, r]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
            localStorage.setItem('golf_active_id', String(r[r.length - 1].id)); localStorage.setItem('golf_default_club', 'Club'); localStorage.setItem('golf_profile_name', 'Testspeler');
            localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); }""", [CLUBS, rondes])
        await pg.reload(); await pg.wait_for_timeout(800)
        check("de lopende ronde van 18 holes is geladen", await pg.evaluate("() => [game.started, game.holes.length]"), [True, 18])

        print("\n=== 1. PER NEGEN ===\n")
        for t in ('score', 'stat'):
            await pg.evaluate("(t) => nav(t)", t); await pg.wait_for_timeout(500)
        tekst = await pg.evaluate("() => document.getElementById('sumInfo').textContent")
        check("'Per negen' staat in beeld", 'Per negen' in tekst or '...' in tekst, True)
        check("de holenaam staat er letterlijk", HOLES[0] in tekst, True)
        check("er is geen code uitgevoerd", await pg.evaluate("() => window.__x"), [])

        print("\n=== 2. AANBEVELING IN DE SPELANALYSE ===\n")
        await pg.evaluate("() => { nav('stat'); openGameAnalysis(); }"); await pg.wait_for_timeout(800)
        alles = await pg.evaluate("() => document.body.textContent")
        check("de aanbeveling over 0 punten staat er", 'keer 0 punten op' in alles, True)
        check("de baannaam staat er letterlijk", BAAN in alles, True)
        check("er is geen code uitgevoerd", await pg.evaluate("() => window.__x"), [])
        check("geen element uit een naam", await pg.evaluate("() => document.querySelectorAll('img[src=\"x\"]').length"), 0)
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
