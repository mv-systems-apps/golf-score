"""Instellingen laat zien hoe vol de app is (1352898-032).

Bovenaan de kaart 'Opruimen & resetten', buiten 'Toon opties', staat hoeveel rondes er
bewaard zijn tegenover het maximum, en ongeveer hoeveel ruimte die rondes innemen. Er is
bewust geen oranje waarschuwing: de regel is alleen informatie.

De test:
  * met de testrondes: het aantal klopt met de opslag, het maximum is 2.500, de grootte
    is die van de rondes in de opslag (in kB), en de regel is zichtbaar zonder 'Toon opties';
  * met 2.137 rondes: het aantal met een punt ('2.137') en de grootte in MB met een komma;
  * na 'Niet-qualifying rondes verwijderen' telt de regel meteen mee;
  * een ronde die in de opslag bijkomt zonder dat de rondelijst opnieuw getekend wordt
    (bijvoorbeeld vanuit een ander venster): bij het openen van Gegevens telt hij mee.
"""
import asyncio, os, sys, copy, re
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, RONDES, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

OPEN = """() => {
  document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'));
  nav('settings'); switchSettingsTab('data');
  const sk = [...document.querySelectorAll('[data-section-key]')].find(k => k.dataset.sectionKey.includes('Opruimen'));
  openSectie(sk.dataset.sectionKey);
}"""
LEES = """() => {
  const el = document.getElementById('rondeVoorraad');
  if (!el) return null;
  const ruw = localStorage.getItem('golf_rounds') || '';
  return { tekst: el.textContent.replace(/\\s+/g, ' ').trim(), zichtbaar: !!el.offsetParent,
           aantal: JSON.parse(ruw).length, tekens: ruw.length };
}"""

def verwacht(aantal, tekens):
    n = f"{aantal:,}".replace(',', '.')
    if tekens < 1000 * 1000:
        grootte = f"{max(1, round(tekens / 1000))} kB"
    else:
        grootte = f"{tekens / 1000 / 1000:.1f}".replace('.', ',') + " MB"
    return f"Opgeslagen: {n} van 2.500 rondes (ongeveer {grootte})"

async def pagina(b, rondes):
    pg = await b.new_page(viewport={'width': 390, 'height': 844})
    pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
    await pg.goto(app_url())
    await pg.evaluate(SEED, [CLUBS, rondes])
    await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
    await pg.reload(); await pg.wait_for_timeout(700)
    await pg.evaluate(OPEN); await pg.wait_for_timeout(300)
    return pg, pf

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()

        pg, pf = await pagina(b, RONDES)
        s = await pg.evaluate(LEES)
        check("de regel staat er", s is not None, True)
        if s:
            print('  ', s['tekst'])
            check("testrondes: aantal, maximum en grootte", s['tekst'], verwacht(s['aantal'], s['tekens']))
            check("zichtbaar zonder 'Toon opties'", s['zichtbaar'], True)
            # niet-qualifying verwijderen: de regel telt meteen mee
            await pg.evaluate("""() => { const k = document.getElementById('purgeNonQBtn');
                 k.closest('.more-full')?.previousElementSibling?.click(); }""")
            await pg.wait_for_timeout(300)
            await pg.evaluate("() => { const k = document.getElementById('purgeNonQBtn'); k.click(); k.click(); }")
            await pg.wait_for_timeout(300)
            await pg.evaluate("() => document.getElementById('dangerModalConfirmBtn').click()")
            await pg.wait_for_timeout(300)
            na = await pg.evaluate(LEES)
            check("er zijn rondes verwijderd", na['aantal'] < s['aantal'], True)
            check("na verwijderen: de regel volgt meteen", na['tekst'], verwacht(na['aantal'], na['tekens']))
            await pg.evaluate("""() => { const l = JSON.parse(localStorage.getItem('golf_rounds'));
                 const r = JSON.parse(JSON.stringify(l[0])); r.id = 999001; r.date = '2026-10-19'; l.push(r);
                 localStorage.setItem('golf_rounds', JSON.stringify(l));
                 switchSettingsTab('main'); switchSettingsTab('data'); }""")
            await pg.wait_for_timeout(200)
            erbij = await pg.evaluate(LEES)
            check("ronde erbij buiten de lijst om: bij openen van Gegevens telt hij mee",
                  [erbij['aantal'], erbij['tekst']], [na['aantal'] + 1, verwacht(na['aantal'] + 1, erbij['tekens'])])
        check("geen fouten in de pagina", pf, [])
        await pg.close()

        veel = []
        for i in range(2137):
            r = ronde(10000 + i, f"{2000 + i // 200}-{1 + (i // 17) % 12:02d}-{1 + i % 28:02d}")
            r['time'] = f"{8 + i % 10:02d}:{i % 60:02d}"
            veel.append(r)
        pg, pf = await pagina(b, veel)
        s = await pg.evaluate(LEES)
        if s:
            print('  ', s['tekst'])
            check("2.137 rondes: aantal met een punt", s['aantal'], 2137)
            check("2.137 rondes: de regel", s['tekst'], verwacht(s['aantal'], s['tekens']))
        check("geen fouten in de pagina (veel rondes)", pf, [])
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
