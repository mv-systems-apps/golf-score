"""De app meldt nooit "opgeslagen" of "geïmporteerd" als het wegschrijven is mislukt.

test-opslagstoring.py en test-opslagstoring-handelingen.py gaan over de ronde die je
speelt. Deze test gaat over de overige handelingen die iets wegschrijven: clubs bewerken,
verwijderen en importeren, en rondes bewerken, vaststellen, inlezen en verwijderen.

Tot 13527DA-122 keken de meeste daarvan niet of het schrijven gelukt was. Bij een volle
opslag zei de clubeditor "Opgeslagen" en de import "Import voltooid", terwijl de wijziging
na herladen weg was.

De regel, per handeling met een falende opslag:
  * er komt een melding dat het niet gelukt is, en geen melding dat het gelukt is;
  * de opslag is niet veranderd;
  * waar dat kan staat het scherm daarna weer gelijk aan de opslag (verwijderen, importeren).
"""
import asyncio, json, os, sys, tempfile
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
def tee(cr, sr): return {"CR": cr, "SR": sr, "holes": [{"par": p, "si": i + 1} for i, p in enumerate(PARS)]}
def club(naam, kort): return {"club": naam, "shortName": kort, "courses": {"Noord": {"holeIds": [f"N{i}" for i in range(1, 10)], "tees": {"Heren": {"Geel": tee(35.0, 120)}}},
                                                                            "Zuid": {"holeIds": [f"Z{i}" for i in range(1, 10)], "tees": {"Heren": {"Geel": tee(34.0, 118)}}}}}
CLUBS = {"Club A": club("Club A", "A"), "Club B": club("Club B", "B")}
def ronde(i, speler="Testspeler", **w):
    holes = [{"id": f"N{k + 1}", "par": p, "si": k + 1, "phcp": 2 if k < 6 else 1, "ppar": p + (2 if k < 6 else 1), "score": p + 2, "putts": 2} for k, p in enumerate(PARS)]
    r = {"id": 100 + i, "date": f"2026-06-{i + 1:02d}", "time": "10:00", "player": speler, "hcp": 30.7, "club": "Club A", "clubShort": "A", "track": "Noord", "gender": "Heren", "tee": "Geel",
         "CR": 35.0, "SR": 120, "PAR": 36, "chcp": 15, "qualifying": True, "pcc": 0, "sdFinal": 31.2, "started": True, "holesCount": 9, "currentHole": -1, "holes": holes, "total": 54, "totalStb": 18}
    r.update(w); return r
RONDES = [ronde(0), ronde(1), ronde(2, qualifying=False), ronde(3, speler="Gast"), ronde(4, _justImported=True)]

STORING = """(sleutel) => { window.__echt = window.__echt || Storage.prototype.setItem;
  Storage.prototype.setItem = function (k, v) { if (k === sleutel) { const e = new Error('vol'); e.name = 'QuotaExceededError'; throw e; } return window.__echt.call(this, k, v); }; }"""
HERSTEL = "() => { if (window.__echt) Storage.prototype.setItem = window.__echt; }"
# Alle zichtbare meldingen samen, daarna sluiten.
MELDING = """() => { const zicht = e => e && !e.classList.contains('hidden') && e.getClientRects().length;
  const t = [...document.querySelectorAll('#confirmModal, #keuzeModal, #clubEditorStatus, #courseEditorStatus')].filter(zicht).map(e => e.innerText).join(' | ').replace(/\\s+/g, ' ').trim();
  document.querySelectorAll('#confirmModal:not(.hidden) button').forEach(b => { if (/Sluiten/.test(b.textContent)) b.click(); }); return t; }"""
OPSLAG = "() => [localStorage.getItem('golf_rounds'), localStorage.getItem('golf_clubs')]"
def bestand(inhoud):
    pad = os.path.join(tempfile.mkdtemp(), 'in.json')
    with open(pad, 'w', encoding='utf-8') as f: json.dump(inhoud, f, ensure_ascii=False)
    return pad
