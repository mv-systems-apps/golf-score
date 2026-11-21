"""Scherm aan houden per ronde en per dag (1352901-001).
- Afronden of pauzeren zet het uit; stond het aan, dan onthoudt Golf welke ronde en welke dag.
- Dezelfde ronde dezelfde dag hervat: weer aan, met de balk 'Scherm blijft aan' en Uitzetten.
  De balk verdwijnt bij Uitzetten (scherm uit) of bij de eerste score (scherm blijft aan).
- Een andere ronde hervatten, of een andere dag: uit, geen balk.
- De volgende dag staat het uit, ook met een lopende ronde (de app stond de nacht open).
Het scherm zelf is hier niet te zien: een nagebootste navigator.wakeLock telt de sloten.
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

NEP_SLOT = """() => {
  window.__slot = {vast: 0};
  Object.defineProperty(navigator, 'wakeLock', {configurable: true, value: {
    request: async (soort) => { window.__slot.vast++; const l = [];
      return { type: soort, released: false, addEventListener: (n, f) => { if (n === 'release') l.push(f); },
        release: async function() { if (this.released) return; this.released = true; window.__slot.vast--; l.forEach(f => f()); } }; } } });
}"""
# [instelling aan, schakelaar aan, balk zichtbaar, slot vast]
STAND = """() => [localStorage.getItem('golf_scherm_aan') === 'on', document.getElementById('schermAanToggle').checked,
  !document.getElementById('schermAanBalk')?.classList.contains('hidden') && !!document.getElementById('schermAanBalk')?.offsetParent, window.__slot.vast]"""
ZET_AAN = "() => { const c = document.getElementById('schermAanToggle'); c.checked = true; c.dispatchEvent(new Event('change')); nav('score'); }"
PAUZEER = "() => { const id = localStorage.getItem('golf_active_id'); finishActiveRound(null); return id; }"
HERVAT = "(id) => { nav('archive'); const i = loadSavedRounds().findIndex(r => String(r.id) === id); loadRoundSingle(i); nav('score'); }"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 780})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        await pg.evaluate(NEP_SLOT)
        wacht = lambda: pg.wait_for_timeout(150)
        # een ronde starten
        await pg.evaluate("nav('setup')"); await pg.click('#startRoundBtn'); await pg.wait_for_timeout(350)
        await pg.evaluate("() => { const b = document.getElementById('confirmModalBtn'); if (b && !document.getElementById('confirmModal').classList.contains('hidden')) b.click(); }")
        await pg.wait_for_timeout(300)
        await pg.evaluate(ZET_AAN); await wacht()
        check("aangezet tijdens de ronde: aan, geen balk, een slot", await pg.evaluate(STAND), [True, True, False, 1])
        id1 = await pg.evaluate(PAUZEER); await wacht()
        check("pauzeren: uit, schakelaar uit, slot eraf", await pg.evaluate(STAND), [False, False, False, 0])
        await pg.evaluate(HERVAT, id1); await wacht()
        check("dezelfde ronde dezelfde dag hervat: weer aan, met de balk en een slot", await pg.evaluate(STAND), [True, True, True, 1])
        check("de balk: 'Scherm blijft aan' met de knop Uitzetten", await pg.evaluate("() => { const b = document.getElementById('schermAanBalk'); return [/Scherm blijft aan/.test(b.textContent), [...b.querySelectorAll('button')].map(k => k.textContent.trim())]; }"), [True, ['Uitzetten']])
        await pg.evaluate("() => document.querySelector('#schermAanBalk button').click()"); await wacht()
        check("Uitzetten: uit, balk weg, slot eraf", await pg.evaluate(STAND), [False, False, False, 0])
        # nog eens: nu verdwijnt de balk bij de eerste score, het scherm blijft aan
        await pg.evaluate(ZET_AAN); await wacht(); await pg.evaluate(PAUZEER); await wacht(); await pg.evaluate(HERVAT, id1); await wacht()
        await pg.evaluate("() => stepScore(currentHole, +1)"); await wacht()
        check("de eerste score na hervatten: de balk weg, het scherm blijft aan", await pg.evaluate(STAND), [True, True, False, 1])
        # Gereed (via de kaart in Rondes): ook uit
        await pg.evaluate("() => { nav('archive'); const k = document.querySelector('#screen-archive button[onclick^=\"saveAndClearActiveRound\"]'); k.click(); k.click(); }"); await wacht()
        check("pauzeren via de kaart in Rondes: uit, slot eraf", await pg.evaluate(STAND), [False, False, False, 0])
        # een andere ronde hervatten: blijft uit
        ander = await pg.evaluate("(id) => String(loadSavedRounds().find(r => String(r.id) !== id).id)", id1)
        await pg.evaluate(HERVAT, ander); await wacht()
        check("een andere ronde hervat: uit, geen balk", await pg.evaluate(STAND), [False, False, False, 0])
        # dezelfde ronde, maar een andere dag: uit
        await pg.evaluate(HERVAT, id1); await wacht(); await pg.evaluate(ZET_AAN); await wacht(); await pg.evaluate(PAUZEER); await wacht()
        await pg.evaluate("() => { const h = JSON.parse(localStorage.getItem('golf_scherm_aan_hervat')); h.dag = '2000-01-01'; localStorage.setItem('golf_scherm_aan_hervat', JSON.stringify(h)); }")
        await pg.evaluate(HERVAT, id1); await wacht()
        check("dezelfde ronde, een andere dag hervat: uit, geen balk", await pg.evaluate(STAND), [False, False, False, 0])
        # de volgende dag met een lopende ronde (de app stond de nacht open): uit
        await pg.evaluate(ZET_AAN); await wacht()
        check("aan met een lopende ronde", await pg.evaluate(STAND), [True, True, False, 1])
        await pg.evaluate("""() => { localStorage.setItem('golf_scherm_aan_dag', '2000-01-01');
            Object.defineProperty(document, 'hidden', {configurable: true, get: () => false}); document.dispatchEvent(new Event('visibilitychange')); }"""); await wacht()
        check("terug in de app op een volgende dag: uit, slot eraf", await pg.evaluate(STAND), [False, False, False, 0])
        print("  -- review --")
        # A aan, B laden (A gepauzeerd en onthouden), B pauzeren, A hervatten: weer aan
        await pg.evaluate("() => { if (game.started) finishActiveRound(null); }"); await wacht()
        await pg.evaluate(HERVAT, id1); await wacht(); await pg.evaluate(ZET_AAN); await wacht()
        await pg.evaluate(HERVAT, ander); await wacht()
        check("A aan, dan B geladen: uit", await pg.evaluate(STAND), [False, False, False, 0])
        await pg.evaluate(PAUZEER); await wacht(); await pg.evaluate(HERVAT, id1); await wacht()
        check("B gepauzeerd, A dezelfde dag hervat: weer aan met de balk", await pg.evaluate(STAND), [True, True, True, 1])
        # een nieuwe ronde starten terwijl A loopt met het scherm aan: de nieuwe begint uit, A onthouden
        await pg.evaluate("() => { nav('setup'); const t = document.getElementById('iTime'); t.value = '05:17'; t.dispatchEvent(new Event('change')); }")
        oud = await pg.evaluate("() => localStorage.getItem('golf_active_id')")
        await pg.click('#startRoundBtn'); await pg.wait_for_timeout(350)
        await pg.evaluate("() => { const b = document.getElementById('confirmModalBtn'); if (b && !document.getElementById('confirmModal').classList.contains('hidden')) b.click(); }"); await pg.wait_for_timeout(300)
        await pg.evaluate("nav('score')"); await wacht()
        check("er loopt een nieuwe ronde", await pg.evaluate("(oud) => !!game.started && localStorage.getItem('golf_active_id') !== oud", oud), True)
        check("nieuwe ronde gestart terwijl er een liep met het scherm aan: uit", await pg.evaluate(STAND), [False, False, False, 0])
        check("…en de gepauzeerde ronde onthouden", await pg.evaluate("(id) => JSON.parse(localStorage.getItem('golf_scherm_aan_hervat') || '{}').id === id", id1), True)
        # de lopende ronde verwijderen met het scherm aan: uit
        await pg.evaluate(ZET_AAN); await wacht()
        await pg.evaluate("() => clearActiveRound()"); await wacht()
        check("de lopende ronde weg (verwijderd): uit", await pg.evaluate("() => [localStorage.getItem('golf_scherm_aan') === 'on', window.__slot.vast]"), [False, 0])
        # koppel: het onthouden ging over de andere ronde van het koppel (matchId), toch weer aan
        paar = await pg.evaluate("""(id) => { const l = loadSavedRounds(); const a = l.find(r => String(r.id) === id); const m = l.find(r => String(r.id) !== id && r.player === a.player && isRondeAf(r));
            m.date = a.date; m.time = a.time; m.player = 'Medespeler'; setRoundsAndMark(JSON.stringify(l));
            localStorage.setItem('golf_scherm_aan_hervat', JSON.stringify({ id: String(m.id), dag: todayISO() })); return String(m.id); }""", id1)
        await pg.evaluate("([m, a]) => { const i = loadSavedRounds().findIndex(r => String(r.id) === a); loadRoundAsCouple(i, loadSavedRounds().find(r => String(r.id) === m).id); nav('score'); }", [paar, id1]); await wacht()
        check("koppel hervat, het onthouden ging over de andere ronde van het koppel: weer aan", await pg.evaluate(STAND), [True, True, True, 1])
        # om middernacht uit, ook zonder tik (er is een wekker)
        check("met het slot vast staat er een wekker voor middernacht", await pg.evaluate("() => _schermMiddernacht !== null"), True)
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
