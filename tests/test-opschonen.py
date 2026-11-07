"""Oude rondes opschonen (1352898-033).

Instellingen → Gegevens → Opruimen & resetten → Toon opties → Oude rondes opschonen:
bewaar de nieuwste N afgeronde rondes. Vaste eisen (gebruiker, 20-10-2026):
  * nooit meer weg dan kan: de handicap, de Low HI en de ESR-verlagingen van elke speler
    blijven exact gelijk, nu én bij elke ronde die je daarna speelt (Rules of Handicapping
    2024, regels 5.2, 5.4, 5.7, 5.8, 5.9);
  * nooit weg: geplande, gepauzeerde en nog niet opgeslagen geïmporteerde rondes; staat er
    een ronde open (spelen of corrigeren), dan kan opschonen niet;
  * eerst een archiefbestand met precies de rondes die weggaan; verwijderen pas daarna, en
    alleen zolang het plan en de inhoud van die rondes niet veranderd zijn;
  * verwijderen nooit met één tik;
  * het archief zet met Toevoegen alles exact terug; Vervangen wordt bij een archief niet
    aangeboden; een tweede archief op dezelfde dag overschrijft het eerste niet.

A. HET PLAN op een verzonnen geschiedenis van 12 jaar (twee spelers, grote schommelingen
   zodat soft/hard cap en ESR optreden, twee rondes op één dag, niet-qualifying rondes,
   rondes zonder dagresultaat), voor 100, 300, 1.000 en 2.500, en ook met een handmatige
   Low HI.
B. DE TOEKOMST: na het opschonen per speler 120 nieuwe rondes rond het eigen niveau (met
   een neiging omhoog, zodat de caps gaan tellen), op acht verschillende geschiedenissen;
   na elke ronde moeten handicap en Low HI gelijk zijn aan die zonder opschonen. (Gevonden
   in de review: alleen 'gelijk van nu' was niet genoeg; deze opzet volgt die van de
   reviewer en faalt op de versie van vóór de review.)
C. DE KNOPPEN: − en +, archief (precies het plan), verwijderen pas na het archief, een ander
   plan of een gewijzigde ronde zet verwijderen weer uit, twee tikken + bevestigen.
D. TERUGZETTEN: het archief biedt alleen Toevoegen, en zet precies de oorspronkelijke rondes
   terug.
E. EEN OPEN RONDE: opschonen kan niet, beide knoppen uit.
F. TWEE ARCHIEVEN OP ÉÉN DAG in een exportmap: allebei bewaard.

De mutaties die deze test moet vangen staan in mutaties-opschonen.py.
"""
import asyncio, os, sys, json, random, tempfile, re
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

def geschiedenis(zaad=20261020):
    import datetime as dt
    rnd = random.Random(zaad)
    uit, rid = [], 1
    dag = dt.date(2014, 3, 1)
    niveau = 30.0
    while dag < dt.date(2026, 10, 15):
        niveau = max(8.0, min(50.0, niveau + rnd.gauss(0, 1.6)))
        sd = round(niveau + rnd.gauss(0, 3.5), 1)
        if rnd.random() < 0.04: sd = round(niveau - 11 - rnd.random() * 3, 1)   # uitzonderlijk
        r = ronde(rid, dag.isoformat()); r['sd'] = r['sdFinal'] = sd
        r['time'] = f"{8 + rid % 9:02d}:{rid % 60:02d}"
        k = rnd.random()
        if k < 0.04: r['qualifying'] = False                                    # niet-qualifying
        elif k < 0.07: r['sd'] = r['sdFinal'] = None                            # zonder dagresultaat
        uit.append(r); rid += 1
        if rnd.random() < 0.05:                                                 # twee op één dag
            r2 = ronde(rid, dag.isoformat()); r2['sd'] = r2['sdFinal'] = round(sd + rnd.gauss(0, 2), 1)
            r2['time'] = '16:30'; uit.append(r2); rid += 1
        if rnd.random() < 0.18:                                                 # medespeler
            p = ronde(rid, dag.isoformat(), speler='Partner'); p['sd'] = p['sdFinal'] = round(22 + rnd.gauss(0, 4), 1)
            p['time'] = '10:00'; uit.append(p); rid += 1
        dag += dt.timedelta(days=rnd.randint(3, 9))
    beschermd = [ronde(900001, '2015-05-05', played=4),                          # gepauzeerd, oud
                 ronde(900002, '2027-03-01', played=0)]                         # gepland
    imp = ronde(900004, '2014-07-01'); imp['_justImported'] = True; beschermd.append(imp)   # geïmporteerd, niet opgeslagen
    for i, r in enumerate(beschermd): r['time'] = f"07:0{i}"   # een eigen tijd: herkenbaar in het archief
    for r in uit + beschermd:                                    # hole-id's als tekst, zoals in de app
        for h in r['holes']: h['id'] = str(h['id'])
    return uit + beschermd, [r['id'] for r in beschermd]

