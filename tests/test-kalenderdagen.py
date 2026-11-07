"""Rekenen in hele kalenderdagen, ook over de zomer- en wintertijd heen (039).

- 'Jaar' in Statistiek en Analyse: de dag van een jaar vóór de laatste ronde telt
  helemaal mee, wat het tijdstip ook is (net als Low HI).
- 'Gebaseerd op N dagen' (Low HI-controle): het aantal kalenderdagen sinds de eerste ronde.
- 'Heel jaar' bij de seizoenskaarten: precies een jaar is een jaar.
- Backupnamen met de lokale datum (een backup om 01:30 hoort bij vandaag), de clubexport
  met lokale datum en tijd.
- Een tijd '9:00' (of met spaties) wordt '09:00': uit een bestand én bij het lezen van de
  opslag, zodat een oude '9:00' naast '09:00' als dubbele ronde herkend wordt.
Met een nep-klok in de tijdzone Europe/Amsterdam.
"""
import asyncio, datetime, json, os, sys
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, RONDES, app_url, SEED
with open(os.path.join(HIER, 'rondes-lowhi.json'), encoding='utf-8') as f:
    LOWHI = json.load(f)   # 40 echte (geanonimiseerde) rondes met dagresultaten
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

def utc(j, m, d, u, mi=0):
    return datetime.datetime(j, m, d, u, mi, tzinfo=datetime.timezone.utc)

