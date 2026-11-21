"""Een import die mislukt, zegt waaróm, in gewone taal.

Het inlezen van rondes ving elke fout op als 'Ongeldig JSON-bestand', ook als het bestand
prima leesbaar was en de fout in de app zat. Dan zoek je het bij het bestand, terwijl
het aan de app ligt, en blijft een programmeerfout onzichtbaar. Het inlezen van clubs
toonde de technische foutmelding van de browser ('Unexpected token…').
Gecontroleerd met echte bestanden via de knoppen: een kapot bestand krijgt een
begrijpelijke melding, een leesbaar maar onbruikbaar bestand een melding over de inhoud,
en nergens wordt een leesbaar bestand 'ongeldig JSON' genoemd.
"""
import asyncio, json, os, sys, tempfile
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

een = ronde(1, '2026-05-01')
RONDEBESTANDEN = [
    ('kapotte tekst',               '{"date": "2026-05-01", "holes": [', 'kapot'),
    ('leeg object',                 '{}', 'inhoud'),
    ('een getal',                   '42', 'inhoud'),
    ('een tekst',                   '"ronde"', 'inhoud'),
    ('null',                        'null', 'inhoud'),
    ('lijst met null',              '[null]', 'inhoud'),
    ('lijst met een getal',         '[1, 2]', 'inhoud'),
    ('ronde met holes als tekst',   json.dumps({**een, 'holes': 'negen'}), 'inhoud'),
    ('ronde met een hole null',     json.dumps({**een, 'holes': [None] * 9}), 'inhoud'),
    ('ronde met datum als getal',   json.dumps({**een, 'date': 20260501}), 'inhoud'),
    ('goede ronde (controle)',      json.dumps(een), 'goed'),
]
CLUBBESTANDEN = [
    ('kapotte tekst',               '{"club": "X", "courses": {', 'kapot'),
    ('een getal',                   '42', 'inhoud'),
    ('null',                        'null', 'inhoud'),
    ('lijst met null',              '[null]', 'inhoud'),
]
VENSTER = """() => { const m = document.getElementById('confirmModal'); return m.classList.contains('hidden') ? '' : document.getElementById('confirmModalTitle').textContent + ' | ' + document.getElementById('confirmModalMessage').textContent; }"""
DICHT = "() => document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))"

async def main():
    map_ = tempfile.mkdtemp()
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:90]))
        await pg.goto(app_url())
        await pg.evaluate("""(c) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', '[]');
          localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }""", CLUBS)
        await pg.reload(); await pg.wait_for_timeout(600); await pg.evaluate(DICHT)
        for soort, lijst, invoer in [('rondes', RONDEBESTANDEN, '#importRoundFile'), ('clubs', CLUBBESTANDEN, '#importClubFile')]:
            print(f"\n=== {soort.upper()} INLEZEN ===\n")
            for naam, tekst, verwacht in lijst:
                pad = os.path.join(map_, f'{soort}-{abs(hash(naam))}.json'); open(pad, 'w', encoding='utf-8').write(tekst)
                await pg.evaluate(DICHT); pf.clear()
                await pg.locator(invoer).set_input_files(pad); await pg.wait_for_timeout(500)
                v = await pg.evaluate(VENSTER); kz = await pg.evaluate("document.getElementById('keuzeModal').classList.contains('hidden') ? '' : document.getElementById('keuzeModalTekst').textContent")
                v = v or kz
                if os.environ.get("TOON"): print("       →", v[:160])
                if verwacht == 'goed':
                    check(f"{naam}: wordt ingelezen", 'mislukt' not in v.lower() and bool(v), True)
                elif verwacht == 'kapot':
                    check(f"{naam}: melding dat het bestand niet leesbaar is, in gewone taal", ('mislukt' in v.lower(), 'niet leesbaar' in v or 'beschadigd' in v, any(w in v for w in ('Unexpected', 'token', 'JSON.parse', 'position'))), (True, True, False))
                else:
                    check(f"{naam}: melding over de inhoud, niet 'ongeldig JSON' of een technische fout", ('mislukt' in v.lower() or 'ongeldig' in v.lower() or 'geen' in v.lower(), 'JSON' in v, any(w in v for w in ('Cannot read', 'undefined', 'is not', 'Unexpected'))), (True, False, False))
                check(f"{naam}: geen losse storing in de app", pf, [])

        print("\n=== EEN STORING IN DE APP TIJDENS HET INLEZEN ===\n")
        # Een programmeerfout nabootsen: de keuring loopt vast. Die hoort niet als
        # 'ongeldig bestand' te verdwijnen, maar bij de algemene foutvanger te komen.
        pad = os.path.join(map_, 'goed.json'); open(pad, 'w', encoding='utf-8').write(json.dumps(ronde(7, '2026-05-07')))
        await pg.evaluate(DICHT); await pg.evaluate("() => { window.__keur = keurRonde; keurRonde = () => { throw new TypeError('proef'); }; }")
        await pg.locator('#importRoundFile').set_input_files(pad); await pg.wait_for_timeout(500)
        d = await pg.evaluate("(document.getElementById('foutMeldingDetail') || {}).textContent || ''")
        check("de foutvanger meldt het, met waar het gebeurde", ('TypeError: proef' in d, 'inlezen van rondes' in d), (True, True))
        check("en er staat geen 'Import mislukt' met een verkeerde reden", await pg.evaluate(VENSTER), '')
        check("de opslag is niet gewijzigd", await pg.evaluate("JSON.parse(localStorage.getItem('golf_rounds')).some(r => r.date === '2026-05-07')"), False)
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN)" if fouten else "\nGEEN FOUTEN"); sys.exit(1 if fouten else 0)
asyncio.run(main())
