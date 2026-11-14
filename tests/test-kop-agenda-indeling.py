"""Tik op de agenda in de kop: de eerstvolgende geplande ronde bovenaan (038).

De tik opent Rondes in de agendaweergave en klapt de drie groepen (Deze week, Volgende
week, Later) zo dat de groep met de eerstvolgende geplande ronde open is, en de weken
ervoor ook (leeg: 'Geen geplande rondes.'). De tik klapt alleen open, nooit
dicht (040): wat al open stond blijft open. Meer rondes in die groep: allemaal
zichtbaar. Een zoekterm of meldingsfilter in Rondes wordt eerst gewist,
anders toont de agenda andere rondes dan de kop. De knop 'Geplande rondes' houdt de
indeling die er staat.
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

ZET_GEPLAND = """(lijst) => {
  const s = loadSavedRounds();
  const b = s.find(r => isRondeAf(r));
  lijst.forEach(([id, datum, tijd]) => s.push({ ...b, id, date: datum, time: tijd, note: undefined,
      holes: b.holes.map(h => ({ ...h, score: null })) }));
  setRoundsAndMark(JSON.stringify(s));
  toonLegeKop(); refreshTabDot();
}"""
# Een begintoestand neerzetten en naar een ander scherm; de tik klapt daar alleen bij open.
BEGIN = """(open) => { const o = Array.isArray(open) ? open : [open, open, open];
  window._planCollapsed = { plan_deze: !o[0], plan_volgende: !o[1], plan_later: !o[2] }; nav('stat'); }"""
# Wat er in beeld staat: welke groepen open zijn (uit de kop van elke groep: het pijltje
# en wat eronder staat), welke van de geplande datums zichtbaar zijn en welke het eerst.
STAND = """(datums) => {
  const p = window._planCollapsed || {};
  const lijst = document.getElementById('savedList');
  const t = lijst.innerText;
  const pos = datums.map(d => t.indexOf(formatRoundDateWithDay(d)));
  const zichtbaar = datums.filter((d, i) => pos[i] >= 0);
  const eerste = zichtbaar.length ? datums[pos.indexOf(Math.min(...pos.filter(x => x >= 0)))] : null;
  return { rondes: document.getElementById('screen-archive').classList.contains('active'),
           agenda: archiefGroepering === 'gepland',
           open: ['plan_deze', 'plan_volgende', 'plan_later'].map(k => p[k] === false),
           leeg: (t.match(/Geen geplande rondes\\./g) || []).length,
           zichtbaar, eerste,
           zoeken: !document.getElementById('archiveSearchWrap').classList.contains('hidden'),
           zoekterm: document.getElementById('archiveSearch').value,
           filter: _warnFilterActive || null };
}"""

vandaag = datetime.date.today()
naar_zondag = (6 - vandaag.weekday())          # maandag = 0, zondag = 6
volgende_maandag = vandaag + datetime.timedelta(days=naar_zondag + 1)
def iso(d): return d.isoformat()
nu = datetime.datetime.now()
# deze week: morgen, of vandaag laat als het zondag is
deze = (iso(vandaag + datetime.timedelta(days=1)), '10:00') if naar_zondag >= 1 else (iso(vandaag), '23:58')
deze2 = (deze[0], '14:00') if naar_zondag >= 1 else (iso(vandaag), '23:59')
volgende = (iso(volgende_maandag + datetime.timedelta(days=2)), '10:00')
later = (iso(volgende_maandag + datetime.timedelta(days=21)), '10:00')

async def nieuw(b):
    pg = await b.new_page(viewport={'width': 390, 'height': 844})
    pf = []
    pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES])
    await pg.reload(); await pg.wait_for_timeout(500)
    return pg, pf

async def tik(pg, datums, open_=True, voor=None):
    await pg.evaluate(BEGIN, open_); await pg.wait_for_timeout(100)
    if voor: await pg.evaluate(voor); await pg.wait_for_timeout(150)
    await pg.evaluate("() => document.querySelector('header').click()"); await pg.wait_for_timeout(300)
    return await pg.evaluate(STAND, datums)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        alle_pf = []

        print("\n=== 1. EERSTVOLGENDE RONDE DEZE WEEK (TWEE DEZE WEEK, EEN LATER) ===\n")
        if naar_zondag == 0 and nu.hour == 23 and nu.minute >= 50:
            print("  (overgeslagen: zondag na 23:50, deze week is dan al voorbij)")
        else:
            pg, pf = await nieuw(b)
            await pg.evaluate(ZET_GEPLAND, [[890001, *deze], [890002, *deze2], [890003, *later]])
            s = await tik(pg, [deze[0], later[0]], open_=False)
            check("Rondes in de agendaweergave", (s['rondes'], s['agenda']), (True, True))
            check("alleen Deze week open", s['open'], [True, False, False])
            check("de ronde van deze week staat bovenaan, die van later niet in beeld", (s['eerste'], s['zichtbaar']), (deze[0], [deze[0]]))
            tijden = await pg.evaluate("""(d) => document.getElementById('savedList').innerText.split(formatRoundDateWithDay(d)).length - 1""", deze[0])
            check("beide rondes van deze week staan er (de datum twee keer)", tijden, 2)
            # De knop houdt de indeling: uit en weer aan
            await pg.evaluate("() => { toggleGroupByPlanned(); toggleGroupByPlanned(); }")
            check("de knop 'Geplande rondes' laat de indeling staan", (await pg.evaluate(STAND, []))['open'], [True, False, False])
            s = await tik(pg, [deze[0], later[0]], open_=True)
            check("stond alles al open: de tik klapt niets dicht", (s['open'], s['zichtbaar']), ([True, True, True], [deze[0], later[0]]))
            alle_pf += pf; await pg.close()

        print("\n=== 2. EERSTVOLGENDE RONDE VOLGENDE WEEK (EN EEN LATER), BEGIN MET ALLES DICHT ===\n")
        pg, pf = await nieuw(b)
        await pg.evaluate(ZET_GEPLAND, [[890011, *volgende], [890012, *later]])
        s = await tik(pg, [volgende[0], later[0]], open_=False)
        check("Deze week en Volgende week open, Later dicht", s['open'], [True, True, False])
        check("deze week leeg: 'Geen geplande rondes.'", s['leeg'], 1)
        check("de ronde van volgende week bovenaan, die van later niet in beeld", (s['eerste'], s['zichtbaar']), (volgende[0], [volgende[0]]))
        s = await tik(pg, [volgende[0], later[0]], open_=[False, False, True])
        check("Later stond open: blijft open, Deze en Volgende week gaan open", s['open'], [True, True, True])
        s = await tik(pg, [volgende[0], later[0]], open_=[False, True, False])
        check("Volgende week stond al open: Deze week erbij, Later blijft dicht", s['open'], [True, True, False])

        print("\n=== 3. VANUIT EEN ANDERE WEERGAVE, MET EEN ZOEKTERM EN EEN MELDINGSFILTER ===\n")
        # Zoeken op de datum van de latere ronde: de agenda zou dan alleen die tonen,
        # terwijl de kop de ronde van volgende week als eerste ziet.
        s = await tik(pg, [volgende[0], later[0]], voor="""() => { nav('archive'); zetGroepering('categorie');
            toggleArchiefZoeken(); const v = document.getElementById('archiveSearch'); v.value = '%s'; zoekInRondes(); }""" % (later[0][8:10] + '-' + later[0][5:7] + '-' + later[0][0:4]), open_=False)
        check("de zoekterm is weg en het zoekveld dicht", (s['zoekterm'], s['zoeken']), ('', False))
        check("agenda aan, de ronde van volgende week bovenaan", (s['agenda'], s['open'], s['eerste']), (True, [True, True, False], volgende[0]))
        # Een echt duplicaat (twee keer dezelfde gespeelde ronde), anders heft de app het
        # filter 'duplicaten' al zelf op voordat er getikt wordt.
        await pg.evaluate("""() => { const s = loadSavedRounds(); const b = s.find(r => isRondeAf(r));
            s.push({ ...b, id: 890099 }); setRoundsAndMark(JSON.stringify(s)); }""")
        await pg.evaluate(BEGIN, False)
        voor = await pg.evaluate("() => { nav('archive'); _warnFilterActive = 'dup'; tekenRondelijst(); return _warnFilterActive; }")
        check("het filter 'duplicaten' staat vóór de tik echt aan", voor, 'dup')
        await pg.evaluate("() => document.querySelector('header').click()"); await pg.wait_for_timeout(300)
        s = await pg.evaluate(STAND, [volgende[0], later[0]])
        check("na de tik is het meldingsfilter weg en staat de agenda er", (s['filter'], s['agenda'], s['eerste']), (None, True, volgende[0]))
        alle_pf += pf; await pg.close()

        print("\n=== 4. EERSTVOLGENDE RONDE LATER ===\n")
        pg, pf = await nieuw(b)
        await pg.evaluate(ZET_GEPLAND, [[890021, *later]])
        s = await tik(pg, [later[0]], open_=False)
        check("alle drie open", s['open'], [True, True, True])
        check("twee lege weken ervoor", s['leeg'], 2)
        check("de ronde van later staat er", s['eerste'], later[0])
        s = await tik(pg, [later[0]])
        check("nog een keer tikken: agenda blijft aan, zelfde indeling", (s['agenda'], s['open']), (True, [True, True, True]))
        alle_pf += pf; await pg.close()

        print("\n=== 4b. MET EEN VASTE KLOK (WOENSDAG): EERSTE TIK ZONDER INDELING, EN WAT AL OPEN STOND ===\n")
        # Los van de echte dag en tijd: deze gevallen moeten altijd draaien.
        ctx = await b.new_context(timezone_id='Europe/Amsterdam', viewport={'width': 390, 'height': 844})
        pg = await ctx.new_page(); pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.clock.install(time=datetime.datetime(2026, 10, 21, 10, 0, tzinfo=datetime.timezone.utc))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        await pg.evaluate(ZET_GEPLAND, [[890031, '2026-10-22', '10:00'], [890032, '2026-11-20', '10:00']])
        await pg.evaluate("() => { window._planCollapsed = null; nav('stat'); }")
        await pg.evaluate("() => document.querySelector('header').click()"); await pg.wait_for_timeout(300)
        s = await pg.evaluate(STAND, ['2026-10-22', '2026-11-20'])
        check("eerste tik zonder indeling, ronde deze week: alleen Deze week open", s['open'], [True, False, False])
        s = await tik(pg, ['2026-10-22', '2026-11-20'], open_=[False, True, False])
        check("ronde deze week, Volgende week stond open: blijft open", s['open'], [True, True, False])
        s = await tik(pg, ['2026-10-22', '2026-11-20'], open_=[True, False, True])
        check("ronde deze week, Later stond open: blijft open, Volgende week dicht", s['open'], [True, False, True])
        alle_pf += pf; await ctx.close()

        print("\n=== 5. WEEKGRENS OVER DE ZOMERTIJD HEEN (KALENDERWEEK, NIET 7 x 24 UUR) ===\n")
        ctx = await b.new_context(timezone_id='Europe/Amsterdam', viewport={'width': 390, 'height': 844})
        pg = await ctx.new_page()
        await pg.clock.install(time=datetime.datetime(2027, 3, 17, 12, 0, tzinfo=datetime.timezone.utc))
        await pg.goto(app_url()); await pg.wait_for_timeout(400)
        g = await pg.evaluate("""() => { const g = planWeekGrenzen(); const f = t => { const d = new Date(t);
            return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate() + ' ' + d.getHours() + ':' + d.getMinutes(); };
            return [f(g.eindDezeWeek), f(g.eindVolgendeWeek)]; }""")
        check("17-03-2027: deze week tot zo 21-03 23:59, volgende week tot zo 28-03 23:59", g, ['2027-3-21 23:59', '2027-3-28 23:59'])
        await ctx.close()
        # en in de herfst (wintertijd op 25-10-2026)
        ctx = await b.new_context(timezone_id='Europe/Amsterdam', viewport={'width': 390, 'height': 844})
        pg = await ctx.new_page()
        await pg.clock.install(time=datetime.datetime(2026, 10, 14, 12, 0, tzinfo=datetime.timezone.utc))
        await pg.goto(app_url()); await pg.wait_for_timeout(400)
        g = await pg.evaluate("""() => { const g = planWeekGrenzen(); const f = t => { const d = new Date(t);
            return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate() + ' ' + d.getHours() + ':' + d.getMinutes(); };
            return [f(g.eindDezeWeek), f(g.eindVolgendeWeek)]; }""")
        check("14-10-2026: deze week tot zo 18-10 23:59, volgende week tot zo 25-10 23:59", g, ['2026-10-18 23:59', '2026-10-25 23:59'])
        await ctx.close()

        check("geen fouten in de pagina", alle_pf, [])
        await b.close()
    print()
    if fouten:
        print(f"{len(fouten)} FOUT(EN)"); sys.exit(1)
    print("ALLES GOED")

asyncio.run(main())
