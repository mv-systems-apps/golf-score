"""De algemene foutvanger: een onverwachte fout wordt gemeld, en alleen gemeld.

Zonder vanger staat een onverwachte fout alleen in de console; op de baan zie je die
niet. De fouten hier ontstaan in de code van de app zelf, door de toestand in het
geheugen stuk te maken en dan te tikken — net als een echte programmeerfout.
Gecontroleerd: de melding komt (bij een tik, in een uitgestelde actie, in een asynchrone
actie), er komt er maar één tegelijk, fouten van buiten de app worden genegeerd, de
laatste vijf staan onder Instellingen, en de vanger raakt je rondes en clubs niet aan.
Tot slot: een gewone sessie met de eigen gegevens geeft geen enkele melding.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

ZET = """([c, r, s]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
  localStorage.setItem('golf_default_club', Object.keys(c)[0]); localStorage.setItem('golf_profile_name', s); localStorage.setItem('golf_player_name', s);
  localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); }"""
DETAIL = "() => { const d = document.getElementById('foutMeldingDetail'); return d ? d.textContent : null; }"
AANTAL = "() => document.querySelectorAll('#foutMelding').length"
BREEK = "() => { COURSES[sel.track] = null; }"          # daarna loopt het tekenen van Start vast, in de app zelf
OPSLAG = "() => [localStorage.getItem('golf_rounds'), localStorage.getItem('golf_clubs')]"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={"width": 390, "height": 844}, permissions=['clipboard-read', 'clipboard-write'])
        pg = await ctx.new_page()
        await pg.goto(app_url()); await pg.evaluate(ZET, [CLUBS, [ronde(i + 1, f"2026-05-{i + 1:02d}") for i in range(6)], 'Testspeler'])
        await pg.reload(); await pg.wait_for_timeout(600)
        voor = await pg.evaluate(OPSLAG)

        print("\n=== 1. MELDING BIJ EEN STORING IN DE APP ===\n")
        check("vooraf: geen melding, niets bewaard", (await pg.evaluate(AANTAL), await pg.evaluate("localStorage.getItem('golf_fouten')")), (0, None))
        await pg.evaluate(BREEK); await pg.click('#tab-setup'); await pg.wait_for_timeout(300)
        d = await pg.evaluate(DETAIL) or ''
        versie = await pg.evaluate("document.getElementById('appVersionStamp').textContent.replace('Versie ', '')")
        check("bij een tik: melding met versie, fout en regelnummer", (d.startswith(versie + ' · '), 'TypeError' in d, '(regel ' in d, 'Uncaught' in d), (True, True, True, False))
        check("de uitleg is in gewone taal", 'mogelijk niet opgeslagen' in await pg.evaluate("document.getElementById('foutMelding').textContent"), True)
        await pg.evaluate("() => { setTimeout(rebuildStartScreen, 0); setTimeout(rebuildStartScreen, 10); }"); await pg.wait_for_timeout(300)
        check("herhaalt de fout zich, dan blijft het bij één venster", await pg.evaluate(AANTAL), 1)
        check("maar ze zijn wel alle drie bewaard", len(json.loads(await pg.evaluate("localStorage.getItem('golf_fouten')"))), 3)
        await pg.locator('#foutMelding button', has_text='Kopieer').click(); await pg.wait_for_timeout(300)
        check("Kopieer zet de regel op het klembord", await pg.evaluate("navigator.clipboard.readText()"), d)
        await pg.locator('#foutMelding button', has_text='Sluiten').click(); await pg.wait_for_timeout(200)
        check("Sluiten haalt de melding weg", await pg.evaluate(AANTAL), 0)
        await pg.evaluate("() => { setTimeout(rebuildStartScreen, 0); }"); await pg.wait_for_timeout(300)
        check("een fout in een uitgestelde actie geeft daarna weer een melding", await pg.evaluate(AANTAL), 1)
        await pg.locator('#foutMelding button', has_text='Sluiten').click()
        await pg.evaluate("() => { exportClub(null); }"); await pg.wait_for_timeout(400)
        d = await pg.evaluate(DETAIL) or ''
        check("een fout in een asynchrone actie ook", ('[async]' in d, 'TypeError' in d), (True, True))
        await pg.locator('#foutMelding button', has_text='Sluiten').click()

        print("\n=== 2. WAT VAN BUITEN DE APP KOMT, WORDT GENEGEERD ===\n")
        n0 = len(json.loads(await pg.evaluate("localStorage.getItem('golf_fouten')")))
        await pg.evaluate("""() => {
          window.dispatchEvent(new ErrorEvent('error', { message: 'Script error.', filename: '' }));
          window.dispatchEvent(new ErrorEvent('error', { message: 'x is not defined', filename: 'chrome-extension://abc/inhoud.js', lineno: 3 }));
          window.dispatchEvent(new ErrorEvent('error', { message: 'ResizeObserver loop limit exceeded', filename: location.href }));
          const af = new Error('gebruiker brak af'); af.name = 'AbortError'; Promise.reject(af);
          const img = new Image(); img.src = 'bestaat-niet.png'; document.body.appendChild(img);
        }"""); await pg.wait_for_timeout(500)
        check("extensie, vreemd script, afgebroken delen en een ontbrekend plaatje: geen melding",
              (await pg.evaluate(AANTAL), len(json.loads(await pg.evaluate("localStorage.getItem('golf_fouten')")))), (0, n0))

        print("\n=== 3. DE LAATSTE VIJF ONDER INSTELLINGEN ===\n")
        for _ in range(4):
            await pg.evaluate("() => { setTimeout(rebuildStartScreen, 0); }"); await pg.wait_for_timeout(150)
        await pg.evaluate("() => { const l = document.getElementById('foutMelding'); if (l) l.querySelectorAll('button')[1].click(); }")
        check("er worden er hooguit vijf bewaard", len(json.loads(await pg.evaluate("localStorage.getItem('golf_fouten')"))), 5)
        blok = await pg.evaluate("() => ({ zichtbaar: !document.getElementById('laatsteFouten').classList.contains('hidden'), regels: document.getElementById('laatsteFoutenTekst').textContent.split('\\n').length })")
        check("ze staan onder Instellingen bij het versienummer", blok, {'zichtbaar': True, 'regels': 5})
        await pg.evaluate("document.querySelector('#laatsteFouten button[onclick=\"wisLaatsteFouten()\"]').click()"); await pg.wait_for_timeout(150)
        check("Wis haalt ze weg en verbergt het blok", (await pg.evaluate("localStorage.getItem('golf_fouten')"), await pg.evaluate("document.getElementById('laatsteFouten').classList.contains('hidden')")), (None, True))
        check("de vanger heeft je rondes en clubs niet aangeraakt", await pg.evaluate(OPSLAG), voor)
        await pg.evaluate("localStorage.setItem('golf_fouten', '{kapot')"); await pg.reload(); await pg.wait_for_timeout(500)
        await pg.evaluate(BREEK); await pg.click('#tab-setup'); await pg.wait_for_timeout(300)
        check("een onleesbare foutenlijst hindert de vanger niet", (await pg.evaluate(AANTAL), len(json.loads(await pg.evaluate("localStorage.getItem('golf_fouten')")))), (1, 1))

        print("\n=== 4. EEN GEWONE SESSIE MET EIGEN GEGEVENS GEEFT GEEN MELDING ===\n")
        R = json.load(open(os.path.join(HIER, 'echte-rondes.json'), encoding='utf-8'))
        C = {c['club']: c for c in json.load(open(os.path.join(HIER, 'echte-clubs.json'), encoding='utf-8'))}
        await pg.evaluate(ZET, [C, R, R[0].get('player') or 'Testspeler']); await pg.reload(); await pg.wait_for_timeout(700)
        for t in ['setup', 'archive', 'stat', 'club', 'settings', 'score', 'setup']:
            await pg.click(f'#tab-{t}'); await pg.wait_for_timeout(350)
        check("zes tabbladen open: geen melding, niets bewaard", (await pg.evaluate(AANTAL), await pg.evaluate("localStorage.getItem('golf_fouten')")), (0, None))
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN)" if fouten else "\nGEEN FOUTEN"); sys.exit(1 if fouten else 0)
asyncio.run(main())