PLAN = """([bewaar, beschermd]) => {
  const alle = loadSavedRounds();
  const plan = opschoonPlan(bewaar, alle);
  const weg = new Set(plan.weg.map(r => r.id));
  const rest = alle.filter(r => !weg.has(r.id));
  const kandidaten = alle.filter(r => hoortInBackup(r) && !isLopendeRonde(r)).sort(archiefNieuwsteEerst);
  const spelers = [...new Set(alle.map(r => r.player))];
  const anders = spelers.filter(p => standVoorOpschonen(p, alle) !== standVoorOpschonen(p, rest));
  // het eenvoudige plan zonder narekenen: het jaar plus 20
  const naief = new Set(kandidaten.slice(bewaar).map(r => r.id));
  for (const p of spelers) {
    const c = verloopChrono(p, alle); if (!c.length) continue;
    const grens = c[c.length - 1].t - 366 * 864e5;
    let i = c.findIndex(x => !(x.t < grens)); if (i < 0) i = c.length;
    c.slice(Math.max(0, i - 20)).forEach(x => naief.delete(x.id));
  }
  return { weg: weg.size, beschermdWeg: beschermd.filter(id => weg.has(id)),
           nieuwsteWeg: kandidaten.slice(0, bewaar).filter(r => weg.has(r.id)).length,
           anders, extraBewaard: naief.size - weg.size };
}"""

# Per speler 120 rondes na het opschonen, rond het eigen niveau met een neiging omhoog:
# na elke ronde de stand met en zonder opschonen vergelijken.
TOEKOMST = """([bewaar, zaad]) => {
  const alle = loadSavedRounds();
  const weg = new Set(opschoonPlan(bewaar, alle).weg.map(r => r.id));
  const rest = alle.filter(r => !weg.has(r.id));
  const fouten = [];
  for (const speler of ['Testspeler', 'Partner']) {
    const A = whsStand(speler, alle);
    if (!A.nu) continue;
    const laatst = A.chrono[A.chrono.length - 1];
    let x = 1; const kans = () => { x = (x * 16807 + zaad) % 2147483647; return x / 2147483647; };
    const extra = [];
    for (let k = 1; k <= 120; k++) {
      const d = new Date(laatst.t + k * 5 * 864e5);
      const sd = Math.round((A.nu.value + (kans() - 0.3) * 14) * 10) / 10;
      extra.push({ ...laatst.ronde, id: speler + '-f' + k, date: d.toISOString().slice(0, 10), time: '12:00',
                   sd, sdFinal: sd, holes: laatst.ronde.holes.map(h => ({ ...h })) });
      const a = whsStand(speler, [...alle, ...extra]), b = whsStand(speler, [...rest, ...extra]);
      const sa = JSON.stringify([a.nu.value, a.lowHi]), sb = JSON.stringify([b.nu.value, b.lowHi]);
      if (sa !== sb) { fouten.push(`${speler} ronde ${k} (${d.toISOString().slice(0, 10)}): ${sa} zonder, ${sb} met opschonen`); break; }
    }
  }
  return { weg: weg.size, fouten };
}"""

OPEN = """() => {
  document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'));
  nav('settings'); switchSettingsTab('data');
  const sk = [...document.querySelectorAll('[data-section-key]')].find(k => k.dataset.sectionKey.includes('Opruimen'));
  openSectie(sk.dataset.sectionKey);
  const t = document.getElementById('opschoonPaneel').closest('.more-full').previousElementSibling;
  if (!t.classList.contains('open')) t.click();
}"""
KNOPPEN = """() => ({ bewaar: document.getElementById('opschoonBewaar').textContent,
  uitleg: document.getElementById('opschoonUitleg').textContent.replace(/\\s+/g, ' ').trim(),
  archief: !document.getElementById('opschoonArchiefBtn').disabled,
  verwijder: !document.getElementById('opschoonVerwijderBtn').disabled,
  aantal: loadSavedRounds().length })"""
