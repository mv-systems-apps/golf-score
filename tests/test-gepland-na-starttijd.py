"""Een geplande ronde blijft gepland, ook net na de starttijd (13528ED-003).

Vóór 13528ED-003 schoof een ronde van 10:00 om 10:01 van Gepland naar Gepauzeerd, en
verdween hij uit de kop: juist als je wilde starten, moest je hem zoeken. Nu blijft hij
gepland zolang het vandaag is en er nog geen score in staat. Met een vaste klok
(Europe/Amsterdam):

  1. om 10:20 staat de ronde van 10:00 in Gepland en in de kop ('Vandaag'), en een tik op
     de kop opent Rondes met die ronde in beeld; een ronde van vandaag met al een score en
     een niet gespeelde ronde van gisteren staan bij Gepauzeerd;
  2. met de eerste score is hij gepauzeerd;
  3. na middernacht is hij gepauzeerd en uit de kop;
  4. een ronde van vandaag zonder tijd (00:00) is de hele dag gepland;
  5. de agenda-export blijft na de starttijd uit (een afspraak in het verleden zet je niet).
"""
import asyncio, datetime, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

def lokaal(j, m, d, u, mi=0):
    """Een tijd in Amsterdam (november: wintertijd, UTC+1) als UTC."""
    return datetime.datetime(j, m, d, u, mi, tzinfo=datetime.timezone.utc) - datetime.timedelta(hours=1)

# Rondes zonder scores bij een vaste datum en tijd; scores: zoveel holes ingevuld.
ZET = """(lijst) => {
  const s = loadSavedRounds();
  const b = s.find(r => isRondeAf(r));
  lijst.forEach(([id, datum, tijd, scores]) => s.push({ ...b, id, date: datum, time: tijd, note: undefined,
      holes: b.holes.map((h, i) => ({ ...h, score: i < scores ? (h.score ?? 5) : null, putts: i < scores ? h.putts : null })) }));
  setRoundsAndMark(JSON.stringify(s));
  toonLegeKop(); refreshTabDot();
}"""
STAND = """() => {
  const v = verdeelArchief(loadSavedRounds(), storage.getItem('golf_active_id'));
  const ids = l => l.map(r => r.id).filter(id => id >= 990000).sort();
  return { gepland: ids(v.planned), gepauzeerd: ids(v.inProgress),
           kop: geplandeMomenten().map(r => r.id).filter(id => id >= 990000),
           kopTekst: document.getElementById('hdrGeplandStrook').classList.contains('hidden') ? null : document.querySelector('header h1').innerText.trim() };
}"""

async def pagina(b, klok):
    ctx = await b.new_context(timezone_id='Europe/Amsterdam', viewport={'width': 390, 'height': 844})
    pg = await ctx.new_page(); pf = []
    pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
    await pg.clock.install(time=klok)
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
    return ctx, pg, pf

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        alle_pf = []

        print("\n=== 1. OM 10:20: DE RONDE VAN 10:00 IS NOG GEPLAND ===\n")
        ctx, pg, pf = await pagina(b, lokaal(2026, 11, 8, 10, 20))
        await pg.clock.set_fixed_time(lokaal(2026, 11, 8, 10, 20))
        await pg.evaluate(ZET, [[990001, '2026-11-08', '10:00', 0], [990002, '2026-11-08', '09:00', 2],
                                [990003, '2026-11-07', '14:00', 0], [990004, '2026-11-12', '10:00', 0]])
        s = await pg.evaluate(STAND)
        check("in Gepland: vandaag 10:00 (zonder score) en de 12e", s['gepland'], [990001, 990004])
        check("gepauzeerd: vandaag met een score, en gisteren niet gespeeld", s['gepauzeerd'], [990002, 990003])
        check("de kop toont eerst de ronde van vandaag", (s['kop'][:1], s['kopTekst'] is not None and s['kopTekst'].startswith('Vandaag')), ([990001], True))
        await pg.evaluate("() => { window._planCollapsed = null; nav('stat'); }")
        await pg.evaluate("() => document.querySelector('header').click()"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("""() => ({ rondes: document.getElementById('screen-archive').classList.contains('active'),
            agenda: archiefGroepering === 'gepland',
            inBeeld: document.getElementById('savedList').innerText.indexOf(formatRoundDateWithDay('2026-11-08')) >= 0 })""")
        check("een tik op de kop opent Rondes in de agenda, met de ronde van vandaag in beeld", r, {'rondes': True, 'agenda': True, 'inBeeld': True})
        exp = await pg.evaluate("""() => { const i = loadSavedRounds().findIndex(r => r.id === 990001); openExportModal(i);
            const k = document.getElementById('exportOptAgenda'); const uit = k.disabled; closeExportModal && closeExportModal(); return uit; }""")
        check("de agenda-export staat na de starttijd uit", exp, True)

        print("\n=== 2. DE EERSTE SCORE: GEPAUZEERD ===\n")
        await pg.evaluate("""() => { const s = loadSavedRounds(); const r = s.find(r => r.id === 990001);
            r.holes[0].score = 5; setRoundsAndMark(JSON.stringify(s)); toonLegeKop(); }""")
        s = await pg.evaluate(STAND)
        check("met een score: gepauzeerd en uit de kop", (990001 in s['gepland'], 990001 in s['gepauzeerd'], 990001 in s['kop']), (False, True, False))

        print("\n=== 3. NA MIDDERNACHT: GEPAUZEERD ===\n")
        await pg.evaluate("""() => { const s = loadSavedRounds(); s.find(r => r.id === 990001).holes[0].score = null;
            setRoundsAndMark(JSON.stringify(s)); }""")
        await pg.clock.set_fixed_time(lokaal(2026, 11, 9, 0, 5))
        await pg.evaluate("() => toonLegeKop()")
        s = await pg.evaluate(STAND)
        check("de volgende dag: de niet gespeelde ronde is gepauzeerd en uit de kop",
              (990001 in s['gepland'], 990001 in s['gepauzeerd'], s['kop']), (False, True, [990004]))
        alle_pf += pf; await ctx.close()

        print("\n=== 4. VANDAAG ZONDER TIJD ===\n")
        ctx, pg, pf = await pagina(b, lokaal(2026, 11, 8, 15, 0))
        await pg.clock.set_fixed_time(lokaal(2026, 11, 8, 15, 0))
        await pg.evaluate(ZET, [[990011, '2026-11-08', '', 0]])
        s = await pg.evaluate(STAND)
        check("een ronde van vandaag zonder tijd is om 15:00 nog gepland en staat in de kop", (s['gepland'], s['kop']), ([990011], [990011]))
        alle_pf += pf; await ctx.close()

        check("geen fouten in de pagina", alle_pf, [])
        await b.close()
    print()
    if fouten:
        print(f"{len(fouten)} FOUT(EN)"); sys.exit(1)
    print("ALLES GOED")

asyncio.run(main())
