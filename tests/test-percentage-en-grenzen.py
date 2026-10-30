"""Wedstrijdpercentage over de onafgeronde course handicap, en geen kunstmatige grens van 54.

Rules of Handicapping 2024, regel 6.2: de speelhandicap is de course handicap maal het
wedstrijdpercentage; sinds 2024 over de ONAFGERONDE course handicap, en pas daarna
afronden (USGA: 'it is recommended that the handicap allowance be applied to the
unrounded Course Handicap'). Een course handicap kan boven 54 uitkomen (index 54 op een
zware baan); de grens van 54 geldt voor de index, niet voor de baanhandicap.

Tot 13527DA-13E:
  * nam de app het percentage over de al afgeronde course handicap. Index 12,0, SR 113,
    CR 72,4, par 72: CH 12,4. 85% hoort 10,54 → 11 te zijn; de app gaf 12 × 85% = 10,2 → 10;
  * zetten + en het percentage een course handicap boven 54 terug naar 54.

Getest met echte tikken op de knoppen (%, −, +) en het keuzevenster, voor speler 1 en 2.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

def tee(cr, sr): return {"CR": cr, "SR": sr, "holes": [{"par": 4, "si": i + 1} for i in range(18)]}
CLUBS = {"Club": {"club": "Club", "shortName": "Club", "courses": {"Baan": {"holeIds": [f"H{i + 1}" for i in range(18)],
         "tees": {"Heren": {"Geel": tee(72.4, 113), "Zwart": tee(74.0, 140)}}}}}}

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.goto(app_url())
        await pg.evaluate("""(c) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', '[]');
            localStorage.setItem('golf_default_club', 'Club'); localStorage.setItem('golf_home_club', 'Club'); localStorage.setItem('golf_profile_name', 'Testspeler');
            localStorage.setItem('golf_kenmerk_gevraagd', '1'); }""", CLUBS)
        await pg.reload(); await pg.wait_for_timeout(600)

        async def zet(hcp, tee_naam, speler=1):
            veld = 'iHcp' if speler == 1 else 'iHcp2'
            await pg.evaluate("""([h, t, s, v]) => { nav('setup'); sel.track = 'Baan'; sel.gender = 'Heren'; sel.tee = t; if (s === 2) { if (!player2Visible) togglePlayer2(); sel2.gender = 'Heren'; sel2.tee = t; }
                const el = document.getElementById(v); el.value = String(h); onHcpBlur(el); rebuildAll(); sel.tee = t; if (s === 2) sel2.tee = t;
                if (s === 1) resetChcpOverride(); else resetChcpSpeler2Override(); }""", [hcp, tee_naam, speler, veld])
            await pg.wait_for_timeout(250)
        async def kies_pct(pct, speler=1):
            await pg.click('#chcpPctBtn' if speler == 1 else '#chcp2PctBtn'); await pg.wait_for_timeout(200)
            await pg.click(f'#choiceEditOptions button[data-choice="{pct}"]'); await pg.wait_for_timeout(100)
            await pg.click('#choiceEditModal button[onclick="confirmChoiceEdit()"]'); await pg.wait_for_timeout(250)
        waarde = lambda s=1: pg.evaluate("(s) => s === 1 ? sel.chcpOverride ?? calcChcpAuto() : sel2.chcpOverride ?? calcChcpAutoSpeler2(parseFloat(document.getElementById('iHcp2').value))", s)
        beeld = lambda s=1: pg.evaluate("(s) => document.getElementById(s === 1 ? 'chcpPreview' : 'chcp2Preview').textContent.trim()", s)

        print("\n=== 1. PERCENTAGE OVER DE ONAFGERONDE COURSE HANDICAP ===\n")
        await zet(12.0, 'Geel')
        check("CH 12,4 wordt 12", await waarde(), 12)
        await kies_pct('85')
        check("85% van 12,4 = 10,54 → 11 (niet 10)", (await waarde(), await beeld()), (11, '11'))
        await kies_pct('95')
        check("95% van 12,4 = 11,78 → 12", await waarde(), 12)
        await kies_pct('50')
        check("50% van 12,4 = 6,2 → 6", await waarde(), 6)
        await zet(-3.0, 'Geel')
        check("plushandicap: index −3,0, CR 72,4: CH −2,6 → −3", await waarde(), -3)
        await kies_pct('85')
        check("85% van −2,6 = −2,21 → −2", await waarde(), -2)

        print("\n=== 2. GEEN GRENS VAN 54 OP DE BAANHANDICAP ===\n")
        await zet(54.0, 'Zwart')
        check("index 54 op SR 140, CR 74,0: CH 54 × 140/113 + 2 = 68,90 → 69", await waarde(), 69)
        await pg.click('#chcpCard .plus'); await pg.wait_for_timeout(200)
        check("+ geeft 70 (niet 54)", (await waarde(), await beeld()), (70, '70'))
        await pg.click('#chcpCard .minus'); await pg.click('#chcpCard .minus'); await pg.wait_for_timeout(200)
        check("twee keer − geeft 68", await waarde(), 68)
        await kies_pct('95')
        check("95% van 68,90 = 65,46 → 65 (niet 54)", await waarde(), 65)

        print("\n=== 3. SPELER 2 ===\n")
        await zet(12.0, 'Geel', speler=2)
        await kies_pct('85', speler=2)
        check("speler 2: 85% van 12,4 → 11", await waarde(2), 11)
        await zet(54.0, 'Zwart', speler=2)
        await pg.click('#chcp2Card .plus'); await pg.wait_for_timeout(200)
        check("speler 2: + bij CH 69 geeft 70", await waarde(2), 70)

        print("\n=== 4. DE RONDE START MET DIE HANDICAP ===\n")
        await zet(12.0, 'Geel'); await kies_pct('85')
        await pg.evaluate("""() => { if (player2Visible) togglePlayer2(); document.getElementById('iName').value = 'Testspeler'; startRound();
            const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
        await pg.wait_for_timeout(400)
        check("de ronde speelt met 11 slagen", await pg.evaluate("() => [game.started, game.chcp, game.holes.reduce((s, h) => s + h.phcp, 0)]"), [True, 11, 11])
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