STANDEN = """() => { const a = loadSavedRounds(); return [...new Set(a.map(r => r.player))].sort().map(p => [p, standVoorOpschonen(p, a)]); }"""
ALS_BESTAND = """() => JSON.stringify(rondesVoorBestand(loadSavedRounds().filter(r => hoortInBackup(r)))
   .sort((a, b) => (a.date + a.time + a.player).localeCompare(b.date + b.time + b.player)))"""
VENSTER_OPEN = "() => !document.getElementById('resetAllModal').classList.contains('hidden')"
MODALS_WEG = "() => document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))"

async def pagina(b, rondes, extra=None):
    ctx = await b.new_context(viewport={'width': 390, 'height': 844}, accept_downloads=True)
    pg = await ctx.new_page()
    pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
    await pg.goto(app_url())
    await pg.evaluate(SEED, [CLUBS, rondes])
    await pg.evaluate("() => { localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.removeItem('golf_active_id'); }")
    if extra: await pg.evaluate(extra)
    await pg.reload(); await pg.wait_for_timeout(900)
    await pg.evaluate(MODALS_WEG)
    return ctx, pg, pf

async def verwijder_twee_tikken(pg):
    await pg.click('#opschoonVerwijderBtn', force=True); await pg.wait_for_timeout(150)
    await pg.click('#opschoonVerwijderBtn', force=True); await pg.wait_for_timeout(300)

