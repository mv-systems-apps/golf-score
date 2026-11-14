"""Agenda-icoon bij geplande rondes en de Outlook-knop in de kop (13528FA-001).

Een geplande ronde heeft links van de datum een agenda-icoon, op het lege scorescherm en
in Rondes (daar in plaats van het gouden driehoekje; een gepauzeerde ronde houdt het
driehoekje). Het icoon zegt of de ronde in de agenda staat:
  groen +   nooit geëxporteerd                     (agenda-nieuw)
  grijs ✓   geëxporteerd, sindsdien gelijk         (agenda-erin)
  goud •    gewijzigd sinds de export              (agenda-gewijzigd)
Gelijk betekent: wat in het agenda-item staat (datum, tijd, duur, titel, plaats) is niet
veranderd; een andere tee telt niet. De ronde onthoudt de export in agendaExport, alleen na
een geslaagde export (gedeeld of gedownload), niet als het deelmenu wordt weggetikt.
Herplannen neemt agendaExport van de oude ronde over. Een tik op het icoon exporteert en
doet verder niets. Rechts in de lege kop staat een knop die Outlook opent; een tik daarop
gaat niet naar Rondes.
"""
import asyncio, os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

HIER = os.path.dirname(os.path.abspath(__file__))
PLAN = open(os.path.join(HIER, 'test-op-deze-baan.py')).read().split('PLAN = """')[1].split('"""')[0]
PLAN = PLAN % (datetime.date.today() + datetime.timedelta(days=5)).isoformat()

# Veilig uitvoeren: een fout in de pagina wordt een waarde, geen afgebroken test
async def ev(pg, js, arg=None):
    try:
        return await pg.evaluate(js, arg)
    except Exception as e:
        return 'FOUT: ' + str(e).split('\n')[0][:120]

STAND = """(id) => { const r = loadSavedRounds().find(x => String(x.id) === String(id)); return r ? (r.agendaExport ? 'gezet' : 'leeg') : null; }"""
ICOON = """(sel) => { const el = document.querySelector(sel); return el ? [...el.classList].find(c => c.startsWith('agenda-') && c !== 'agenda-status') || 'geen stand' : null; }"""
# Een export met een nagebootst deelmenu: 'ok' (gedeeld), 'weg' (weggetikt) of 'geen' (geen
# deelmenu: download). Geeft terug wat er gebeurde.
EXPORT = """async ([sel, wijze]) => { const el = document.querySelector(sel); if (!el) return null;
  const echt = { cs: navigator.canShare, sh: navigator.share, dl: window.downloadBestand, st: window.startVanuitLeeg, nr: window.naarRondesVanuitLeeg, oa: window.openRondeKaart };
  const log = []; let klaar; const wacht = new Promise(r => klaar = r);
  try {
    if (wijze === 'geen') { navigator.canShare = undefined; }
    else { navigator.canShare = () => true;
           navigator.share = async (d) => { log.push('deel:' + d.files[0].name); if (wijze === 'weg') { setTimeout(klaar, 50); const e = new Error('weg'); e.name = 'AbortError'; throw e; } setTimeout(klaar, 50); }; }
    window.downloadBestand = (inhoud, naam) => { log.push('download:' + naam); setTimeout(klaar, 50); };
    window.startVanuitLeeg = () => log.push('start'); window.naarRondesVanuitLeeg = () => log.push('rondes');
    el.click();
    await Promise.race([wacht, new Promise(r => setTimeout(r, 1500))]);
    await new Promise(r => setTimeout(r, 50));
  } finally { navigator.canShare = echt.cs; navigator.share = echt.sh; window.downloadBestand = echt.dl; window.startVanuitLeeg = echt.st; window.naarRondesVanuitLeeg = echt.nr; }
  return log; }"""

KAART = '#scoreEmptyMsg .lege-knop[data-soort="gepland"]'

