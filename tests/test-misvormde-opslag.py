"""Leesbare maar misvormde opslag: de app moet altijd opstarten.

test-corrupt.py dekt opslag die niet te ontleden is. Hier is de tekst geldige JSON, maar
klopt de inhoud niet: een club zonder gegevens, een ronde zonder holes, een getal waar een
ronde hoort. Uitgangspunt zijn de eigen rondes en clubs, met telkens één misvormd
element erbij. Per geval wordt gemeten:
  - draait het hele script (de app is niet 'dood');
  - geven de zes tabbladen een fout;
  - blijft de opslag onaangeroerd (er wordt niets weggegooid of overschreven);
  - blijven de goede rondes zichtbaar;
  - krijgt de gebruiker een melding, en weigert de app daarna te schrijven;
  - (met echte tikken) het beschadigde element weghalen herstelt alles, zonder dat een
    lopende, geplande of ingelezen ronde verloren gaat.
Drie gevallen zijn onschuldig (ronde zonder spelernaam, baan als getal, baan zonder tees):
die lopen nergens op vast en hoeven dus geen melding te geven.
"""
import asyncio, json, os, sys, tempfile
from playwright.async_api import async_playwright
from testdata import app_url

HIER = os.path.dirname(os.path.abspath(__file__))
RONDES = json.load(open(os.path.join(HIER, 'echte-rondes.json'), encoding='utf-8'))
CLUBS = {c['club']: c for c in json.load(open(os.path.join(HIER, 'echte-clubs.json'), encoding='utf-8'))}
SPELER = RONDES[0].get('player') or 'Testspeler'
kopie = lambda x: json.loads(json.dumps(x))

def rondes_met(extra, voorop=True):
    return ([extra] + kopie(RONDES)) if voorop else (kopie(RONDES) + [extra])
def ronde_zonder(veld):
    r = kopie(RONDES[0]); r['id'] = 999001; del r[veld]; return r
def ronde_met(veld, waarde):
    r = kopie(RONDES[0]); r['id'] = 999002; r[veld] = waarde; return r
def clubs_met(naam, waarde):
    c = kopie(CLUBS); c[naam] = waarde; return c
def club_kapot(pad, waarde):
    c = kopie(CLUBS); naam = list(c)[0]; doel = c[naam]
    if pad == 'baan': doel['courses'][list(doel['courses'])[0]] = waarde
    elif pad == 'tees': doel['courses'][list(doel['courses'])[0]]['tees'] = waarde
    else: doel[pad] = waarde
    return c

GEVALLEN = [
    ('CONTROLE: goede gegevens',         RONDES, CLUBS),
    ('ronde is null',                    rondes_met(None), CLUBS),
    ('ronde is een getal',               rondes_met(42), CLUBS),
    ('ronde is een tekst',               rondes_met('ronde'), CLUBS),
    ('ronde is een lege lijst',          rondes_met([]), CLUBS),
    ('ronde is een leeg object',         rondes_met({}), CLUBS),
    ('ronde zonder holes',               rondes_met(ronde_zonder('holes')), CLUBS),
    ('ronde met holes als tekst',        rondes_met(ronde_met('holes', 'negen')), CLUBS),
    ('ronde met een hole die null is',   rondes_met(ronde_met('holes', [None] * 9)), CLUBS),
    ('ronde zonder datum',               rondes_met(ronde_zonder('date')), CLUBS),
    ('ronde met datum als getal',        rondes_met(ronde_met('date', 20260101)), CLUBS),
    ('ronde zonder spelernaam (onschuldig)',          rondes_met(ronde_zonder('player')), CLUBS),
    ('ronde met baan als getal (onschuldig)',         rondes_met(ronde_met('course', 7)), CLUBS),
    ('misvormde ronde achteraan',        rondes_met(None, voorop=False), CLUBS),
    ('club is null',                     RONDES, clubs_met('X', None)),
    ('club is een getal',                RONDES, clubs_met('X', 5)),
    ('club is een tekst',                RONDES, clubs_met('X', 'club')),
    ('club is een leeg object',          RONDES, clubs_met('X', {})),
    ('clubs is een lijst',               RONDES, list(CLUBS.values())),
    ('clubs is een getal',               RONDES, 7),
    ('club met courses als tekst',       RONDES, club_kapot('courses', 'banen')),
    ('club met courses null',            RONDES, club_kapot('courses', None)),
    ('baan is null',                     RONDES, club_kapot('baan', None)),
    ('baan zonder tees (onschuldig)',                 RONDES, club_kapot('baan', {'holeIds': [1, 2, 3, 4, 5, 6, 7, 8, 9]})),
    ('tees is een tekst',                RONDES, club_kapot('tees', 'geel')),
    ('club zonder naam',                 RONDES, club_kapot('club', None)),
]
TABS = ['setup', 'archive', 'stat', 'club', 'settings', 'score']

