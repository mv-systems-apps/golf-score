"""Oefenronde (1352901-001): een ronde die nergens meetelt, ook niet in de baananalyse.
- Instelling Oefenrondes (standaard uit) toont op Start de schakelaar Oefenronde; aan zet
  hem Qualifying uit en vast. De ronde krijgt oefen: true en is niet-qualifying; daarna
  staat de schakelaar weer uit.
- Ronde bewerken (één speler en twee spelers): Oefenronde aan/uit; aan zet Q uit en vast,
  uit geeft de vorige Q-stand terug.
- Telt niet mee: niet in meetelFilter (handicap, statistiek), niet in de baananalyse.
- Op de rondekaart de badge O; in de legenda bij Symbolen.
- Inlezen: oefen blijft, en is dan altijd niet-qualifying.
- 'Verwijder niet-qualifying en oefenrondes' neemt ze mee.
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

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 780})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        wacht = lambda: pg.wait_for_timeout(200)

        print("\n=== START ===")
        await pg.evaluate("nav('setup')"); await wacht()
        check("instelling standaard uit: op Start geen schakelaar Oefenronde",
              await pg.evaluate("() => [localStorage.getItem('golf_oefenrondes'), !!document.getElementById('oefenRow')?.offsetParent]"), [None, False])
        await pg.evaluate("() => { nav('settings'); const c = document.getElementById('oefenrondesToggle'); c.checked = true; c.dispatchEvent(new Event('change')); nav('setup'); }"); await wacht()
        check("instelling aan: de schakelaar staat er, uit", await pg.evaluate("() => [!!document.getElementById('oefenRow')?.offsetParent, document.getElementById('oefenToggle').checked]"), [True, False])
        await pg.evaluate("() => { const q = document.getElementById('qualifyToggle1'); if (!q.checked) { q.checked = true; q.dispatchEvent(new Event('change')); } }")
        await pg.evaluate("() => { const t = document.getElementById('oefenToggle'); t.checked = true; t.dispatchEvent(new Event('change')); }"); await wacht()
        check("Oefenronde aan: Qualifying uit en vast", await pg.evaluate("() => { const q = document.getElementById('qualifyToggle1'); return [q.checked, q.disabled]; }"), [False, True])
        await pg.evaluate("() => { const t = document.getElementById('oefenToggle'); t.checked = false; t.dispatchEvent(new Event('change')); }"); await wacht()
        check("weer uit: Qualifying terug zoals hij stond, en vrij", await pg.evaluate("() => { const q = document.getElementById('qualifyToggle1'); return [q.checked, q.disabled]; }"), [True, False])
        await pg.evaluate("() => { const t = document.getElementById('oefenToggle'); t.checked = true; t.dispatchEvent(new Event('change')); }")
        await pg.click('#startRoundBtn'); await pg.wait_for_timeout(350)
        await pg.evaluate("() => { const b = document.getElementById('confirmModalBtn'); if (b && !document.getElementById('confirmModal').classList.contains('hidden')) b.click(); }"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => { const id = localStorage.getItem('golf_active_id'); const r = loadSavedRounds().find(x => String(x.id) === id); return [r.oefen, r.qualifying]; }")
        check("gestart als oefenronde: oefen true, niet qualifying", r, [True, False])
        await pg.evaluate("nav('setup')"); await wacht()
        check("na het starten staat de schakelaar weer uit", await pg.evaluate("() => document.getElementById('oefenToggle').checked"), False)
        await pg.evaluate("() => { nav('archive'); }"); await wacht()
        check("op de kaart van de oefenronde de badge O", await pg.evaluate("() => document.querySelectorAll('#screen-archive .tee-badge.badge-o').length >= 1"), True)
        check("in de legenda bij Symbolen", await pg.evaluate("() => [...document.querySelectorAll('#screen-settings .tee-badge.badge-o')].length"), 1)
        await pg.evaluate("() => finishActiveRound(null)"); await wacht()

        print("\n=== BEWERKEN, METELLEN EN BAANANALYSE ===")
        # een afgeronde qualifying ronde van de hoofdspeler die meetelt
        info = await pg.evaluate("""() => { const f = meetelFilter(startPlayerName()); const lijst = loadSavedRounds();
            const i = lijst.findIndex(f); const r = lijst[i];
            return {i, id: String(r.id), club: r.club, track: r.track, ca: JSON.stringify(courseAnalysisData(r.club, r.track))}; }""")
        check("er is een meetellende ronde om mee te proberen", info['i'] >= 0, True)
        await pg.evaluate("(i) => doOpenRoundInfoModal(i)", info['i']); await wacht()
        check("Ronde bewerken: Oefenronde uit, Q aan", await pg.evaluate("() => [document.getElementById('editOefenToggle').checked, document.getElementById('editQualifyToggle').checked]"), [False, True])
        await pg.evaluate("() => { const t = document.getElementById('editOefenToggle'); t.checked = true; t.dispatchEvent(new Event('change')); }")
        check("Oefenronde aan: Q uit en vast", await pg.evaluate("() => { const q = document.getElementById('editQualifyToggle'); return [q.checked, q.disabled]; }"), [False, True])
        await pg.evaluate("() => confirmRoundInfo()"); await wacht()
        na = await pg.evaluate("""(inf) => { const r = loadSavedRounds().find(x => String(x.id) === inf.id);
            return {oefen: r.oefen, q: r.qualifying, telt: loadSavedRounds().filter(meetelFilter(startPlayerName())).some(x => String(x.id) === inf.id),
              ca: JSON.stringify(courseAnalysisData(inf.club, inf.track))}; }""", info)
        check("opgeslagen als oefenronde, niet qualifying", [na['oefen'], na['q']], [True, False])
        check("telt niet meer mee (handicap, statistiek)", na['telt'], False)
        check("de baananalyse van die baan is veranderd (de ronde telt daar niet meer)", na['ca'] != info['ca'], True)
        idx = await pg.evaluate("(id) => loadSavedRounds().findIndex(x => String(x.id) === id)", info['id'])
        await pg.evaluate("(i) => doOpenRoundInfoModal(i)", idx); await wacht()
        await pg.evaluate("() => { const t = document.getElementById('editOefenToggle'); t.checked = false; t.dispatchEvent(new Event('change')); const q = document.getElementById('editQualifyToggle'); q.checked = true; confirmRoundInfo(); }"); await wacht()
        terug = await pg.evaluate("(inf) => { const r = loadSavedRounds().find(x => String(x.id) === inf.id); return ['oefen' in r, r.qualifying, JSON.stringify(courseAnalysisData(inf.club, inf.track)) === inf.ca]; }", info)
        check("Oefenronde weer uit: geen veld oefen, qualifying, de baananalyse weer als eerst", terug, [False, True, True])

        print("\n=== WAAR DE SCHAKELAAR STAAT ===")
        # instelling uit
        await pg.evaluate("() => localStorage.setItem('golf_oefenrondes', 'off')")
        ZICHT = "() => !!document.getElementById('editOefenRow').offsetParent"
        SLUIT = "() => closeRoundInfoModal()"
        i_gewoon = await pg.evaluate("() => loadSavedRounds().findIndex(r => isRondeAf(r) && !isOefenRonde(r))")
        await pg.evaluate("(i) => doOpenRoundInfoModal(i, false)", i_gewoon); await wacht()
        check("instelling uit, via Rondes: Oefenronde staat er", await pg.evaluate(ZICHT), True)
        await pg.evaluate(SLUIT)
        # via het scorescherm: het keuzemenu en dan Ronde bewerken (en de vraag bij een afgeronde ronde)
        await pg.evaluate("""(i) => { openRoundEditChoice(i, true); document.getElementById('roundEditChoiceInfo').click();
            const b = document.getElementById('confirmModalBtn'); if (b && !document.getElementById('confirmModal').classList.contains('hidden')) b.click(); }""", i_gewoon); await wacht()
        check("instelling uit, via het scorescherm: geen Oefenronde", await pg.evaluate("() => [!document.getElementById('roundInfoModal').classList.contains('hidden'), !!document.getElementById('editOefenRow').offsetParent]"), [True, False])
        await pg.evaluate(SLUIT)
        await pg.evaluate("() => localStorage.setItem('golf_oefenrondes', 'on')")
        await pg.evaluate("(i) => doOpenRoundInfoModal(i, true)", i_gewoon); await wacht()
        check("instelling aan, via het scorescherm: Oefenronde staat er", await pg.evaluate(ZICHT), True)
        await pg.evaluate(SLUIT)
        await pg.evaluate("() => localStorage.setItem('golf_oefenrondes', 'off')")
        i_oefen = await pg.evaluate("() => { const l = loadSavedRounds(); const i = l.findIndex(r => isRondeAf(r) && !isOefenRonde(r)); l[i].oefen = true; l[i].qualifying = false; setRoundsAndMark(JSON.stringify(l)); return i; }")
        await pg.evaluate("(i) => doOpenRoundInfoModal(i, true)", i_oefen); await wacht()
        check("instelling uit, al een oefenronde, via het scorescherm: Oefenronde staat er (aan)", await pg.evaluate("() => [!!document.getElementById('editOefenRow').offsetParent, document.getElementById('editOefenToggle').checked]"), [True, True])
        await pg.evaluate("() => confirmRoundInfo()"); await wacht()
        check("…en opslaan zonder iets te wijzigen houdt hem oefenronde", await pg.evaluate("(i) => loadSavedRounds()[i].oefen", i_oefen), True)
        await pg.evaluate("() => localStorage.setItem('golf_oefenrondes', 'on')")

        print("\n=== VENSTERS NEMEN NIETS OVER VAN HET VORIGE (review) ===")
        # een oefenronde openen en annuleren, dan een qualifying ronde: Q aan en vrij, opslaan houdt hem qualifying
        i_q = await pg.evaluate("() => loadSavedRounds().findIndex(r => isRondeAf(r) && r.qualifying && !isOefenRonde(r))")
        await pg.evaluate("(i) => { doOpenRoundInfoModal(i, false); closeRoundInfoModal(); }", i_oefen)
        await pg.evaluate("(i) => doOpenRoundInfoModal(i, false)", i_q); await wacht()
        check("na een oefenronde een qualifying ronde openen: Q aan en vrij", await pg.evaluate("() => { const q = document.getElementById('editQualifyToggle'); return [q.checked, q.disabled]; }"), [True, False])
        await pg.evaluate("() => confirmRoundInfo()"); await wacht()
        check("…en opslaan zonder iets te wijzigen houdt hem qualifying", await pg.evaluate("(i) => loadSavedRounds()[i].qualifying", i_q), True)
        # Oefenronde aanzetten en annuleren, dan een niet-qualifying ronde: Oefenronde uitzetten laat Q uit
        i_nq = await pg.evaluate("() => loadSavedRounds().findIndex(r => isRondeAf(r) && !r.qualifying && !isOefenRonde(r))")
        if i_nq >= 0:
            await pg.evaluate("(i) => { doOpenRoundInfoModal(i, false); const t = document.getElementById('editOefenToggle'); t.checked = true; t.dispatchEvent(new Event('change')); closeRoundInfoModal(); }", i_q)
            await pg.evaluate("(i) => { doOpenRoundInfoModal(i, false); const t = document.getElementById('editOefenToggle'); t.checked = true; t.dispatchEvent(new Event('change')); t.checked = false; t.dispatchEvent(new Event('change')); }", i_nq)
            check("een niet-qualifying ronde: Oefenronde aan en weer uit laat Q uit", await pg.evaluate("() => document.getElementById('editQualifyToggle').checked"), False)
            await pg.evaluate(SLUIT)
        # Start: Oefenronde aan, een lus en terug (herstelQualifyingNaLus): Q blijft uit en vast
        check("Start, Oefenronde aan, terug van een lus: Q uit en vast", await pg.evaluate("""() => { nav('setup'); sel.qualifying = true; sel.oefen = true; toonOefenOpStart();
            zetQualifyingUitVoorLus(); herstelQualifyingNaLus(); const q = document.getElementById('qualifyToggle1'); const uit = [q.checked, q.disabled];
            sel.oefen = false; toonOefenOpStart(); return uit; }"""), [False, True])

        print("\n=== TWEE SPELERS ===")
        # twee afgeronde rondes op één moment zetten, de tweede van een medespeler
        paar = await pg.evaluate("""() => { const l = loadSavedRounds(); const af = l.filter(r => isRondeAf(r) && !isOefenRonde(r));
            const [a, m] = [af[af.length - 1], af[af.length - 2]]; m.date = a.date; m.time = a.time; m.player = 'Medespeler';
            setRoundsAndMark(JSON.stringify(l)); return [String(a.id), String(m.id)]; }""")
        check("er is een ronde met twee spelers", paar is not None, True)
        if paar:
            await pg.evaluate("() => localStorage.setItem('golf_oefenrondes', 'off')")
            await pg.evaluate("(ids) => openRondesBewerken(ids)", paar); await wacht()
            check("twee spelers (alleen via het scorescherm), instelling uit: geen Oefenronde", await pg.evaluate("() => !!document.getElementById('rbOefenRow').offsetParent"), False)
            await pg.evaluate("() => sluitRondesBewerken()")
            await pg.evaluate("() => localStorage.setItem('golf_oefenrondes', 'on')")
            await pg.evaluate("(ids) => openRondesBewerken(ids)", paar); await wacht()
            check("twee spelers, instelling aan: Oefenronde (beide) staat er", await pg.evaluate("() => !!document.getElementById('rbOefenRow').offsetParent"), True)
            await pg.evaluate("() => { const t = document.getElementById('rbOefen'); t.checked = true; t.dispatchEvent(new Event('change')); }")
            check("twee spelers, Oefenronde aan: beide Q uit en vast", await pg.evaluate("() => ['rbQ1', 'rbQ2'].map(id => [document.getElementById(id).checked, document.getElementById(id).disabled])"), [[False, True], [False, True]])
            await pg.evaluate("() => bevestigRondesBewerken()"); await wacht()
            check("beide rondes oefenronde", await pg.evaluate("(ids) => loadSavedRounds().filter(r => ids.includes(String(r.id))).map(r => [r.oefen, r.qualifying])", paar), [[True, False], [True, False]])
            # een gemengd paar (één ronde los gemarkeerd in Rondes): Opslaan zonder omzetten houdt ieder zijn stand
            await pg.evaluate("""(ids) => { const l = loadSavedRounds(); const [a, m] = ids.map(id => l.find(r => String(r.id) === id));
                delete a.oefen; a.qualifying = true; setRoundsAndMark(JSON.stringify(l)); }""", paar)
            await pg.evaluate("(ids) => openRondesBewerken(ids)", paar); await wacht()
            check("gemengd paar: Oefenronde (beide) uit, Q zoals per ronde", await pg.evaluate("() => [document.getElementById('rbOefen').checked, document.getElementById('rbQ1').checked, document.getElementById('rbQ1').disabled]"), [False, True, False])
            await pg.evaluate("() => bevestigRondesBewerken()"); await wacht()
            check("gemengd paar, opslaan zonder omzetten: ieder houdt zijn stand", await pg.evaluate("(ids) => ids.map(id => { const r = loadSavedRounds().find(x => String(x.id) === id); return [!!r.oefen, r.qualifying]; })", paar), [[False, True], [True, False]])

        print("\n=== INLEZEN EN VERWIJDEREN ===")
        imp = await pg.evaluate("""() => { const r = JSON.parse(JSON.stringify(loadSavedRounds().find(isRondeAf))); r.oefen = true; r.qualifying = true;
            const e = buildImportEntry(r, new Set(), true); const r2 = JSON.parse(JSON.stringify(r)); delete r2.oefen; const e2 = buildImportEntry(r2, new Set(), true);
            return [e.oefen, e.qualifying, 'oefen' in e2]; }""")
        check("inlezen: oefen blijft en is niet-qualifying; zonder oefen geen veld", imp, [True, False, False])
        await pg.evaluate("() => { nav('settings'); switchSettingsTab('data'); }"); await wacht()
        tekst = await pg.evaluate("() => [document.getElementById('purgeNonQBtn').textContent.trim(), Number(document.getElementById('nonQCount').textContent)]")
        check("de knop heet 'Verwijder niet-qualifying en oefenrondes'", tekst[0], 'Verwijder niet-qualifying en oefenrondes')
        n_oefen = await pg.evaluate("() => loadSavedRounds().filter(isOefenRonde).length")
        check("er staan oefenrondes", n_oefen >= 3, True)
        await pg.evaluate("() => { const k = document.getElementById('purgeNonQBtn'); k.click(); k.click(); }"); await wacht()
        await pg.evaluate("() => { const b = [...document.querySelectorAll('button')].find(b => b.offsetParent && /^Verwijderen$/.test(b.textContent.trim())); if (b) b.click(); }"); await wacht()
        check("na verwijderen: geen oefenrondes meer (behalve een lopende)", await pg.evaluate("() => loadSavedRounds().filter(r => isOefenRonde(r) && !isLopendeRonde(r)).length"), 0)
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
