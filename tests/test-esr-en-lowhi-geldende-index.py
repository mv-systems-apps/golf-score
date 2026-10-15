"""Uitzonderlijke score tegen de index die gold, en een Low HI mét uitzonderlijke scores.

Rules of Handicapping 2024:
  - Regel 5.9: een uitzonderlijke score is 7,0 of meer beter dan de "Handicap Index in effect
    when the round was played". Dat is de index die je had, dus na soft of hard cap.
  - Regel 5.7: de Low HI is de laagste Handicap Index in de 365 dagen vóór de laatste score.
    Een Handicap Index na een uitzonderlijke score draagt die verlaging (5.9), dus de Low
    HI ook.

Tot 13527DA-141:
  - vergeleek de app met de index vóór de cap. Met 20 × 20,0, 20 × 27,0 en dan 19,5: 27,0 −
    19,5 = 7,5 en dus −1 op de laatste 20, terwijl de geldende index 23,0 was (hard cap) en
    19,5 dus maar 3,5 beter;
  - rekende de Low HI zonder de verlagingen. Met 20 × 20,0 en dan 10,0 (10 beter, −2 op de
    laatste 20) was de index daarna 16,8; de app nam als Low HI 18,0 (de laagste zonder ESR),
    en de hard cap kwam daardoor op 23,0 in plaats van 21,8.

De regels: zoals hierboven, en overal dezelfde uitkomst — de handicap van nu, de Low HI
op Instellingen, de waarde op de rondekaart en de grafiek.
"""
import asyncio, re, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

def ronde(i, sd):
    return {"id": i, "date": f"2026-{1 + (i - 1) // 28:02d}-{1 + (i - 1) % 28:02d}", "time": "10:00", "player": "Mark", "hcp": 20.0, "club": "Golfclub Heelsum",
            "track": "Airborne", "tee": "Blauw", "gender": "Heren", "CR": 72.0, "SR": 113, "PAR": 72, "chcp": 20, "qualifying": True, "sdFinal": sd,
            "holes": [{"id": str(k + 1), "par": 4, "si": k + 1, "phcp": 1, "score": 5} for k in range(18)]}
NU = "() => { const all = leesRondes(); return whsHandicap(last20Qualifying('Mark', all, null, null), effectiveLowHi('Mark', all), esrMapFor('Mark', all)).value; }"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.add_init_script("""window.addEventListener('DOMContentLoaded', () => { const orig = window.renderSdChart;
            if (orig) window.renderSdChart = function (...a) { window.__cap = a[2]; return orig.apply(this, a); }; });""")
        await pg.goto(app_url())
        async def zet(rondes):
            await pg.evaluate("""(r) => { localStorage.clear(); localStorage.setItem('golf_rounds', JSON.stringify(r)); localStorage.setItem('golf_profile_name', 'Mark');
                localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); }""", rondes)
            await pg.reload(); await pg.wait_for_timeout(600)
        async def kaart(i):
            await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(400)
            t = await pg.evaluate("(i) => { const e = document.getElementById('round-full-' + i); return e ? e.textContent.replace(/\\s+/g, ' ') : ''; }", i)
            m = re.search(r'Whs (-?\d+[.,]\d)(-?\d+[.,]\d)', t)
            return float(m.group(2).replace(',', '.')) if m else None
        async def grafiek():
            await pg.evaluate("() => { window.__cap = null; nav('stat'); }"); await pg.wait_for_timeout(600)
            c = await pg.evaluate("() => window.__cap")
            return [v for v in c if v is not None][-1] if c else None
        async def low_hi_scherm():
            await pg.evaluate("() => nav('settings')"); await pg.wait_for_timeout(400)
            return await pg.evaluate("() => document.getElementById('derivedLowHiVal').textContent.trim()")

        print("\n=== 1. UITZONDERLIJK TEGEN DE INDEX DIE GOLD (NA DE CAP) ===\n")
        # 20 × 20,0: Low HI 18,0 (na de eerste ronde: 20,0 − 2,0). Dan 20 × 27,0: ongecapt
        # 27,0, hard cap 18,0 + 5,0 = 23,0. Dan 19,5: 3,5 beter dan 23,0 → geen verlaging.
        await zet([ronde(i, 20.0) for i in range(1, 21)] + [ronde(i, 27.0) for i in range(21, 41)] + [ronde(41, 19.5)])
        check("de index vóór de laatste ronde: 23,0 (hard cap)", await pg.evaluate("() => handicapTabellen().hcpTrendMap[40].newHcp"), 23.0)
        check("19,5 is geen uitzonderlijke score: geen verlaging", await pg.evaluate("() => esrMapFor('Mark', leesRondes()).get(41)"), 0)
        check("de kaart van de laatste ronde: geen ESR-teken", await pg.evaluate("() => handicapTabellen().hcpTrendMap[41].esrApplied"), False)
        nu = await pg.evaluate(NU)
        check("handicap nu 23,0", nu, 23.0)
        check("kaart van de laatste ronde: dezelfde", await kaart(41), nu)
        check("grafiek, laatste punt: dezelfde", await grafiek(), nu)

        print("\n=== 2. DE LOW HI DRAAGT DE VERLAGING ===\n")
        # 20 × 20,0, dan 10,0: 10,0 beter → −2 op de laatste 20. Index: (8,0 + 7 × 18,0) / 8 =
        # 16,75 → 16,8. Dan 24 × 30,0: ongecapt 30,0; Low HI 16,8 → hard cap 21,8.
        await zet([ronde(i, 20.0) for i in range(1, 21)] + [ronde(21, 10.0)] + [ronde(i, 30.0) for i in range(22, 46)])
        check("na de uitzonderlijke ronde: index 16,8", await pg.evaluate("() => handicapTabellen().hcpTrendMap[21].newHcp"), 16.8)
        check("Low HI (afgeleid): 16,8", await pg.evaluate("() => derivedLowHi('Mark', leesRondes())"), 16.8)
        check("Low HI op Instellingen: 16.8", await low_hi_scherm(), '16.8')
        nu = await pg.evaluate(NU)
        check("handicap nu: 16,8 + 5,0 = 21,8 (hard cap)", nu, 21.8)
        check("kaart van de laatste ronde: dezelfde", await kaart(45), nu)
        check("grafiek, laatste punt: dezelfde", await grafiek(), nu)
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
