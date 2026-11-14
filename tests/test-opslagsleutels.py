"""Eén register voor de opslagsleutels (1352898-016).

OPSLAGSLEUTELS in golf-score.html noemt elke vaste sleutel in localStorage met wat er bij
'Alles wissen' mee gebeurt ('wissen', 'houden' of 'oud'); OPSLAG_VOORVOEGSELS de sleutels
met een naam erachter. Deze test bewaakt dat het register niet stil veroudert:

  1. Elke 'golf_…'-tekst in de app staat in het register (of begint met een voorvoegsel).
  2. Elke sleutel die niet 'oud' is, wordt in de app ook echt gebruikt.
  3. Elke sleutel en elk voorvoegsel staat in DATAMODEL.md.
  4. Oude sleutels zijn na het starten weg; de andere blijven staan.
  5. 'Alles wissen' laat alleen de plek staan, plus wat een verse start zelf neerzet.
"""
import asyncio, os, re, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, ronde, APP

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

html = open(APP, encoding='utf-8').read()
m = re.search(r"const OPSLAGSLEUTELS = \{(.*?)\n\};", html, re.S)
reg = dict(re.findall(r"(golf_[a-z0-9_]+): '(wissen|houden|oud)'", m.group(1))) if m else {}
mv = re.search(r"const OPSLAG_VOORVOEGSELS = \[(.*?)\];", html, re.S)
voor = re.findall(r"'(golf_[a-z0-9_]+)'", mv.group(1)) if mv else []
buiten = html.replace(m.group(0), '') if m else html
# De naam van de IndexedDB voor de exportmap is geen localStorage-sleutel.
buiten = re.sub(r"indexedDB\.open\('golf_[a-z0-9_]+'", "indexedDB.open(''", buiten)
gebruikt = set(re.findall(r"['\"`](golf_[a-z0-9_]+)['\"`]", buiten))
datamodel = open(os.path.join(HIER, '..', 'DATAMODEL.md'), encoding='utf-8').read()

print("\n=== 1-3. HET REGISTER ===\n")
check("er is een register met sleutels", len(reg) > 40, True)
check("elke 'golf_…'-tekst in de app staat in het register",
      sorted(k for k in gebruikt if k not in reg and k not in voor and not any(k.startswith(v) for v in voor)), [])
check("elke sleutel die niet 'oud' is, wordt gebruikt", sorted(k for k, w in reg.items() if w != 'oud' and k not in gebruikt), [])
check("elk voorvoegsel wordt gebruikt", sorted(v for v in voor if v not in gebruikt), [])
check("elke sleutel en elk voorvoegsel staat in DATAMODEL.md",
      sorted(k for k in list(reg) + voor if k not in datamodel), [])

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()

        print("\n=== 4. OUDE SLEUTELS NA HET STARTEN ===\n")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page()
        await pg.goto(app_url())
        await pg.evaluate(SEED, [CLUBS, [ronde(1, '2026-01-01')]])
        await pg.evaluate("(ks) => ks.forEach(k => localStorage.setItem(k, 'x'))", [k for k, w in reg.items() if w == 'oud'] or ['golf_round_limit', 'golf_clubs_changed'])
        await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
        await pg.reload(); await pg.wait_for_timeout(700)
        over = await pg.evaluate("() => Object.keys(localStorage)")
        check("geen oude sleutel meer na het starten", sorted(k for k in over if reg.get(k) == 'oud' or k in ('golf_round_limit', 'golf_clubs_changed')), [])
        check("de rondes staan er nog", 'golf_rounds' in over, True)
        await ctx.close()

        print("\n=== 5. ALLES WISSEN ===\n")
        # Wat een verse start zelf neerzet
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page(); await pg.goto(app_url()); await pg.wait_for_timeout(700)
        vers = set(await pg.evaluate("() => Object.keys(localStorage)"))
        await ctx.close()
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page()
        await pg.goto(app_url())
        await pg.evaluate(SEED, [CLUBS, [ronde(1, '2026-01-01')]])
        alles = [k for k in reg] + [v + 'Testspeler' for v in voor]
        await pg.evaluate("(ks) => ks.forEach(k => { if (localStorage.getItem(k) === null) localStorage.setItem(k, 'x'); })", alles)
        await pg.evaluate("() => { localStorage.setItem('golf_storage_id', 'ABC123'); localStorage.setItem('golf_opslag_kenmerk', 'Thuis'); }")
        await pg.reload(); await pg.wait_for_timeout(700)
        await pg.evaluate("() => doResetAll()"); await pg.wait_for_timeout(1200)
        na = await pg.evaluate("() => Object.fromEntries(Object.keys(localStorage).map(k => [k, localStorage.getItem(k)]))")
        houden = {k for k, w in reg.items() if w == 'houden'} | {'golf_storage_id', 'golf_opslag_kenmerk', 'golf_kenmerk_gevraagd'}
        check("na Alles wissen alleen de plek en wat een verse start neerzet", sorted(k for k in na if k not in vers and k not in houden), [])
        check("de opslagcode en -naam blijven", [na.get('golf_storage_id'), na.get('golf_opslag_kenmerk')], ['ABC123', 'Thuis'])
        check("geen rondes meer", na.get('golf_rounds') in (None, '[]'), True)
        await ctx.close()
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
