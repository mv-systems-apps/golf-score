"""Kan de browser niets bewaren, dan hoor je dat vóór je gaat spelen.

Soms is blijvende opslag er niet: een privévenster op een oudere iPhone, of opslag die in
de browserinstellingen is geblokkeerd. De app draait dan in het geheugen; alles is weg
zodra je hem sluit. Twee varianten: schrijven wordt geweigerd, en de opslag is helemaal
niet toegankelijk. Gecontroleerd: de app start, je krijgt bij het opstarten een melding,
en vóór het starten van een ronde nog een keer. De controle met gewone opslag blijft stil.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

VARIANTEN = [
    ('schrijven wordt geweigerd', "Storage.prototype.setItem = function () { throw new DOMException('quota', 'QuotaExceededError'); };"),
    ('opslag niet toegankelijk',  "Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('geblokkeerd', 'SecurityError'); } });"),
]
VENSTER = """() => { const m = document.getElementById('confirmModal'); return m.classList.contains('hidden') ? '' : (document.getElementById('confirmModalTitle').textContent + ' | ' + document.getElementById('confirmModalMessage').textContent); }"""
SLUIT = "() => document.getElementById('confirmModal').classList.add('hidden')"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for naam, script in VARIANTEN + [('CONTROLE: gewone opslag', '')]:
            controle = naam.startswith('CONTROLE')
            print(f"\n=== {naam.upper()} ===\n")
            ctx = await b.new_context(viewport={"width": 390, "height": 844}); pg = await ctx.new_page()
            pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:90]))
            if script: await pg.add_init_script(script)
            await pg.goto(app_url()); await pg.wait_for_timeout(900)
            leeft = await pg.evaluate("typeof nav === 'function' && typeof kopieerVersie === 'function'")
            check("de app start", (leeft, pf), (True, []))
            if not leeft: await ctx.close(); continue
            check("de app weet of de opslag blijvend is", await pg.evaluate("storageIsPersistent"), controle)
            v = await pg.evaluate(VENSTER)
            if controle: check("geen melding over opslag", 'bewaard' in v or 'opslag' in v.lower(), False)
            else: check("melding bij het opstarten dat niets bewaard blijft", ('niet bewaard' in v or 'niets bewaren' in v), True)
            await pg.evaluate("() => document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))")
            for t in ['archive', 'stat', 'club', 'settings', 'setup']:
                await pg.click(f'#tab-{t}'); await pg.wait_for_timeout(250)
            check("alle tabbladen openen zonder fout", (pf, await pg.evaluate("document.querySelectorAll('#foutMelding').length")), ([], 0))
            await pg.evaluate(SLUIT)
            # Clubs klaarzetten via de app zelf: de opslag van de browser is hier niet te vullen.
            await pg.evaluate("(c) => { Object.assign(CLUBS, c); saveClubsToStorage(); storage.setItem('golf_default_club', 'Golfclub Heelsum'); rebuildCourseLookup(false); rebuildAll(); nav('setup'); }", CLUBS)
            await pg.wait_for_timeout(300)
            await pg.fill('#iName', 'Testspeler'); await pg.fill('#iHcp', '30.7'); await pg.keyboard.press('Tab'); await pg.wait_for_timeout(200)
            await pg.evaluate("() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); startRound(); }"); await pg.wait_for_timeout(400)
            v = await pg.evaluate(VENSTER)
            if controle:
                check("een ronde starten vraagt niets over opslag, en de ronde loopt", ('bewaard' in v, await pg.evaluate("game.started")), (False, True))
                await pg.click('#tab-score'); await pg.wait_for_timeout(250)
                check("geen rode regel op de scorekaart", await pg.evaluate("document.getElementById('nietBewaardRegel').offsetParent === null"), True)
            else:
                check("vóór het starten van een ronde: waarschuwing met de keuze om toch te spelen", ('niet bewaard' in v, await pg.evaluate("game.started")), (True, False))
                await pg.evaluate("document.getElementById('confirmModalBtn').click()"); await pg.wait_for_timeout(400)
                check("na 'Toch starten' loopt de ronde", await pg.evaluate("game.started"), True)
                await pg.click('#tab-score'); await pg.wait_for_timeout(250)
                check("op de scorekaart staat een rode regel 'Niet bewaard'", await pg.evaluate("(() => { const e = document.getElementById('nietBewaardRegel'); return e.offsetParent !== null && e.textContent.startsWith('Niet bewaard'); })()"), True)
            await ctx.close()
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN)" if fouten else "\nGEEN FOUTEN"); sys.exit(1 if fouten else 0)
asyncio.run(main())
