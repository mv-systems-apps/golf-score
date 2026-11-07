"""
13528F3-001
1. Scherm aan houden (Instellingen, Tijdens de ronde; standaard uit): zolang het
   Score-scherm een lopende ronde toont, houdt Golf een schermslot (Wake Lock) vast.
   Ander scherm, ronde klaar of de app naar de achtergrond: het slot gaat eraf; terug op
   het Score-scherm komt het terug. Zonder de instelling nooit een slot.
   Het echte uitblijven van het scherm is alleen op een toestel te zien: hier staat een
   nagebootste navigator.wakeLock die telt.
2. De hoofdknoppen (btn-primary en btn-main) en de gekozen knop in een rij keuzes zijn
   goud met donkere tekst; de gekozen via de klasse 'gekozen', nergens een eigen gouden
   vlak op het element. De andere knoppen in die rij hebben de gewone vulling.
3. Alleen Pauzeren/Gereed/Sluiten onder de scores heeft een gouden rand, met de vulling
   van een gewone knop en de gewone tekstkleur (13528F3-002).
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testdata
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

NEP_SLOT = """() => {
  window.__slot = {gevraagd: 0, los: 0, vast: 0};
  Object.defineProperty(navigator, 'wakeLock', {configurable: true, value: {
    request: async (soort) => {
      window.__slot.gevraagd++; window.__slot.vast++;
      const luister = [];
      return { type: soort, released: false,
        addEventListener: (n, f) => { if (n === 'release') luister.push(f); },
        release: async function() { if (this.released) return; this.released = true; window.__slot.los++; window.__slot.vast--; luister.forEach(f => f()); } };
    } } });
}"""
STAND = "() => ({...window.__slot})"

async def main():
    fouten = []
    def check(naam, kreeg, verwacht):
        ok = kreeg == verwacht
        print(('  ok   ' if ok else '  FOUT ') + naam + ('' if ok else f'  — kreeg {kreeg!r}, verwacht {verwacht!r}'))
        if not ok: fouten.append(naam)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 780})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        await pg.evaluate(NEP_SLOT)

        print("\n=== 1. SCHERM AAN HOUDEN ===\n")
        check("de schakelaar staat bovenaan Tijdens de ronde, standaard uit", await pg.evaluate("""() => { nav('settings');
            const kop = [...document.querySelectorAll('#screen-settings .groep-kop')].find(k => /Tijdens de ronde/.test(k.textContent));
            const kaart = kop.nextElementSibling; return [!!kaart.querySelector('#schermAanToggle'), /Scherm aan houden/.test(kaart.textContent), document.getElementById('schermAanToggle').checked]; }"""), [True, True, False])
        # een ronde starten, instelling uit
        await pg.evaluate("nav('setup')"); await pg.click('#startRoundBtn'); await pg.wait_for_timeout(350)
        await pg.evaluate("() => { const b = document.getElementById('confirmModalBtn'); if (b && !document.getElementById('confirmModal').classList.contains('hidden')) b.click(); }")
        await pg.wait_for_timeout(300)
        check("een lopende ronde op Score, instelling uit: geen slot", [await pg.evaluate("() => !!game.started && document.getElementById('screen-score').classList.contains('active')"), (await pg.evaluate(STAND))['gevraagd']], [True, 0])
        await pg.evaluate("() => { nav('settings'); const c = document.getElementById('schermAanToggle'); c.checked = true; c.dispatchEvent(new Event('change')); }")
        await pg.wait_for_timeout(100)
        check("aan gezet op Instellingen: nog geen slot (niet op Score)", (await pg.evaluate(STAND))['vast'], 0)
        check("de keuze is bewaard", await pg.evaluate("() => localStorage.getItem('golf_scherm_aan')"), 'on')
        await pg.evaluate("nav('score')"); await pg.wait_for_timeout(100)
        check("terug op Score met een lopende ronde: het slot", await pg.evaluate(STAND), {'gevraagd': 1, 'los': 0, 'vast': 1})
        await pg.evaluate("() => { renderScore(); renderScore(); }"); await pg.wait_for_timeout(100)
        check("opnieuw tekenen vraagt geen tweede slot", (await pg.evaluate(STAND))['gevraagd'], 1)
        await pg.evaluate("nav('stat')"); await pg.wait_for_timeout(100)
        check("naar Statistiek: het slot eraf", (await pg.evaluate(STAND))['vast'], 0)
        await pg.evaluate("nav('score')"); await pg.wait_for_timeout(100)
        check("terug: weer een slot", await pg.evaluate(STAND), {'gevraagd': 2, 'los': 1, 'vast': 1})
        # de browser laat het slot los als de app naar de achtergrond gaat
        await pg.evaluate("""() => { Object.defineProperty(document, 'hidden', {configurable: true, get: () => true});
            document.dispatchEvent(new Event('visibilitychange')); }"""); await pg.wait_for_timeout(100)
        check("de app naar de achtergrond: het slot eraf", (await pg.evaluate(STAND))['vast'], 0)
        await pg.evaluate("""() => { Object.defineProperty(document, 'hidden', {configurable: true, get: () => false});
            document.dispatchEvent(new Event('visibilitychange')); }"""); await pg.wait_for_timeout(100)
        check("terug in de app: weer een slot", await pg.evaluate(STAND), {'gevraagd': 3, 'los': 2, 'vast': 1})
        # de ronde beëindigen: geen slot meer
        await pg.evaluate("() => { game.started = false; renderScore(); }"); await pg.wait_for_timeout(100)
        check("geen lopende ronde meer: het slot eraf", (await pg.evaluate(STAND))['vast'], 0)
        await pg.evaluate("() => { game.started = true; renderScore(); const c = document.getElementById('schermAanToggle'); c.checked = false; c.dispatchEvent(new Event('change')); }"); await pg.wait_for_timeout(100)
        check("instelling uit tijdens de ronde: het slot eraf", (await pg.evaluate(STAND))['vast'], 0)
        # een browser zonder Wake Lock: niets breekt
        await pg.evaluate("() => { Object.defineProperty(navigator, 'wakeLock', {configurable: true, value: undefined}); const c = document.getElementById('schermAanToggle'); c.checked = true; c.dispatchEvent(new Event('change')); nav('score'); }")
        check("zonder Wake Lock in de browser: geen fout", pf, [])

        print("\n=== 2. HOOFDKNOPPEN EN KEUZES: GOUD; PAUZEREN: GOUDEN RAND ===\n")
        INFO = """() => { window.__k = v => { const s = document.createElement('span'); s.style.color = v; document.body.appendChild(s); const c = getComputedStyle(s).color; s.remove(); return c; };
            window.__gewoon = (() => { const b = document.createElement('button'); b.className = 'btn-secondary'; document.body.appendChild(b); const c = getComputedStyle(b).backgroundColor; b.remove(); return c; })();
            // [goud vlak, donkere tekst]: een gouden kleur of een verloop vanaf goud
            window.__goud = el => { const c = getComputedStyle(el), g = __k('var(--gold)');
                return [c.backgroundColor === g || /gradient/.test(c.backgroundImage), c.color === __k('var(--green-deep)')]; };
            window.__gewoneKnop = el => { const c = getComputedStyle(el); return c.backgroundColor === __gewoon && c.backgroundImage === 'none'; }; }"""
        for thema in ('light', 'dark'):
            await pg.evaluate("(t) => { localStorage.setItem('golf_theme', t); }", thema); await pg.reload(); await pg.wait_for_timeout(500)
            await pg.evaluate(INFO)
            r = await pg.evaluate("""() => {
                nav('setup'); const st = __goud(document.getElementById('startRoundBtn'));
                showConfirmModal('Ronde verwijderen?', 'Zeker?', () => {}, 'Annuleren', null, 'Verwijderen');
                const ok = __goud(document.getElementById('confirmModalBtn'));
                closeConfirmModal();
                nav('archive'); const m = document.querySelector('#screen-archive .btn-main');
                nav('settings'); switchSettingsTab('data');
                const tabs = [__gewoneKnop(document.getElementById('settingsTabBtnMain')), __goud(document.getElementById('settingsTabBtnData'))];
                switchSettingsTab('main');
                const vlak = [...document.querySelectorAll('button')].filter(b => /background:\\s*var\\(--gold\\)/.test(b.getAttribute('style') || '')).map(b => b.id || b.textContent.trim());
                return {start: st, venster: ok, kaart: m ? __goud(m) : null, tabs, vlak}; }""")
            # er loopt hier nog een ronde, dan toont Statistiek de ronde; de spelerstatistiek zelf opbouwen
            await pg.evaluate("() => { nav('stat'); renderPlayerStats(); }"); await pg.wait_for_timeout(600)
            r['periode'] = await pg.evaluate("""() => { const pk = document.querySelector('.stat-periode-knop.gekozen'), ander = document.querySelector('.stat-periode-knop:not(.gekozen):not([disabled])');
                return pk ? [__goud(pk), ander ? __gewoneKnop(ander) : null] : null; }""")
            await pg.evaluate("nav('score')"); await pg.wait_for_timeout(300)
            r['pauze'] = await pg.evaluate("""() => { const p = document.getElementById('finishRoundBtn'), c = getComputedStyle(p);
                return [!document.getElementById('finishRoundBtnRow').classList.contains('hidden'), __gewoneKnop(p), c.borderTopColor === __k('var(--gold)'), c.color === __k('var(--text)')]; }""")
            check(f"{thema}: Nieuwe ronde: goud, donkere tekst", r['start'], [True, True])
            check(f"{thema}: OK in een venster: idem", r['venster'], [True, True])
            check(f"{thema}: ▶ op de rondekaart: idem", r['kaart'], [True, True])
            check(f"{thema}: tabs in Instellingen: de gekozen goud, de andere de gewone vulling", r['tabs'], [True, [True, True]])
            check(f"{thema}: de gekozen periode op Statistiek goud, een andere gewoon", r['periode'], [[True, True], True])
            check(f"{thema}: Pauzeren onder de scores: gewone vulling, gouden rand, gewone tekst", r['pauze'], [True, True, True, True])
            check(f"{thema}: geen eigen gouden vlak op een knop (alles via een klasse)", r['vlak'], [])
        check("geen paginafouten", pf, [])
        await b.close()
    print('\nGEEN FOUTEN' if not fouten else f'\n{len(fouten)} FOUT(EN)')
    sys.exit(1 if fouten else 0)

asyncio.run(main())
