"""Soft en hard cap pas vanaf 20 scores, ook op de rondekaarten en in de grafiek.

Rules of Handicapping 2024, regel 5.7: "A Low Handicap Index is established once a player
has at least 20 acceptable scores in their scoring record." Regel 5.8: "The soft cap and
hard cap procedures start to take effect only after the Low Handicap Index has been
established."

De handicap van nu hield zich daaraan. Tot 13527DA-140 deden het verloop per ronde (de
waarde 'Whs oud → nieuw' op de rondekaarten) en de gecapte lijn in de grafiek dat niet:
met 6 rondes (10,0 en vijf keer 40,0) toonde de kaart van ronde 6 een hard cap op 13,0,
terwijl de index 24,0 was.

De regels: vóór 20 scores geen cap, op geen enkele plek; daarna overal dezelfde waarde als
de handicap van nu. Een handmatig ingestelde Low HI geldt altijd, zoals bij de handicap van nu.
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
    return {"id": i, "date": f"2026-{1 + (i - 1) // 28:02d}-{1 + (i - 1) % 28:02d}", "time": "10:00", "player": "Testspeler", "hcp": 20.0, "club": "Golfclub Heelsum",
            "track": "Airborne", "tee": "Blauw", "gender": "Heren", "CR": 72.0, "SR": 113, "PAR": 72, "chcp": 20, "qualifying": True, "sdFinal": sd,
            "holes": [{"id": str(k + 1), "par": 4, "si": k + 1, "phcp": 1, "score": 5} for k in range(18)]}
OFFICIEEL = "() => { const all = leesRondes(); return whsHandicap(last20Qualifying('Testspeler', all), effectiveLowHi('Testspeler', all), esrMapFor('Testspeler', all)).value; }"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.add_init_script("""window.addEventListener('DOMContentLoaded', () => { const orig = window.renderSdChart;
            if (orig) window.renderSdChart = function (...a) { window.__cap = a[2]; return orig.apply(this, a); }; });""")
        await pg.goto(app_url())
        async def zet(rondes, handmatig=None):
            await pg.evaluate("""([r, h]) => { localStorage.clear(); localStorage.setItem('golf_rounds', JSON.stringify(r)); localStorage.setItem('golf_profile_name', 'Testspeler');
                localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); if (h != null) localStorage.setItem('golf_low_hi', String(h)); }""", [rondes, handmatig])
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

        print("\n=== 1. ZES RONDES: NOG GEEN LOW HI, GEEN CAP ===\n")
        await zet([ronde(1, 10.0)] + [ronde(i, 40.0) for i in range(2, 7)])
        check("handicap nu: 24,0 (laagste 2 van 6: (10 + 40) / 2 − 1)", await pg.evaluate(OFFICIEEL), 24.0)
        check("kaart van ronde 6: ook 24,0 (geen hard cap op 13,0)", await kaart(6), 24.0)
        check("grafiek, laatste punt: ook 24,0", await grafiek(), 24.0)

        print("\n=== 2. VANAF 20 SCORES: CAP, OVERAL DEZELFDE ===\n")
        # 20 × 20,0 en dan 15 × 40,0. Laatste 20: 5 × 20,0 en 15 × 40,0 → laagste 8: (100 + 120) / 8
        # = 27,5 ongecapt. Low HI: de laagste index in de 365 dagen ervoor; na de eerste rondes
        # was dat 18,0 (1–3 rondes: laagste − 2,0). Soft cap: 18 + 3 + 0,5 × 6,5 = 24,25; hard
        # cap: 18 + 5 = 23,0 → 23,0.
        rondes = [ronde(i, 20.0) for i in range(1, 21)] + [ronde(i, 40.0) for i in range(21, 36)]
        await zet(rondes)
        check("handicap nu: 23,0 (hard cap)", await pg.evaluate(OFFICIEEL), 23.0)
        check("kaart van de laatste ronde: 23,0", await kaart(35), 23.0)
        check("grafiek, laatste punt: 23,0", await grafiek(), 23.0)

        print("\n=== 3. HANDMATIGE LOW HI GELDT ALTIJD ===\n")
        await zet([ronde(1, 10.0)] + [ronde(i, 40.0) for i in range(2, 7)], handmatig=15.0)
        nu = await pg.evaluate(OFFICIEEL)
        check("met een handmatige Low HI van 15,0: handicap nu 20,0 (hard cap)", nu, 20.0)
        check("kaart van ronde 6: dezelfde", await kaart(6), nu)
        check("grafiek, laatste punt: dezelfde", await grafiek(), nu)
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
