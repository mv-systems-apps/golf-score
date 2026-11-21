"""Losse knoppen met alleen een icoon zijn allemaal even groot (1352900-002): 46 x 38 px met een
icoon van 16 px, de maat van de knoppen bovenin Rondes. Daarvoor liepen ze uiteen van 42 x 34
(notitie) tot 48 x 41 (speler 2 toevoegen) en 50 x 38 (handicap terugzetten). Niet voor knoppen
die meegroeien met hun buren (annuleer-icoon, prullenbak naast Annuleren), de tabbalk, de brede
knoppen (Ronde afronden, Thuisclub in de editor) en de kleine knoppen in een baanrij.
"""
import asyncio, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

APP = os.environ.get('APP') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'golf-score.html')
bron = open(APP, encoding='utf-8').read()

# 1. In de bron: elke btn-secondary met alleen een icoon heeft de klasse, op de uitzonderingen na
UITZONDERING = re.compile(r'id="(finishRoundBtn|editorHomeBtn)"|title="Baananalyse"|openCourseEditor\(|tee-move')
zonder = []
for m in re.finditer(r'<button\b([^>]*)>\s*(?:\$\{[^}]*\}\s*)?<svg\b[^>]*>.*?</svg>\s*</button>', bron, flags=re.S):
    a = m.group(1)
    if 'btn-secondary' not in a or UITZONDERING.search(a): continue
    if 'icoon-knop' not in a:
        t = re.search(r'title="([^"]*)"|aria-label="([^"]*)"|onclick="([^"(]*)', a)
        zonder.append(next(g for g in t.groups() if g) if t else '?')
check("bron: elke losse icoonknop (btn-secondary, alleen een svg) heeft de vaste maat", zonder, [])

MEET = """() => [...document.querySelectorAll('button.icoon-knop')].filter(b => b.offsetParent).map(b => {
  const r = b.getBoundingClientRect(), s = b.querySelector('svg').getBoundingClientRect();
  return [Math.round(r.width), Math.round(r.height), Math.round(s.width), Math.round(s.height),
    Math.abs((s.left + s.right) / 2 - (r.left + r.right) / 2) <= 1 && Math.abs((s.top + s.bottom) / 2 - (r.top + r.bottom) / 2) <= 1.5]; })"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 740})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto('file://' + os.path.abspath(APP) if os.environ.get('APP') else app_url())
        await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        stappen = [
            ('Ronde', "() => nav('setup')"),
            ('Rondes', "() => nav('archive')"),
            ('Clubs', "() => nav('club')"),
            ('Club bewerken', "() => openClubEditor('Golfclub Heelsum')"),
            ('Baan bewerken, tees en holes open', "() => { openCourseEditor('Airborne'); toggleEditorSection('tees'); toggleEditorSection('holes'); }"),
        ]
        for w in (360, 320):
            await pg.set_viewport_size({'width': w, 'height': 740})
            await pg.evaluate("() => { document.querySelectorAll('.modal-overlay').forEach(o => o.style.display = 'none'); }")
            for naam, js in stappen:
                await pg.evaluate(js); await pg.wait_for_timeout(300)
                m = await pg.evaluate(MEET)
                check(f"{w} px, {naam}: knoppen gevonden", len(m) > 0, True)
                check(f"{w} px, {naam}: alle 46 x 38, icoon 16 px in het midden", sorted(set(tuple(x) for x in m)), [(46, 38, 16, 16, True)])
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
