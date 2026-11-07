"""De keuring bij het laden vangt ook velden van het verkeerde soort.

Aanvulling op test-misvormde-opslag.py, uit de onafhankelijke review: een ronde met een
tekstveld dat geen tekst is (de speler als getal) liet het opstarten en Rondes vastlopen,
en een hole zonder slagverdeling gaf 'Stb NaN' op de rondekaart. Uitgangspunt zijn Testspelers
eigen rondes met telkens één afwijkende ronde erbij. Per geval: geen fout bij opstarten of
op de zes tabbladen, nergens 'NaN' of 'undefined' in beeld, en de goede rondes zichtbaar.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import app_url

R = json.load(open(os.path.join(HIER, 'echte-rondes.json'), encoding='utf-8'))
C = {c['club']: c for c in json.load(open(os.path.join(HIER, 'echte-clubs.json'), encoding='utf-8'))}
SPELER = R[0]['player']
for k, r in enumerate(R): r['id'] = 700000 + k
WEG = object()
def met(veld, waarde, hole=False):
    r = json.loads(json.dumps(R[0])); r['id'] = 999001
    doel = r['holes'][2] if hole else r
    if waarde is WEG: doel.pop(veld, None)
    else: doel[veld] = waarde
    return R + [r]
GEVALLEN = [
    ('CONTROLE: eigen rondes', R),
    ('speler als getal', met('player', 5)),
    ('speler als object', met('player', {'naam': 'Testspeler'})),
    ('tijd als getal', met('time', 930)),
    ('baan als getal', met('track', 7)),
    ('tee als getal', met('tee', 5)),
    ('club als getal', met('club', 5)),
    ('notitie als getal', met('note', 5)),
    ('hole met slagverdeling leeg', met('phcp', None, hole=True)),
    ('hole zonder slagverdeling', met('phcp', WEG, hole=True)),
    ('hole met slagverdeling als tekst', met('phcp', 'twee', hole=True)),
    ('hole met par leeg', met('par', None, hole=True)),
    ('hole zonder par', met('par', WEG, hole=True)),
    ('score als tekst', met('score', 'vijf', hole=True)),
]
TABS = ['setup', 'archive', 'stat', 'club', 'settings', 'score']

async def main():
    fouten = 0
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for naam, rondes in GEVALLEN:
            pg = await b.new_page(viewport={"width": 390, "height": 844}); pf = []
            pg.on('pageerror', lambda e: pf.append(str(e).split('\n')[0][:90]))
            await pg.goto(app_url())
            await pg.evaluate("""([r, c, s]) => { localStorage.clear(); localStorage.setItem('golf_rounds', JSON.stringify(r)); localStorage.setItem('golf_clubs', JSON.stringify(c));
              localStorage.setItem('golf_player_name', s); localStorage.setItem('golf_profile_name', s); localStorage.setItem('golf_default_club', Object.keys(c)[0]); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }""", [rondes, C, SPELER])
            await pg.reload(); await pg.wait_for_timeout(700)
            await pg.evaluate("() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); }")
            vreemd = set()
            for t in TABS:
                try: await pg.evaluate(f"nav('{t}')")
                except Exception as e: pf.append(str(e).split('\n')[0][:90])
                await pg.wait_for_timeout(250)
                tekst = await pg.evaluate("document.querySelector('.screen.active') ? document.querySelector('.screen.active').innerText : document.body.innerText")
                for w in ('NaN', 'undefined', '[object Object]'):
                    if w in tekst: vreemd.add(f'{t}: {w}')
            gevangen = await pg.evaluate("document.querySelectorAll('#foutMelding').length")
            zichtbaar = await pg.evaluate("leesRondes().filter(r => r.id >= 700000 && r.id < 800000).length")
            ok = not pf and not gevangen and not vreemd and zichtbaar == len(R)
            if not ok: fouten += 1
            print(f"{'ok  ' if ok else 'FOUT'} {naam}")
            for f in pf[:2]: print('       fout:', f)
            if gevangen: print('       de foutvanger meldt een storing')
            for v in sorted(vreemd)[:3]: print('       in beeld:', v)
            if zichtbaar != len(R): print(f'       goede rondes zichtbaar: {zichtbaar} van {len(R)}')
            await pg.close()
        # Via import: een ronde met een hole zonder slagverdeling hoort te worden geweigerd.
        import tempfile
        pg = await b.new_page(viewport={"width": 390, "height": 844})
        await pg.goto(app_url())
        await pg.evaluate("([c, s]) => { localStorage.clear(); localStorage.setItem('golf_rounds', '[]'); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_profile_name', s); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }", [C, SPELER])
        await pg.reload(); await pg.wait_for_timeout(600); await pg.evaluate("() => document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))")
        r = json.loads(json.dumps(R[0])); r.pop('id'); r['holes'][2].pop('phcp')
        pad = os.path.join(tempfile.mkdtemp(), 'ronde.json'); open(pad, 'w', encoding='utf-8').write(json.dumps(r))
        await pg.locator('#importRoundFile').set_input_files(pad); await pg.wait_for_timeout(500)
        v = await pg.evaluate("document.getElementById('confirmModalTitle').textContent + ' | ' + document.getElementById('confirmModalMessage').textContent")
        ok = 'mislukt' in v.lower() and 'slag' in v.lower() and await pg.evaluate("JSON.parse(localStorage.getItem('golf_rounds')).length") == 0
        print(f"{'ok  ' if ok else 'FOUT'} import van een ronde met een hole zonder slagverdeling wordt geweigerd")
        if not ok: fouten += 1; print('       melding:', v[:120])
        # Ontbreekt de slagverdeling bij álle holes, dan wordt ze afgeleid uit baanhandicap en SI.
        await pg.evaluate("() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); localStorage.setItem('golf_rounds', '[]'); }")
        r = json.loads(json.dumps(R[0])); r.pop('id'); verwacht = [h['phcp'] for h in r['holes']]
        for h in r['holes']: h.pop('phcp')
        pad = os.path.join(tempfile.mkdtemp(), 'ronde.json'); open(pad, 'w', encoding='utf-8').write(json.dumps(r))
        await pg.locator('#importRoundFile').set_input_files(pad); await pg.wait_for_timeout(500)
        kreeg = await pg.evaluate("(JSON.parse(localStorage.getItem('golf_rounds'))[0] || { holes: [] }).holes.map(h => h.phcp)")
        ok = kreeg == verwacht
        print(f"{'ok  ' if ok else 'FOUT'} zonder slagverdeling bij alle holes: afgeleid uit baanhandicap en SI, gelijk aan het origineel")
        if not ok: fouten += 1; print('      ', kreeg, verwacht)
        await b.close()
    print(f'\n{fouten} FOUT(EN)' if fouten else '\nGEEN FOUTEN'); sys.exit(1 if fouten else 0)
asyncio.run(main())
