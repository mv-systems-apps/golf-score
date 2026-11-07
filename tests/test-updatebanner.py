"""De gouden banner over versies moet de juiste kant op wijzen.

De banner vergelijkt de versie van de draaiende pagina met die van de kopie in het
geheugen van de browser (de cache van de servicewerker). Eerder gaf ELK verschil de
melding "nieuwe versie beschikbaar" — ook als de cache juist OUDER was. Dan klopte de
tekst niet en hielp verversen ook niet, want de oude kopie bleef staan.

Nu wordt gekeken welke kant het verschil op staat:
  * cache nieuwer  -> "Nieuwe versie beschikbaar", tikken = herladen
  * cache ouder    -> "Verouderde kopie in het geheugen", tikken = eerst opruimen
  * gelijk         -> geen banner

Deze test draait over http, want de cache van de browser werkt niet op een bestandsadres.
"""
import asyncio, os, subprocess, sys, time
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import APP

POORT = 8901
fouten = []


def check(naam, gekregen, verwacht):
    if gekregen != verwacht:
        fouten.append(naam)
        print(f" FOUT  {naam}: {gekregen!r} — verwacht {verwacht!r}")
    else:
        print(f"  ok   {naam}: {gekregen!r}")


async def main():
    map_ = os.path.dirname(os.path.abspath(APP))
    server = subprocess.Popen([sys.executable, '-m', 'http.server', str(POORT)],
                              cwd=map_, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 390, "height": 844})
            paginafouten = []
            page.on('pageerror', lambda e: paginafouten.append(str(e)))
            url = f'http://127.0.0.1:{POORT}/' + os.path.basename(APP)
            await page.goto(url)
            await page.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
            await page.goto(url)
            await page.wait_for_timeout(800)

            eigen = await page.evaluate("""() => document.getElementById('appVersionStamp')
                .textContent.match(/Versie ([0-9A-F]+-[0-9A-F]+)/)[1]""")

            # Een nieuwere en een oudere versie dan de eigen, afgeleid van het eigen stempel
            # (datum in hex + volgnummer). Vaste waarden als 13527FF-999 werden 'ouder' zodra
            # de app een later stempel kreeg.
            dag, nr = eigen.split('-')
            NIEUWER = f"{int(dag, 16) + 1:X}-{nr}"
            OUDER = f"{int(dag, 16) - 1:X}-{nr}"
            # Sinds 13527DA-13C kijkt de app alleen in caches van Golf Score (golf-score-…).
            async def metCache(versie, naam='golf-score-proef'):
                return await page.evaluate("""async ([v, naam]) => {
                    for (const n of await caches.keys()) await caches.delete(n);
                    const c = await caches.open(naam);
                    await c.put('./golf-score.html',
                        new Response('<span id="appVersionStamp">Versie ' + v + '</span>'));
                    const b = document.getElementById('updateBanner');
                    b.classList.add('hidden'); b.textContent = ''; delete b.dataset.ouder;
                    await checkAppUpdate();
                    return { zichtbaar: !b.classList.contains('hidden'),
                             tekst: b.textContent, ouder: b.dataset.ouder || '' };
                }""", [versie, naam])

            nieuwer = await metCache(NIEUWER)
            check("bij een nieuwere kopie verschijnt de banner", nieuwer["zichtbaar"], True)
            check("met de tekst over een nieuwe versie",
                  nieuwer["tekst"].startswith('Nieuwe versie'), True)
            check("en die hoeft niet opgeruimd te worden", nieuwer["ouder"], '')

            ouder = await metCache(OUDER)
            check("bij een oudere kopie verschijnt de banner ook", ouder["zichtbaar"], True)
            check("maar met een andere tekst",
                  ouder["tekst"].startswith('Verouderde kopie'), True)
            check("en die moet wél opgeruimd worden", ouder["ouder"], '1')

            vreemd = await metCache(NIEUWER, 'trends-proef')
            check("een nieuwere kopie in de cache van een andere app telt niet", vreemd["zichtbaar"], False)

            gelijk = await metCache(eigen)
            check("bij een gelijke versie geen banner", gelijk["zichtbaar"], False)

            if paginafouten:
                fouten.append('paginafouten')
                print("\nFOUTEN IN DE PAGINA:")
                for f in paginafouten[:5]:
                    print("   " + f[:150])

            await browser.close()
    finally:
        server.terminate()

    print()
    if fouten:
        print(f"{len(fouten)} FOUT(EN)")
        sys.exit(1)
    print("GEEN FOUTEN")


asyncio.run(main())
