"""13528A1-002: opslag niet beschermd is geen waarschuwing. Alleen het woord "nee" is
oranje; de rest van de regel blijft grijs en er komt geen stip bij."""
import asyncio
from playwright.async_api import async_playwright
from testdata import app_url

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        await page.goto(app_url())
        await page.wait_for_timeout(500)
        uit = await page.evaluate("""async () => {
            const st = navigator.storage, echt = st.persisted;
            const stip = () => document.getElementById('tab-settings').classList.contains('has-dot');
            const meet = async (waarde) => {
                st.persisted = async () => waarde;
                const voor = stip();
                await refreshStorageStatus();
                const el = document.getElementById('storageStatusLine');
                const w = el.querySelector('span');
                return { tekst: el.textContent.split(' \\u00b7 ')[0], woord: w ? w.textContent : null,
                         oranje: !!w && getComputedStyle(w).color !== getComputedStyle(el).color,
                         stipVeranderd: stip() !== voor };
            };
            const nee = await meet(false), ja = await meet(true);
            st.persisted = echt;
            return { nee, ja };
        }""")
        fouten = []
        def eis(naam, ok):
            print(('  OK   ' if ok else '  FOUT ') + naam)
            if not ok: fouten.append(naam)
        eis('nee: de regel zegt het', uit['nee']['tekst'] == 'Opslag beschermd: nee')
        eis('nee: alleen het woord is oranje', uit['nee']['woord'] == 'nee' and uit['nee']['oranje'])
        eis('nee: geen stip erbij', not uit['nee']['stipVeranderd'])
        eis('ja: niets oranje', uit['ja']['tekst'] == 'Opslag beschermd: ja' and not uit['ja']['oranje'])
        print('\n' + ('GEEN FOUTEN' if not fouten else f'{len(fouten)} FOUT(EN): ' + ', '.join(fouten)))
        await b.close()

asyncio.run(main())
