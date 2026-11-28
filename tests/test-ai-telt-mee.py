"""De prompt voor AI: welke rondes meetellen, hoort bij de speler van nu (1352898-030).

De prompt zet achter elk van de laatste 20 rondes een * als die ronde in de beste 8 zit
die de handicap nu bepalen. Tot 029 las hij dat uit _whsUsedIds, een waarde die alleen de
rondelijst op Rondes zet als die wordt getekend. Was de lijst sindsdien niet opnieuw
getekend — bijvoorbeeld na het veranderen van de naam bij Start — dan hoorden de sterren
bij de vorige speler. Nu rekent de prompt het zelf uit (whsStand, dezelfde berekening als
overal).

De test: twee spelers met elk genoeg rondes. Eerst Testspeler, de lijst getekend; dan bij Start
de naam van de andere speler, zonder de lijst opnieuw te tekenen, en de prompt kopiëren.
De sterren moeten precies de meetellende rondes van die speler zijn, en ook voor Testspeler
(terug) weer de zijne.

Sinds 031 ook:
  * de rondes zijn veranderd zonder dat de lijst opnieuw getekend is: een ronde van Testspeler
    krijgt een veel betere score en hoort daardoor ineens bij de beste 8 (faalt op 029);
  * direct na het openen van de app, vóór Rondes. Op 029 ging dat goed omdat de app de
    lijst bij het opstarten al tekent; de controle staat er als vangnet voor als dat
    ooit verandert.
"""
import asyncio, os, sys, copy
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, RONDES, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

DATA = copy.deepcopy(RONDES)
for i in range(12):
    r = ronde(700 + i, f'2026-0{1 + i % 9}-{10 + i:02d}', speler='Partner')
    r['sd'] = r['sdFinal'] = 20.0 + (i * 7) % 11
    DATA.append(r)

MEET = """async (naam) => {
  document.getElementById('iName').value = naam;     // alleen het veld: de lijst wordt niet opnieuw getekend
  window.__klembord = [];
  await copyAnalysisForAi();
  const tekst = window.__klembord.join('\\n');
  const deel = tekst.slice(tekst.indexOf('LAATSTE '));
  const rijen = deel.split('\\n').filter(r => /^\\d{4}-\\d{2}-\\d{2} \\|/.test(r));
  const met = rijen.filter(r => /\\|\\s*\\*\\s*$/.test(r)).map(r => r.split(' | ').slice(0, 2).join(' '));
  const nu = whsStand(naam).nu;
  const hoort = nu ? analysisRounds().slice(-20).filter(r => nu.usedIds.has(r.id)).map(r => r.date + ' ' + (r.time || '')) : [];
  return { rijen: rijen.length, met: met.sort(), hoort: hoort.sort() };
}"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await pg.add_init_script("window.__klembord = []; Object.defineProperty(navigator, 'clipboard', { value: { writeText: async t => { window.__klembord.push(t); } } });")
        await pg.goto(app_url())
        await pg.evaluate(SEED, [CLUBS, DATA])
        await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
        await pg.reload(); await pg.wait_for_timeout(700)
        await pg.evaluate("() => document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))")

        nooit = await pg.evaluate(MEET, 'Testspeler')
        check("lijst op Rondes nooit getekend: er zijn rondes die meetellen", len(nooit['hoort']) > 0, True)
        check("lijst op Rondes nooit getekend: de * staan toch bij de meetellende rondes", nooit['met'], nooit['hoort'])

        await pg.evaluate("() => nav('archive')")
        await pg.wait_for_timeout(300)

        testspeler = await pg.evaluate(MEET, 'Testspeler')
        print(f"  Testspeler: {testspeler['rijen']} rijen, {len(testspeler['met'])} met *")
        check("Testspeler: er zijn rondes die meetellen", len(testspeler['hoort']) > 0, True)
        check("Testspeler: de * staan precies bij zijn meetellende rondes", testspeler['met'], testspeler['hoort'])

        partner = await pg.evaluate(MEET, 'Partner')
        print(f"  Partner: {partner['rijen']} rijen, {len(partner['met'])} met *")
        check("Partner: er zijn rondes die meetellen", len(partner['hoort']) > 0, True)
        check("andere naam bij Start, lijst niet opnieuw getekend: de * horen bij die speler", partner['met'], partner['hoort'])

        terug = await pg.evaluate(MEET, 'Testspeler')
        check("en terug naar Testspeler: weer de zijne", terug['met'], terug['hoort'])

        # Een ronde van Testspeler die nu niet meetelt, krijgt een veel betere score; de lijst
        # wordt daarna niet opnieuw getekend.
        gewijzigd = await pg.evaluate("""() => {
          const nu = whsStand('Testspeler').nu;
          const lijst = JSON.parse(localStorage.getItem('golf_rounds'));
          const laatste = analysisRounds().slice(-20).map(r => r.id);
          const r = lijst.find(x => x.player === 'Testspeler' && laatste.includes(x.id) && !nu.usedIds.has(x.id) && x.sd != null);
          r.sd = r.sdFinal = -5;
          localStorage.setItem('golf_rounds', JSON.stringify(lijst));
          return r.date + ' ' + (r.time || '');
        }""")
        na = await pg.evaluate(MEET, 'Testspeler')
        check("ronde gewijzigd zonder de lijst te tekenen: die ronde telt nu mee", gewijzigd in na['hoort'], True)
        check("ronde gewijzigd zonder de lijst te tekenen: de * volgen de nieuwe stand", na['met'], na['hoort'])
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
