"""Een clubbackup maken en terugzetten geeft exact dezelfde clubs terug — en een bestand
dat niet deugt verandert niets.

Voor rondes is dit getest (test-ronde-velden.py). Voor clubs alleen in losse gevallen.
Hier met het eigen clubbestand (vijf clubs), aangevuld met een wedstrijdlus die zijn
herkomst onthoudt, zodat ook de nieuwste velden meedoen.

  1. alle clubs uitlezen, de app leegmaken, het bestand inlezen: alles is gelijk
  2. hetzelfde bestand inlezen over bestaande clubs heen (overschrijven): alles is gelijk,
     en de gekozen club, thuisclub en favorieten blijven staan
  3. één club uitlezen met de knop op de clubkaart en weer inlezen
  4. bestanden die niet deugen: er verandert niets
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import app_url
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
CLUBS = {c['club']: c for c in json.load(open(os.path.join(HIER, 'echte-clubs.json'), encoding='utf-8'))}
fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}" + ('' if ok else f": {str(echt)[:400]} — verwacht {str(verwacht)[:400]}"))
    if not ok: fouten.append(naam)

# De clubs zoals ze zijn opgeslagen, met de sleutels op vaste volgorde. De volgorde van
# holes en van holeIds blijft staan: die doet ertoe.
OPSLAG = """() => { const vast = v => Array.isArray(v) ? v.map(vast) : (v && typeof v === 'object') ? Object.fromEntries(Object.keys(v).sort().map(k => [k, vast(v[k])])) : v;
  return JSON.stringify(vast(JSON.parse(localStorage.getItem('golf_clubs') || '{}'))); }"""
KEUZES = "() => [localStorage.getItem('golf_default_club'), localStorage.getItem('golf_home_club'), localStorage.getItem('golf_fav_clubs')]"

async def start(pg, clubs):
    await pg.goto(app_url())
    await pg.evaluate("""(clubs) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(clubs)); localStorage.setItem('golf_rounds', '[]');
        localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_profile_name', 'Testspeler');
        localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_home_club', 'Golfclub Heelsum');
        localStorage.setItem('golf_fav_clubs', JSON.stringify(['Golfclub Zeewolde'])); }""", clubs)
    await pg.reload(); await pg.wait_for_timeout(400)

async def inlezen(pg, inhoud, bevestig=True):
    pad = os.path.join(HIER, '_clubs_in.json'); open(pad, 'w', encoding='utf-8').write(inhoud if isinstance(inhoud, str) else json.dumps(inhoud))
    await pg.evaluate("() => { document.querySelectorAll('[id$=Modal]:not(.hidden)').forEach(m => m.classList.add('hidden')); nav('settings'); }")
    await pg.locator('#importClubFile').set_input_files(pad); await pg.wait_for_timeout(450)
    if bevestig:
        await pg.evaluate("() => { const k = document.getElementById('confirmModalBtn'); if (k && !document.getElementById('confirmModal').classList.contains('hidden')) k.click(); }")
        await pg.wait_for_timeout(300)
    melding = await pg.evaluate("() => [...document.querySelectorAll('[id$=Modal]:not(.hidden)')].map(m => m.innerText.replace(/\\s+/g, ' ').trim().slice(0, 90))")
    await pg.evaluate("() => document.querySelectorAll('[id$=Modal]:not(.hidden)').forEach(m => m.classList.add('hidden'))")
    os.remove(pad)
    return melding

async def uitlezen(pg):
    return await pg.evaluate("async () => { let uit = null; window.tryWriteToExportFolder = async (n, j) => { uit = j; return true; }; await exportAllClubs(); return uit; }")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await start(pg, CLUBS)
        # Een wedstrijdlus erbij, via het echte venster, zodat 'bron' en 'bronStempel' meedoen.
        await pg.evaluate("""() => { nav('club'); openClubEditor('Golfclub Heelsum'); openLusMaker(); document.getElementById('lusNaam').value = 'Proeflus';
            kiesLusBron('Sandr'); [1, 2, 8].forEach(tikLusHole); kiesLusBron('Airborne'); [0, 1, 2, 3, 4, 5].forEach(tikLusHole); bewaarLus(); closeClubEditor(); }""")
        await pg.wait_for_timeout(250)
        voor = await pg.evaluate(OPSLAG); keuzes = await pg.evaluate(KEUZES)
        aantal = json.loads(voor)
        check("uitgangspunt: vijf clubs, de wedstrijdlus met herkomst", (len(aantal), 'bron' in aantal['Golfclub Heelsum']['courses']['Proeflus']), (5, True))

        print("\n=== 1. UITLEZEN, LEEGMAKEN, INLEZEN ===\n")
        bestand = await uitlezen(pg)
        check("het bestand bevat vijf clubs", len(json.loads(bestand)), 5)
        await start(pg, {})
        check("de app is leeg", await pg.evaluate(OPSLAG), '{}')
        await inlezen(pg, bestand)
        check("na inlezen zijn de clubs exact gelijk", await pg.evaluate(OPSLAG) == voor, True)
        check("nog een keer uitlezen geeft hetzelfde bestand", json.loads(await uitlezen(pg)) == json.loads(bestand), True)
        await pg.reload(); await pg.wait_for_timeout(400)
        check("en dat blijft zo na herladen", await pg.evaluate(OPSLAG) == voor, True)

        print("\n=== 2. INLEZEN OVER BESTAANDE CLUBS HEEN ===\n")
        await start(pg, json.loads(voor))
        await inlezen(pg, bestand)
        check("overschrijven met hetzelfde bestand verandert niets", await pg.evaluate(OPSLAG) == voor, True)
        check("gekozen club, thuisclub en favorieten blijven staan", await pg.evaluate(KEUZES), keuzes)
        check("het startscherm toont nog de banen van de gekozen club", await pg.evaluate("() => { nav('setup'); sel.holeCount = null; sel._holeCountUserCleared = true; buildTrackList(); return Object.keys(COURSES).length; }"),
              len(aantal['Golfclub Heelsum']['courses']))

        print("\n=== 3. ÉÉN CLUB: UITLEZEN MET DE KNOP, VERWIJDEREN, INLEZEN ===\n")
        await pg.evaluate("() => { window._uit = null; window.tryWriteToExportFolder = async (n, j) => { window._uit = j; return true; }; nav('club'); }"); await pg.wait_for_timeout(250)
        await pg.evaluate("() => { const k = document.querySelector('button[data-club=\"Golfclub Heelsum\"][onclick^=\"exportClub\"]'); k.closest('.card').querySelectorAll('.hidden').forEach(e => e.classList.remove('hidden')); k.scrollIntoView({block:'center'}); }")
        knop = pg.locator('button[data-club="Golfclub Heelsum"][onclick^="exportClub"]').first
        await knop.click(); await pg.wait_for_timeout(120); await knop.click(); await pg.wait_for_timeout(400)
        een = await pg.evaluate("() => window._uit")
        await pg.evaluate("() => { delete CLUBS['Golfclub Heelsum']; rebuildCourseLookup(); saveClubsToStorage(); rebuildAll(); }")
        check("de club is weg", 'Golfclub Heelsum' in json.loads(await pg.evaluate(OPSLAG)), False)
        await inlezen(pg, een)
        check("na inlezen van die ene club is alles weer exact gelijk", await pg.evaluate(OPSLAG) == voor, True)

        print("\n=== 4. BESTANDEN DIE NIET DEUGEN VERANDEREN NIETS ===\n")
        heelsum = aantal['Golfclub Heelsum']
        def kapot(wijzig):
            c = json.loads(json.dumps(heelsum)); wijzig(c); return c
        def dubbele_si(c): t = c['courses']['Sandr']['tees']['Heren']['Rood']['holes']; t[1]['si'] = t[0]['si']
        def te_kort(c): c['courses']['Sandr']['tees']['Heren']['Rood']['holes'].pop()
        def geen_cr(c): del c['courses']['Sandr']['tees']['Heren']['Rood']['CR']
        def par_fout(c): c['courses']['Sandr']['tees']['Heren']['Rood']['holes'][0]['par'] = 9
        gevallen = [("geen JSON", "dit is geen clubbestand {"), ("leeg bestand", ""), ("een lijst rondes", [{"date": "2026-01-01", "holes": []}]), ("een lege lijst", []), ("één losse ronde", {"date": "2026-01-01", "holes": []}), ("een lijst met alleen kapotte clubs", [{"club": "X"}, {"courses": {}}]),
                    
                    ("club zonder banen", {"club": "Golfclub Heelsum", "shortName": "x", "courses": {}}),
                    ("dubbele SI", kapot(dubbele_si)), ("een hole te weinig", kapot(te_kort)), ("geen CR", kapot(geen_cr)), ("par 9", kapot(par_fout))]
        for naam, inhoud in gevallen:
            melding = await inlezen(pg, inhoud)
            check(f"{naam}: clubs ongewijzigd", await pg.evaluate(OPSLAG) == voor, True)
            check(f"{naam}: er komt een melding", len(melding) > 0 and not any('voltooid' in m.lower() for m in melding), True)
        echt = json.loads(next(iter(json.load(open(os.path.join(HIER, 'overstap-standen.json'), encoding='utf-8')).values()))['opslag']['golf_rounds'])[:3]
        melding = await inlezen(pg, echt)
        check("De eigen rondebackup bij Clubs: 'Import mislukt', met de aanwijzing dat het rondes zijn",
              [('mislukt' in m.lower(), 'rondes' in m.lower()) for m in melding], [(True, True)])
        check("en de clubs zijn ongewijzigd", await pg.evaluate(OPSLAG) == voor, True)
        # Een lijst met één goede en één kapotte club: de goede komt erin, de kapotte niet.
        goed = json.loads(json.dumps(aantal['Golfclub Zeewolde'])); goed['shortName'] = 'ZW-nieuw'
        melding = await inlezen(pg, [goed, kapot(dubbele_si)])
        na = json.loads(await pg.evaluate(OPSLAG))
        check("lijst met één goede en één kapotte club: de kapotte verandert niets", json.dumps(na['Golfclub Heelsum'], sort_keys=True) == json.dumps(aantal['Golfclub Heelsum'], sort_keys=True), True)
        check("en de melding zegt dat er een is overgeslagen", any('overgeslagen' in m.lower() for m in melding), True)

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