def mislukt(m): return any(w in m.lower() for w in ('niet opgeslagen', 'mislukt', 'niet gelukt'))
def gelukt(m): return any(w in m.lower() for w in ('opgeslagen', 'voltooid', 'geïmporteerd', 'overschreven')) and not mislukt(m)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.goto(app_url())
        async def vers():
            await pg.evaluate(HERSTEL)
            await pg.evaluate("""([c, r]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
              localStorage.setItem('golf_default_club', 'Club A'); localStorage.setItem('golf_home_club', 'Club A'); localStorage.setItem('golf_profile_name', 'Testspeler'); localStorage.setItem('golf_profile_hcp', '30.7');
              localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString().slice(0, 10)); }""", [CLUBS, RONDES])
            await pg.reload(); await pg.wait_for_timeout(600); await pg.evaluate(MELDING); del pf[:]
        async def geval(naam, sleutel, doe, scherm_gelijk=None):
            await vers(); voor = await pg.evaluate(OPSLAG)
            await pg.evaluate(STORING, sleutel)
            try: await doe()
            except Exception as e: pf.append(f"{naam}: {str(e)[:100]}")
            await pg.wait_for_timeout(350)
            m = await pg.evaluate(MELDING)
            check(f"{naam}: gemeld als niet gelukt, en niet als gelukt", (mislukt(m), gelukt(m)), (True, False))
            check(f"{naam}: de opslag is onveranderd", await pg.evaluate(OPSLAG), voor)
            if scherm_gelijk: check(f"{naam}: het scherm is weer gelijk aan de opslag", await pg.evaluate(scherm_gelijk), True)
            check(f"{naam}: geen fout in de pagina", pf[:2], [])
            await pg.evaluate(HERSTEL)
        js = lambda code, *a: (lambda: pg.evaluate(code, *a))
        CLUBS_GELIJK = "() => JSON.stringify(CLUBS) === localStorage.getItem('golf_clubs')"
        DANGER = "() => { const m = document.getElementById('resetAllModal'); if (m && !m.classList.contains('hidden')) document.getElementById('dangerModalConfirmBtn').click(); }"

        print("\n=== CLUBS ===\n")
        await geval("clubeditor: korte naam wijzigen en opslaan", 'golf_clubs', js("() => { nav('club'); openClubEditor('Club B'); document.getElementById('editorShortName').value = 'BB'; saveClubFromEditor(); }"))
        async def club_weg():
            await pg.evaluate("() => { nav('club'); openClubEditor('Club B'); const k = document.querySelector('#clubEditorOverlay [onclick*=\"deleteClubFromEditor\"]'); k.dataset.confirm = '1'; deleteClubFromEditor(k); }")
            await pg.wait_for_timeout(200); await pg.evaluate(DANGER)
        await geval("club verwijderen", 'golf_clubs', club_weg, CLUBS_GELIJK)
        async def baan_weg():
            await pg.evaluate("() => { nav('club'); openClubEditor('Club B'); openCourseEditor('Zuid'); const k = document.querySelector('#courseEditorOverlay [onclick*=\"deleteCourseFromEditor\"]'); k.dataset.confirm = '1'; deleteCourseFromEditor(k); }")
            await pg.wait_for_timeout(200); await pg.evaluate(DANGER)
        await geval("baan verwijderen", 'golf_clubs', baan_weg, CLUBS_GELIJK)
        async def club_in(inhoud):
            await pg.evaluate("() => nav('club')"); await pg.locator('#importClubFile').set_input_files(bestand(inhoud)); await pg.wait_for_timeout(450)
        await geval("één club importeren", 'golf_clubs', lambda: club_in(club("Club C", "C")), CLUBS_GELIJK)
        await geval("meerdere clubs importeren", 'golf_clubs', lambda: club_in([club("Club C", "C"), club("Club D", "D")]), CLUBS_GELIJK)

        print("\n=== RONDES ===\n")
        async def ronde_in():
            r = ronde(20); [r.pop(k) for k in ('id', 'started', 'holesCount', 'currentHole', 'total', 'totalStb')]
            await pg.evaluate("() => nav('settings')"); await pg.locator('#importRoundFile').set_input_files(bestand(r)); await pg.wait_for_timeout(450)
        await geval("één ronde importeren", 'golf_rounds', ronde_in)
        await geval("een geïmporteerde ronde opslaan (Sla op)", 'golf_rounds', js("() => { nav('archive'); const i = loadSavedRounds().findIndex(r => r._justImported); const k = document.createElement('button'); k.dataset.roundId = String(loadSavedRounds()[i].id); k.dataset.confirm = '1'; document.body.appendChild(k); archiveImportedRound(i, k); k.remove(); }"))
        await geval("een ronde verwijderen", 'golf_rounds', js("() => { nav('archive'); performDeleteRound(0); }"))
        async def bewerk():
            await pg.evaluate("() => { nav('archive'); const i = loadSavedRounds().findIndex(r => r.id === 101); doOpenRoundInfoModal(i); }"); await pg.wait_for_timeout(250)
            await pg.evaluate("() => { const d = document.querySelector('#roundInfoModal input[type=date]'); d.value = '2026-07-15'; d.dispatchEvent(new Event('input', { bubbles: true })); d.dispatchEvent(new Event('change', { bubbles: true })); confirmRoundInfo(); }")
        await geval("een ronde bewerken (datum)", 'golf_rounds', bewerk)
        async def vaststellen():
            await pg.evaluate("() => { nav('archive'); const i = loadSavedRounds().findIndex(r => r.id === 101); doOpenRoundResultModal(i); }"); await pg.wait_for_timeout(250)
            await pg.evaluate("() => { const v = document.querySelector('#roundResultModal input[inputmode=decimal], #roundResultModal input[type=text]'); if (v) { v.value = '29.9'; v.dispatchEvent(new Event('input', { bubbles: true })); } confirmRoundResult(); }")
        await geval("een dagresultaat vaststellen", 'golf_rounds', vaststellen)
        async def hernoem():
            await pg.evaluate("() => { nav('setup'); const n = document.getElementById('iName'); n.dataset.vorigeNaam = 'Testspeler'; n.value = 'Marcus'; controleerNaamswijziging(n); }"); await pg.wait_for_timeout(250)
            await pg.evaluate("() => { const k = [...document.querySelectorAll('#keuzeModal:not(.hidden) button')].find(x => /Alles aanpassen/.test(x.textContent)); if (k) k.click(); }")
        await geval("spelernaam wijzigen: alles aanpassen", 'golf_rounds', hernoem)
        async def opschonen(fn, knop):
            await pg.evaluate("(a) => { nav('settings'); const k = document.createElement('button'); k.dataset.confirm = '1'; document.body.appendChild(k); window[a](k); k.remove(); }", fn); await pg.wait_for_timeout(250); await pg.evaluate(DANGER)
        await geval("niet-qualifying rondes opschonen", 'golf_rounds', lambda: opschonen('confirmPurgeNonQ', 0))
        await geval("rondes van andere spelers verwijderen", 'golf_rounds', lambda: opschonen('confirmDeleteOtherPlayers', 0))

        print("\n=== ZONDER STORING MELDT DE APP GEWOON SUCCES ===\n")
        await vers()
        await pg.evaluate("() => { nav('club'); openClubEditor('Club B'); document.getElementById('editorShortName').value = 'BB'; saveClubFromEditor(); }"); await pg.wait_for_timeout(300)
        m = await pg.evaluate(MELDING)
        check("clubeditor: Opgeslagen, en de korte naam staat in de opslag", (gelukt(m), await pg.evaluate("() => JSON.parse(localStorage.getItem('golf_clubs'))['Club B'].shortName")), (True, 'BB'))
        await club_in(club("Club C", "C")); m = await pg.evaluate(MELDING)
        check("club importeren: Import voltooid, en de club staat in de opslag", (gelukt(m), await pg.evaluate("() => 'Club C' in JSON.parse(localStorage.getItem('golf_clubs'))")), (True, True))
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