async def main():
    fouten = 0
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for naam, rondes, clubs in GEVALLEN:
            page = await b.new_page(); pf = []
            page.on('pageerror', lambda e: pf.append(str(e).split('\n')[0][:90]))
            await page.goto(app_url())
            ruwR, ruwC = json.dumps(rondes, separators=(',', ':'), ensure_ascii=False), json.dumps(clubs, separators=(',', ':'), ensure_ascii=False)
            await page.evaluate("""([r, c, s]) => { localStorage.clear(); localStorage.setItem('golf_rounds', r);
                localStorage.setItem('golf_clubs', c); localStorage.setItem('golf_player_name', s); }""", [ruwR, ruwC, SPELER])
            pf.clear()
            await page.reload(); await page.wait_for_timeout(700)
            bij_start = list(pf)
            # het laatste stuk van het script bestaat alleen als alles ervoor is uitgevoerd
            leeft = await page.evaluate("typeof nav === 'function' && typeof kopieerVersie === 'function' && typeof storage !== 'undefined'")
            melding = await page.evaluate("""() => [document.getElementById('confirmModal'), document.getElementById('keuzeModal')].filter(m => !m.classList.contains('hidden')).map(m => m.textContent.replace(/\\s+/g, ' ').trim().slice(0, 70))""")
            await page.evaluate("document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))")
            tabfout = []
            for t in TABS:
                pf.clear()
                try: await page.evaluate(f"nav('{t}')")
                except Exception as e: pf.append(str(e).split('\n')[0][:90])
                await page.wait_for_timeout(250)
                if pf: tabfout.append(f'{t}: {pf[0]}')
            kaarten = await page.evaluate("typeof leesRondes === 'function' ? (() => { try { nav('archive'); return document.querySelectorAll('#savedList .round-card, #savedList [data-round-id], #savedList .saved-card').length; } catch (e) { return -1; } })() : -1")
            # inhoud vergelijken, niet de tekst: de app mag de opslag in eigen opmaak terugschrijven
            nu = await page.evaluate("() => [localStorage.getItem('golf_rounds'), localStorage.getItem('golf_clubs')]")
            def zelfde(a, b):
                try: return json.loads(a) == json.loads(b)
                except Exception: return a == b
            ongewijzigd = zelfde(nu[0], ruwR) and zelfde(nu[1], ruwC)
            controle = naam.startswith('CONTROLE') or 'onschuldig' in naam
            soort = 'clubs' if rondes is RONDES else 'rondes'
            try: stand = await page.evaluate("""() => ({ n: leesRondes().length, clubs: Object.keys(CLUBS).length,
                rem: rondesOnleesbaar, remC: clubsOnleesbaar,
                schrijf: setRoundsAndMark(JSON.stringify(loadSavedRounds())), schrijfC: saveClubsToStorage() })""") if leeft else {}
            except Exception: stand = {}; leeft = False
            goedeR = stand.get('n') == len(RONDES) + (1 if 'onschuldig' in naam and soort == 'rondes' else 0)
            remgoed = controle or (stand.get('schrijf') is False if soort == 'rondes' else stand.get('schrijfC') is False)
            goed = leeft and not bij_start and not tabfout and ongewijzigd and (bool(melding) != controle) and (goedeR or soort == 'clubs') and remgoed
            if not goed: fouten += 1
            print(f"{'ok  ' if goed else 'FOUT'} {naam}")
            if not leeft: print('       app start niet: het script is niet afgemaakt')
            for f in bij_start[:2]: print('       fout bij opstarten:', f)
            for f in tabfout[:3]: print('       fout op tabblad', f)
            if not ongewijzigd: print('       de opslag is gewijzigd:', 'rondes' if not zelfde(nu[0], ruwR) else '', 'clubs' if not zelfde(nu[1], ruwC) else '')
            if not melding and not controle: print('       geen melding aan de gebruiker')
            if leeft and soort == 'rondes' and not goedeR: print('       goede rondes niet allemaal zichtbaar:', stand.get('n'), 'van', len(RONDES))
            if leeft and not remgoed: print('       de app schrijft nog over de beschadigde opslag heen')
            if melding and controle: print('       onverwachte melding:', melding[0])
            await page.close()
        # Herstel met echte tikken. Naast afgeronde rondes ook een lopende, een geplande en
        # een ingelezen ronde: die zitten niet in een backup, dus 'backup maken en terugzetten'
        # zou ze wegvagen. Het herstel haalt alleen het beschadigde element weg.
        page = await b.new_page(accept_downloads=True)
        await page.goto(app_url())
        lopend = kopie(RONDES[0]); lopend['id'] = 888001; lopend['date'] = '2026-10-01'
        for h in lopend['holes'][4:]: h['score'] = None; h.pop('putts', None)
        gepland = kopie(RONDES[0]); gepland['id'] = 888002; gepland['date'] = '2027-04-01'; gepland.pop('sdFinal', None)
        for h in gepland['holes']: h['score'] = None; h.pop('putts', None)
        ingelezen = kopie(RONDES[1]); ingelezen['id'] = 888003; ingelezen['_justImported'] = True
        goed = kopie(RONDES) + [lopend, gepland, ingelezen]
        for k, r in enumerate(goed[:len(RONDES)]): r['id'] = 700000 + k          # een backup heeft geen id's; in de opslag wel
        ruw = json.dumps([None] + goed)
        await page.evaluate("""([r, c, s]) => { localStorage.clear(); localStorage.setItem('golf_rounds', r);
            localStorage.setItem('golf_clubs', c); localStorage.setItem('golf_player_name', s); localStorage.setItem('golf_active_id', '888001'); }""",
            [ruw, json.dumps(CLUBS), SPELER])
        await page.reload(); await page.wait_for_timeout(900)
        vraag = await page.evaluate("document.getElementById('keuzeModal').classList.contains('hidden') ? '' : document.getElementById('keuzeModalTekst').textContent")
        tikbaar = await page.locator('#keuzeModal button:visible', has_text='Bewaar').count()
        if tikbaar:
            async with page.expect_download() as d: await page.locator('#keuzeModal button:visible', has_text='Bewaar').first.click()
            bewaard = open(await (await d.value).path(), encoding='utf-8').read()
            await page.wait_for_timeout(600)
        else: bewaard = None
        na = await page.evaluate("""() => ({ ids: JSON.parse(localStorage.getItem('golf_rounds')).map(r => r && r.id), rem: (loadSavedRounds(), rondesOnleesbaar),
            actief: localStorage.getItem('golf_active_id'), loopt: !!(game && game.started && String(game.id) === '888001') })""")
        for wat, ok in [('melding noemt het aantal en biedt weghalen aan, zonder backup terug te zetten', '1 van je opgeslagen rondes' in vraag and tikbaar == 1 and 'terug' not in vraag.lower()),
                        ('de beschadigde gegevens zijn eerst als bestand bewaard, ongewijzigd', bewaard == ruw),
                        (f'daarna staan alle {len(goed)} goede rondes er nog, ook lopend, gepland en ingelezen', sorted(map(str, na['ids'])) == sorted(str(r['id']) for r in goed)),
                        ('de rem is eraf, en de lopende ronde loopt gewoon door', (na['rem'], na['actief'], na['loopt']) == (False, '888001', True))]:
            print(f"{'ok  ' if ok else 'FOUT'} herstel: {wat}")
            if not ok: fouten += 1
        # Hetzelfde voor clubs: alleen de beschadigde club gaat weg.
        page = await b.new_page()
        await page.goto(app_url())
        await page.evaluate("""([r, c, s]) => { localStorage.clear(); localStorage.setItem('golf_rounds', r);
            localStorage.setItem('golf_clubs', c); localStorage.setItem('golf_player_name', s); }""",
            [json.dumps(RONDES), json.dumps(clubs_met('X', None)), SPELER])
        await page.reload(); await page.wait_for_timeout(900)
        await page.locator('#keuzeModal button:visible', has_text='Weghalen').first.click(); await page.wait_for_timeout(500)
        na = await page.evaluate("() => ({ clubs: Object.keys(JSON.parse(localStorage.getItem('golf_clubs'))).sort(), rem: clubsOnleesbaar })")
        ok = na == {'clubs': sorted(CLUBS), 'rem': False}
        print(f"{'ok  ' if ok else 'FOUT'} herstel clubs: alleen de beschadigde club is weg, de rem is eraf")
        if not ok: fouten += 1; print('      ', na)
        await b.close()
    print(f'\n{fouten} FOUT(EN)' if fouten else '\nGEEN FOUTEN')
    sys.exit(1 if fouten else 0)

asyncio.run(main())
