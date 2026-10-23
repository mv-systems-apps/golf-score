"""Wat je ziet, wordt uitgerekend uit de holes, niet overgenomen uit een opgeslagen totaal.

Een ronde bewaart naast de holes ook een Stableford-totaal (totalStb) en per hole de netto
par (ppar). Die kunnen ontbreken (een backup bevat totalStb niet) of verouderd zijn (een
bewerkte ronde, een bestand van elders). Gecontroleerd op de plekken waar ze gelezen
worden: de rondekaart, het gemiddelde op Statistiek, de CSV-export en de kopie voor een
AI-gesprek. Ook met de eigen rondes, die zonder totalStb in de opslag kunnen staan.
"""
import asyncio, json, os, re, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

def stb(r): return sum(max(0, h['par'] + h['phcp'] + 2 - h['score']) for h in r['holes'] if h.get('score') is not None)

goed = ronde(1, '2026-09-01');     goed['totalStb'] = stb(goed)
fout = ronde(2, '2026-09-02');     fout['totalStb'] = 99                     # verouderd
weg  = ronde(3, '2026-09-03');     del weg['totalStb']                       # ontbreekt, zoals na een backup
zonder = ronde(4, '2026-09-04');   zonder['totalStb'] = stb(zonder)
for h in zonder['holes']: del h['ppar']                                     # netto par ontbreekt
half = ronde(5, '2026-09-05', played=5); half['totalStb'] = stb(half)
for h in half['holes']: del h['ppar']                                       # half gespeeld, uit een bestand zonder netto par
RONDES = [goed, fout, weg, zonder]
ECHT = {r['id']: stb(r) for r in RONDES}

ZET = """([c, r, s]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
  localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', s); localStorage.setItem('golf_player_name', s);
  localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); }"""
KAARTEN = """() => [...document.querySelectorAll('#savedList [onclick^="openExportModal("]')].map(k => {
  const i = +k.getAttribute('onclick').match(/\\((\\d+)/)[1]; const r = loadSavedRounds()[i];
  let kaart = k; while (kaart && !(kaart.textContent || '').match(/Stb|Stableford/) && kaart.parentElement && kaart.parentElement.id !== 'savedList') kaart = kaart.parentElement;
  const m = (kaart.textContent || '').match(/Stb (\\d+)/); return [r.id, m ? +m[1] : null]; })"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={"width": 390, "height": 844}, accept_downloads=True)
        pg = await ctx.new_page(); await pg.goto(app_url()); await pg.evaluate(ZET, [CLUBS, RONDES, 'Testspeler'])
        await pg.reload(); await pg.wait_for_timeout(600); await pg.evaluate("document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))")

        print("\n=== RONDEKAART ===\n")
        await pg.click('#tab-archive'); await pg.wait_for_timeout(300)
        k = dict(await pg.evaluate(KAARTEN))
        for r, naam in [(goed, 'totaal klopt'), (fout, 'totaal verouderd (99)'), (weg, 'totaal ontbreekt'), (zonder, 'netto par ontbreekt')]:
            check(f"kaart, {naam}: Stb is de som over de holes", k.get(r['id']), ECHT[r['id']])

        print("\n=== STATISTIEK ===\n")
        await pg.click('#tab-stat'); await pg.wait_for_timeout(500)
        gem = await pg.evaluate("""() => { const t = [...document.querySelectorAll('*')].find(e => e.children.length === 0 && e.textContent.trim() === 'Gem. Stb');
            if (!t) return null; const kaart = t.closest('div').parentElement; return kaart.textContent.replace('Gem. Stb', '').trim(); }""")
        # Sinds 13527DA-145 rekent Gem. Stb met de volle baanhandicap (keuze van de gebruiker): de slagen
        # per hole uit index, CR, SR en par van de ronde, niet de gespeelde. Ook dan komt het
        # uit de holes en nooit uit een opgeslagen totaal (hier 99 bij één ronde).
        verwacht = await pg.evaluate("() => { const q = leesRondes().filter(r => r.qualifying); return (q.reduce((s, r) => s + stbVoorStatistiek(r), 0) / q.length).toFixed(1); }")
        check("Gem. Stb is het gemiddelde over de holes van alle vier (met de volle baanhandicap)", gem, verwacht)
        check("en niet beïnvloed door het opgeslagen totaal van 99", gem != f"{(sum(ECHT.values()) - ECHT[fout['id']] + 99) / len(ECHT):.1f}", True)

        print("\n=== CSV-EXPORT ===\n")
        async with pg.expect_download() as d: await pg.evaluate("exportCsv(loadSavedRounds().find(r => r.id === 4))")
        csv = open(await (await d.value).path(), encoding='utf-8').read()
        check("CSV van een ronde zonder netto par: geen 'undefined' of 'NaN'", [w for w in ('undefined', 'NaN') if w in csv], [])
        regels = [l for l in csv.split('\n') if re.match(r'^"?\d+"?,', l)]
        check("en de netto par per hole is par + slagen", [l.split(',')[3].strip('"') for l in regels[:3]], [str(h['par'] + h['phcp']) for h in zonder['holes'][:3]])

        print("\n=== DOORSPELEN OP EEN RONDE ZONDER NETTO PAR ===\n")
        await pg.evaluate(ZET, [CLUBS, RONDES + [half], 'Testspeler']); await pg.evaluate("localStorage.setItem('golf_active_id', '5')")
        await pg.reload(); await pg.wait_for_timeout(700); await pg.evaluate("document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))")
        await pg.click('#tab-score'); await pg.wait_for_timeout(300)
        h = await pg.evaluate("() => { const i = currentHole; setDoubleBogey(i); return [i, game.holes[i].score, game.holes[i].par + game.holes[i].phcp + 2]; }")
        await pg.wait_for_timeout(2500)
        opg = await pg.evaluate(f"JSON.parse(localStorage.getItem('golf_rounds')).find(r => r.id === 5).holes[{h[0]}].score")
        check("lang indrukken (netto dubbel bogey) geeft par + slagen + 2, ook in de opslag", (h[1], opg), (h[2], h[2]))

        print("\n=== HET TOTAAL STAAT NIET MEER IN DE OPSLAG ===\n")
        IN_OPSLAG = "() => JSON.parse(localStorage.getItem('golf_rounds')).filter(r => 'totalStb' in r).map(r => r.id)"
        check("na het spelen van een score op de lopende ronde: niet in die ronde", 5 in await pg.evaluate(IN_OPSLAG), False)
        backup = await pg.evaluate("() => JSON.parse(localStorage.getItem('golf_rounds'))")
        await pg.evaluate("(r) => { const g = schiftRondes(r).goed; doFullRestoreImport(g, false); }", backup); await pg.wait_for_timeout(400)
        check("na het terugzetten van een backup: in geen enkele ronde", await pg.evaluate(IN_OPSLAG), [])
        html = open(os.environ.get('APP') or os.path.join(os.path.dirname(HIER), 'golf-score.html'), encoding='utf-8').read()
        lezers = [m.group(0) for m in re.finditer(r'.{0,30}\.totalStb\b.{0,20}', html) if 'delete entry.totalStb' not in m.group(0)]
        check("statisch: de code leest of schrijft het opgeslagen totaal nergens", lezers, [])
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN)" if fouten else "\nGEEN FOUTEN"); sys.exit(1 if fouten else 0)
asyncio.run(main())
