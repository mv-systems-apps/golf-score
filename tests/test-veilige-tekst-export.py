"""Tekst uit de gegevens blijft tekst: in het scherm, in een rekenblad en in de agenda.

Uit de security audit van 13527DA-135:
  * de startmelding "Tee … heeft geen volledige par/SI-gegevens" zette de teenaam als
    HTML in beeld; code in een teenaam werd daar uitgevoerd;
  * in de CSV-export werd een naam die met = + - of @ begint door Excel of Sheets als
    formule uitgevoerd (bijvoorbeeld uit een geïmporteerde ronde van een medespeler);
  * in de agenda-export bleef een losse regeleinde-code (\\r) in de clubnaam staan, zodat
    de clubnaam een extra regel in de afspraak kon maken.

De regel: een naam is tekst. In beeld letterlijk, in de CSV met een ' ervoor als hij met
een formuleteken begint, in de agenda zonder eigen regeleinden. Getallen en de teksten
die de app zelf maakt, blijven precies gelijk.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

PARS = [4, 3, 5, 4, 4, 3, 4, 5, 4]
TEE_HTML = '<img src=x onerror=__x.push(1)>'
def club(tee, holes=9):
    return {"C": {"club": "C", "shortName": "C", "courses": {"B": {"holeIds": [f"H{i}" for i in range(1, 10)],
            "tees": {"Heren": {tee: {"CR": 35.0, "SR": 120, "holes": [{"par": p, "si": i + 1} for i, p in enumerate(PARS)][:holes]}}}}}}}
def ronde(**v):
    r = {"id": 1, "date": "2026-06-10", "time": "10:00", "player": "Testspeler", "hcp": 30.7, "club": "C", "clubShort": "C", "track": "B",
         "gender": "Heren", "tee": "Geel", "CR": 35.0, "SR": 120, "PAR": 36, "chcp": 15, "qualifying": True, "pcc": 0,
         "holes": [{"id": f"H{i + 1}", "par": p, "si": i + 1, "phcp": 2 if i < 6 else 1, "score": p + 2, "putts": 2} for i, p in enumerate(PARS)]}
    r.update(v); return r

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, accept_downloads=True)
        pg = await ctx.new_page()
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.add_init_script("window.__x = [];")
        await pg.goto(app_url())

        print("\n=== 1. STARTMELDING MET EEN TEENAAM VOL TEKENS ===\n")
        await pg.evaluate("""(c) => { localStorage.clear(); localStorage.setItem('golf_rounds', '[]'); localStorage.setItem('golf_clubs', JSON.stringify(c));
          localStorage.setItem('golf_default_club', 'C'); localStorage.setItem('golf_home_club', 'C'); localStorage.setItem('golf_profile_name', 'Testspeler');
          localStorage.setItem('golf_kenmerk_gevraagd', '1'); }""", club(TEE_HTML, holes=8))
        await pg.reload(); await pg.wait_for_timeout(500)
        await pg.evaluate("""(t) => { nav('setup'); sel.track = 'B'; sel.gender = 'Heren'; sel.tee = t; document.getElementById('iName').value = 'Testspeler';
          document.getElementById('iHcp').value = '30.7'; startRound(); const cb = document.getElementById('confirmModalBtn');
          if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""", TEE_HTML)
        await pg.wait_for_timeout(400)
        check("de melding verschijnt", 'geen volledige par/SI-gegevens' in await pg.evaluate("() => document.getElementById('startRoundError').textContent"), True)
        check("de teenaam staat er letterlijk als tekst", TEE_HTML in await pg.evaluate("() => document.getElementById('startRoundError').textContent"), True)
        check("er is geen element uit de teenaam ontstaan", await pg.evaluate("() => document.querySelectorAll('#startRoundError img').length"), 0)
        check("er is geen code uitgevoerd", await pg.evaluate("() => window.__x"), [])
        check("er is geen ronde gestart", await pg.evaluate("() => game.started"), False)

        print("\n=== 2. CSV: NAMEN DIE MET EEN FORMULETEKEN BEGINNEN ===\n")
        async def csv_van(r):
            async with pg.expect_download() as d:
                await pg.evaluate("(r) => exportCsv(r)", r)
            pad = await (await d.value).path()
            return open(pad, encoding='utf-8-sig', newline='').read()
        def cel(csv, label):
            for regel in csv.split('\r\n'):
                if regel.startswith(f'"{label}",'): return regel.split(',', 1)[1]
        csv = await csv_van(ronde(player='=HYPERLINK("http://x","klik")', club='+Club', clubShort='@kort', track='-Baan', tee='=Geel',
                                  holes=[dict(h, id='=1+1' if i == 0 else h['id']) for i, h in enumerate(ronde()['holes'])]))
        check("speler krijgt een ' ervoor", cel(csv, 'Speler'), '"\'=HYPERLINK(""http://x"",""klik"")"')
        check("club krijgt een ' ervoor", cel(csv, 'Club'), '"\'+Club"')
        check("korte clubnaam krijgt een ' ervoor", cel(csv, 'ClubKort'), '"\'@kort"')
        check("baan krijgt een ' ervoor", cel(csv, 'Baan'), '"\'-Baan"')
        check("tee krijgt een ' ervoor", cel(csv, 'Tee'), '"\'=Geel"')
        check("holenaam krijgt een ' ervoor, de rest van de regel blijft gelijk", [r for r in csv.split('\r\n') if r.startswith('"\'=1+1"')], ['"\'=1+1","1","4","6","6","2","2","6","Dubbel"'])
        gewoon = await csv_van(ronde())
        check("gewone namen blijven gelijk", [cel(gewoon, k) for k in ('Speler', 'Club', 'Baan', 'Tee', 'Geslacht')], ['"Testspeler"', '"C"', '"B"', '"Geel"', '"Heren"'])
        check("de teksten van de app zelf blijven gelijk", cel(gewoon, 'Bruto'), '"54","+18 vs par"')
        check("de gewone holeregel blijft gelijk", [r for r in gewoon.split('\r\n') if r.startswith('"H1"')], ['"H1","1","4","6","6","2","2","6","Dubbel"'])

        print("\n=== 3. AGENDA: LOSSE REGELEINDE-CODE IN DE CLUBNAAM ===\n")
        await pg.evaluate("(r) => { localStorage.setItem('golf_rounds', JSON.stringify([r])); _rondesCache = null; }",
                          ronde(id=77, club='Club\rDESCRIPTION:ingevoegd', date='2026-12-01', holes=[dict(h, score=None) for h in ronde()['holes']]))
        await pg.evaluate("() => { try { Object.defineProperty(navigator, 'share', { value: undefined, configurable: true }); Object.defineProperty(navigator, 'canShare', { value: undefined, configurable: true }); } catch (e) {} }")
        async with pg.expect_download() as d:
            await pg.evaluate("() => exportRoundIcs(77)")
        ics = open(await (await d.value).path(), encoding='utf-8', newline='').read()
        regels = ics.split('\r\n')
        check("geen losse regeleinde-code in het bestand", '\r' in ics.replace('\r\n', ''), False)
        check("de clubnaam staat op één regel", [r for r in regels if r.startswith('LOCATION:')], ['LOCATION:Club\\nDESCRIPTION:ingevoegd'])
        check("er is geen extra regel ontstaan", [r for r in regels if r.startswith('DESCRIPTION')], [])

        check("aan het eind: geen fouten in de pagina", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
