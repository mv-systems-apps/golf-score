"""Baanhandicap bij 9 holes en bij een ander aantal holes (wedstrijdlus, korte baan).

9 holes: Rules of Handicapping, R&A-tekst van regel 6.1b, zoals de NGF rekent: "(Handicap
Index ÷ 2) x (Slope Rating ÷ 113) + (Course Rating – par)", de halve index NIET afgerond.
De USGA-tekst rondt die helft eerst af op een tiende; 13527DA-142 had die afronding
overgenomen. Bij Marks ronde van 30-11-2025 (index 31,7, CR 33,8, SR 119, par 36) gaf dat
15,9 × 119/113 − 2,2 = 14,54 → 15, waar de NGF-app 14 geeft (15,85 → 14,49 → 14). Zijn
ronde van 15-12-2025 (index 32,1, CR 33,2, SR 115, par 35) bevestigt het: NGF 15
(16,05 → 14,53 → 15; naar beneden afgerond zou het 14 zijn).

Een ander aantal holes dan 9 of 18: daarvoor geven de regels geen formule (dat bepaalt de
commissie). Tot 13527DA-141 kreeg zo'n ronde de volledige 18-holesindex: 6 holes met index
30,8 en slope 120 gaven 33 slagen, ruim 5 per hole. Marks keuze: naar rato van het aantal
holes, net als bij 9 holes onafgerond, met een melding op het startscherm dat het een
benadering is die je met − en + kunt bijstellen.

De regels:
  1. 9 holes: de onafgeronde halve index; op het startscherm, in de gestarte ronde
     (baanhandicap en de som van de slagen per hole) en in de maximale score per hole.
  2. n holes (niet 9 of 18): de index × n/18; met de melding. Bij 9 en 18 holes staat die
     melding er niet.
  3. 18 holes: ongewijzigd.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

def baan(n, cr, sr, pars=None):
    holes = [{"par": (pars or [4] * n)[i], "si": i + 1} for i in range(n)]
    return {"tees": {"Heren": {"Geel": {"CR": cr, "SR": sr, "holes": holes}}}, "holeIds": [f"H{i + 1}" for i in range(n)]}
CLUBS = {"Proefclub": {"club": "Proefclub", "shortName": "Proef", "courses": {
    "Negen": baan(9, 33.8, 119),        # par 36, zoals Airborne Rood (Marks ronde 30-11-2025)
    "Pluut": baan(9, 33.2, 115, [4, 4, 4, 4, 3, 4, 4, 4, 4]),   # par 35 (Marks ronde 15-12-2025)
    "Zes": dict(baan(6, 24.0, 120), lus=True),   # wedstrijdlus van 6 holes, par 24
    "Achttien": baan(18, 72.0, 113),    # par 72
}}}

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.goto(app_url())
        async def zet(hcp):
            await pg.evaluate("""([c, h]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', '[]');
                localStorage.setItem('golf_default_club', 'Proefclub'); localStorage.setItem('golf_profile_name', 'Mark'); localStorage.setItem('golf_profile_hcp', h);
                localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); }""", [CLUBS, hcp])
            await pg.reload(); await pg.wait_for_timeout(600)
        async def scherm(track):
            return await pg.evaluate("""(t) => { nav('setup'); sel.track = t; sel.tee = 'Geel'; sel.chcpOverride = null; sel.chcpPct = null; updateChcp();
                const n = document.getElementById('chcpNaarRatoNote');
                return [document.getElementById('chcpPreview').textContent, !!n && !n.classList.contains('hidden') ? n.textContent : ''];
            }""", track)
        async def start(track):
            await pg.evaluate("""(t) => { nav('setup'); sel.track = t; sel.tee = 'Geel'; sel.chcpOverride = null; sel.chcpPct = null; startRound();
                const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""", track)
            await pg.wait_for_timeout(400)
            return await pg.evaluate("() => { const r = leesRondes().find(x => String(x.id) === localStorage.getItem('golf_active_id')); return [r.chcp, r.holes.reduce((s, h) => s + h.phcp, 0)]; }")

        print("\n=== 1. 9 HOLES: DE HALVE INDEX ONAFGEROND (ZOALS DE NGF) ===\n")
        await zet('31.7')
        pv, melding = await scherm('Negen')
        check("startscherm, ronde 30-11-2025: 15,85 × 119/113 − 2,2 = 14,49 → 14 (NGF-app: 14)", pv, '14')
        check("geen melding bij 9 holes", melding, '')
        check("gestarte ronde: baanhandicap 14, slagen per hole samen 14", await start('Negen'), [14, 14])
        # Maximale score per hole (net double bogey) rekent met dezelfde baanhandicap.
        ags = await pg.evaluate("""() => { const r = { holes: Array.from({ length: 9 }, (_, i) => ({ par: 4, si: i + 1, phcp: 0, score: 12 })), CR: 33.8, SR: 119, PAR: 36, hcp: 31.7 };
            return agsSlagen(r).reduce((s, x) => s + x, 0); }""")
        check("maximale score per hole: slagen samen 14", ags, 14)
        await pg.evaluate("() => { finishActiveRound(null); }"); await pg.wait_for_timeout(300)
        await zet('32.1')
        check("startscherm, ronde 15-12-2025: 16,05 × 115/113 − 1,8 = 14,53 → 15 (NGF-app: 15)", (await scherm('Pluut'))[0], '15')

        print("\n=== 2. LUS VAN 6 HOLES: INDEX NAAR RATO, MET MELDING ===\n")
        await zet('30.8')
        # Met echte tikken: de lussen openklappen en de lus kiezen.
        await pg.evaluate("() => { localStorage.setItem('golf_lussen_open', '1'); nav('setup'); rebuildStartScreen(); }"); await pg.wait_for_timeout(300)
        await pg.locator('.track-btn', has_text='Zes').click(); await pg.wait_for_timeout(400)
        getikt = await pg.evaluate("""() => { const n = document.getElementById('chcpNaarRatoNote');
            return [sel.track, document.getElementById('chcpPreview').textContent, !n || n.classList.contains('hidden') ? '' : n.textContent]; }""")
        check("na een tik op de lus: 30,8 × 6/18 = 10,267; × 120/113 = 10,90 → 11", getikt[:2], ['Zes', '11'])
        check("melding dat het een benadering is", getikt[2], '6 holes: index naar rato (6/18), geen officiële regel · bijstellen met − en +')
        await pg.locator('.track-btn', has_text='Negen').click(); await pg.wait_for_timeout(400)
        check("terug naar de 9-holesbaan: 15,4 × 119/113 − 2,2 = 14,02 → 14, melding weg", await pg.evaluate("() => [document.getElementById('chcpPreview').textContent, !document.getElementById('chcpNaarRatoNote') || document.getElementById('chcpNaarRatoNote').classList.contains('hidden')]"), ['14', True])
        check("gestarte ronde: baanhandicap 11, slagen per hole samen 11", await start('Zes'), [11, 11])
        await pg.evaluate("() => { finishActiveRound(null); }"); await pg.wait_for_timeout(300)

        print("\n=== 3. 18 HOLES: ONGEWIJZIGD ===\n")
        pv, melding = await scherm('Achttien')
        check("startscherm: 30,8 × 113/113 = 30,8 → 31, geen melding", [pv, melding], ['31', ''])
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
