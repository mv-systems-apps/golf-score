"""Laatste 20, dagresultaat boven 54, en een onbevestigde tik bij het weggaan.

Gevonden in de onafhankelijke review van 13527DA-13D:
  1. Een afgeronde qualifying ronde zonder dagresultaat (9 holes zonder index erbij) nam
     een plek in de laatste 20 in en drukte een geldige 21e ronde eruit.
  2. Een vastgesteld dagresultaat boven 54 werd stil 54,0, en de backupkeuring weigerde
     dagresultaten boven 60. De grens van 54 geldt voor de index (Rules of Handicapping
     2024, regel 5.2), niet voor een dagresultaat.
  3. Een tik die nog op bevestiging wacht (score of het wissen van de putts) stond al in
     de opslag. Ging de app daarna naar de achtergrond en werd hij gesloten, dan bleef die
     onbevestigde wijziging staan.

De regels:
  1. In de laatste 20 tellen alleen rondes met een dagresultaat; overal dezelfde 20
     (handicap nu, handicapverloop per ronde).
  2. Een dagresultaat mag −20,0 t/m 100,0 zijn, bij invoer en bij inlezen.
  3. Gaat de app naar de achtergrond, dan wordt een onbevestigde tik teruggedraaid en dat
     meteen bewaard.
"""
import asyncio, json, os, sys, tempfile
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

PARS = [4, 3, 5, 4, 4, 3, 4, 5, 4]
def ronde(id_, dag, sd=None, holes=18, hcp=20.0):
    hs = [{"id": str(i + 1), "par": 4, "si": i + 1, "phcp": 1, "score": 5} for i in range(holes)]
    r = {"id": id_, "date": f"2026-{1 + dag // 28:02d}-{1 + dag % 28:02d}", "time": "10:00", "player": "Mark", "hcp": hcp, "club": "Golfclub Heelsum",
         "track": "Airborne", "tee": "Blauw", "gender": "Heren", "CR": 72.0 if holes == 18 else 36.0, "SR": 113, "PAR": 4 * holes, "chcp": 20 if holes == 18 else 10,
         "qualifying": True, "holes": hs}
    if sd is not None: r["sdFinal"] = sd
    return r
