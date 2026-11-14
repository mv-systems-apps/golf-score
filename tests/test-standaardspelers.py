"""Standaard speler 1 en 2 (13528FA-003).

Instellingen > Spelers: Standaard speler 1 en Standaard speler 2 (geen favoriete speler 2
meer). Op het startscherm heeft elke speler een poppetje dat de standaard invult; de ster
bij speler 2 is weg. Speler 1 is de speler voor wie de handicap wordt berekend: een andere
naam gaat langs dezelfde controle als typen, en pas als die naam blijft komt de handicap:
de ingestelde, of zonder ingestelde de berekende WHS-hcp. Een bestaande favoriete speler 2
wordt bij het opstarten de standaard als die leeg was, en daarna opgeruimd.

Via de echte bediening: Instellen, typen, Opslaan, het poppetje, de keuzes in het venster.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

async def ev(pg, js, arg=None):
    try:
        return await pg.evaluate(js, arg)
    except Exception as e:
        return 'FOUT: ' + str(e).split('\n')[0][:120]

async def klik(pg, loc):
    try: await loc.click(timeout=2000); await pg.wait_for_timeout(150); return True
    except Exception: return False

async def vul(pg, sel, tekst):
    # zoals typen: teken voor teken (het handicapveld weigert per toets wat buiten -10..54 valt)
    try:
        await pg.locator(sel).fill('', timeout=2000)
        await pg.locator(sel).press_sequentially(tekst, timeout=4000)
        await pg.locator(sel).press('Tab', timeout=2000)
    except Exception: pass

LS = "(k) => localStorage.getItem(k)"

async def nieuw(b, extra=None):
    pg = await b.new_page(viewport={'width': 360, 'height': 800})
    pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES])
    if extra: await pg.evaluate(extra)
    await pg.reload(); await pg.wait_for_timeout(500)
    return pg, pf

async def instellen(pg, nr, naam, hcp):
    await ev(pg, "() => { nav('settings'); switchSettingsTab('main'); openSectie([...document.querySelectorAll('[data-section-key]')].map(k => k.dataset.sectionKey).find(k => k.includes('Spelers'))); }")
    await pg.wait_for_timeout(200)
    knop = pg.locator(f'#stdPlayer{nr}Summary').locator('xpath=../..').get_by_role('button', name='Instellen')
    await klik(pg, knop)
    await vul(pg, '#spelerModalNaam', naam); await vul(pg, '#spelerModalHcp', hcp)
    await klik(pg, pg.locator('#spelerModal').get_by_role('button', name='Opslaan'))

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()

        print("\n=== 1. DE FAVORIETE SPELER 2 VERDWIJNT ===\n")
        pg, pf = await nieuw(b, "() => { localStorage.setItem('golf_fav_player2_name', 'Favoriet'); localStorage.setItem('golf_fav_player2_hcp', '18'); }")
        check("standaard leeg: de favoriet wordt de standaard", [await ev(pg, LS, 'golf_default_player2_name'), await ev(pg, LS, 'golf_default_player2_hcp')], ['Favoriet', '18'])
        check("en de favoriet is opgeruimd", [await ev(pg, LS, 'golf_fav_player2_name'), await ev(pg, LS, 'golf_fav_player2_hcp')], [None, None])
        await pg.close()
        pg, pf = await nieuw(b, "() => { localStorage.setItem('golf_fav_player2_name', 'Favoriet'); localStorage.setItem('golf_default_player2_name', 'Standaard'); localStorage.setItem('golf_default_player2_hcp', '28'); }")
        check("standaard al ingevuld: die blijft", [await ev(pg, LS, 'golf_default_player2_name'), await ev(pg, LS, 'golf_default_player2_hcp'), await ev(pg, LS, 'golf_fav_player2_name')], ['Standaard', '28', None])
        await pg.close()

        pg, pf = await nieuw(b)
        print("\n=== 2. INSTELLINGEN ===\n")
        await ev(pg, "() => nav('settings')")
        tekst = await ev(pg, "() => document.getElementById('settingsTabMain').textContent")
        check("Standaard speler 1 en 2, geen favoriet", isinstance(tekst, str) and 'Standaard speler 1' in tekst and 'Standaard speler 2' in tekst and 'Favoriete speler' not in tekst, True)
        check("nog niet ingesteld", await ev(pg, "() => [stdPlayer1Summary.textContent, stdPlayer2Summary.textContent]"), ['Nog niet ingesteld', 'Nog niet ingesteld'])
        await instellen(pg, 1, 'Testspeler', '')
        check("speler 1 zonder handicap: bewaard, 'berekende hcp'", [await ev(pg, LS, 'golf_std_player1_name'), await ev(pg, LS, 'golf_std_player1_hcp'), await ev(pg, "() => stdPlayer1Summary.textContent")], ['Testspeler', None, 'Testspeler · berekende hcp'])
        await instellen(pg, 2, 'Medespeler', '24,04')
        check("speler 2: handicap met komma wordt 24", [await ev(pg, LS, 'golf_default_player2_name'), await ev(pg, LS, 'golf_default_player2_hcp'), await ev(pg, "() => stdPlayer2Summary.textContent")], ['Medespeler', '24', 'Medespeler · hcp 24'])
        # typen zoals op Start: een toets die buiten -10..54 komt of een tweede decimaal geeft, telt niet
        for invoer, verwacht in (('60', '6'), ('-12', '-1'), ('12.36', '12.3'), ('abc', None), ('', None), ('54', '54')):
            await instellen(pg, 2, 'Medespeler', invoer)
            check(f"handicap getypt {invoer!r} bewaard als {verwacht!r}", await ev(pg, LS, 'golf_default_player2_hcp'), verwacht)
        r = await ev(pg, """() => { const m = document.getElementById('hcpRangeMsg1'); m.classList.add('hidden'); openSpelerModal(2); const h = document.getElementById('spelerModalHcp');
            h.value = '99'; h.dispatchEvent(new Event('input')); const r = [document.getElementById('spelerModalHcpBereik').classList.contains('hidden'), m.classList.contains('hidden'), h.value]; sluitSpelerModal(); return r; }""")
        check("te hoog getypt: de melding in het venster, niet op Start", r, [False, True, '54'])
        r = await ev(pg, """() => { sel.chcpOverride = 7; openSpelerModal(2); const h = document.getElementById('spelerModalHcp'); h.value = '20'; h.dispatchEvent(new Event('blur')); const w = sel.chcpOverride; sluitSpelerModal(); sel.chcpOverride = null; return w; }""")
        check("het venster raakt de baanhandicap van speler 1 op Start niet", r, 7)
        await instellen(pg, 2, 'Medespeler', '24')

        print("\n=== 3. HET STARTSCHERM ===\n")
        await ev(pg, "() => { nav('setup'); if (document.getElementById('player2Card').classList.contains('hidden')) togglePlayer2(); }"); await pg.wait_for_timeout(200)
        check("geen ster meer bij speler 2", await ev(pg, "() => document.querySelectorAll('#player2Card polygon').length"), 0)
        knoppen = await ev(pg, "() => [...document.querySelectorAll('#screen-setup [aria-label$=\"invullen\"]')].map(b => b.getAttribute('aria-label'))")
        check("een poppetje bij speler 1 en bij speler 2", knoppen, ['Standaard speler 1 invullen', 'Standaard speler 2 invullen'])
        await ev(pg, "() => { iHcp.value = '12'; savePlayerProfile(); }")
        await klik(pg, pg.get_by_role('button', name='Standaard speler 1 invullen'))
        r = await ev(pg, "() => [iName.value, iHcp.value, document.getElementById('computedHcpVal').textContent, player1StdMsg.textContent]")
        check("speler 1 zonder ingestelde handicap: de berekende WHS-hcp", isinstance(r, list) and r[0] == 'Testspeler' and r[1] == r[2] and r[1] not in ('', '—') and r[3] == 'Standaard speler 1 ingevuld', True)
        print('    (', r, ')')
        await instellen(pg, 1, 'Testspeler', '18'); await ev(pg, "() => nav('setup')")
        await klik(pg, pg.get_by_role('button', name='Standaard speler 1 invullen'))
        check("met ingestelde handicap: die", await ev(pg, "() => [iName.value, iHcp.value]"), ['Testspeler', '18'])
        await ev(pg, "() => { localStorage.setItem('golf_whs_volgen', 'off'); localStorage.removeItem('golf_std_player1_hcp'); iHcp.value = '12'; }")
        await klik(pg, pg.get_by_role('button', name='Standaard speler 1 invullen'))
        check("Handicap bijhouden uit en geen ingestelde: het veld blijft leeg", await ev(pg, "() => iHcp.value"), '')
        await ev(pg, "() => localStorage.removeItem('golf_whs_volgen')")

        # een andere naam: dezelfde vragen als bij typen
        await ev(pg, "() => { localStorage.setItem('golf_std_player1_name', 'Nieuwe Naam'); localStorage.setItem('golf_std_player1_hcp', '20'); iHcp.value = '12'; savePlayerProfile(); }")
        await klik(pg, pg.get_by_role('button', name='Standaard speler 1 invullen'))
        vraag = await ev(pg, "() => [!document.getElementById('keuzeModal').classList.contains('hidden'), keuzeModalTitel.textContent]")
        check("andere naam met rondes op de oude: de vraag 'Naam gewijzigd'", vraag, [True, 'Naam gewijzigd'])
        await klik(pg, pg.locator('#keuzeModal').get_by_role('button', name='Annuleren'))
        check("Annuleren: naam en handicap blijven", await ev(pg, "() => [iName.value, iHcp.value]"), ['Testspeler', '12'])
        await klik(pg, pg.get_by_role('button', name='Standaard speler 1 invullen'))
        await klik(pg, pg.locator('#keuzeModal').get_by_role('button', name='Alleen nieuwe rondes'))
        check("Alleen nieuwe rondes: de nieuwe naam, daarna de handicap", await ev(pg, "() => [iName.value, iHcp.value, localStorage.getItem('golf_profile_name')]"), ['Nieuwe Naam', '20', 'Nieuwe Naam'])
        check("de rondes staan nog op de oude naam", await ev(pg, "() => leesRondes().filter(r => r.player === 'Testspeler').length > 0"), True)
        await ev(pg, "() => { iName.value = 'Testspeler'; iName.dataset.vorigeNaam = 'Nieuwe Naam'; controleerNaamswijziging(iName); }")
        await ev(pg, "() => document.querySelectorAll('#keuzeModal button').forEach(b => { if (b.textContent === 'Toch gebruiken') b.click(); })")

        # speler 2
        await ev(pg, "() => { iName2.value = ''; }")
        await klik(pg, pg.get_by_role('button', name='Standaard speler 2 invullen'))
        check("speler 2: naam en handicap ingevuld", await ev(pg, "() => [iName2.value, iHcp2.value, player2StdMsg.textContent]"), ['Medespeler', '24', 'Standaard speler 2 ingevuld'])
        await ev(pg, "() => localStorage.setItem('golf_default_player2_name', iName.value)")
        await klik(pg, pg.get_by_role('button', name='Standaard speler 2 invullen'))
        check("speler 2 gelijk aan speler 1: geweigerd, met melding", await ev(pg, "() => player2StdMsg.textContent"), 'Speler 2 kan niet dezelfde zijn als speler 1')
        await ev(pg, "() => { localStorage.removeItem('golf_std_player1_name'); localStorage.removeItem('golf_std_player1_hcp'); }")
        await klik(pg, pg.get_by_role('button', name='Standaard speler 1 invullen'))
        check("geen standaard speler 1: melding", await ev(pg, "() => player1StdMsg.textContent"), 'Geen standaard speler 1 ingesteld')
        check("geen paginafouten", pf, [])
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN): {', '.join(fouten)}" if fouten else "\nGEEN FOUTEN")
    sys.exit(1 if fouten else 0)

asyncio.run(main())
