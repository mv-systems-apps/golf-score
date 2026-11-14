"""Snel verder.

1. Starttijd: een tijd die de app zelf zette (of die je met het klokje op 'nu' zette)
   schuift mee met de klok; een tijd die je zelf invulde, of die van een herplande ronde,
   blijft staan. Ook bij het starten zelf.
2. Een ronde na vandaag zonder scores: de knop heet 'Sluiten' en werkt met één tik; ernaast
   de agendaknop (sinds 13528FA-004 een vierkante knop met het agenda-icoon), dezelfde export als Agenda in het exportvenster.
3. Het lege scorescherm: de koppen 'Eerste geplande ronde' en 'Gepauzeerde ronde' boven de knoppen, met de namen
   (elke speler op een eigen regel), de hole waar je verdergaat (de eerste zonder score, ook als er een hole is
   overgeslagen), de datum ('vandaag' of met jaartal) en de tijd, club en baan op een
   eigen regel, de ▶ rechts als de Laad-knop van de rondekaart, en de notitie; twee spelers op één moment worden in één tik gekoppeld, de speler bovenin Start
   is speler 1.
4. Vaststellen: de cursor staat meteen achter de waarde in Dagresultaat, ook na
   'tik om over te nemen', en Enter slaat op.
7. Op een speeldag (een geplande of gepauzeerde ronde van vandaag) opent de app op
   Score, ook via de snelkoppeling Score; anders op Start.
8. Een tik op de knop naast de ▶ gaat naar de ronde in Rondes: een geplande in de agenda,
   een gepauzeerde in de categorieën; de kaart komt in beeld en licht kort goud op, en de
   knoppenbalk volgt 'Actieknoppen altijd zichtbaar'. De ▶ zelf start.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

async def nieuw(b, tijd):
    pg = await b.new_page(viewport={'width': 390, 'height': 844}, device_scale_factor=2)
    pf = []
    pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
    await pg.clock.install(time=tijd)
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES])
    await pg.reload(); await pg.wait_for_timeout(600)
    return pg, pf

TIJD = "() => document.getElementById('iTime').value"

# Een gepauzeerde ronde (twee spelers, verschillende holes) en een geplande ronde
# (twee spelers, met notitie), afgeleid van een afgeronde testronde.
ZET = """([gepland, gepauzeerd]) => {
  const s = loadSavedRounds();
  const b = s.find(r => isRondeAf(r));
  const p1 = startPlayerName();
  const maak = (id, speler, [datum, tijd], scores, extra) => ({ ...b, ...extra, id, player: speler, date: datum, time: tijd,
      holes: b.holes.map((h, i) => ({ ...h, score: i < scores ? h.score : null })) });
  s.unshift(maak(990001, p1, gepauzeerd, 5, { currentHole: 5, note: undefined }));
  s.unshift(maak(990002, 'Medespeler met een heel erg lange naam', gepauzeerd, 3, { currentHole: 3, note: undefined }));
  s.unshift(maak(990003, 'Medespeler met een heel erg lange naam', gepland, 0, { note: 'Clubkampioenschap, eerste ronde, met de hele commissie erbij' }));
  s.unshift(maak(990004, p1, gepland, 0, { note: 'Clubkampioenschap, eerste ronde, met de hele commissie erbij' }));
  setRoundsAndMark(JSON.stringify(s));
  return { hole1: b.holes[5].id, hole2: b.holes[3].id };
}"""
KNOPPEN = """() => [...document.querySelectorAll('.lege-knop')].map(k => ({
  soort: k.dataset.soort,
  /* sinds Op deze baan (13528F8-001) kan de knop in een kaart .met-baan staan; de kop staat dan vóór die kaart */
  titel: (b => (b && b.classList.contains('lege-kop')) ? b.textContent : null)((k.parentElement.classList.contains('met-baan') ? k.parentElement : k).previousElementSibling),
  wanneer: k.querySelector('.lege-knop-wanneer').textContent,
  waar: (k.querySelector('.lege-knop-waar') || {}).textContent || '',
  pijlRechts: k.querySelector('svg').getBoundingClientRect().left > k.querySelector('.lege-knop-tekst').getBoundingClientRect().right - 1,
  namen: [...k.querySelectorAll('.lege-knop-speler')].map(x => { const n = x.querySelector('.lege-knop-naam'), h = x.querySelector('.lege-knop-hole');
      return ((n.dataset.vol || n.textContent) + (h ? h.textContent : '')).replace(/\\s+/g, ' ').trim(); }).join(' & '),
  ampersand: k.querySelector('.lege-knop-namen').textContent.includes('&'),
  eigenRegel: (() => { const t = [...k.querySelectorAll('.lege-knop-speler')].map(x => x.getBoundingClientRect().top); return t.every((y, i) => i === 0 || y > t[i - 1] + 5); })(),
  notitie: (k.querySelector('.lege-knop-notitie') || {}).textContent || '',
  past: (() => { const n = k.querySelector('.lege-knop-namen'); return n.scrollWidth <= n.clientWidth + 1; })(),
}))"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()

        print("\n=== 1. STARTTIJD SCHUIFT MEE ALS DE APP HEM ZETTE ===\n")
        pg, pf = await nieuw(b, '2026-11-03T08:05:00')
        await pg.evaluate("nav('setup')")
        check("om 08:05 staat de tijd op 08:05", await pg.evaluate(TIJD), '08:05')
        await pg.evaluate("nav('archive')")
        await pg.clock.set_system_time('2026-11-03T13:40:00')
        await pg.evaluate("nav('setup')")
        check("om 13:40 terug op Start: 13:40", await pg.evaluate(TIJD), '13:40')
        await pg.evaluate("() => { const t = document.getElementById('iTime'); t.value = '15:00'; onDateTimeChange(); nav('archive'); }")
        await pg.clock.set_system_time('2026-11-03T16:00:00')
        await pg.evaluate("nav('setup')")
        check("zelf 15:00 ingevuld: om 16:00 nog 15:00", await pg.evaluate(TIJD), '15:00')
        # het klokje zet 'nu': dat schuift weer mee
        await pg.click('button[onclick="setDateTimeNow(this)"]')
        check("klokje: 16:00", await pg.evaluate(TIJD), '16:00')
        await pg.evaluate("nav('archive')")
        await pg.clock.set_system_time('2026-11-03T16:30:00')
        await pg.evaluate("nav('setup')")
        check("na het klokje schuift de tijd weer mee: 16:30", await pg.evaluate(TIJD), '16:30')
        # het startscherm stond open sinds 16:30; de app komt om 17:10 weer in beeld
        await pg.clock.set_system_time('2026-11-03T17:10:00')
        check("zolang Start in beeld blijft: de tijd die er staat", await pg.evaluate(TIJD), '16:30')
        await pg.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")
        check("terug in de app met Start in beeld: 17:10", await pg.evaluate(TIJD), '17:10')
        check("de opslag verandert daar niet door (een scherm openen wist niets)", await pg.evaluate("localStorage.getItem('golf_setup_time')"), '16:00')
        await pg.click('#startRoundBtn'); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { const b = document.getElementById('confirmModalBtn'); if (b && !document.getElementById('confirmModal').classList.contains('hidden')) b.click(); }")
        await pg.wait_for_timeout(300)
        check("de ronde krijgt de tijd die in beeld staat: 17:10", await pg.evaluate("game.time"), '17:10')
        check("in de ronde staat het aantal holes weer op de gewone grootte", await pg.evaluate("document.getElementById('hdrHoleCount').style.fontSize"), '')
        await pg.click('#finishRoundBtn'); await pg.click('#finishRoundBtn'); await pg.wait_for_timeout(300)
        # herplannen: de tijd van de herplande ronde blijft staan
        await pg.evaluate("""() => { const s = loadSavedRounds(); const r = s.find(r => isRondeAf(r)); r.date = todayISO(); r.time = '09:00';
            setRoundsAndMark(JSON.stringify(s)); herplanRonde(r.id, true); }""")
        await pg.clock.set_system_time('2026-11-03T18:00:00')
        await pg.evaluate("nav('setup')")
        check("na herplannen blijft de tijd van de ronde staan", await pg.evaluate("[sel.time, localStorage.getItem('golf_setup_auto')]"), ['09:00', None])
        check("geen paginafouten", pf, [])
        await pg.close()

        print("\n=== 2. SLUITEN BIJ EEN RONDE NA VANDAAG ===\n")
        pg, pf = await nieuw(b, '2026-11-03T08:05:00')
        holes = await pg.evaluate(ZET, [['2026-11-07', '10:00'], ['2026-11-02', '15:10']])
        await pg.evaluate("nav('score')"); await pg.wait_for_timeout(300)
        k = await pg.evaluate(KNOPPEN)
        check("twee knoppen: eerst gepland, dan gepauzeerd", [x['soort'] for x in k], ['gepland', 'gepauzeerd'])
        check("de labels noemen alleen wat het is", [x['titel'] for x in k], ['Eerste geplande ronde', 'Gepauzeerde ronde'])
        check("na vandaag: de datum met jaartal en de tijd", [x['wanneer'] for x in k], ['Za 7-11-2026 · 10:00', 'Ma 2-11-2026 · 15:10'])
        waar = await pg.evaluate("() => { const r = loadSavedRounds().find(r => r.id === 990004); return [r.clubShort || r.club, r.track].filter(Boolean).join(' · '); }")
        check("club en baan op een eigen regel", [x['waar'] for x in k], [waar, waar])
        check("de ▶ staat rechts van de tekst", [x['pijlRechts'] for x in k], [True, True])
        stijl = await pg.evaluate("""() => { const kaart = document.createElement('div'); kaart.className = 'saved-item';
            kaart.innerHTML = '<div class="saved-name">d</div><div class="saved-meta">m</div><div class="kaart-notitie" style="font-size:15px;font-style:italic">n</div>';
            document.body.appendChild(kaart); const lt = e => e ? [getComputedStyle(e).fontSize, getComputedStyle(e).fontWeight] : null;
            const ref = [lt(kaart.children[0]), lt(kaart.children[1]), lt(kaart.children[1]), lt(kaart.children[2])]; const grijs = getComputedStyle(kaart.children[1]).color; kaart.remove();
            const knoppen = [...document.querySelectorAll('.lege-knop')].map(k => [lt(k.querySelector('.lege-knop-wanneer')), lt(k.querySelector('.lege-knop-naam')),
              lt(k.querySelector('.lege-knop-waar')), lt(k.querySelector('.lege-knop-notitie'))]);
            const namenGrijs = [...document.querySelectorAll('.lege-knop-naam')].every(n => getComputedStyle(n).color === grijs);
            return [ref, knoppen, namenGrijs]; }""")
        check("letters als op de rondekaart: datum, namen, club en notitie", stijl[1], [stijl[0], stijl[0][:3] + [None]])
        check("de namen grijs, als de spelers op de rondekaart", stijl[2], True)
        kop = await pg.evaluate("""() => { const t = document.createElement('div'); t.innerHTML = archiefInklapKop('x', 1, 'k', '_mockKop') + '</div>';
            document.body.appendChild(t); const st = e => { const c = getComputedStyle(e); return [c.fontSize, c.fontWeight, c.color, c.textTransform, c.letterSpacing, c.paddingTop, c.paddingBottom, c.marginBottom]; };
            const ref = JSON.stringify(st(t.firstElementChild)); t.remove();
            const zonderBoven = x => JSON.stringify(JSON.parse(x).filter((_, i) => i !== 5));
            return [...document.querySelectorAll('.lege-kop')].map(k => [zonderBoven(JSON.stringify(st(k))) === zonderBoven(ref), !k.closest('button')]); }""")
        check("de koppen buiten de knop, in de stijl van de groepkoppen in Rondes", kop, [[True, True], [True, True], [True, True]])
        # de rondes die klaarstaan bovenaan, daaronder 'Andere ronde' met de twee knoppen, zonder de uitleg
        opbouw = await pg.evaluate("""() => { const m = document.getElementById('scoreEmptyMsg');
            return [[...m.children].map(e => e.classList.contains('lege-kop') ? 'kop:' + e.textContent : (e.classList.contains('lege-knop') || e.classList.contains('met-baan')) ? 'kaart' : e.querySelector('button') ? 'knoppen' : 'anders'),
              m.textContent.includes('Maak een nieuwe ronde'), getComputedStyle(m.firstElementChild).paddingTop]; }""")
        check("de opbouw: kaarten bovenaan, dan Andere ronde met Nieuwe ronde en Rondes, zonder uitleg; de bovenste kop zonder ruimte erboven", opbouw,
              [['kop:Eerste geplande ronde', 'kaart', 'kop:Gepauzeerde ronde', 'kaart', 'kop:Andere ronde', 'knoppen'], False, '0px'])
        # (13528FA-001: de datumregel van de geplande ronde heeft ook de klasse met-agenda; die telt hier niet)
        volg = await pg.evaluate("() => [...document.querySelectorAll('.lege-knop-tekst')].map(t => [...t.children].map(c => c.className.replace(' met-agenda', '').replace('lege-knop-', '')))")
        # sinds 13528F8-002 een regel met geslacht, tee, holes en par na club en baan
        check("datum en tijd boven de spelers", volg, [['wanneer', 'namen', 'waar', 'tee', 'notitie'], ['wanneer', 'namen', 'waar', 'tee']])
        check("namen met &", ' & '.join(x.strip() for x in k[0]['namen'].split('&')), 'Testspeler & Medespeler met een heel erg lange naam')
        check("elke speler op een eigen regel, zonder '&'", [(x['eigenRegel'], x['ampersand']) for x in k], [(True, False), (True, False)])
        check("de namen lopen niet over", (k[0]['past'], k[1]['past']), (True, True))
        zelfde = await pg.evaluate("""() => { const z = document.createElement('button'); z.className = 'btn-secondary btn-main'; document.body.appendChild(z);
            const st = e => { const c = getComputedStyle(e); return [c.backgroundColor, c.color, c.borderColor, c.borderRadius]; };
            const u = [...document.querySelectorAll('.lege-knop-actie')].map(st); const v = st(z); z.remove(); return u.length === 2 && u.every(x => JSON.stringify(x) === JSON.stringify(v)); }""")
        check("de ▶ ziet eruit als Laad op de rondekaart (licht)", zelfde, True)
        await pg.evaluate("document.documentElement.classList.remove('light-mode')")
        zelfde = await pg.evaluate("""() => { const z = document.createElement('button'); z.className = 'btn-secondary btn-main'; document.body.appendChild(z);
            const st = e => { const c = getComputedStyle(e); return [c.backgroundColor, c.color, c.borderColor, c.borderRadius]; };
            const u = [...document.querySelectorAll('.lege-knop-actie')].map(st); const v = st(z); z.remove(); return u.length === 2 && u.every(x => JSON.stringify(x) === JSON.stringify(v)); }""")
        check("de ▶ ziet eruit als Laad op de rondekaart (donker)", zelfde, True)
        await pg.evaluate("document.documentElement.classList.add('light-mode')")
        check("de notitie staat erbij", k[0]['notitie'].startswith('Clubkampioenschap'), True)
        check("hervatten: per speler de hole, zonder het woord hole", ' & '.join(x.strip() for x in k[1]['namen'].split('&')),
              f"Testspeler · {holes['hole1']} & Medespeler met een heel erg lange naam · {holes['hole2']}")
        afk = await pg.evaluate("""() => [...[...document.querySelectorAll('.lege-knop')][1].querySelectorAll('.lege-knop-speler')].map(sp => {
            const n = sp.querySelector('.lege-knop-naam'), h = sp.querySelector('.lege-knop-hole');
            return { af: n.textContent.endsWith('…'), past: n.scrollWidth <= n.clientWidth + 1 }; })""")
        # De naam wordt zelf afgekapt, zodat hij past en de hole er direct achter staat (geen
        # gat). Met text-overflow alleen zou de tekst niet passen (scrollWidth > clientWidth).
        check("alleen de langste naam wordt afgekapt, en de tekst past", [(x['af'], x['past']) for x in afk], [(False, True), (True, True)])
        NAAM2 = "() => [...document.querySelectorAll('.lege-knop')][1].querySelectorAll('.lege-knop-naam')[1].textContent"
        smal = await pg.evaluate(NAAM2)
        await pg.set_viewport_size({'width': 430, 'height': 844}); await pg.wait_for_timeout(200)
        breder = await pg.evaluate(NAAM2)
        check("breder scherm: opnieuw afgekapt vanaf de hele naam, met meer tekst", len(breder) > len(smal) and 'Medespeler met een heel erg lange naam'.startswith(breder.rstrip('…')), True)
        await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(200)
        check("weer smaller: weer de korte versie", await pg.evaluate(NAAM2), smal)
        await pg.click('.lege-knop[data-soort="gepland"] .lege-knop-actie'); await pg.wait_for_timeout(500)
        s = await pg.evaluate("() => [game.date, game.player, game2Id, document.getElementById('finishRoundLabel').textContent, document.querySelector('.screen.active').id]")
        check("Toon: de scorekaart van de geplande ronde, gekoppeld, speler 1 bovenaan", s, ['2026-11-07', 'Testspeler', 990003, 'Sluiten', 'screen-score'])
        # De agendaknop naast Sluiten: dezelfde export als Agenda in het exportvenster
        await pg.evaluate("() => { window.__agenda = []; window.__echtIcs = exportRoundIcs; window.exportRoundIcs = id => window.__agenda.push(id); }")
        check("de agendaknop staat naast Sluiten", await pg.evaluate("!document.getElementById('agendaVanRondeBtn').classList.contains('hidden')"), True)
        await pg.click('#agendaVanRondeBtn'); await pg.wait_for_timeout(200)
        check("een tik exporteert deze ronde naar de agenda, en de ronde blijft open",
              await pg.evaluate("[window.__agenda, String(game.id), !!(game && game.started)]"), [[await pg.evaluate("String(game.id)")], await pg.evaluate("String(game.id)"), True])
        await pg.evaluate("() => { switchToPlayer(2); window.__agenda = []; }"); await pg.wait_for_timeout(200)
        await pg.click('#agendaVanRondeBtn'); await pg.wait_for_timeout(200)
        check("op de tab van speler 2: toch de ronde van speler 1 (geen tweede afspraak)", await pg.evaluate("window.__agenda"), ['990004'])
        await pg.evaluate("() => { switchToPlayer(1); window.exportRoundIcs = window.__echtIcs; }")
        await pg.click('#finishRoundBtn'); await pg.wait_for_timeout(400)
        check("Sluiten: één tik, daarna het lege scherm", await pg.evaluate("[!!(game && game.started), document.querySelectorAll('.lege-knop').length]"), [False, 2])
        check("de ronde staat nog gepland, zonder scores", await pg.evaluate("() => { const r = loadSavedRounds().find(r => r.id === 990004); return [!!r, gespeeldeHoles(r)]; }"), [True, 0])
        await pg.click('.lege-knop[data-soort="gepauzeerd"] .lege-knop-actie'); await pg.wait_for_timeout(500)
        check("Hervat: beide spelers, verder op de hole waar je was", await pg.evaluate("[game.date, game.time, game2Id, currentHole, document.getElementById('finishRoundLabel').textContent]"),
              ['2026-11-02', '15:10', 990002, 5, 'Pauzeren'])
        check("geen paginafouten", pf, [])
        await pg.close()

        print("\n=== 3. VANDAAG GEPLAND: START ===\n")
        pg, pf = await nieuw(b, '2026-11-03T08:05:00')
        await pg.evaluate(ZET, [['2026-11-03', '14:30'], ['2026-11-02', '15:10']])
        await pg.evaluate("nav('score')"); await pg.wait_for_timeout(300)
        k = await pg.evaluate(KNOPPEN)
        check("vandaag: dezelfde kop, en 'Vandaag' in de datumregel", (k[0]['titel'], k[0]['wanneer']), ('Eerste geplande ronde', 'Vandaag · 14:30'))
        await pg.click('.lege-knop[data-soort="gepland"] .lege-knop-actie'); await pg.wait_for_timeout(500)
        check("vandaag: gewoon Pauzeren, niet Sluiten", await pg.evaluate("document.getElementById('finishRoundLabel').textContent"), 'Pauzeren')
        check("vandaag: geen agendaknop", await pg.evaluate("document.getElementById('agendaVanRondeBtn').classList.contains('hidden')"), True)
        # één tik op Pauzeren zet de knoppen ernaast uit, maar niet de verborgen agendaknop
        await pg.click('#finishRoundBtn'); await pg.wait_for_timeout(100)
        check("na één tik op Pauzeren: de verborgen agendaknop niet vergrendeld", await pg.evaluate("document.getElementById('agendaVanRondeBtn').disabled"), False)
        await pg.wait_for_timeout(2300)
        await pg.close()
        pg, pf = await nieuw(b, '2026-11-03T08:05:00')
        await pg.evaluate("() => localStorage.setItem('golf_rounds', JSON.stringify(JSON.parse(localStorage.getItem('golf_rounds')).filter(r => r.holes.every(h => h.score != null))))")
        await pg.reload(); await pg.wait_for_timeout(500)
        await pg.evaluate("nav('score')"); await pg.wait_for_timeout(300)
        check("niets gepland of gepauzeerd: geen extra knoppen", await pg.evaluate("document.querySelectorAll('.lege-knop').length"), 0)
        check("niets gepland of gepauzeerd: de uitleg met de twee knoppen, zonder kop", await pg.evaluate("[document.getElementById('scoreEmptyMsg').textContent.includes('Maak een nieuwe ronde'), document.querySelectorAll('#scoreEmptyMsg .lege-kop').length, document.querySelectorAll('#scoreEmptyMsg button').length]"), [True, 0, 2])
        await pg.close()

        print("\n=== 4. VASTSTELLEN: FOCUS, CURSOR ACHTERAAN, ENTER ===\n")
        pg, pf = await nieuw(b, '2026-11-03T08:05:00')
        i = await pg.evaluate("() => { const s = loadSavedRounds(); const r = s.find(r => isRondeAf(r)); r.sdFinal = null; setRoundsAndMark(JSON.stringify(s)); return loadSavedRounds().findIndex(x => x.id === r.id); }")
        await pg.evaluate("(i) => openRoundResultModal(i)", i); await pg.wait_for_timeout(200)
        check("bij openen (leeg): focus in Dagresultaat", await pg.evaluate("() => { const e = document.activeElement; return [e.id, e.value]; }"), ['editSdInput', ''])
        await pg.evaluate("() => { document.getElementById('roundResultModal').classList.add('hidden'); const s = loadSavedRounds(); s.find(r => isRondeAf(r)).sdFinal = 24.5; setRoundsAndMark(JSON.stringify(s)); }")
        await pg.evaluate("(i) => openRoundResultModal(i)", i); await pg.wait_for_timeout(200)
        # een vastgesteld resultaat vraagt eerst 'Toch aanpassen?'
        await pg.evaluate("() => { const b = [...document.querySelectorAll('button')].find(b => b.offsetParent && b.textContent.trim() === 'Aanpassen'); b.click(); }")
        await pg.wait_for_timeout(300)
        check("na 'Toch aanpassen?': focus in Dagresultaat, cursor achter de waarde", await pg.evaluate("() => { const e = document.activeElement; return [e.id, e.value, e.selectionStart, e.selectionEnd]; }"), ['editSdInput', '24.5', 4, 4])
        await pg.click('#editSdCalc')
        c = await pg.evaluate("() => { const e = document.activeElement; return [e.id, e.selectionStart === e.value.length && e.selectionEnd === e.value.length && e.value.length > 0]; }")
        check("na overnemen: cursor achteraan", c, ['editSdInput', True])
        await pg.evaluate("() => { const e = document.getElementById('editSdInput'); e.value = '23.1'; e.dispatchEvent(new Event('input')); }")
        await pg.keyboard.press('Enter'); await pg.wait_for_timeout(300)
        check("Enter slaat op en sluit", await pg.evaluate("(i) => [document.getElementById('roundResultModal').classList.contains('hidden'), loadSavedRounds()[i].sdFinal]", i), [True, 23.1])
        check("geen paginafouten", pf, [])
        await pg.close()

        print("\n=== 5. RANDGEVALLEN VAN DE KNOPPEN ===\n")
        pg, pf = await nieuw(b, '2026-11-03T08:05:00')
        # een overgeslagen hole: gescoord op 1-3 en 6
        h = await pg.evaluate("""() => { const s = loadSavedRounds(); const b = s.find(r => isRondeAf(r)); const p1 = startPlayerName();
            s.unshift({ ...b, id: 990010, player: p1, date: '2026-11-02', time: '16:00', note: undefined, currentHole: 5,
                holes: b.holes.map((x, i) => ({ ...x, score: (i < 3 || i === 5) ? x.score : null })) });
            setRoundsAndMark(JSON.stringify(s)); nav('score'); return [String(b.holes[3].id), String(b.holes[5].id)]; }""")
        k = await pg.evaluate(KNOPPEN)
        check("overgeslagen hole: de knop noemt de eerste hole zonder score", k[-1]['namen'].endswith('· ' + h[0]), True)
        await pg.click('.lege-knop[data-soort="gepauzeerd"] .lege-knop-actie'); await pg.wait_for_timeout(500)
        check("en daar ga je ook verder", await pg.evaluate("currentHole"), 3)
        await pg.click('#finishRoundBtn'); await pg.click('#finishRoundBtn'); await pg.wait_for_timeout(300)
        # verouderde knop: de ronde wordt verwijderd terwijl de knop er nog staat
        await pg.evaluate("nav('score')"); await pg.wait_for_timeout(200)
        check("de knop toont de gepauzeerde ronde", await pg.evaluate("document.querySelector('.lege-knop[data-soort=gepauzeerd]').dataset.ids"), '990010')
        await pg.evaluate("() => performDeleteRound(loadSavedRounds().findIndex(r => r.id === 990010))")
        check("(de knop staat er nog)", await pg.evaluate("!!document.querySelector('.lege-knop[data-ids=\"990010\"]')"), True)
        await pg.click('.lege-knop[data-soort="gepauzeerd"] .lege-knop-actie'); await pg.wait_for_timeout(400)
        check("verouderde knop: geen andere ronde gestart, de knoppen zijn ververst",
              await pg.evaluate("[!!(game && game.started), [...document.querySelectorAll('.lege-knop')].some(k => k.dataset.ids === '990010')]"), [False, False])
        # twee rondes van dezelfde speler op één moment: niet koppelen
        await pg.evaluate("""() => { const s = loadSavedRounds(); const b = s.find(r => isRondeAf(r)); const p1 = startPlayerName();
            [990020, 990021].forEach(id => s.unshift({ ...b, id, player: id === 990020 ? p1 : p1.toUpperCase(), date: '2026-11-02', time: '17:00', note: undefined,
                holes: b.holes.map((x, i) => ({ ...x, score: i < 2 ? x.score : null })) }));
            setRoundsAndMark(JSON.stringify(s)); nav('score'); }""")
        k = await pg.evaluate(KNOPPEN)
        check("twee rondes van dezelfde speler op één moment: één naam, niet koppelen", '&' in k[-1]['namen'], False)
        # holenaam ontbreekt: het nummer
        await pg.evaluate("""() => { const s = loadSavedRounds(); s.filter(r => r.time === '17:00').forEach(r => r.holes.forEach(x => { x.id = null; })); setRoundsAndMark(JSON.stringify(s)); nav('score'); }""")
        k = await pg.evaluate(KNOPPEN)
        check("zonder holenaam: het holenummer, geen 'undefined'", ('undefined' in k[-1]['namen'], k[-1]['namen'].endswith('· 3')), (False, True))
        check("geen paginafouten", pf, [])
        await pg.close()

        print("\n=== 6. SLUITEN OVER MIDDERNACHT ===\n")
        pg, pf = await nieuw(b, '2026-11-06T23:59:00')
        await pg.evaluate(ZET, [['2026-11-07', '10:00'], ['2026-11-02', '15:10']])
        await pg.evaluate("nav('score')"); await pg.wait_for_timeout(200)
        await pg.click('.lege-knop[data-soort="gepland"] .lege-knop-actie'); await pg.wait_for_timeout(400)
        check("om 23:59: Sluiten", await pg.evaluate("document.getElementById('finishRoundLabel').textContent"), 'Sluiten')
        await pg.clock.set_system_time('2026-11-07T00:00:30')
        await pg.click('#finishRoundBtn'); await pg.wait_for_timeout(400)
        check("om 00:00 doet één tik nog steeds wat er staat", await pg.evaluate("!!(game && game.started)"), False)
        check("geen paginafouten", pf, [])
        await pg.close()

        print("\n=== 8. TIK NAAST DE ▶: NAAR DE RONDE IN RONDES ===\n")
        # De ▶ start (zie hierboven); de rest van de knop gaat naar de ronde in Rondes.
        STAND = """(id) => { const k = document.getElementById('round-full-' + id); const b = k ? k.getBoundingClientRect() : null;
            const a = k && k.querySelector('.saved-actions');
            return { scherm: document.querySelector('.screen.active').id, groep: archiefGroepering, kaart: !!k,
                     inBeeld: !!b && b.top >= 0 && b.bottom <= innerHeight, goud: !!k && k.classList.contains('round-flash'),
                     balk: !!a && (!a.classList.contains('actions-hidden') || a.classList.contains('actions-revealed')),
                     verborgen: !!a && a.classList.contains('actions-hidden') }; }"""
        for zichtbaar in ('on', 'off'):
            pg, pf = await nieuw(b, '2026-11-03T08:05:00')
            await pg.evaluate("(z) => localStorage.setItem('golf_actions_always_visible', z)", zichtbaar)
            await pg.evaluate(ZET, [['2026-11-07', '10:00'], ['2026-11-02', '15:10']])
            await pg.evaluate("nav('score')"); await pg.wait_for_timeout(300)
            await pg.click('.lege-knop[data-soort="gepland"] .lege-knop-wanneer'); await pg.wait_for_timeout(250)
            s = await pg.evaluate(STAND, 990004)
            check(f"[knoppen altijd {zichtbaar}] geplande ronde: Rondes, agenda, kaart in beeld en goud",
                  (s['scherm'], s['groep'], s['kaart'], s['inBeeld'], s['goud']), ('screen-archive', 'gepland', True, True, True))
            check(f"[knoppen altijd {zichtbaar}] er is niets gestart", await pg.evaluate("!!(game && game.started)"), False)
            await pg.evaluate("nav('score')"); await pg.wait_for_timeout(300)
            await pg.click('.lege-knop[data-soort="gepauzeerd"] .lege-knop-wanneer'); await pg.wait_for_timeout(250)
            s = await pg.evaluate(STAND, 990001)
            check(f"[knoppen altijd {zichtbaar}] gepauzeerde ronde: Rondes, categorieën, kaart in beeld en goud",
                  (s['scherm'], s['groep'], s['kaart'], s['inBeeld'], s['goud']), ('screen-archive', 'categorie', True, True, True))
            check(f"[knoppen altijd {zichtbaar}] de knoppenbalk volgt de instelling, en die blijft staan",
                  (s['balk'], await pg.evaluate("localStorage.getItem('golf_actions_always_visible')")), (zichtbaar == 'on', zichtbaar))
            check("geen paginafouten", pf, [])
            await pg.close()

        print("\n=== 7. OPENEN OP EEN SPEELDAG ===\n")
        # Een geplande ronde van vandaag of een gepauzeerde ronde: de app opent op Score
        # (ook de snelkoppeling Score). Een geplande ronde later, of niets: op Start.
        ACTIEF = "() => document.querySelector('.screen.active').id"
        async def open_met(gepland, gepauzeerd, adres='', zonderClub=False):
            pg, pf = await nieuw(b, '2026-11-03T08:05:00')
            await pg.evaluate("""([g, p]) => { const s = loadSavedRounds().filter(r => isRondeAf(r)); const b = s[0];
                const maak = (id, [d, t], n) => ({ ...b, id, player: startPlayerName(), date: d, time: t, holes: b.holes.map((h, i) => ({ ...h, score: i < n ? h.score : null })) });
                if (g) s.unshift(maak(990101, g, 0)); if (p) s.unshift(maak(990102, p, 4));
                localStorage.setItem('golf_rounds', JSON.stringify(s)); }""", [gepland, gepauzeerd])
            # zonder clubs: dan is er ook geen standaardclub (de app kiest er anders zelf een)
            if zonderClub: await pg.evaluate("() => { localStorage.removeItem('golf_default_club'); localStorage.setItem('golf_clubs', '{}'); }")
            if adres: await pg.goto(app_url() + adres)
            else: await pg.reload()
            await pg.wait_for_timeout(600)
            uit = [await pg.evaluate(ACTIEF), await pg.evaluate("document.querySelectorAll('.lege-knop').length")]
            await pg.close()
            return uit
        check("geplande ronde vandaag: opent op Score, met de knop", await open_met(['2026-11-03', '14:30'], None), ['screen-score', 1])
        check("gepauzeerde ronde van vandaag: opent op Score", (await open_met(None, ['2026-11-03', '07:00']))[0], 'screen-score')
        check("gepauzeerde ronde van eerder: opent op Start", (await open_met(None, ['2026-11-01', '10:00']))[0], 'screen-setup')
        check("geplande ronde pas zaterdag: opent op Start", (await open_met(['2026-11-07', '10:00'], None))[0], 'screen-setup')
        check("niets te spelen: opent op Start", (await open_met(None, None))[0], 'screen-setup')
        check("snelkoppeling Score op een speeldag: Score", (await open_met(['2026-11-03', '14:30'], None, '?snel=score'))[0], 'screen-score')
        check("snelkoppeling Score zonder iets te spelen: Start", (await open_met(None, None, '?snel=score'))[0], 'screen-setup')
        check("zonder clubs (en dus standaardclub) op een speeldag: toch Score", (await open_met(['2026-11-03', '14:30'], None, zonderClub=True))[0], 'screen-score')
        # Staat de rem aan (onleesbare rondes) of komt een actieve ronde niet terug, dan niet naar Score
        pg, pf = await nieuw(b, '2026-11-03T08:05:00')
        check("met de rem aan of een achtergebleven actieve ronde: geen speeldag",
              await pg.evaluate("""() => { const s = loadSavedRounds().filter(r => isRondeAf(r)); const b = s[0];
                  s.unshift({ ...b, id: 990103, player: startPlayerName(), date: todayISO(), time: '07:00', holes: b.holes.map((h, i) => ({ ...h, score: i < 3 ? h.score : null })) });
                  localStorage.setItem('golf_rounds', JSON.stringify(s)); leesRondes(); const gewoon = isSpeeldag();
                  rondesOnleesbaar = true; const rem = isSpeeldag(); rondesOnleesbaar = false;
                  localStorage.setItem('golf_active_id', '990103'); const actief = isSpeeldag(); localStorage.removeItem('golf_active_id');
                  return [gewoon, rem, actief]; }"""), [True, False, False])
        await pg.close()
        check("zonder clubs en niets te spelen: Club", (await open_met(None, None, zonderClub=True))[0], 'screen-club')

        await b.close()
    print(f"\n{'GEEN FOUTEN' if not fouten else str(len(fouten)) + ' FOUT(EN): ' + ', '.join(fouten)}")
    sys.exit(1 if fouten else 0)

asyncio.run(main())