def bestand(x):
    pad = os.path.join(tempfile.mkdtemp(), 'in.json'); json.dump(x, open(pad, 'w', encoding='utf-8')); return pad

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.goto(app_url())
        async def zet(rondes, actief=None):
            await pg.evaluate("""([c, r, a]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
                if (a) localStorage.setItem('golf_active_id', String(a)); localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Mark');
                localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); }""", [CLUBS, rondes, actief])
            await pg.reload(); await pg.wait_for_timeout(600)

        print("\n=== 1. DE LAATSTE 20: ALLEEN RONDES MET EEN DAGRESULTAAT ===\n")
        # 20 rondes met dagresultaat (de oudste 5,0, de rest 20,0..39,0), en als nieuwste een
        # 9-holesronde zonder index (geen dagresultaat). De laagste 8 van de 20: 5,0 en 20..26
        # → (5 + 20+21+22+23+24+25+26) / 8 = 20,75 → 20,8. Zonder de oudste: 20..27 → 23,5.
        rondes = [ronde(1, 1, 5.0)] + [ronde(k + 2, k + 2, 20.0 + k) for k in range(19)] + [ronde(99, 60, holes=9, hcp=None)]
        await zet(rondes)
        check("de nieuwste 9-holesronde heeft geen dagresultaat", await pg.evaluate("() => effectiveSD(leesRondes().find(r => r.id === 99))"), None)
        check("de laatste 20 bevatten de oudste (5,0), niet de ronde zonder dagresultaat",
              await pg.evaluate("() => { const l = last20Qualifying('Mark', leesRondes(), null, null).map(r => r.id); return [l.length, l.includes(1), l.includes(99)]; }"), [20, True, False])
        check("handicap nu: 20,8", await pg.evaluate("() => whsHandicap(last20Qualifying('Mark', leesRondes(), null, null), null, esrMapFor('Mark', leesRondes())).value"), 20.8)
        await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(400)
        kaart = await pg.evaluate("() => { const e = document.getElementById('round-full-20'); return e ? e.textContent.replace(/\\s+/g, ' ') : ''; }")
        officieel = await pg.evaluate("() => { const all = leesRondes(); return whsHandicap(last20Qualifying('Mark', all, null, null), effectiveLowHi('Mark', all), esrMapFor('Mark', all)).value; }")
        import re as _re
        m = _re.search(r'Whs (-?\d+[.,]\d)(-?\d+[.,]\d)', kaart)
        check("de kaart van de nieuwste ronde met dagresultaat toont dezelfde handicap als de app nu geeft", float(m.group(2).replace(',', '.')) if m else None, officieel)

        print("\n=== 2. DAGRESULTAAT BOVEN 54 ===\n")
        await zet([ronde(5, 5, None, hcp=54.0)])
        await pg.evaluate("() => { nav('archive'); doOpenRoundResultModal(0); }"); await pg.wait_for_timeout(300)
        veld = pg.locator('#editSdInput')
        await veld.click(); await veld.fill(''); await veld.type('58.3'); await veld.blur(); await pg.wait_for_timeout(150)
        check("58,3 blijft in het veld staan", await veld.input_value(), '58.3')
        await pg.click('#roundResultModal button[onclick="confirmRoundResult()"]'); await pg.wait_for_timeout(400)
        check("en wordt zo bewaard", await pg.evaluate("() => leesRondes()[0].sdFinal"), 58.3)
        await pg.evaluate("() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); doOpenRoundResultModal(0); }"); await pg.wait_for_timeout(300)
        await veld.click(); await veld.fill(''); await veld.type('101'); await veld.blur(); await pg.wait_for_timeout(150)
        check("101 kan niet worden ingevoerd (het veld houdt 10)", await veld.input_value(), '10.0')
        await pg.evaluate("() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); nav('settings'); }")
        await pg.locator('#importRoundFile').set_input_files(bestand([ronde(6, 6, 75.0, hcp=54.0), ronde(7, 7, 101.0, hcp=54.0)])); await pg.wait_for_timeout(500)
        venster = await pg.evaluate("() => document.getElementById('keuzeModal').innerText.replace(/\\s+/g, ' ')")
        check("het bestand telt 1 inleesbare ronde (101,0 is geweigerd)", 'bevat 1 ronde' in venster, True)
        await pg.locator('#keuzeModal button', has_text='Toevoegen').click(); await pg.wait_for_timeout(500)
        check("inlezen: 75,0 wordt aangenomen, 101,0 niet", sorted(await pg.evaluate("() => leesRondes().map(r => r.sdFinal)"), key=lambda v: (v is None, v)), [58.3, 75.0])

        print("\n=== 3. ONBEVESTIGDE TIK BIJ HET WEGGAAN ===\n")
        lopend = ronde(50, 50, hcp=20.0); lopend['holes'] = [dict(h, score=None) for h in lopend['holes']]; lopend['holes'][0]['score'] = 5; lopend['holes'][0]['putts'] = 2
        lopend['holes'][1]['score'] = 4; lopend['holes'][1]['putts'] = 2
        await zet([lopend], actief=50)
        await pg.evaluate("() => nav('score')")
        weg = """() => { Object.defineProperty(document, 'hidden', { value: true, configurable: true }); document.dispatchEvent(new Event('visibilitychange'));
            Object.defineProperty(document, 'hidden', { value: false, configurable: true }); }"""
        opslag = "() => { const r = leesRondes()[0]; return [r.holes[0].score, r.holes[0].putts ?? null, r.holes[1].score]; }"
        await pg.evaluate("() => { setCurrentHole(1); armScoreChange(1, 7); }")
        check("de voorlopige score staat al in de opslag", (await pg.evaluate(opslag))[2], 7)
        await pg.evaluate(weg); await pg.wait_for_timeout(200)
        check("naar de achtergrond: de score is terug op 4, ook in de opslag", (await pg.evaluate(opslag))[2], 4)
        await pg.evaluate("() => { setCurrentHole(0); clearPutts(0); }")
        check("putts voorlopig gewist", (await pg.evaluate(opslag))[1], None)
        await pg.evaluate("() => window.dispatchEvent(new PageTransitionEvent('pagehide'))"); await pg.wait_for_timeout(200)
        check("pagina verlaten: de putts zijn terug (2)", (await pg.evaluate(opslag))[1], 2)
        await pg.evaluate("() => { setCurrentHole(1); armScoreChange(1, 6); confirmScoreTap(1); }")
        await pg.evaluate(weg); await pg.wait_for_timeout(200)
        check("een bevestigde tik blijft staan (6)", (await pg.evaluate(opslag))[2], 6)
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
