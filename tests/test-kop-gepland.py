"""Geplande rondes in de kop, zonder actieve ronde.

Regel 1, zoals bij een actieve ronde: links hoe lang nog (Vandaag, Morgen, '+3 dagen' zolang
de dag in de strook valt, daarna '+2 weken' in hele weken naar beneden; 'dgn'/'wkn' alleen
als de volledige vorm niet past), rechts de volledige
datum met tijd. Aan het eind van de strook in goud het aantal momenten daarna ('+1' t/m
'+9', daarboven '>9'). Regel 2: de volledige clubnaam, met de baan
alleen als die er helemaal bij past. Daaronder 14 dagen vanaf vandaag, met een gouden
rondje op elke dag met een geplande ronde. Tik op de kop: Rondes in de agendaweergave.
Zonder geplande rondes: 'Geen geplande rondes' met het baansilhouet.
"""
import asyncio, datetime, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

UIT = os.environ.get('SCHERMAFDRUKKEN')   # optioneel: map voor schermafdrukken
fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

KOP = """() => {
  const strook = document.getElementById('hdrGeplandStrook');
  const dagen = [...strook.querySelectorAll('.kop-dag')];
  const sub = document.getElementById('hdrRoundName');
  return {
    regel1: document.getElementById('hdrClubName').textContent.trim(),
    regel1Past: (() => { const h = document.querySelector('header h1'); return h.scrollWidth <= h.clientWidth; })(),
    later: (strook.querySelector('.kop-later span:last-child') || {}).textContent || '',
    rechts: document.getElementById('hdrTrack').textContent.trim(),
    regel2: sub.textContent.trim(),
    regel2Past: sub.scrollWidth <= sub.clientWidth,
    strook: !strook.classList.contains('hidden'),
    silhouet: !document.getElementById('hdrLeegBeeld').classList.contains('hidden'),
    aantalDagen: dagen.filter(d => !d.classList.contains('kop-later')).length,
    gouden: dagen.filter(d => !d.classList.contains('kop-later')).map((d, i) => d.classList.contains('gepland') ? i : null).filter(x => x !== null),
    vandaagRing: dagen.length ? dagen[0].classList.contains('vandaag') : null,
    kopHoogte: Math.round(document.querySelector('header').getBoundingClientRect().height),
  };
}"""

def dag(n):
    return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()

# Een geplande ronde: alle holes leeg.
ZET_GEPLAND = """(lijst) => {
  const s = loadSavedRounds();
  const b = s.find(r => isRondeAf(r));
  lijst.forEach(([id, datum, tijd, speler, club, baan]) => s.push({ ...b, id, date: datum, time: tijd,
      player: speler, club: club || b.club, track: baan || b.track, note: undefined,
      holes: b.holes.map(h => ({ ...h, score: null })) }));
  setRoundsAndMark(JSON.stringify(s));
  toonLegeKop(); refreshTabDot();
}"""

