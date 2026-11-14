"""De gouden koppen: één stijl op één plek (goud-kop en groep-kop), zonder dat er iets verschuift.

1. In de bron staat geen gouden kop meer met de stijl inline (20px, 800, goud, hoofdletters),
   en geen code die een kop via zijn inline stijl herkent of omkleurt.
2. Elke gouden kop heeft dezelfde letter: 20px, gewicht 800, hoofdletters, 0,7px.
3. Instellingen: de sectiekoppen worden nog herkend (inklapbaar, met de juiste namen), en
   een tik klapt een sectie dicht en weer open.
4. Rondes: de onderkoppen (bij speler: Gepland, Laatste 12 maanden, Overig; bij club: de
   baan) zijn groen, de hoofdkoppen goud.
"""
import asyncio, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, APP
from playwright.async_api import async_playwright

fouten = []
def check(naam, kreeg, verwacht):
    if kreeg == verwacht: print(f"  ok   {naam}: {kreeg!r}")
    else: print(f"  FOUT {naam}: {kreeg!r} — verwacht {verwacht!r}"); fouten.append(naam)

async def main():
    print("\n=== 1. DE BRON ===\n")
    bron = open(APP, encoding='utf-8').read()
    inline = [m for m in re.findall(r'style="([^"]*)"', bron)
              if 'font-size:20px' in m and 'font-weight:800' in m and 'color:var(--gold)' in m and 'uppercase' in m]
    check("geen gouden kop met de stijl inline", inline, [])
    check("geen kop die via zijn inline stijl wordt omgekleurd", bron.count(".replace('color:var(--gold)'"), 0)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 780})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)))
        await pg.goto(app_url())
        await pg.evaluate("([c, r]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r)); localStorage.setItem('golf_profile_name', 'Testspeler'); }", [CLUBS, RONDES])
        await pg.reload(); await pg.wait_for_timeout(800)
        print("\n=== 2. DEZELFDE LETTER ===\n")
        await pg.evaluate("zetGroepering('speler'); nav('archive')"); await pg.wait_for_timeout(300)
        letters = await pg.evaluate("""() => [...new Set([...document.querySelectorAll('.goud-kop, .groep-kop')].map(e => { const c = getComputedStyle(e);
            return [c.fontSize, c.fontWeight, c.textTransform, c.letterSpacing].join(' '); }))]""")
        check("alle gouden koppen dezelfde letter", letters, ['20px 800 uppercase 0.7px'])
        print("\n=== 3. INSTELLINGEN ===\n")
        await pg.evaluate("nav('settings')"); await pg.wait_for_timeout(300)
        secties = await pg.evaluate("() => [...document.querySelectorAll('[data-section-key]')].map(k => k.dataset.sectionKey.split('|')[1])")
        check("de sectiekoppen worden herkend", secties, VERWACHT)
        dicht = await pg.evaluate("""() => { const k = [...document.querySelectorAll('[data-section-key]')].find(k => k.dataset.sectionKey.endsWith('|Uitleg'));
            const inhoud = () => k.nextElementSibling && getComputedStyle(k.nextElementSibling).display;
            const a = inhoud(); k.click(); const b = inhoud(); k.click(); return [a !== b, inhoud() === a]; }""")
        check("een tik klapt Uitleg om, een tweede tik terug", dicht, [True, True])
        print("\n=== 4. RONDES: GROENE ONDERKOPPEN ===\n")
        kleur = """(sel) => { const g = document.createElement('span'); document.body.appendChild(g); g.style.color = 'var(--gold)'; const goud = getComputedStyle(g).color;
            g.style.color = 'var(--green-light)'; const groen = getComputedStyle(g).color; g.remove();
            return [...document.querySelectorAll('#screen-archive .groep-kop')].map(k => [k.querySelector('span').textContent.trim(), getComputedStyle(k).color === groen ? 'groen' : getComputedStyle(k).color === goud ? 'goud' : 'anders']); }"""
        await pg.evaluate("zetGroepering('speler'); nav('archive'); document.querySelectorAll('#screen-archive [data-inklap]').forEach(k => k.click())"); await pg.wait_for_timeout(300)
        sp = await pg.evaluate(kleur, '')
        check("bij speler: de jaargroepen groen", sorted({k for k, c in sp if c == 'groen'}), ['Gepland', 'Laatste 12 maanden', 'Overig'])
        check("bij speler: de spelers goud", all(c == 'goud' for k, c in sp if k not in ('Gepland', 'Laatste 12 maanden', 'Overig')), True)
        await pg.evaluate("zetGroepering('club'); nav('archive'); document.querySelectorAll('#screen-archive [data-inklap]').forEach(k => k.click())"); await pg.wait_for_timeout(300)
        cl = await pg.evaluate(kleur, '')
        banen = {r.get('track') for r in RONDES}
        check("bij club: de banen groen", ({k for k, c in cl if c == "groen"} <= banen, any(c == "groen" for k, c in cl)), (True, True))
        check("bij club: de clubs goud", all(c == 'goud' for k, c in cl if k not in banen) and any(c == 'goud' for k, c in cl), True)
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ", ".join(fouten)))
    sys.exit(1 if fouten else 0)

VERWACHT = ['Weergave', 'Agenda', 'Tijdens de ronde ()', 'Putts en greens', 'Spelers ()', 'Handicap ()', 'Uitleg', 'Symbolen',
            'Clubs & Rondes (&)', 'Exporteren', 'Importeren', 'Deze installatie', 'Opruimen & resetten', 'Over Golf Score']
asyncio.run(main())