async def main():
    rondes, beschermd = geschiedenis()
    map_ = tempfile.mkdtemp(prefix='opschonen-')
    print(f"  {len(rondes)} rondes, waarvan {sum(1 for r in rondes if r['player'] == 'Testspeler')} van Testspeler")
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx, pg, pf = await pagina(b, rondes)

        print("\n=== A. HET PLAN ===\n")
        for bewaar in (100, 300, 1000, 2500):
            r = await pg.evaluate(PLAN, [bewaar, beschermd])
            print(f"  bewaar {bewaar}: {r['weg']} weg, {r['extraBewaard']} extra bewaard door narekenen")
            check(f"bewaar {bewaar}: beschermde rondes blijven", r['beschermdWeg'], [])
            check(f"bewaar {bewaar}: de nieuwste {bewaar} blijven", r['nieuwsteWeg'], 0)
            check(f"bewaar {bewaar}: handicap, Low HI, ESR en het laatste jaar van elke speler gelijk", r['anders'], [])
            check(f"bewaar {bewaar}: het narekenen bewaart nooit minder dan het jaar plus 20", r['extraBewaard'] >= 0, True)
        r100 = await pg.evaluate(PLAN, [100, beschermd])
        check("bij 100 gaat er echt iets weg", r100['weg'] > 400, True)
        await pg.evaluate("() => localStorage.setItem('golf_low_hi', '15.0')")
        r = await pg.evaluate(PLAN, [100, beschermd])
        check("met een handmatige Low HI: ook gelijk", r['anders'], [])
        await pg.evaluate("() => localStorage.removeItem('golf_low_hi')")

        print("\n=== B. DE TOEKOMST ===\n")
        bfouten = []
        for zaad in (20261020, 1, 2, 3, 4, 5, 6, 7):
            if zaad != 20261020:
                await pg.evaluate("(r) => { localStorage.setItem('golf_rounds', JSON.stringify(r)); }", geschiedenis(zaad)[0])
            for bewaar in (100, 300):
                for z2 in (7, 99991):
                    t = await pg.evaluate(TOEKOMST, [bewaar, z2])
                    bfouten += [f"geschiedenis {zaad}, bewaar {bewaar}: {f}" for f in t['fouten']]
        print(f"  8 geschiedenissen × 2 × 2 toekomsten, per speler 120 rondes")
        check("na elke nieuwe ronde dezelfde handicap en Low HI als zonder opschonen", bfouten[:3], [])
        await pg.evaluate("(r) => { localStorage.setItem('golf_rounds', JSON.stringify(r)); }", rondes)

        print("\n=== C. DE KNOPPEN ===\n")
        await pg.evaluate(OPEN); await pg.wait_for_timeout(300)
        k = await pg.evaluate(KNOPPEN)
        print('  ', k['uitleg'])
        check("standaard: de nieuwste 1.000", k['bewaar'], '1.000')
        check("verwijderen staat uit zolang er geen archief is", k['verwijder'], False)
        for _ in range(9): await pg.click('#opschoonMin')
        check("negen keer −: 100", (await pg.evaluate(KNOPPEN))['bewaar'], '100')
        await pg.click('#opschoonMin')
        check("nog een keer −: blijft 100", (await pg.evaluate(KNOPPEN))['bewaar'], '100')
        await pg.click('#opschoonPlus'); await pg.click('#opschoonPlus')
        k = await pg.evaluate(KNOPPEN)
        check("twee keer +: 300", k['bewaar'], '300')
        plan = await pg.evaluate(PLAN, [300, beschermd])
        check("de uitleg noemt het aantal van het plan", f"Er gaan {plan['weg']:,}".replace(',', '.') in k['uitleg'], True)
        check("verwijderen staat nog uit", k['verwijder'], False)

        voor_aantal = k['aantal']
        async with pg.expect_download() as dl:
            await pg.click('#opschoonArchiefBtn')
        d = await dl.value
        pad = os.path.join(map_, d.suggested_filename)
        await d.save_as(pad)
        archief = json.load(open(pad, encoding='utf-8'))
        check("archief: naam met datum en tijd", bool(re.match(r'^rondes_archief_\d{8}-\d{6}_', d.suggested_filename)), True)
        check("archief: wordt herkend als bestand van deze installatie", await pg.evaluate("(n) => andereOpslagCode(n)", d.suggested_filename), None)
        check("archief: van een andere installatie wordt de code herkend",
              await pg.evaluate("(n) => andereOpslagCode(n.replace(/\\(([A-Z0-9]{4})\\)/, '(ZZ99)'))", d.suggested_filename), 'ZZ99')
        check("archief: precies zoveel rondes als het plan", len(archief), plan['weg'])
        check("archief: geen beschermde ronde erin", [x['date'] + ' ' + x['time'] for x in archief if x['time'].startswith('07:0')], [])
        await pg.wait_for_timeout(200)
        check("na het archief: verwijderen kan", (await pg.evaluate(KNOPPEN))['verwijder'], True)
        await pg.click('#opschoonPlus')
        check("ander plan (+): verwijderen staat weer uit", (await pg.evaluate(KNOPPEN))['verwijder'], False)
        await pg.click('#opschoonMin')
        check("terug naar hetzelfde plan: verwijderen kan weer", (await pg.evaluate(KNOPPEN))['verwijder'], True)

        # een ronde uit het plan wordt gecorrigeerd nadat het archief er is (zoals vanuit een
        # ander venster: buiten de app om in de opslag)
        await pg.evaluate("""([datum, tijd]) => { const l = JSON.parse(localStorage.getItem('golf_rounds'));
            const r = l.find(x => x.date === datum && x.time === tijd); r.note = 'later gecorrigeerd';
            localStorage.setItem('golf_rounds', JSON.stringify(l)); }""", [archief[0]['date'], archief[0]['time']])
        await verwijder_twee_tikken(pg)
        check("ronde uit het plan gewijzigd na het archief: geen venster, niets weg",
              [await pg.evaluate(VENSTER_OPEN), await pg.evaluate("() => loadSavedRounds().length")], [False, voor_aantal])
        check("en verwijderen staat uit", (await pg.evaluate(KNOPPEN))['verwijder'], False)
        # opnieuw een archief, nu met de correctie
        voor_bestand = await pg.evaluate(ALS_BESTAND)
        voor_standen = await pg.evaluate(STANDEN)
        await pg.wait_for_timeout(1100)
        async with pg.expect_download() as dl:
            await pg.click('#opschoonArchiefBtn')
        d = await dl.value
        pad = os.path.join(map_, d.suggested_filename)
        await d.save_as(pad)
        check("het nieuwe archief bevat de correctie", any(x.get('note') == 'later gecorrigeerd' for x in json.load(open(pad, encoding='utf-8'))), True)
        await pg.wait_for_timeout(200)

        await pg.click('#opschoonVerwijderBtn'); await pg.wait_for_timeout(200)
        check("één tik: niets verwijderd, geen venster", [await pg.evaluate("() => loadSavedRounds().length"),
              await pg.evaluate(VENSTER_OPEN)], [voor_aantal, False])
        await pg.click('#opschoonVerwijderBtn'); await pg.wait_for_timeout(300)
        check("tweede tik: het venster", await pg.evaluate(VENSTER_OPEN), True)
        check("nog niets verwijderd", await pg.evaluate("() => loadSavedRounds().length"), voor_aantal)
        await pg.click('#dangerModalConfirmBtn'); await pg.wait_for_timeout(400)
        na_aantal = await pg.evaluate("() => loadSavedRounds().length")
        check("bevestigd: precies het plan verwijderd", voor_aantal - na_aantal, plan['weg'])
        check("en de stand van elke speler is gelijk", await pg.evaluate(STANDEN), voor_standen)
        check("beschermde rondes staan er nog", await pg.evaluate("(ids) => ids.filter(id => !loadSavedRounds().some(r => r.id === id))", beschermd), [])
        await pg.evaluate(MODALS_WEG)
        check("de regel met hoe vol het is volgt", (await pg.evaluate("() => document.getElementById('rondeVoorraad').textContent")).startswith(f"Opgeslagen: {na_aantal:,}".replace(',', '.')), True)
        check("daarna: verwijderen staat weer uit", (await pg.evaluate(KNOPPEN))['verwijder'], False)

        print("\n=== D. TERUGZETTEN ===\n")
        await pg.evaluate("() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); nav('archive'); }")
        await pg.set_input_files('#importRoundFile', pad); await pg.wait_for_timeout(600)
        knoppen = await pg.evaluate("""() => [...document.querySelectorAll('button')].filter(k => k.offsetParent && /^(Toevoegen|Vervangen…|Annuleren)$/.test(k.textContent.trim())).map(k => k.textContent.trim())""")
        check("een archief inlezen: alleen Toevoegen en Annuleren", sorted(knoppen), ['Annuleren', 'Toevoegen'])
        await pg.get_by_text('Toevoegen', exact=True).first.click(); await pg.wait_for_timeout(800)
        await pg.evaluate(MODALS_WEG)
        check("na Toevoegen: weer evenveel rondes", await pg.evaluate("() => loadSavedRounds().length"), voor_aantal)
        check("na Toevoegen: precies dezelfde rondes als voor het opschonen", await pg.evaluate(ALS_BESTAND) == voor_bestand, True)
        check("en dezelfde stand", await pg.evaluate(STANDEN), voor_standen)
        check("geen fouten in de pagina", pf, [])
        await ctx.close()

        print("\n=== E. EEN OPEN RONDE ===\n")
        ctx, pg, pf = await pagina(b, rondes, "() => localStorage.setItem('golf_active_id', '5')")
        await pg.evaluate(OPEN); await pg.wait_for_timeout(300)
        for _ in range(9): await pg.click('#opschoonMin')
        k = await pg.evaluate(KNOPPEN)
        print('  ', k['uitleg'])
        check("een ronde staat open: de uitleg zegt het, beide knoppen uit", ['open' in k['uitleg'], k['archief'], k['verwijder']], [True, False, False])
        check("en het plan haalt niets weg", await pg.evaluate("() => opschoonPlan(100).weg.length"), 0)
        check("geen fouten in de pagina (open ronde)", pf, [])
        await ctx.close()

        print("\n=== F. TWEE ARCHIEVEN OP ÉÉN DAG IN EEN EXPORTMAP ===\n")
        ctx, pg, pf = await pagina(b, rondes)
        await pg.evaluate("""() => { window.__map = {}; tryWriteToExportFolder = async (naam, tekst) => { window.__map[naam] = JSON.parse(tekst).length; return true; }; }""")
        await pg.evaluate(OPEN); await pg.wait_for_timeout(300)
        for _ in range(7): await pg.click('#opschoonMin')        # 300
        for keer in (1, 2):
            await pg.click('#opschoonArchiefBtn'); await pg.wait_for_timeout(300)
            await verwijder_twee_tikken(pg)
            await pg.click('#dangerModalConfirmBtn'); await pg.wait_for_timeout(400)
            await pg.evaluate(MODALS_WEG)
            if keer == 1:
                for _ in range(2): await pg.click('#opschoonMin')  # 100
                await pg.wait_for_timeout(1100)                    # een volgende seconde
        mapinhoud = await pg.evaluate("() => window.__map")
        print('  ', mapinhoud)
        check("twee archieven op één dag: allebei in de map", len(mapinhoud), 2)
        check("en samen precies wat er weg is", sum(mapinhoud.values()), len(rondes) - await pg.evaluate("() => loadSavedRounds().length"))
        check("geen fouten in de pagina (exportmap)", pf, [])
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