async def nieuw(b, breedte=360, thema='light'):
    pg = await b.new_page(viewport={'width': breedte, 'height': 800}, device_scale_factor=2)
    pf = []
    pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES])
    await pg.evaluate("(t) => localStorage.setItem('golf_theme', t)", thema)
    await pg.reload(); await pg.wait_for_timeout(500)
    return pg, pf

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()

        print("\n=== 1. GEEN GEPLANDE RONDES ===\n")
        pg, pf = await nieuw(b)
        k0 = await pg.evaluate(KOP)
        check("tekst", k0['regel1'], 'Geen geplande rondes')
        check("baansilhouet zichtbaar, geen strook", (k0['silhouet'], k0['strook']), (True, False))
        hoogteLeeg = k0['kopHoogte']
        await pg.evaluate("() => document.querySelector('header').click()")
        check("tik op de kop doet niets", await pg.evaluate("() => document.getElementById('screen-archive').classList.contains('active') || (archiefGroepering === 'gepland')"), False)

        print("\n=== 2. GEPLANDE RONDES ===\n")
        club = await pg.evaluate("() => loadSavedRounds().find(r => isRondeAf(r)).club")
        await pg.evaluate(ZET_GEPLAND, [
            [880001, dag(3), '11:00', 'Testspeler', None, None],
            [880002, dag(3), '11:00', 'Partner', None, None],      # zelfde moment: telt als één
            [880003, dag(7), '09:30', 'Testspeler', None, None],
            [880004, dag(20), '10:00', 'Testspeler', None, None],        # na de 14 dagen
            [880005, dag(-2), '10:00', 'Testspeler', None, None],        # verleden: telt niet
        ])
        k = await pg.evaluate(KOP)
        check("regel 1 links: hoe lang nog, voluit als het past", k['regel1'], '+3 dagen')
        check("regel 1 rechts: volledige datum en tijd", k['rechts'], await pg.evaluate("(d) => formatFullDate(d)", dag(3)) + ' · 11:00')
        check("regel 1 past zonder afkappen", k['regel1Past'], True)
        check("aan het eind van de strook: na 14 dagen", k['later'], '+1')
        check("regel 2 begint met de volledige clubnaam", k['regel2'].startswith(club), True)
        check("regel 2 past zonder afkappen", k['regel2Past'], True)
        check("strook zichtbaar, silhouet weg", (k['strook'], k['silhouet']), (True, False))
        check("14 dagen", k['aantalDagen'], 14)
        check("gouden dagen (zelfde moment telt één keer)", k['gouden'], [3, 7])
        check("vandaag heeft een ring", k['vandaagRing'], True)
        letters = await pg.evaluate("""() => [...document.querySelectorAll('#hdrGeplandStrook .kop-dag:not(.kop-later)')].map(d =>
            [d.classList.contains('weekend'), getComputedStyle(d.querySelector('span')).fontWeight])""")
        check("zaterdag en zondag vet, de rest niet",
              all((w == '800') if weekend else (w == '400') for weekend, w in letters) and any(wk for wk, _ in letters), True)
        cijfers = await pg.evaluate("""() => {
            const gewicht = sel => [...new Set([...document.querySelectorAll(sel)].map(e => getComputedStyle(e).fontWeight))];
            return { gewoon: gewicht('#hdrGeplandStrook .kop-dag:not(.kop-later):not(.gepland):not(.vandaag) span:last-child'),
                     gepland: gewicht('#hdrGeplandStrook .kop-dag.gepland span:last-child'),
                     vandaag: gewicht('#hdrGeplandStrook .kop-dag.vandaag span:last-child'),
                     later: getComputedStyle(document.querySelector('#hdrGeplandStrook .kop-later span:last-child')).fontWeight }; }""")
        check("gewone dagcijfers niet vet", cijfers['gewoon'], ['400'])
        check("vandaag en geplande dagen vet", (cijfers['vandaag'], cijfers['gepland']), (['800'], ['800']))
        check("het aantal daarna vet", cijfers['later'], '800')
        weekend = await pg.evaluate("""() => [...document.querySelectorAll('#hdrGeplandStrook .kop-dag:not(.kop-later)')].map((d, i) => {
            const t = new Date(); t.setDate(t.getDate() + i); const cs = getComputedStyle(d);
            return { dag: t.getDay(), getint: cs.backgroundColor !== 'rgba(0, 0, 0, 0)' && cs.backgroundColor !== 'transparent',
                     links: cs.borderTopLeftRadius !== '0px', rechts: cs.borderTopRightRadius !== '0px', i }; })""")
        check("alleen zaterdag en zondag getint", all(w['getint'] == (w['dag'] in (0, 6)) for w in weekend), True)
        check("zaterdag links afgerond, zondag rechts (één blokje)",
              all((w['links'] and (w['rechts'] == (w['i'] == 13))) if w['dag'] == 6 else
                  (w['rechts'] and (w['links'] == (w['i'] == 0))) if w['dag'] == 0 else True for w in weekend), True)
        check("kop blijft even hoog", k['kopHoogte'], hoogteLeeg)
        if UIT: await pg.screenshot(path=os.path.join(UIT, 'kop-360-licht.png'), clip={'x': 0, 'y': 0, 'width': 360, 'height': 140})

        print("\n=== 3. VANDAAG EN MORGEN ===\n")
        await pg.evaluate(ZET_GEPLAND, [[880006, dag(1), '', 'Testspeler', None, None]])
        k = await pg.evaluate(KOP)
        check("morgen zonder tijd", (k['regel1'], k['rechts']), ('Morgen', await pg.evaluate("(d) => formatFullDate(d)", dag(1))))
        # Zelfde definitie als de agenda: datum/tijd moet nog komen.
        await pg.evaluate(ZET_GEPLAND, [[880009, dag(0), '00:01', 'Testspeler', None, None]])
        check("vandaag, tijd al voorbij: niet gepland", (await pg.evaluate(KOP))['regel1'], 'Morgen')
        await pg.evaluate(ZET_GEPLAND, [[880007, dag(0), '23:59', 'Testspeler', None, None]])
        k = await pg.evaluate(KOP)
        check("vandaag, tijd nog te komen", (k['regel1'], k['rechts']), ('Vandaag', await pg.evaluate("(d) => formatFullDate(d)", dag(0)) + ' · 23:59'))
        check("gouden dagen", k['gouden'], [0, 1, 3, 7])

        print("\n=== 4. LANGE NAAM: BAAN WEGLATEN, NIET AFKAPPEN ===\n")
        await pg.evaluate("""() => { const s = loadSavedRounds().filter(r => ![880006, 880007, 880009].includes(r.id));
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(s))); toonLegeKop(); refreshTabDot(); }""")
        await pg.evaluate(ZET_GEPLAND, [[880008, dag(2), '08:00', 'Testspeler', 'Golfclub Midden-Brabant', 'Championship Course Noord']])
        k = await pg.evaluate(KOP)
        check("alleen de clubnaam", k['regel2'], 'Golfclub Midden-Brabant')
        check("en die past", k['regel2Past'], True)

        print("\n=== 5. TIK OP DE KOP: AGENDA IN RONDES ===\n")
        await pg.evaluate("() => { nav('stat'); document.querySelector('header').click(); }")
        await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => ({ rondes: document.getElementById('screen-archive').classList.contains('active'), agenda: (archiefGroepering === 'gepland') })")
        check("Rondes open in de agendaweergave", (r['rondes'], r['agenda']), (True, True))
        await pg.evaluate("() => { nav('stat'); document.querySelector('header').click(); }")
        await pg.wait_for_timeout(300)
        check("nog een keer tikken laat de agenda aan", await pg.evaluate("() => (archiefGroepering === 'gepland')"), True)

        print("\n=== 6. EEN RONDE LOOPT: GEWONE KOP ===\n")
        await pg.evaluate("""() => { nav('setup'); sel.track = 'Airborne'; sel.gender = 'Heren'; sel.tee = 'Blauw';
            document.getElementById('iName').value = 'Testspeler'; document.getElementById('iHcp').value = '30.7'; }""")
        await pg.wait_for_timeout(250)
        await pg.evaluate("""() => { startRound(); const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
        await pg.wait_for_timeout(400)
        k = await pg.evaluate(KOP)
        check("de ronde loopt", await pg.evaluate("() => !!game.started"), True)
        check("geen strook, geen silhouet", (k['strook'], k['silhouet']), (False, False))
        check("regel 1 is de club van de ronde", k['regel1'] == await pg.evaluate("() => game.clubShort || game.club"), True)
        check("regel 2 heeft weer de gewone grootte", await pg.evaluate("() => document.getElementById('hdrRoundName').style.fontSize"), '')
        await pg.evaluate("() => { nav('stat'); document.querySelector('header').click(); }")
        check("tik op de kop doet niets tijdens een ronde", await pg.evaluate("() => document.getElementById('screen-stat').classList.contains('active')"), True)

        print("\n=== 7. RONDE GEPAUZEERD: GEPLANDE RONDES TERUG ===\n")
        # Terug naar de gewone lijst (de agenda staat nog aan van stap 5).
        await pg.evaluate("() => { nav('archive'); if (archiefGroepering === 'gepland') toggleGroupByPlanned(); }"); await pg.wait_for_timeout(250)
        knop = pg.locator('button[onclick^="saveAndClearActiveRound"]').first
        await knop.click(); await pg.wait_for_timeout(80); await knop.click(); await pg.wait_for_timeout(300)
        k = await pg.evaluate(KOP)
        check("strook terug", k['strook'], True)
        check("eerstvolgende ronde terug", (k['regel1'], k['rechts']), ('+2 dagen', await pg.evaluate("(d) => formatFullDate(d)", dag(2)) + ' · 08:00'))
        check("de gepauzeerde ronde zelf telt niet als gepland",
              await pg.evaluate("() => geplandeMomenten().some(r => r.date === todayISO())"), False)
        check("geen fouten in de pagina", pf, [])
        await pg.close()

        print("\n=== 8. HOE LANG NOG EN HET AANTAL LATER ===\n")
        pg, pf = await nieuw(b)
        uit = await pg.evaluate("""(d) => d.map(x => hoeLangNog(x))""", [dag(n) for n in [0, 1, 2, 13, 14, 20, 21, 27, 70]])
        check("labels voluit", uit, ['Vandaag', 'Morgen', '+2 dagen', '+13 dagen', '+2 weken', '+2 weken', '+3 weken', '+3 weken', '+10 weken'])
        kort = await pg.evaluate("""(d) => d.map(x => hoeLangNog(x, true))""", [dag(n) for n in [0, 1, 2, 13, 14, 70]])
        check("labels kort", kort, ['Vandaag', 'Morgen', '+2 dgn', '+13 dgn', '+2 wkn', '+10 wkn'])
        check("1 week voluit en kort", await pg.evaluate("(iso) => [hoeLangNog(iso).includes('weken'), KOP_DAGEN]", dag(14)), [True, 14])
        for aantal, verwacht in [(9, '+9'), (10, '>9')]:
            await pg.evaluate("""() => { const s = loadSavedRounds().filter(r => r.id < 870000 || r.id > 879999);
                metVerwijderen(() => setRoundsAndMark(JSON.stringify(s))); }""")
            await pg.evaluate(ZET_GEPLAND, [[870000 + i, dag(20 + i), '10:00', 'Testspeler', None, None] for i in range(aantal)])
            k = await pg.evaluate(KOP)
            check(f"{aantal} rondes na de strook", (k['later'], k['regel1'] in ('+2 weken', '+2 wkn'), k['regel1Past']), (verwacht, True, True))
        # Voluit of kort hangt af van wat past, en de datum rechts blijft altijd compleet.
        # De test legt NIET vast bij welke breedte de omslag ligt: dat hangt af van het
        # lettertype van het toestel (in de ene omgeving past '+13 dagen' op 360 px, in de
        # andere niet). Hij controleert de regel zelf: staat er de korte vorm, dan past de
        # volle vorm aantoonbaar niet; en de reeks loopt door tot een breedte waarop de
        # korte vorm er moet komen, zodat beide takken geraakt worden.
        PAST_VOLUIT = """(vol) => { const el = document.getElementById('hdrClubName'); const was = el.textContent;
            el.textContent = vol; const h = document.querySelector('header h1'); const past = h.scrollWidth <= h.clientWidth;
            el.textContent = was; return past; }"""
        vormen = []
        for breedte in (412, 360, 320, 280, 240):
            await pg.set_viewport_size({'width': breedte, 'height': 800})
            await pg.evaluate("""() => { const s = loadSavedRounds().filter(r => r.id < 870000 || r.id > 879999);
                metVerwijderen(() => setRoundsAndMark(JSON.stringify(s))); }""")
            await pg.evaluate(ZET_GEPLAND, [[870100, dag(13), '09:30', 'Testspeler', None, None]])
            await pg.evaluate("() => { _legeKopSleutel = null; toonLegeKop(); refreshTabDot(); }")
            k = await pg.evaluate(KOP)
            volPast = await pg.evaluate(PAST_VOLUIT, '+13 dagen')
            vormen.append(k['regel1'])
            check(f"{breedte} px: voluit als het past, anders kort", (k['regel1'], k['rechts'].endswith('· 09:30')),
                  ('+13 dagen' if volPast else '+13 dgn', True))
            if breedte >= 360:
                check(f"{breedte} px: de regel past", k['regel1Past'], True)
        check("412 px: voluit", vormen[0], '+13 dagen')
        check("beide vormen komen voor in de reeks", sorted(set(vormen)), ['+13 dagen', '+13 dgn'])
        await pg.set_viewport_size({'width': 360, 'height': 800})
        await pg.evaluate("() => { _legeKopSleutel = null; toonLegeKop(); refreshTabDot(); }")
        # Het breedste geval: 'Vandaag' met een datum met twee cijfers voor dag en maand.
        breedst = await pg.evaluate("""() => { document.getElementById('hdrClubName').textContent = 'Vandaag';
            document.getElementById('hdrTrack').textContent = '28-12-2026 · 09:30';
            const h = document.querySelector('header h1'); return h.scrollWidth <= h.clientWidth; }""")
        check("breedste geval past op 360 px", breedst, True)
        check("geen fouten in de pagina", pf, [])
        await pg.close()

        print("\n=== 9. KLEUREN: GOUD VOOR VANDAAG, GROEN VOOR DE RONDES ===\n")
        KLEUR = """() => {
          const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
          const rgb = h => { const x = document.createElement('div'); x.style.color = h; document.body.appendChild(x);
                             const c = getComputedStyle(x).color; x.remove(); return c; };
          const lum = c => { const [r, g, b] = c.match(/\\d+/g).slice(0, 3).map(n => { n /= 255; return n <= 0.03928 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4; });
                             return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
          const contrast = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
          const dagen = [...document.querySelectorAll('#hdrGeplandStrook .kop-dag')];
          const cijfer = d => getComputedStyle(d.querySelector('span:last-child'));
          const vandaag = cijfer(dagen[0]);
          const gepland = dagen.filter(d => d.classList.contains('gepland')).map(cijfer);
          const later = document.querySelector('#hdrGeplandStrook .kop-later span:last-child');
          return {
            vandaagRingGoud: vandaag.boxShadow.includes(rgb(css('--gold'))),
            geplandGroen: gepland.length > 0 && gepland.every(c => c.backgroundColor === rgb(css('--green-light'))),
            contrastMin: Math.round(Math.min(...gepland.map(c => contrast(c.color, c.backgroundColor))) * 10) / 10,
            laterGroen: !!later && getComputedStyle(later).color === rgb(css('--green-light')),
          };
        }"""
        for thema in ['light', 'dark']:
            pg, pf = await nieuw(b, 360, thema)
            # vandaag gepland (later op de dag), nog een ronde in de strook en een daarna
            await pg.evaluate(ZET_GEPLAND, [[880201, dag(0), '23:59', 'Testspeler', None, None],
                                            [880202, dag(4), '09:30', 'Testspeler', None, None],
                                            [880203, dag(22), '10:00', 'Testspeler', None, None]])
            k = await pg.evaluate(KLEUR)
            check(f"{thema}: vandaag (met ronde) houdt een gouden ring", k['vandaagRingGoud'], True)
            check(f"{thema}: geplande dagen groen", k['geplandGroen'], True)
            check(f"{thema}: cijfer in het groen leesbaar (contrast >= 4.5)", k['contrastMin'] >= 4.5, True)
            check(f"{thema}: aantal daarna groen", k['laterGroen'], True)
            if UIT: await pg.screenshot(path=os.path.join(UIT, f'kop-kleur-{thema}.png'), clip={'x': 0, 'y': 0, 'width': 360, 'height': 125})
            await pg.evaluate("""() => { const s = loadSavedRounds().filter(r => r.id !== 880201);
                metVerwijderen(() => setRoundsAndMark(JSON.stringify(s))); _legeKopSleutel = null; toonLegeKop(); refreshTabDot(); }""")
            k = await pg.evaluate(KLEUR)
            check(f"{thema}: vandaag zonder ronde: gouden ring", k['vandaagRingGoud'], True)
            check("geen fouten in de pagina", pf, [])
            await pg.close()

        print("\n=== 10. WEEKENDBLOKJE AAN DE RANDEN VAN DE STROOK ===\n")
        # Zondag 4-10-2026 als 'vandaag': de strook begint op een zondag (zaterdag valt
        # ervoor weg) en eindigt op een zaterdag (zondag valt erna weg). Die twee dagen
        # moeten dan aan beide kanten afgerond zijn.
        import datetime as _dt
        pg = await b.new_page(viewport={'width': 360, 'height': 800}, device_scale_factor=2)
        await pg.clock.install(time=_dt.datetime(2026, 10, 4, 9, 0))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        await pg.evaluate(ZET_GEPLAND, [[880301, '2026-10-06', '10:00', 'Testspeler', None, None]])
        rand = await pg.evaluate("""() => { const d = [...document.querySelectorAll('#hdrGeplandStrook .kop-dag:not(.kop-later)')];
            const r = e => { const c = getComputedStyle(e); return [c.borderTopLeftRadius !== '0px', c.borderTopRightRadius !== '0px']; };
            return { eerste: r(d[0]), laatste: r(d[d.length - 1]), eersteIsZondag: d[0].querySelector('span').textContent };
        }""")
        check("strook begint op zondag", rand['eersteIsZondag'], 'Z')
        check("zondag als eerste dag: aan beide kanten afgerond", rand['eerste'], [True, True])
        check("zaterdag als laatste dag: aan beide kanten afgerond", rand['laatste'], [True, True])
        if UIT: await pg.screenshot(path=os.path.join(UIT, 'kop-weekend-rand.png'), clip={'x': 0, 'y': 0, 'width': 360, 'height': 125})
        await pg.close()

        print("\n=== 11. DONKER THEMA EN 412 PX ===\n")
        for breedte, thema in [(412, 'dark'), (360, 'dark')]:
            pg, pf = await nieuw(b, breedte, thema)
            await pg.evaluate(ZET_GEPLAND, [[880001, dag(3), '11:00', 'Testspeler', None, None], [880003, dag(7), '09:30', 'Testspeler', None, None]])
            k = await pg.evaluate(KOP)
            check(f"{breedte}px {thema}: strook en regel 2 passen", (k['strook'], k['regel2Past'], k['aantalDagen']), (True, True, 14))
            if UIT: await pg.screenshot(path=os.path.join(UIT, f'kop-{breedte}-{thema}.png'), clip={'x': 0, 'y': 0, 'width': breedte, 'height': 140})
            check("geen fouten in de pagina", pf, [])
            await pg.close()
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