async def pagina(b, klok):
    ctx = await b.new_context(timezone_id='Europe/Amsterdam', viewport={'width': 390, 'height': 844})
    pg = await ctx.new_page()
    pf = []
    pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
    await pg.clock.install(time=klok)
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES])
    await pg.reload(); await pg.wait_for_timeout(500)
    return ctx, pg, pf

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        alle_pf = []

        print("\n=== 1. 'JAAR': DE DAG VAN EEN JAAR TERUG TELT HELEMAAL MEE ===\n")
        ctx, pg, pf = await pagina(b, utc(2026, 10, 24, 12))
        uit = await pg.evaluate("""() => {
          const r = (date, time) => ({ date, time });
          // laatste ronde op de dag van de zomertijd, 10:00; een jaar terug viel in wintertijd
          const lijst = [r('2025-03-28', '18:00'), r('2025-03-29', '08:30'), r('2025-03-29', ''), r('2025-06-01', '10:00'), r('2026-03-29', '10:00')];
          const herfst = [r('2025-10-24', '23:00'), r('2025-10-25', '10:30'), r('2026-10-25', '10:00')];
          return [periodeStart(lijst, 'jaar'), periodeStart(herfst, 'jaar')];
        }""")
        check("voorjaar: 29-03-2025 08:30 en zonder tijd tellen mee, 28-03 niet (begin bij de tweede)", uit[0], 1)
        check("najaar: 25-10-2025 10:30 telt mee, 24-10 niet", uit[1], 1)

        print("\n=== 2. 'GEBASEERD OP N DAGEN': KALENDERDAGEN ===\n")
        # nu: 25-10-2026 00:30 (zomertijd, UTC+2); eerste ronde 25-10-2025 23:00
        await pg.clock.set_fixed_time(utc(2026, 10, 24, 22, 30))
        n = await pg.evaluate("""() => { const s = loadSavedRounds(); const b = s.find(r => isRondeAf(r));
            const een = { ...b, id: 990001, date: '2025-10-25', time: '23:00' };
            const qual = [een].filter(meetelVoorHandicap(b.player));
            return [qual.length, lowHiCheckStatus(b.player, [een]).daysSinceFirst]; }""")
        check("de ronde telt mee voor de handicap", n[0], 1)
        check("van 25-10-2025 23:00 tot 25-10-2026 00:30: 365 dagen", n[1], 365)

        print("\n=== 3. 'HEEL JAAR' BIJ DE SEIZOENSKAARTEN ===\n")
        j = await pg.evaluate("""() => {
          const t = (d, u) => new Date(d + 'T' + u).getTime();
          return [beslaatJaar([t('2025-03-29', '10:00'), t('2026-03-29', '10:00')]),
                  beslaatJaar([t('2025-05-01', '14:00'), t('2026-05-01', '10:00')]),
                  beslaatJaar([t('2025-05-02', '08:00'), t('2026-05-01', '20:00')]),
                  beslaatJaar([])]; }""")
        check("29-03-2025 tot 29-03-2026 (over de zomertijd): een jaar", j[0], True)
        check("01-05-2025 14:00 tot 01-05-2026 10:00: een jaar", j[1], True)
        check("02-05-2025 tot 01-05-2026: nog geen jaar", j[2], False)
        check("geen gegevens: geen jaar", j[3], False)
        alle_pf += pf; await ctx.close()

        print("\n=== 3b. 'HEEL JAAR' ZOALS HET OP DE KAART EN IN DE ANALYSE STAAT ===\n")
        # De kaart telt alleen rondes met een dagresultaat EN een handicap van toen. Daarom:
        # 20 rondes in 2024 (daar ontstaat de handicap), de andere 20 verdeeld over precies
        # een jaar, van 29-03-2025 10:00 tot 29-03-2026 10:00 (over de zomertijd heen: 365
        # dagen min een uur), met aan beide kanten een ronde met dagresultaat. De periode
        # 'Jaar' laat precies dat jaar zien.
        def verdeeld(eerste):
            rs = sorted(LOWHI, key=lambda r: (r['date'], r.get('time') or ''))
            vroeg = [dict(r, date=(datetime.date(2024, 1, 6) + datetime.timedelta(days=7 * i)).isoformat(), time='10:00') for i, r in enumerate(rs[:20])]
            met = [r for r in rs[20:] if r.get('sdFinal') is not None]; zonder = [r for r in rs[20:] if r.get('sdFinal') is None]
            rest = [met[0]] + zonder + met[1:]
            begin = datetime.date.fromisoformat(eerste); eind = datetime.date(2026, 3, 29)
            stap = (eind - begin).days / (len(rest) - 1)
            return vroeg + [dict(r, date=(begin + datetime.timedelta(days=round(i * stap))).isoformat(), time='10:00') for i, r in enumerate(rest)]
        async def jaarTekst(rs):
            ctx, pg, pf = await pagina(b, utc(2026, 4, 15, 12))
            await pg.evaluate("""([c, rs]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c));
                localStorage.setItem('golf_rounds', JSON.stringify(rs)); localStorage.setItem('golf_stats_grp_prestaties', 'open');
                localStorage.setItem('golf_profile_name', 'Testspeler'); }""", [CLUBS, rs])
            await pg.reload(); await pg.wait_for_timeout(800)
            uit = await pg.evaluate("""() => { nav('stat'); _statChartPeriod = 'jaar'; _weekdayViewMode = 'maand'; renderPlayerStats();
                const k = [...document.querySelectorAll('#screen-stat .card')].find(c => /Wanneer speel je het best/.test(c.textContent));
                const a = buildGameAnalysis(); const m = a.secties.find(s => s.kop === 'Moment');
                const strip = x => String(x).replace(/<[^>]*>/g, '');
                return { kaart: k ? /nog geen heel jaar/.test(k.innerText) : null,
                         analyse: m ? m.regels.map(strip).some(x => /nog geen heel jaar/.test(x)) : null,
                         kwartaal: m ? m.regels.map(strip).some(x => /^Per kwartaal/.test(x)) : null }; }""")
            nonlocal alle_pf
            alle_pf += pf; await ctx.close()
            return uit
        s = await jaarTekst(verdeeld('2025-03-29'))
        check("precies een jaar: de kaart zegt niet 'nog geen heel jaar'", s['kaart'], False)
        check("de analyse noemt per kwartaal en zegt het ook niet", (s['kwartaal'], s['analyse']), (True, False))
        s = await jaarTekst(verdeeld('2025-03-30'))
        check("een dag korter: kaart en analyse zeggen 'nog geen heel jaar'", (s['kaart'], s['analyse']), (True, True))

        print("\n=== 4. BESTANDSNAMEN MET DE LOKALE DATUM ===\n")
        # 24-10-2026 01:30 in Amsterdam = 23-10-2026 23:30 UTC
        ctx, pg, pf = await pagina(b, utc(2026, 10, 23, 23, 30))
        await pg.clock.set_fixed_time(utc(2026, 10, 23, 23, 30))   # stilstaand: een trage start mag de minuut niet verschuiven
        namen = await pg.evaluate("""async () => {
          const namen = [];
          window.tryWriteToExportFolder = async (naam) => { namen.push(naam); return true; };
          await exportAllRounds(); await exportAllClubs();
          const club = Object.keys(JSON.parse(localStorage.getItem('golf_clubs') || '{}'))[0];
          /* de clubknop vraagt een tweede tik ter bevestiging */
          if (club) { const k = document.createElement('button'); document.body.appendChild(k); await exportClub(club, k); await exportClub(club, k); k.remove(); }
          return namen; }""")
        check("drie bestanden weggeschreven", len(namen), 3)
        check("rondebackup om 01:30 heet naar vandaag (20261024)", any(n.startswith('rondes_backup_20261024_') for n in namen), True)
        check("clubbackup ook", any(n.startswith('clubs_backup_20261024_') for n in namen), True)
        check("losse clubexport: lokale datum en tijd 202610240130", any(n.endswith('_202610240130.json') for n in namen), True)
        alle_pf += pf; await ctx.close()

        print("\n=== 5. EEN TIJD '9:00' WORDT '09:00': UIT EEN BESTAND EN AL IN DE OPSLAG ===\n")
        ctx, pg, pf = await pagina(b, utc(2026, 10, 24, 12))
        t = await pg.evaluate("""() => [zetRondeRecht({ date: '2026-05-01', time: '9:00' }).time,
            zetRondeRecht({ date: '2026-05-01', time: '10:00' }).time,
            zetRondeRecht({ date: '2026-05-01', time: ' 10:00 ' }).time,
            isFinite(tijdstipVan(zetRondeRecht({ date: '2026-05-01', time: '9:05' })))]""")
        check("'9:00' wordt '09:00', '10:00' blijft, spaties gaan eraf, het tijdstip is geldig", t, ['09:00', '10:00', '10:00', True])
        # Een ronde die tot 038 met '9:00' in de opslag kon komen, naast dezelfde met '09:00':
        # bij het inlezen gelijkgetrokken, zodat de controle op dubbele rondes hem ziet.
        d = await pg.evaluate("""() => { const s = loadSavedRounds(); const b = s.find(r => isRondeAf(r));
            s.push({ ...b, id: 990101, date: '2026-05-01', time: '9:00' }, { ...b, id: 990102, date: '2026-05-01', time: '09:00' });
            localStorage.setItem('golf_rounds', JSON.stringify(s));
            const na = loadSavedRounds().filter(r => r.id === 990101 || r.id === 990102);
            const dup = findDuplicateRounds(loadSavedRounds());
            return [na.map(r => r.time), !!dup && dup.has('990101') && dup.has('990102')]; }""")
        check("uit de opslag gelezen: allebei '09:00'", d[0], ['09:00', '09:00'])
        check("en ze worden als dubbel herkend", d[1], True)
        alle_pf += pf; await ctx.close()

        check("geen fouten in de pagina", alle_pf, [])
        await b.close()
    print()
    if fouten:
        print(f"{len(fouten)} FOUT(EN)"); sys.exit(1)
    print("ALLES GOED")

asyncio.run(main())
