import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, app_url
from playwright.async_api import async_playwright

SEED_LEEG = """([clubs]) => {
    localStorage.clear();
    localStorage.setItem('golf_clubs', JSON.stringify(clubs));
    localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
    localStorage.setItem('golf_profile_name', 'Mark');
    localStorage.setItem('golf_profile_hcp', '30.7');
}"""

async def verse(page):
    await page.goto(app_url())
    await page.evaluate(SEED_LEEG, [CLUBS])
    await page.reload(); await page.wait_for_timeout(500)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={'width': 390, 'height': 780})
        fouten = []
        page.on('pageerror', lambda e: fouten.append(str(e)[:120]))
        res = {}

        print('1. KNOP EN VELD AANWEZIG IN BEIDE BLOKKEN')
        await verse(page)
        r1 = await page.evaluate("""() => {
            nav('setup');
            if (!player2Visible) togglePlayer2();
            const uit = {};
            [1, 2].forEach(nr => {
                const knop = document.getElementById('noteBtn' + nr);
                const wrap = document.getElementById('noteWrap' + nr);
                const veld = document.getElementById('startNote' + nr);
                uit['blok' + nr] = { knop: !!knop, veld: !!veld,
                                     dichtBijStart: wrap ? wrap.classList.contains('hidden') : null,
                                     kaart: knop ? (knop.closest('.card') || {}).id : null };
            });
            return uit;
        }""")
        for k, v in r1.items(): print(f'   {k}: {v}')
        res['knoppen'] = all(v['knop'] and v['veld'] and v['dichtBijStart'] for v in r1.values())

        print('\n2. UITKLAPPEN EN MEEGROEIEN')
        r2 = await page.evaluate("""async () => {
            document.getElementById('noteBtn1').click();
            const wrap = document.getElementById('noteWrap1');
            const veld = document.getElementById('startNote1');
            const open = !wrap.classList.contains('hidden');
            const h1 = Math.round(veld.getBoundingClientRect().height);
            veld.value = 'Clubcompetitie met een wat langere notitie die over meerdere regels loopt zodat het veld moet meegroeien';
            groeiStartNote(veld);
            await new Promise(r => setTimeout(r, 100));
            const h2 = Math.round(veld.getBoundingClientRect().height);
            return { open, hoogteLeeg: h1, hoogteVol: h2, gegroeid: h2 > h1 };
        }""")
        for k, v in r2.items(): print(f'   {k:<12} {v}')
        res['groeit'] = r2['open'] and r2['gegroeid']

        print('\n3. NOTITIE KOMT IN DE RONDE TERECHT (één speler)')
        await verse(page)
        r3 = await page.evaluate("""() => {
            nav('setup');
            if (player2Visible) togglePlayer2();
            sel.track='Airborne'; sel.gender='Heren'; sel.tee='Blauw';
            document.getElementById('iName').value='Mark';
            document.getElementById('iHcp').value='30.7';
            zetStartNote(1, 'Test notitie speler 1');
            startRound();
            const cb=document.getElementById('confirmModalBtn');
            if(cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            saveActiveRound(true);
            const r = loadSavedRounds().find(x => String(x.id) === String(game.id));
            return { inGame: game.note, inOpslag: r ? r.note : null,
                     veldLeeg: document.getElementById('startNote1').value === '',
                     wrapDicht: document.getElementById('noteWrap1').classList.contains('hidden') };
        }""")
        for k, v in r3.items(): print(f'   {k:<12} {v!r}')
        res['ronde1'] = r3['inGame'] == 'Test notitie speler 1' and r3['inOpslag'] == 'Test notitie speler 1'
        res['opgeruimd'] = r3['veldLeeg'] and r3['wrapDicht']

        print('\n4. TWEE SPELERS — elk zijn eigen notitie')
        await verse(page)
        r4 = await page.evaluate("""() => {
            nav('setup');
            if (!player2Visible) togglePlayer2();
            sel.track='Airborne'; sel.gender='Heren'; sel.tee='Blauw';
            sel2.gender='Heren'; sel2.tee='Blauw';
            document.getElementById('iName').value='Mark';
            document.getElementById('iHcp').value='30.7';
            document.getElementById('iName2').value='Jan';
            document.getElementById('iHcp2').value='18.0';
            zetStartNote(1, 'Notitie van Mark');
            zetStartNote(2, 'Notitie van Jan');
            startRound();
            const cb=document.getElementById('confirmModalBtn');
            if(cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            saveActiveRound(true);
            const alle = loadSavedRounds();
            return { mark: (alle.find(r => r.player === 'Mark') || {}).note,
                     jan: (alle.find(r => r.player === 'Jan') || {}).note };
        }""")
        for k, v in r4.items(): print(f'   {k:<6} {v!r}')
        res['tweeSpelers'] = r4['mark'] == 'Notitie van Mark' and r4['jan'] == 'Notitie van Jan'

        print('\n5. HERPLANNEN — notities komen mee')
        r5 = await page.evaluate("""() => {
            // de twee zojuist gemaakte rondes terugzetten naar 'gepland'
            const alle = loadSavedRounds();
            alle.forEach(r => { (r.holes||[]).forEach(h => h.score = null); r.started = true; });
            setRoundsAndMark(JSON.stringify(alle));
            game = { started: false, holes: [] };
            const doel = loadSavedRounds().find(r => r.player === 'Mark');
            herplanRonde(doel.id);
            return { veld1: document.getElementById('startNote1').value,
                     veld2: document.getElementById('startNote2').value,
                     wrap1Open: !document.getElementById('noteWrap1').classList.contains('hidden'),
                     wrap2Open: !document.getElementById('noteWrap2').classList.contains('hidden') };
        }""")
        for k, v in r5.items(): print(f'   {k:<12} {v!r}')
        res['herplanNotities'] = r5['veld1'] == 'Notitie van Mark' and r5['veld2'] == 'Notitie van Jan'
        res['herplanOpen'] = r5['wrap1Open'] and r5['wrap2Open']

        print('\n6. HERPLANNEN ANNULEREN — velden leeg, geen doorlekken')
        r6 = await page.evaluate("""() => {
            annuleerHerplan();
            return { veld1: document.getElementById('startNote1').value,
                     veld2: document.getElementById('startNote2').value,
                     dicht1: document.getElementById('noteWrap1').classList.contains('hidden') };
        }""")
        for k, v in r6.items(): print(f'   {k:<8} {v!r}')
        res['annuleren'] = r6['veld1'] == '' and r6['veld2'] == '' and r6['dicht1']

        print('\n7. GRENS VAN 200 TEKENS')
        r7 = await page.evaluate("""() => {
            const veld = document.getElementById('startNote1');
            return { maxlength: veld.getAttribute('maxlength'),
                     naLangeInvoer: (() => { zetStartNote(1, 'x'.repeat(300)); return leesStartNote(1).length; })() };
        }""")
        for k, v in r7.items(): print(f'   {k:<16} {v}')
        res['grens'] = r7['maxlength'] == '200' and r7['naLangeInvoer'] == 200


        print('\n8. TWEEDE TIK OP DE KNOP — leesstand, niet inklappen')
        await verse(page)
        r8 = await page.evaluate("""() => {
            nav('setup');
            const knop = document.getElementById('noteBtn1');
            const wrap = document.getElementById('noteWrap1');
            const veld = document.getElementById('startNote1');
            const uit = [];
            knop.click();                                  // dicht -> bewerken
            uit.push({ stap: 'na 1e tik (leeg)', open: !wrap.classList.contains('hidden'), lezen: veld.readOnly });
            veld.value = 'Clubcompetitie'; groeiStartNote(veld);
            knop.click();                                  // gevuld -> lezen
            uit.push({ stap: 'na 2e tik (gevuld)', open: !wrap.classList.contains('hidden'), lezen: veld.readOnly });
            knop.click();                                  // lezen -> bewerken
            uit.push({ stap: 'na 3e tik', open: !wrap.classList.contains('hidden'), lezen: veld.readOnly });
            return uit;
        }""")
        for x in r8: print(f"   {x['stap']:<22} zichtbaar: {str(x['open']):<6} leesstand: {x['lezen']}")
        res['leesstand'] = (r8[0]['open'] and not r8[0]['lezen'] and
                            r8[1]['open'] and r8[1]['lezen'] and
                            r8[2]['open'] and not r8[2]['lezen'])

        print('\n9. LEEG VELD KLAPT WEL DICHT')
        r9 = await page.evaluate("""() => {
            const knop = document.getElementById('noteBtn1');
            const wrap = document.getElementById('noteWrap1');
            const veld = document.getElementById('startNote1');
            veld.value = '';
            knop.click();
            return { dicht: wrap.classList.contains('hidden') };
        }""")
        print(f"   leeg veld klapt dicht: {r9['dicht']}")
        res['leegDicht'] = r9['dicht']

        print('\n10. HOOGTE NA HERPLANNEN (veld gevuld terwijl scherm verborgen was)')
        r10 = await page.evaluate("""() => {
            nav('archive');
            zetStartNote(1, 'Notitie die bij herplannen meekomt');
            nav('setup');
            const veld = document.getElementById('startNote1');
            const h = Math.round(veld.getBoundingClientRect().height);
            return { hoogte: h, scrollHeight: veld.scrollHeight, past: h >= veld.scrollHeight - 2,
                     lezen: veld.readOnly };
        }""")
        for k, v in r10.items(): print(f'   {k:<14} {v}')
        res['hoogteNaHerplan'] = r10['past']
        res['herplanLeesstand'] = r10['lezen']


        print('\n11. KLEUR VAN HET POTLOOD — alleen goud tijdens bewerken')
        await verse(page)
        r11 = await page.evaluate("""() => {
            nav('setup');
            const knop = document.getElementById('noteBtn1');
            const veld = document.getElementById('startNote1');
            const goud = () => (knop.style.color || '').includes('gold');
            const uit = {};
            uit.dichtLeeg = goud();
            knop.click();                         uit.openBewerken = goud();
            veld.value = 'Test'; knop.click();    uit.leesstand = goud();
            knop.click();                         uit.weerBewerken = goud();
            veld.value = ''; knop.click();        uit.leeggemaaktDicht = goud();
            return uit;
        }""")
        for k, v in r11.items(): print(f'   {k:<20} goud: {v}')
        res['potloodKleur'] = (not r11['dichtLeeg'] and r11['openBewerken'] and
                               not r11['leesstand'] and r11['weerBewerken'] and
                               not r11['leeggemaaktDicht'])

        alles = all(res.values())
        print('\n' + ('GEEN FOUTEN' if alles and not fouten else
                      '1 FOUT(EN): ' + ', '.join(k for k, v in res.items() if not v)))
        if fouten: print('browserfouten:', fouten)
        await b.close()

asyncio.run(main())
