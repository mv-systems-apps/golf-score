"""Overal waar de AGS in beeld of in een export staat, is het de AGS van de volledige course handicap.

Rules of Handicapping 2024, regel 3.1b (zie test-ags-volledige-baanhandicap.js voor het
rekenwerk). Deze test kijkt of alle plekken dezelfde, juiste waarde tonen: het
rondeoverzicht, de rondekaart, de tekst om te delen, de CSV (totaal en per hole) en het
dagresultaat. Stableford en netto blijven op de gespeelde (85%-)handicap.

Ronde: HI 20, CR 72,0, SR 130, par 72 (alle holes par 4, SI 1..18) → CH 23; met 85%
gespeeld (20 slagen). Zestien holes een 5; op SI 4 en 5 een 8.
  - AGS volgens de regel: 16 × 5 + 8 + 8 = 96; dagresultaat 20,9.
  - Tot 13527DA-13D: 94 en 19,1.
  - Stableford blijft met de 20 gespeelde slagen gerekend, zoals voorheen.
"""
import asyncio, json, os, sys, tempfile
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

SLAGEN_85 = [2 if si <= 2 else 1 for si in range(1, 19)]          # 20 slagen
SCORES = [8 if si in (4, 5) else 5 for si in range(1, 19)]
STB = sum(max(0, 4 + s + 2 - sc) for s, sc in zip(SLAGEN_85, SCORES))   # Stableford op de gespeelde handicap
TEE = {"CR": 72.0, "SR": 130, "holes": [{"par": 4, "si": i + 1} for i in range(18)]}
CLUBS = {"Club": {"club": "Club", "shortName": "Club", "courses": {"Baan": {"holeIds": [f"H{i + 1}" for i in range(18)], "tees": {"Heren": {"Geel": TEE}}}}}}
RONDE = {"id": 1700000000001, "date": "2026-06-10", "time": "10:00", "player": "Testspeler", "hcp": 20.0, "gender": "Heren", "track": "Baan", "tee": "Geel",
         "club": "Club", "clubShort": "Club", "CR": 72.0, "SR": 130, "PAR": 72, "chcp": 20, "qualifying": True, "pcc": 0,
         "holes": [{"id": f"H{i + 1}", "par": 4, "si": i + 1, "phcp": SLAGEN_85[i], "ppar": 4 + SLAGEN_85[i], "score": SCORES[i], "putts": 2} for i in range(18)]}

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={"width": 390, "height": 844}, accept_downloads=True); pg = await ctx.new_page()
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.goto(app_url())
        await pg.evaluate("""([c, r]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify([r]));
            localStorage.setItem('golf_default_club', 'Club'); localStorage.setItem('golf_profile_name', 'Testspeler'); localStorage.setItem('golf_kenmerk_gevraagd', '1');
            localStorage.setItem('golf_last_backup_date', new Date().toISOString()); }""", [CLUBS, RONDE])
        await pg.reload(); await pg.wait_for_timeout(700)

        print("\n=== REKENWERK IN DE APP ===\n")
        check("dagresultaat 20,9", await pg.evaluate("() => computeSD(leesRondes()[0])"), {"value": 20.9, "approx": False})
        check("Stableford blijft op de gespeelde handicap", await pg.evaluate("() => stbTotaal(leesRondes()[0])"), STB)

        print("\n=== RONDEKAART ===\n")
        await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(500)
        kaart = await pg.evaluate("() => document.getElementById('savedList').textContent.replace(/\\s+/g, ' ')")
        check("de kaart toont geen afgetopte 94 (bruto 96 is hier ook de AGS)", ' 96' in kaart and ' 94' not in kaart, True)
        check("de kaart toont dagresultaat 20,9", '20,9' in kaart or '20.9' in kaart, True)

        print("\n=== TEKST OM TE DELEN ===\n")
        tekst = await pg.evaluate("() => buildScoreText(leesRondes()[0])")
        check("Aangepast (AGS): 96", 'Aangepast (AGS): 96' in tekst, True)
        check("Voorlopig dagresultaat: 20.9", 'Voorlopig dagresultaat: 20.9' in tekst, True)

        print("\n=== CSV ===\n")
        async with pg.expect_download() as d:
            await pg.evaluate("() => exportCsv(leesRondes()[0])")
        csv = open(await (await d.value).path(), encoding='utf-8-sig', newline='').read()
        regels = csv.split('\r\n')
        check("totaalregel: AGS 96", [r for r in regels if r.startswith('"Score",')], ['"Score","96","AGS","96"'])
        check("hole met SI 4: AGS 8 (net double bogey met 2 slagen)", [r.split(',')[7] for r in regels if r.startswith('"H4",')], ['"8"'])
        check("hole met SI 3: AGS 5", [r.split(',')[7] for r in regels if r.startswith('"H3",')], ['"5"'])

        print("\n=== ZELFDE RONDE ALS LOPENDE RONDE: OVERZICHT ===\n")
        await pg.evaluate("(r) => { localStorage.setItem('golf_active_id', String(r.id)); }", RONDE)
        await pg.reload(); await pg.wait_for_timeout(700)
        await pg.evaluate("() => nav('stat')"); await pg.wait_for_timeout(500)
        info = await pg.evaluate("() => document.getElementById('sumInfo').textContent.replace(/\\s+/g, ' ')")
        check("het rondeoverzicht toont Aangepast (AGS) 96", 'Aangepast (AGS) 96' in info or 'Aangepast (AGS)96' in info, True)
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
