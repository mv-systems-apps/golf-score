"""Het scorescherm past zonder scrollen, en Gereed blijft in beeld.

1. Een ronde van 18 holes (met de negentabbladen) op een scherm dat net zo hoog is als
   een telefoon (de hoogte waarbij het oude scherm 9 px scrolde): de pagina scrolt niet,
   en de knop Pauzeren staat boven de tabbalk.
2. Alle holes ingevuld, één tik op Gereed: de knop wordt oranje en zegt zelf 'Tik nogmaals
   om te bevestigen' (geen regel erboven), dus er verschuift niets en hij blijft boven de
   tabbalk. Na twee seconden staat er weer Gereed; de tweede tik rondt af.
   Boven de scores (zonder negentabbladen) en tussen de laatste rij en de knop 8 px, iets
   meer dan tussen de rijen (5 px), zodat de knop niet als een rij leest.
3. De knop steekt af tegen de scorerijen: een gouden rand, met de tekst in de gewone
   tekstkleur (goud op licht is te weinig contrast).
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import app_url
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
CLUBS = {c['club']: c for c in json.load(open(os.path.join(HIER, 'echte-clubs.json')))}
R = json.load(open(os.path.join(HIER, 'echte-rondes.json')))
for i, x in enumerate(R):
    if not x.get('id'): x['id'] = 1700000000000 + i
LOS = next(x for x in R if len(x['holes']) == 18)
RONDE = dict(LOS, id=999, date='2026-11-04', time='12:04', player='Testspeler',
             holes=[{k: v for k, v in h.items() if k != 'putts'} | {'score': None} for h in LOS['holes']])
RONDES = [x for x in R if all(h.get('score') is not None for h in x['holes'])] + [RONDE]
HOOGTE = 750   # headless (Inter): het oude scherm liep hier 9 px door, net als op de telefoon

fouten = []
def check(naam, kreeg, verwacht):
    if kreeg == verwacht: print(f"  ok   {naam}: {kreeg!r}")
    else: print(f"  FOUT {naam}: {kreeg!r} — verwacht {verwacht!r}"); fouten.append(naam)

MAAT = """() => { const k = document.getElementById('finishRoundBtn').getBoundingClientRect(), t = document.querySelector('.tabs').getBoundingClientRect();
  return { scroll: document.scrollingElement.scrollHeight - innerHeight, ruimte: Math.round(t.top - k.bottom), scrollY: Math.round(scrollY) }; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': HOOGTE})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.clock.install(time='2026-11-04T11:43:00')
        await pg.goto(app_url())
        await pg.evaluate("""([c, r]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
            localStorage.setItem('golf_profile_name', 'Testspeler'); localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_active_id', '999'); }""", [CLUBS, RONDES])
        await pg.reload(); await pg.wait_for_timeout(800)

        print("\n=== 1. 18 HOLES PAST ZONDER SCROLLEN ===\n")
        check("een ronde van 18 holes op het scorescherm", await pg.evaluate("[game.holes.length, document.querySelector('.screen.active').id, !document.getElementById('nineTabBar').classList.contains('hidden')]"), [18, 'screen-score', True])
        m = await pg.evaluate(MAAT)
        check("de pagina scrolt niet", m['scroll'] <= 0, True)
        check("Pauzeren staat boven de tabbalk", m['ruimte'] >= 4, True)
        ruimte = await pg.evaluate("""() => { const r = [...document.querySelectorAll('#sumRows .sum-tr')].map(e => e.getBoundingClientRect());
            return [Math.round(r[1].top - r[0].bottom), Math.round(document.getElementById('finishRoundBtn').getBoundingClientRect().top - r[r.length - 1].bottom)]; }""")
        check("tussen de rijen 5 px, tussen de laatste rij en de knop 8 px", ruimte, [5, 8])
        await pg.evaluate("() => { document.getElementById('nineTabBar').classList.add('hidden'); }")
        check("zonder negentabbladen 8 px boven de scores, gelijk aan de ruimte onder", await pg.evaluate("getComputedStyle(document.getElementById('screen-score')).paddingTop"), '8px')
        await pg.evaluate("() => { document.getElementById('nineTabBar').classList.remove('hidden'); }")

        print("\n=== 2. GEREED BLIJFT IN BEELD NA DE EERSTE TIK ===\n")
        await pg.evaluate("() => { game.holes.forEach(h => { h.score = h.par + 1; }); saveActiveRound(); renderScore(); }")
        await pg.wait_for_timeout(200)
        check("de knop heet Gereed", await pg.evaluate("document.getElementById('finishRoundLabel').textContent"), 'Gereed')
        voor = await pg.evaluate(MAAT)
        await pg.click('#finishRoundBtn'); await pg.wait_for_timeout(300)
        m = await pg.evaluate(MAAT)
        check("de vraag staat in de knop, oranje", await pg.evaluate("[document.getElementById('finishRoundLabel').textContent, document.getElementById('finishRoundBtn').style.background]"), ['Tik nogmaals om te bevestigen', 'var(--orange)'])
        check("de knop verschuift niet en blijft boven de tabbalk, zonder scrollen", (m['ruimte'] == voor['ruimte'], m['ruimte'] >= 4, m['scroll'] <= 0), (True, True, True))
        await pg.evaluate("renderScore()")
        check("een hertekening laat de vraag staan", await pg.evaluate("document.getElementById('finishRoundLabel').textContent"), 'Tik nogmaals om te bevestigen')
        await pg.wait_for_timeout(2200)
        check("na twee seconden weer Gereed, gewone kleur", await pg.evaluate("[document.getElementById('finishRoundLabel').textContent, document.getElementById('finishRoundBtn').style.background]"), ['Gereed', ''])
        await pg.click('#finishRoundBtn'); await pg.wait_for_timeout(200)
        await pg.click('#finishRoundBtn'); await pg.wait_for_timeout(500)
        check("de tweede tik rondt af", await pg.evaluate("!!(game && game.started)"), False)
        print("\n=== 3. DE KNOP STEEKT AF ===\n")
        await pg.evaluate("() => { localStorage.setItem('golf_active_id', '999'); const s = JSON.parse(localStorage.getItem('golf_rounds')); const r = s.find(x => x.id === 999); r.holes.forEach(h => { h.score = null; }); localStorage.setItem('golf_rounds', JSON.stringify(s)); }")
        await pg.reload(); await pg.wait_for_timeout(800)
        kl = await pg.evaluate("""() => { const k = getComputedStyle(document.getElementById('finishRoundBtn')); const g = document.createElement('span'); g.style.color = 'var(--gold)'; document.body.appendChild(g);
            const goud = getComputedStyle(g).color; g.style.color = 'var(--text)'; const tekst = getComputedStyle(g).color; g.remove();
            return [k.borderTopWidth, k.borderTopColor === goud, k.color === tekst]; }""")
        check("gouden rand van 2 px, tekst in de tekstkleur", kl, ['2px', True, True])
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ", ".join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