# Lettertypen voor de uitlijning: Roboto ligt dicht bij Android (meegeleverd in tests/fonts,
# SIL Open Font License); daarop stond het icoon in 13528FA-001 2 px te hoog.
LETTERTYPEN = ('standaard', 'DejaVu Sans', 'Roboto')
import base64
FONTFACE = ''.join("@font-face{font-family:'Roboto';font-weight:%d;src:url(data:font/woff2;base64,%s)}"
                   % (w, base64.b64encode(open(os.path.join(HIER, 'fonts', f'roboto-latin-{w}-normal.woff2'), 'rb').read()).decode()) for w in (400, 600, 700, 800))
async def zetLettertype(pg, lt):
    await ev(pg, """([lt, ff]) => { document.getElementById('lt')?.remove(); if (lt === 'standaard') return;
        const st = document.createElement('style'); st.id = 'lt'; st.textContent = (lt === 'Roboto' ? ff : '') + 'body,button{font-family:' + JSON.stringify(lt) + ' !important}'; document.head.appendChild(st); }""", [lt, FONTFACE])
    await ev(pg, "() => document.fonts.ready.then(() => 1)"); await pg.wait_for_timeout(200)

async def oog(pg, sel):
    """Verticaal verschil (px, + = icoon te laag) tussen het midden van het getekende icoon en het
    midden van de cijfers op dezelfde regel, gemeten in de pixels."""
    try:
        import io
        from PIL import Image
        vak = await pg.evaluate("""(sel) => { const a = document.querySelector(sel); if (!a) return null; a.scrollIntoView({ block: 'center' }); const s = a.querySelector('svg').getBoundingClientRect();
            return [s.left, s.right, s.right + 6, s.right + 110, s.top - 2, s.bottom + 2]; }""", sel)
        if not vak: return 'geen icoon'
        im = Image.open(io.BytesIO(await pg.screenshot())).convert('RGB'); f = 2
        def band(x0, x1, donker):
            rijen = [y for y in range(int(vak[4] * f), int(vak[5] * f)) if any(donker(im.getpixel((x, y))) for x in range(int(x0 * f), int(x1 * f)))]
            return (rijen[0] + rijen[-1]) / 2 / f if rijen else None
        mi = band(vak[0], vak[1], lambda c: max(c) - min(c) > 40)
        mt = band(vak[2], vak[3], lambda c: sum(c) < 250)
        return round(mi - mt, 2) if mi is not None and mt is not None else 'niet gevonden'
    except Exception as e:
        return 'FOUT: ' + str(e)[:100]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 800}, device_scale_factor=2)
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        baan = await ev(pg, """() => { const sp = startPlayerName(); const r = loadSavedRounds().find(r => r.player === sp && r.qualifying && isRondeAf(r) && r.tee);
            return r ? [r.club, r.track, r.tee] : null; }""")
        if not isinstance(baan, list):
            check("testdata heeft een afgeronde ronde om te plannen", baan, 'baan'); await b.close(); sys.exit(1)
        await ev(pg, PLAN, [990101, *baan, None]); await pg.wait_for_timeout(300)

        print("\n=== 1. HET ICOON OP HET LEGE SCORESCHERM ===\n")
        m = await ev(pg, """(sel) => { const k = document.querySelector(sel); if (!k) return null; const a = k.querySelector('.agenda-status');
            const d = k.querySelector('.lege-knop-wanneer'); if (!a || !d) return { icoon: !!a };
            const sa = a.querySelector('svg').getBoundingClientRect(), t = d.lastElementChild.getBoundingClientRect();
            return { icoon: true, links: sa.right <= t.left, maat: Math.round(sa.width), midden: Math.abs((sa.top + sa.bottom) / 2 - (t.top + t.bottom) / 2) < 2,
                     regel: d.getBoundingClientRect().height < 34, rol: a.getAttribute('role'), label: a.getAttribute('aria-label'),
                     tikvlak: [Math.round(a.getBoundingClientRect().width), Math.round(a.getBoundingClientRect().height)] }; }""", KAART)
        check("geplande ronde: agenda-icoon in de kaart", (m or {}).get('icoon') if isinstance(m, dict) else m, True)
        if isinstance(m, dict) and 'links' in m:
            check("links van de datum", m['links'], True)
            check("22 px", m['maat'], 22)
            check("datumregel blijft één regel", m['regel'], True)
            check("een knop voor schermlezers", (m['rol'], m['label']), ('button', 'In agenda zetten'))
            check("tikvlak minstens 44×38", m['tikvlak'][0] >= 44 and m['tikvlak'][1] >= 38, True)
            print('    (tikvlak:', m['tikvlak'], ')')
        # Op het oog: het midden van het getekende icoon op het midden van de cijfers (binnen 1 px),
        # gemeten in de pixels van een schermafdruk, niet aan de vakken. Ook met andere lettertypen
        # (LETTERTYPEN): de uitlijning rekent met de cijferhoogte van het lettertype zelf.
        for lt in LETTERTYPEN:
            await zetLettertype(pg, lt)
            v = await oog(pg, KAART + ' .agenda-status')
            check(f"scorescherm, {lt}: icoon op het oog midden naast de cijfers (binnen 1 px)", isinstance(v, float) and abs(v) <= 1, True)
            print('    (verschil:', v, 'px)')
        await zetLettertype(pg, 'standaard')
        check("stand: nooit geëxporteerd (groen +)", await ev(pg, ICOON, KAART + ' .agenda-status'), 'agenda-nieuw')
        check("de gepauzeerde ronde heeft geen agenda-icoon", await ev(pg, "() => { const k = document.querySelector('#scoreEmptyMsg .lege-knop[data-soort=\"gepauzeerd\"]'); return k ? !!k.querySelector('.agenda-status') : 'geen gepauzeerde ronde'; }"), False)

        print("\n=== 2. EXPORTEREN MET HET ICOON ===\n")
        STROOK = """() => [...document.querySelectorAll('#hdrGeplandStrook .kop-dag.gepland')].map(d => d.classList.contains('te-exporteren'))"""
        check("agendastrook: de dag is goud zolang de ronde niet in de agenda staat", await ev(pg, STROOK), [True])
        r = await ev(pg, EXPORT, [KAART + ' .agenda-status', 'weg'])
        check("deelmenu weggetikt: er is gedeeld, verder niets", r, ['deel:golf-' + (datetime.date.today() + datetime.timedelta(days=5)).isoformat() + '-1051.ics'])
        check("weggetikt: de ronde onthoudt niets", await ev(pg, STAND, 990101), 'leeg')
        check("weggetikt: icoon blijft groen", await ev(pg, ICOON, KAART + ' .agenda-status'), 'agenda-nieuw')
        r = await ev(pg, EXPORT, [KAART + ' .agenda-status', 'ok'])
        check("gedeeld: alleen het deelmenu, geen start en geen Rondes", isinstance(r, list) and len(r) == 1 and r[0].startswith('deel:'), True)
        check("gedeeld: de ronde onthoudt de export", await ev(pg, STAND, 990101), 'gezet')
        check("gedeeld: icoon meteen grijs ✓ (zonder opnieuw tekenen)", await ev(pg, ICOON, KAART + ' .agenda-status'), 'agenda-erin')
        check("agendastrook: na de export meteen groen", await ev(pg, STROOK), [False])
        check("label past mee", await ev(pg, "(s) => document.querySelector(s)?.getAttribute('aria-label')", KAART + ' .agenda-status'), 'Staat in agenda, opnieuw exporteren')
        check("na herladen nog steeds ✓", await ev(pg, "() => { verversLegeScoreKnoppen(); return 1; }") == 1 and await ev(pg, ICOON, KAART + ' .agenda-status'), 'agenda-erin')

        print("\n=== 3. WAT TELT ALS GEWIJZIGD ===\n")
        WIJZIG = """([id, veld, waarde]) => { const s = loadSavedRounds(); const r = s.find(x => x.id === id); const oud = r[veld]; r[veld] = waarde;
            setRoundsAndMark(JSON.stringify(s)); const st = agendaStatus(loadSavedRounds().find(x => x.id === id));
            r[veld] = oud; setRoundsAndMark(JSON.stringify(s)); return st; }"""
        andereTee = await ev(pg, "(id) => { const r = loadSavedRounds().find(x => x.id === id); const tees = Object.keys((CLUBS[r.club]?.tracks?.[r.track]?.tees) || {}); return tees.find(t => t !== r.tee) || (r.tee + 'X'); }", 990101)
        check("andere tee: blijft ✓ (staat niet in de afspraak)", await ev(pg, WIJZIG, [990101, 'tee', andereTee]), 'erin')
        check("andere tijd: goud", await ev(pg, WIJZIG, [990101, 'time', '08:02']), 'gewijzigd')
        check("andere datum: goud", await ev(pg, WIJZIG, [990101, 'date', (datetime.date.today() + datetime.timedelta(days=6)).isoformat()]), 'gewijzigd')
        check("andere baan: goud", await ev(pg, WIJZIG, [990101, 'track', 'Anders']), 'gewijzigd')
        check("18 in plaats van 9 holes (andere eindtijd): goud", await ev(pg, WIJZIG, [990101, 'holesCount', 18]), 'gewijzigd')
        check("terug zoals het was: weer ✓", await ev(pg, "(id) => agendaStatus(loadSavedRounds().find(x => x.id === id))", 990101), 'erin')
        await ev(pg, "() => { const s = loadSavedRounds(); s.find(x => x.id === 990101).time = '08:02'; setRoundsAndMark(JSON.stringify(s)); verversLegeScoreKnoppen(); }")
        check("gewijzigd op het scherm: goud", await ev(pg, ICOON, KAART + ' .agenda-status'), 'agenda-gewijzigd')
        check("gewijzigd: label", await ev(pg, "(s) => document.querySelector(s)?.getAttribute('aria-label')", KAART + ' .agenda-status'), 'Agenda bijwerken')
        r = await ev(pg, EXPORT, [KAART + ' .agenda-status', 'geen'])
        check("zonder deelmenu: download", isinstance(r, list) and len(r) == 1 and r[0].startswith('download:'), True)
        check("na de download weer ✓", await ev(pg, ICOON, KAART + ' .agenda-status'), 'agenda-erin')

        print("\n=== 4. DE VINGERAFDRUK VOLGT HET AGENDA-ITEM ===\n")
        v = await ev(pg, """(id) => { const r = loadSavedRounds().find(x => x.id === id); return [agendaVingerafdruk(r), r.date, r.time, r.club]; }""", 990101)
        if isinstance(v, list):
            delen = v[0].split('|')
            check("datum, tijd, duur, titel, plaats", [delen[0], delen[1], delen[2], delen[4]], [v[1], v[2], '150', v[3]])
            check("titel zoals in de export", delen[3].startswith('Golf - '), True)
        else:
            check("vingerafdruk", v, 'lijst')
        check("een ronde zonder tijd: 09:00 zoals de export", await ev(pg, "() => agendaVingerafdruk({ date: '2026-12-01', time: null, holes: [], club: 'X' }).split('|')[1]"), '09:00')

        print("\n=== 5. OPSLAG ===\n")
        check("keurRonde: agendaExport moet tekst zijn", await ev(pg, "(id) => { const r = loadSavedRounds().find(x => x.id === id); r.agendaExport = 5; return keurRonde(r); }", 990101), 'agendaexport is geen tekst')
        check("keurRonde: met een tekst hetzelfde oordeel als zonder het veld", await ev(pg, "(id) => { const r = loadSavedRounds().find(x => x.id === id); const met = keurRonde(r); delete r.agendaExport; return met === keurRonde(r); }", 990101), True)
        h = await ev(pg, """(id) => { const echt = _herplanIds; try { _herplanIds = [id]; return [agendaExportVanHerplan(0) === loadSavedRounds().find(x => x.id === id).agendaExport, agendaExportVanHerplan(1)]; } finally { _herplanIds = echt; } }""", 990101)
        check("herplannen neemt de export van de oude ronde over", h, [True, None])
        z = await ev(pg, """() => { const echt = { g: game, c: currentHole }; try {
              game = { ...loadSavedRounds().find(x => x.id === 990101), started: true }; delete game.agendaExport;
              const zonder = 'agendaExport' in buildRoundEntry();
              markeerAgendaExport(990101); const met = buildRoundEntry().agendaExport === agendaVingerafdruk(game);
              return [zonder, met]; } finally { game = echt.g; currentHole = echt.c; } }""")
        check("lopende ronde: leeg veld niet opgeslagen, na export wel mee in de opslag", z, [False, True])
        af = await ev(pg, """() => { const echt = { g: game, c: currentHole }; try {
              const basis = { ...loadSavedRounds().find(x => x.id === 990101), started: true, agendaUid: 'golfscore-1', agendaExport: 'x|y' };
              game = { ...basis, holes: basis.holes.map((h, i) => ({ ...h, score: i ? null : 4 })) };
              const bezig = buildRoundEntry();
              game = { ...basis, holes: basis.holes.map(h => ({ ...h, score: 4 })) };
              const klaar = buildRoundEntry();
              return [['agendaUid' in bezig, 'agendaExport' in bezig], ['agendaUid' in klaar, 'agendaExport' in klaar]]; } finally { game = echt.g; currentHole = echt.c; } }""")
        check("agendavelden blijven tijdens het spelen, en vallen weg als de ronde af is (niet in de backup)", af, [[True, True], [False, False]])
        bron = await ev(pg, "() => { const r = loadSavedRounds().find(x => x.id === 990101); return startRoundConfirmed.toString().includes('agendaExportVanHerplan(0)') && startRoundConfirmed.toString().includes('agendaExportVanHerplan(1)'); }")
        check("startRoundConfirmed zet de overgenomen export bij beide spelers", bron, True)

        print("\n=== 6. RONDES ===\n")
        await ev(pg, "() => naarAgendaInRondes()"); await pg.wait_for_timeout(500)
        rk = await ev(pg, """() => { const el = [...document.querySelectorAll('#screen-archive .agenda-status')].find(a => a.dataset.id === '990101');
            if (!el) return null; const kaart = el.closest('[onclick], .saved-round, .round-card') || el.parentElement;
            return { stand: [...el.classList].find(c => c.startsWith('agenda-') && c !== 'agenda-status'), maat: Math.round(el.querySelector('svg').getBoundingClientRect().width),
                     driehoek: !!el.parentElement.querySelector('svg[title="Bezig"]') }; }""")
        check("geplande ronde in Rondes: agenda-icoon in plaats van het driehoekje", rk and (rk.get('stand'), rk.get('maat'), rk.get('driehoek')) if isinstance(rk, dict) else rk, ('agenda-erin', 20, False))
        for lt in LETTERTYPEN:
            await zetLettertype(pg, lt)
            v = await oog(pg, '#screen-archive .agenda-status')
            check(f"Rondes, {lt}: icoon op het oog midden naast de cijfers (binnen 1 px)", isinstance(v, float) and abs(v) <= 1, True)
            print('    (verschil:', v, 'px)')
        await zetLettertype(pg, 'standaard')
        n = await ev(pg, "() => [...document.querySelectorAll('#screen-archive svg[title=\"Bezig\"]')].length")
        print('    (driehoekjes bij niet-geplande, niet-afgeronde rondes:', n, ')')
        r = await ev(pg, """async () => { const el = [...document.querySelectorAll('#screen-archive .agenda-status')].find(a => a.dataset.id === '990101'); if (!el) return null;
            const echt = { cs: navigator.canShare, sh: navigator.share }; const voor = location.hash + document.querySelector('.screen.active')?.id; const log = [];
            const kaart = el.parentElement; const klik = []; document.addEventListener('click', e => klik.push(e.target === el || el.contains(e.target)), { once: true, capture: false });
            try { navigator.canShare = () => true; navigator.share = async () => { log.push('deel'); }; el.click(); await new Promise(r => setTimeout(r, 120)); }
            finally { navigator.canShare = echt.cs; navigator.share = echt.sh; }
            return [log, klik.length, voor === location.hash + document.querySelector('.screen.active')?.id]; }""")
        check("tik in Rondes: alleen exporteren, de klik gaat niet verder", r, [['deel'], 0, True])

        print("\n=== 6b. MEDESPELER OP HETZELFDE MOMENT ===\n")
        # Per moment één afspraak: de kaart van de medespeler toont en exporteert die van speler 1.
        mede = await ev(pg, """() => { const s = loadSavedRounds(); const h = s.find(x => x.id === 990101);
            s.push({ ...h, id: 990109, player: 'Medespeler', agendaExport: undefined, agendaUid: undefined }); setRoundsAndMark(JSON.stringify(s)); tekenRondelijst();
            const el = [...document.querySelectorAll('#screen-archive .agenda-status')]; return el.map(a => a.dataset.id).sort(); }""")
        check("beide kaarten tonen de afspraak van speler 1", mede, ['990101', '990101'] if isinstance(mede, list) and len(mede) == 2 else mede)
        ex = await ev(pg, """async () => { const echt = { cs: navigator.canShare, sh: navigator.share }; let tekst = null;
            const s = loadSavedRounds(); delete s.find(x => x.id === 990101).agendaExport; setRoundsAndMark(JSON.stringify(s));
            try { navigator.canShare = () => true; navigator.share = async d => { tekst = await d.files[0].text(); }; await exportRoundIcs('990109'); }
            finally { navigator.canShare = echt.cs; navigator.share = echt.sh; }
            const n = loadSavedRounds(); return [((tekst || '').split('UID:')[1] || '').split(String.fromCharCode(13))[0], !!n.find(x => x.id === 990101).agendaExport, !!n.find(x => x.id === 990109).agendaExport]; }""")
        check("exportvenster op de kaart van de medespeler: de afspraak van speler 1", ex, ['golfscore-990101@golf-score.local', True, False])
        await ev(pg, "() => { const s = loadSavedRounds().filter(x => x.id !== 990109); metVerwijderen(() => setRoundsAndMark(JSON.stringify(s))); }")

        print("\n=== 6c. DE KNOP OP DE SCOREKAART ===\n")
        # Een geplande ronde open op de scorekaart: naast Sluiten een vierkante knop met het icoon.
        await ev(pg, "() => { const s = loadSavedRounds(); delete s.find(x => x.id === 990101).agendaExport; setRoundsAndMark(JSON.stringify(s)); nav('score'); verversLegeScoreKnoppen(); }")
        await ev(pg, "() => startVanuitLeeg(document.querySelector('#scoreEmptyMsg .lege-knop[data-soort=\"gepland\"]'))"); await pg.wait_for_timeout(400)
        KNOP = """() => { const k = document.getElementById('agendaVanRondeBtn'), s = document.getElementById('finishRoundBtn'); if (!k || k.classList.contains('hidden')) return null;
            const rk = k.getBoundingClientRect(), rs = s.getBoundingClientRect(), svg = k.querySelector('svg');
            return { breed: Math.round(rk.width), hoogGelijk: Math.abs(rk.height - rs.height) < 0.5, sluitenBreder: rs.width > rk.width * 3,
                     stand: [...k.classList].find(c => c.startsWith('agenda-')), label: k.getAttribute('aria-label'), tekst: k.textContent.trim(),
                     icoon: svg ? Math.round(svg.getBoundingClientRect().width) : 0,
                     kleur: getComputedStyle(k).color === getComputedStyle(document.querySelector('#scoreEmptyMsg .agenda-status, .agenda-status') || k).color }; }"""
        m = await ev(pg, KNOP)
        check("vierkant naast Sluiten: 46 breed, even hoog, Sluiten krijgt de rest, geen tekst", m and [m['breed'], m['hoogGelijk'], m['sluitenBreder'], m['tekst'], m['icoon']], [46, True, True, '', 22])
        check("nog niet geëxporteerd: goud met +, label", m and [m['stand'], m['label']], ['agenda-nieuw', 'In agenda zetten'])
        kl = await ev(pg, "() => [getComputedStyle(agendaVanRondeBtn).color, getComputedStyle(document.documentElement).getPropertyValue('--gold').trim()]")
        check("in de goudkleur", isinstance(kl, list) and kl[0] == (lambda h: f"rgb({int(h[1:3],16)}, {int(h[3:5],16)}, {int(h[5:7],16)})")(kl[1]) if isinstance(kl, list) and kl[1].startswith('#') else kl, True)
        r = await ev(pg, """async () => { const echt = { cs: navigator.canShare, sh: navigator.share }; try { navigator.canShare = () => true; navigator.share = async () => {}; agendaVanRondeBtn.click(); await new Promise(r => setTimeout(r, 150)); }
            finally { navigator.canShare = echt.cs; navigator.share = echt.sh; } return [[...agendaVanRondeBtn.classList].find(c => c.startsWith('agenda-')), agendaVanRondeBtn.getAttribute('aria-label')]; }""")
        check("na de export meteen groen met ✓", r, ['agenda-erin', 'Staat in agenda, opnieuw exporteren'])
        await ev(pg, "() => document.getElementById('finishRoundBtn').click()"); await pg.wait_for_timeout(300)

        print("\n=== 7. OUTLOOK IN DE KOP ===\n")
        await ev(pg, "() => nav('score')"); await pg.wait_for_timeout(200)
        ko = await ev(pg, "() => { const k = document.querySelector('#hdrHoleCount .kop-agenda'); return k ? [k.getAttribute('role'), k.getAttribute('aria-label'), Math.round(k.querySelector('svg').getBoundingClientRect().width)] : null; }")
        check("rechts op regel 2 een agendaknop", ko, ['button', 'Open agenda', 20])
        check("opent standaard Outlook (ms-outlook://calendar; de link zelf: test-agendalink.py)", await ev(pg, "() => typeof agendaLink === 'function' && agendaLink()"), 'ms-outlook://calendar')
        r = await ev(pg, """() => { const k = document.querySelector('#hdrHoleCount .kop-agenda'); if (!k) return null; const echt = { o: window.openAgendaLink, n: window.naarAgendaInRondes }; const log = [];
            window.openAgendaLink = () => log.push('outlook'); window.naarAgendaInRondes = () => log.push('rondes');
            try { k.click(); } finally { window.openAgendaLink = echt.o; window.naarAgendaInRondes = echt.n; } return log; }""")
        check("tik: alleen Outlook, niet naar Rondes", r, ['outlook'])
        hoog = await ev(pg, "() => document.querySelector('header').getBoundingClientRect().height")
        await ev(pg, "() => { const s = loadSavedRounds().filter(r => !isGeplandeRonde(r)); metVerwijderen(() => setRoundsAndMark(JSON.stringify(s))); _legeKopSleutel = null; toonLegeKop(); }")
        check("ook zonder geplande rondes", await ev(pg, "() => !!document.querySelector('#hdrHoleCount .kop-agenda')"), True)
        check("de kop blijft even hoog", await ev(pg, "() => document.querySelector('header').getBoundingClientRect().height") == hoog, True)

        check("geen paginafouten", pf, [])
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN): {', '.join(fouten)}" if fouten else "\nGEEN FOUTEN")
    sys.exit(1 if fouten else 0)

asyncio.run(main())
