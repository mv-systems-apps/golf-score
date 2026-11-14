"""Een dichtgeklapte groep op Statistiek wordt niet berekend (1352898-025).

Tot 024 rekende renderPlayerStats bij elke opbouw alles uit, ook de kaarten in een
dichtgeklapte groep: het handicapverloop per ronde, de regelkaart, 'Wat als' en alle
kaarten van Prestaties. Sinds 025 is het rekenwerk per kaart gescheiden van de HTML, en
wordt een kaart in een dichte groep niet berekend.

De test telt per groep de aanroepen van functies die alleen die groep nodig heeft:
  Handicap    indexVoorRonde (het verloop per ronde), bouwRegelkaartGrafiek
  Prestaties  bouwSiKaart, bouwDagKaart, bouwPuttKaart, bouwParTypeKaart, bouwTeeGrafiek
  Clubs       bouwClubBlok
Open: elke functie wordt minstens één keer aangeroepen (anders bewijst 'dicht: 0' niets).
Dicht: nul keer. Ook 'Wat als' dicht: bouwVooruitblik nul keer.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, RONDES, SEED, app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

GROEPEN = {
    'handicap': ['indexVoorRonde', 'bouwRegelkaartGrafiek'],
    'prestaties': ['bouwSiKaart', 'bouwDagKaart', 'bouwPuttKaart', 'bouwParTypeKaart', 'bouwTeeGrafiek'],
    'banen': ['bouwClubBlok'],
}
ALLE = [f for fs in GROEPEN.values() for f in fs] + ['bouwVooruitblik']

TEL = """([namen, opslag, js]) => {
  for (const [k, v] of Object.entries(opslag)) localStorage.setItem(k, v);
  (new Function(js))();
  const tel = {};
  const orig = {};
  namen.forEach(n => { tel[n] = 0; orig[n] = window[n]; window[n] = function (...a) { tel[n]++; return orig[n].apply(this, a); }; });
  nav('stat'); renderPlayerStats();
  namen.forEach(n => { window[n] = orig[n]; });
  return tel;
}"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await pg.goto(app_url())
        await pg.evaluate(SEED, [CLUBS, RONDES])
        await pg.reload(); await pg.wait_for_timeout(600)
        # alle clubs open, zodat bouwClubBlok echt iets tekent
        alles_open = "window._watIfCollapsed = false; window._statClubSectionCollapsed = {};"

        print("=== ALLE GROEPEN OPEN (en 'Wat als' open) ===")
        open_ = await pg.evaluate(TEL, [ALLE, {f'golf_stats_grp_{g}': 'open' for g in GROEPEN}, alles_open])
        for f in ALLE:
            check(f"open: {f} wordt aangeroepen", open_[f] > 0, True)

        for groep, functies in GROEPEN.items():
            print(f"\n=== ALLEEN {groep.upper()} DICHT ===")
            # indexVoorRonde rekent ook 't.o.v. je handicap' in Prestaties: bij Handicap dicht
            # gaat Prestaties daarom ook dicht, anders telt die aanroep mee.
            dicht = {groep, 'prestaties'} if groep == 'handicap' else {groep}
            opslag = {f'golf_stats_grp_{g}': ('closed' if g in dicht else 'open') for g in GROEPEN}
            tel = await pg.evaluate(TEL, [ALLE, opslag, alles_open])
            for f in functies:
                check(f"{groep} dicht: {f} niet aangeroepen", tel[f], 0)
            # de andere groepen rekenen gewoon door
            for g, fs in GROEPEN.items():
                if g in dicht: continue
                for f in fs:
                    check(f"{groep} dicht: {f} ({g}, open) wel aangeroepen", tel[f] > 0, True)

        print("\n=== 'WAT ALS' DICHT ===")
        tel = await pg.evaluate(TEL, [ALLE, {f'golf_stats_grp_{g}': 'open' for g in GROEPEN}, "window._watIfCollapsed = true;"])
        check("wat als dicht: bouwVooruitblik niet aangeroepen", tel['bouwVooruitblik'], 0)

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
