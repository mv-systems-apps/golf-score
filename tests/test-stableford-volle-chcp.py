"""Playing handicap, wedstrijdpercentage en de stableford bij 100% (13527DA-145).

Speel je een wedstrijd met een percentage (bijvoorbeeld 85%), dan telt de stableford met die
wedstrijdbaanhandicap: de playing handicap (Rules of Handicapping, regel 6.2). Tot 13527DA-144
zag je daarna nergens dat er een percentage was gebruikt, noch hoeveel punten je met je volle
baanhandicap had gehaald; Gem. Stb en de nullers rekenden met de wedstrijdbaanhandicap.

De regels (keuzes van de gebruiker, variant B2):
  1. De ronde bewaart het wedstrijdpercentage (chcpPct) als de baanhandicap met het %-knopje
     is bepaald, niet bij 100%, niet als hij daarna met − of + is bijgesteld, en niet als het
     percentage niet meer klopt (na een wissel van index of tee).
  2. Wijkt de gespeelde baanhandicap af van de volle: rondekaart "Phcp 13 (85%)", of zonder
     bewaard percentage het verschil: "Phcp 13 (−2)". Anders "Chcp 15".
  3. Extra regel "Stb 24 · Chcp 15 (100%)" alleen bij een afgeronde qualifying ronde met een
     afwijkende baanhandicap. Overzicht: "Playing hcp (85%)", "Baanhandicap (Chcp)",
     "Stableford (STB)", "Stableford bij 100%". Gedeelde tekst: "Phcp (85%): 13", "Chcp: 15",
     "STB: 22", "STB bij 100%: 24".
  4. Niet-qualifying (teambaanhandicap): wel "Phcp", geen stableford bij 100%.
  5. Gem. Stb op Statistiek rekent met de volle baanhandicap.
  6. De keuring van een backup accepteert chcpPct (0 < pct < 100, of leeg) en weigert de rest.

Voorbeeld: Airborne blauw (CR 34,5, SR 120, par 36), index 30,7. Volle chcp: 15,35 × 120/113
− 1,5 = 14,80 → 15. 85% van 14,80 = 12,58 → 13. Elke hole een bogey: per hole slagen + 1
punt, dus met 13 slagen 22 punten en met 15 slagen 24.
"""
import asyncio, os, re, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.goto(app_url())
        await pg.evaluate("""(c) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', '[]');
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Testspeler'); localStorage.setItem('golf_profile_hcp', '30.7');
            localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); }""", CLUBS)
        await pg.reload(); await pg.wait_for_timeout(600)

        async def kies_pct(pct):
            await pg.click('#chcpPctBtn'); await pg.wait_for_timeout(200)
            await pg.locator('#choiceEditModal button', has_text=pct).first.click(); await pg.wait_for_timeout(100)
            await pg.evaluate("() => confirmChoiceEdit()"); await pg.wait_for_timeout(200)

        async def speel(datum, pct=None, plus=0, minus=0, qual=True, hcp=None):
            """Start een ronde met echte tikken op %, − en +, elke hole een bogey, en rond af."""
            await pg.evaluate("""([d, q]) => { nav('setup'); const i = document.getElementById('iDate'); i.value = d; onDateTimeChange();
                sel.track = 'Airborne'; sel.tee = 'Blauw'; sel.chcpOverride = null; sel.chcpPct = null; sel.qualifying = q; updateChcp(); }""", [datum, qual])
            if pct: await kies_pct(pct)
            for _ in range(minus): await pg.click('button.score-btn.minus[onclick="adjustChcp(-1)"]'); await pg.wait_for_timeout(50)
            for _ in range(plus): await pg.click('button.score-btn.plus[onclick="adjustChcp(1)"]'); await pg.wait_for_timeout(50)
            if hcp is not None:
                await pg.evaluate("(h) => { const i = document.getElementById('iHcp'); i.value = h; i.dispatchEvent(new Event('input')); i.dispatchEvent(new Event('change')); }", hcp)
                await pg.wait_for_timeout(200)
            notitie = await pg.evaluate("() => { const r = document.getElementById('chcpOverrideRow'); return r.classList.contains('hidden') ? '' : document.getElementById('chcpOverrideNote').textContent; }")
            await pg.evaluate("""() => { startRound(); const t = document.getElementById('confirmModalTitle')?.textContent;
                const cb = document.getElementById('confirmModalBtn'); if (cb && t !== 'Dubbele datum & tijd' && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
            await pg.wait_for_timeout(400)
            await pg.evaluate("() => { nav('score'); for (let i = 0; i < 9; i++) { setCurrentHole(i); stepScore(i, 1); } }")
            await pg.wait_for_timeout(300)
            await pg.evaluate("() => nav('stat')"); await pg.wait_for_timeout(300)
            info = await pg.evaluate("""() => { const k = [...document.querySelectorAll('#sumInfo .card')].find(c => /Resultaat/i.test(c.textContent));
                return k ? [...k.querySelectorAll('.sum-info-row')].map(r => [r.querySelector('.sum-info-label').textContent.trim(), r.querySelector('.sum-info-value').textContent.trim()]) : []; }""")
            opslag = await pg.evaluate("() => { const r = leesRondes().find(x => String(x.id) === localStorage.getItem('golf_active_id')); return [r.chcp, r.chcpPct ?? null, r.qualifying]; }")
            await pg.evaluate("() => finishActiveRound(null)"); await pg.wait_for_timeout(400)
            return opslag, dict(info), notitie

        async def kaart(datum):
            await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(400)
            return await pg.evaluate("""(d) => { const r = leesRondes().find(x => x.date === d); const e = r && document.getElementById('round-full-' + r.id);
                if (!e) return null; const m = [...e.querySelectorAll('.saved-meta')].map(x => x.textContent.replace(/\\s+/g, ' ').trim());
                return [m.find(t => /^[HD] · /.test(t)) || '', m.filter(t => /^Stb/.test(t)).map(t => t.replace(/ · Whs.*/, ''))]; }""", datum)
        async def tekst(datum):
            t = await pg.evaluate("(d) => buildScoreText(leesRondes().find(x => x.date === d))", datum)
            return [l for l in t.split('\n') if re.match(r'^(Phcp|Chcp|STB)', l)]

        print("\n=== 1. WEDSTRIJD MET 85% (HET %-KNOPJE) ===\n")
        opslag, info, notitie = await speel('2026-09-01', pct='85')
        check("startscherm: Handmatig aangepast · 85% van 15", notitie, 'Handmatig aangepast · 85% van 15')
        check("opgeslagen: chcp 13, percentage 85, qualifying", opslag, [13, 85, True])
        check("overzicht: playing hcp, volle chcp, beide stablefords",
              [info.get('Playing hcp (85%)'), info.get('Baanhandicap (Chcp)'), info.get('Stableford (STB)'), info.get('Stableford bij 100%')], ['13', '15', '22', '24'])
        check("rondekaart: Phcp 13 (85%) en de regel bij 100%", await kaart('2026-09-01'), ['H · Blauw · Phcp 13 (85%)', ['Stb 22', 'Stb 24 · Chcp 15 (100%)']])
        check("gedeelde tekst", await tekst('2026-09-01'), ['Phcp (85%): 13', 'Chcp: 15', 'STB: 22', 'STB bij 100%: 24'])

        print("\n=== 2. VOLLE BAANHANDICAP: NIETS EXTRA ===\n")
        opslag, info, _ = await speel('2026-09-02')
        check("opgeslagen: chcp 15, geen percentage", opslag, [15, None, True])
        check("overzicht: alleen Baanhandicap en Stableford", [info.get('Baanhandicap (Chcp)'), info.get('Stableford (STB)'), any(k.startswith('Playing') or 'bij 100%' in k for k in info)], ['15', '24', False])
        check("rondekaart: Chcp 15, geen regel bij 100%", await kaart('2026-09-02'), ['H · Blauw · Chcp 15', ['Stb 24']])
        check("gedeelde tekst", await tekst('2026-09-02'), ['Chcp: 15', 'STB: 24'])

        print("\n=== 3. MET − EN +: HET VERSCHIL ===\n")
        opslag, info, _ = await speel('2026-09-03', minus=2)
        check("opgeslagen: chcp 13, geen percentage", opslag, [13, None, True])
        check("rondekaart: Phcp 13 (−2)", await kaart('2026-09-03'), ['H · Blauw · Phcp 13 (−2)', ['Stb 22', 'Stb 24 · Chcp 15 (100%)']])
        check("overzicht: Playing hcp (−2)", info.get('Playing hcp (−2)'), '13')
        opslag, _, notitie = await speel('2026-09-04', pct='85', plus=1)
        check("85% en daarna +1: geen percentage meer, startscherm zegt alleen 'Handmatig aangepast'", [opslag, notitie], [[14, None, True], 'Handmatig aangepast'])
        check("rondekaart: Phcp 14 (−1)", (await kaart('2026-09-04'))[0], 'H · Blauw · Phcp 14 (−1)')

        print("\n=== 4. PERCENTAGE DAT NIET MEER KLOPT ===\n")
        # 85% bij index 30,7 (13), daarna de index naar 35,0: volle chcp 17,08 → 17, 85% → 15.
        # Blijft 13 staan, dan is dat geen 85% meer en mag het percentage niet in beeld of opslag.
        opslag, _, notitie = await speel('2026-09-05', pct='85', hcp='35')
        check("na een indexwissel geen onjuist percentage in de opslag", opslag[1] is None or opslag[0] == 15, True)
        check("en het startscherm noemt geen onjuist percentage", ('85%' not in notitie) or opslag[0] == 15, True)
        await pg.evaluate("() => { const i = document.getElementById('iHcp'); i.value = '30.7'; i.dispatchEvent(new Event('input')); i.dispatchEvent(new Event('change')); }")

        print("\n=== 5. NIET-QUALIFYING (TEAMBAANHANDICAP) ===\n")
        opslag, info, _ = await speel('2026-09-06', pct='50', qual=False)
        check("opgeslagen: chcp 7, percentage 50, niet-qualifying", opslag, [7, 50, False])
        check("rondekaart: Phcp 7 (50%), geen regel bij 100%", await kaart('2026-09-06'), ['H · Blauw · Phcp 7 (50%)', ['Stb 16']])
        check("overzicht: geen Stableford bij 100%", 'Stableford bij 100%' in info, False)

        print("\n=== 6. STATISTIEK: GEM. STB MET VOLLE BAANHANDICAP ===\n")
        await pg.evaluate("() => { nav('stat'); renderPlayerStats(); }"); await pg.wait_for_timeout(500)
        verwacht = await pg.evaluate("""() => { const q = leesRondes().filter(r => r.qualifying); return (q.reduce((s, r) => s + stbVol(r).stb, 0) / q.length).toFixed(1); }""")
        gespeeld = await pg.evaluate("() => { const q = leesRondes().filter(r => r.qualifying); return (q.reduce((s, r) => s + stbTotaal(r), 0) / q.length).toFixed(1); }")
        kpi = await pg.evaluate("() => { const t = document.getElementById('playerStats').innerText.replace(/\\s+/g, ' '); const m = t.match(/([0-9]+[.,][0-9]) Gem\\. Stb/i); return m ? m[1].replace(',', '.') : null; }")
        check("Gem. Stb is het gemiddelde met de volle baanhandicap", kpi, verwacht)
        check("en dat verschilt hier van het gespeelde gemiddelde", kpi != gespeeld, True)

        print("\n=== 7. OPSLAG EN KEURING ===\n")
        check("elk bewaard percentage klopt met de opgeslagen baanhandicap", await pg.evaluate("""() => leesRondes().filter(r => r.chcpPct != null).every(r => {
            const ruw = calcChcpOnafgerond(r.holes.length, r.CR, r.SR, r.holes.reduce((s, h) => s + h.par, 0), r.hcp); return percentageVan(r.chcp, r.chcpPct, ruw) === r.chcpPct; })"""), True)
        keur = await pg.evaluate("""() => { const r = leesRondes().find(x => x.date === '2026-09-01');
            const k = x => keurRonde(zetRondeRecht(x));   // zoals bij inlezen: eerst rechtzetten, dan keuren
            return [k({ ...r }), k({ ...r, chcpPct: 150 }), k({ ...r, chcpPct: '' }), k({ ...r, chcpPct: undefined }), k({ ...r, chcpPct: '85' }), zetRondeRecht({ ...r, chcpPct: '85' }).chcpPct]; }""")
        check("keuring: 85 goed, 150 geweigerd, leeg, ontbrekend en '85' als tekst goed (wordt 85)", [keur[0], keur[1] is not None, keur[2], keur[3], keur[4], keur[5]], [None, True, None, None, None, 85])
        check("baanhandicap als tekst geeft geen schijnverschil", await pg.evaluate("() => { const r = leesRondes().find(x => x.date === '2026-09-02'); return chcpAfwijking({ ...r, chcp: '15' }); }"), None)
        check("85% dat op dezelfde baanhandicap uitkomt: geen regel bij 100%", await pg.evaluate("""() => { const r = leesRondes().find(x => x.date === '2026-09-01');
            return stbBij100({ ...r, chcp: 15, chcpPct: 85 }); }"""), None)
        print("\n=== 8. SPELER 2: PERCENTAGE EN DAARNA EEN ANDERE TEE ===\n")
        # Speler 2 (index 20,0) kiest 85% op Geel, en wisselt daarna naar Blauw. De
        # baanhandicap blijft dan staan, maar is geen 85% van de baanhandicap op Blauw meer:
        # dan mag het percentage niet worden bewaard (review 13527DA-145).
        await pg.evaluate("""() => { nav('setup'); const i = document.getElementById('iDate'); i.value = '2026-09-07'; onDateTimeChange();
            sel.track = 'Airborne'; sel.tee = 'Blauw'; sel.chcpOverride = null; sel.chcpPct = null; sel.qualifying = true;
            if (!player2Visible) togglePlayer2(); document.getElementById('iName2').value = 'Jan'; const h = document.getElementById('iHcp2'); h.value = '20';
            h.dispatchEvent(new Event('input')); sel2.tee = 'Geel'; sel2.chcpOverride = null; sel2.chcpPct = null; sel2.qualifying = true; buildTeeButtonsSpeler2(); updateChcpSpeler2(); }""")
        await pg.wait_for_timeout(300)
        await pg.click('#chcp2PctBtn'); await pg.wait_for_timeout(200)
        await pg.locator('#choiceEditModal button', has_text='85').first.click(); await pg.wait_for_timeout(100)
        await pg.evaluate("() => confirmChoiceEdit()"); await pg.wait_for_timeout(200)
        voor = await pg.evaluate("() => [sel2.chcpOverride, sel2.chcpPct, document.getElementById('chcp2OverrideNote').textContent]")
        await pg.locator('#teeBtns2 button[data-tee="Blauw"]').click(); await pg.wait_for_timeout(200)
        na = await pg.evaluate("() => [sel2.chcpOverride, calcChcpAutoSpeler2(20), document.getElementById('chcp2OverrideNote').textContent]")
        await pg.evaluate("""() => { startRound(); const t = document.getElementById('confirmModalTitle')?.textContent;
            const cb = document.getElementById('confirmModalBtn'); if (cb && t !== 'Dubbele datum & tijd' && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
        await pg.wait_for_timeout(400)
        r2 = await pg.evaluate("() => { const r = leesRondes().find(x => x.player === 'Jan'); return r ? [r.tee, r.chcp, r.chcpPct ?? null] : null; }")
        print('    voor de wissel', voor, '· na de wissel', na, '· opgeslagen', r2)
        check("speler 2 op Geel met 85%: het startscherm noemt 85%", '85%' in (voor[2] or ''), True)
        klopt = r2 is not None and (r2[2] is None or await pg.evaluate("(c) => percentageVan(c, 85, calcChcpOnafgerond(9, 34.5, 120, 36, 20)) === 85", r2[1]))
        check("na de wissel naar Blauw: geen onjuist percentage in de opslag", klopt, True)
        check("en het startscherm noemt dan geen onjuist percentage", ('85%' not in na[2]) or (na[0] == round(na[1] * 0.85)), True)
        await pg.evaluate("() => { finishActiveRound(null); }")

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
