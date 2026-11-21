"""Analyseer mijn spel: de adviezen volgen de getallen die erbij staan (poetsronde 13528FF-001).
- Speelritme: het advies noemt de groep met het beste dagresultaat en de groep waarmee het
  vergelijkt; eerder zei het 'Speel je kort op elkaar' terwijl de beste groep 8 t/m 14 dagen was.
- Waar verlies je je slagen: 'Verreweg de meeste … vóór de green' alleen vanaf 75 % (het
  percentage dat erbij staat), 'De meeste' tussen 50 en 75 %; eerder stond 'verreweg' bij 54 %.
- Instellingen › Gegevens › Opruimen: bij één ronde enkelvoud ('1 ronde'), niet '1 rondes'.
"""
import asyncio, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

def kaal(t): return re.sub(r'<[^>]+>', '', t)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        a = await pg.evaluate("() => buildGameAnalysis()")
        tekst = lambda x: kaal(x if isinstance(x, str) else str(x))
        secties = {s['kop']: [tekst(r) for r in s['regels']] for s in a.get('secties', [])}
        aanbev = [tekst(x) for x in a.get('aanbev', a.get('aanbevelingen', []))]
        ritme = secties.get('Speelritme', [])
        groepen = {m.group(1).lower(): float(m.group(2)) for r in ritme for m in [re.match(r'^(.*?): gemiddeld (-?\d+\.\d)', r)] if m}
        print('    groepen:', groepen)
        if len(groepen) >= 2 and max(groepen.values()) - min(groepen.values()) >= 1.5:
            beste = min(groepen, key=groepen.get); slechtste = max(groepen, key=groepen.get)
            adv = [x for x in aanbev if 'tussen twee rondes' in x or 'kort op elkaar' in x or 'langere pauze' in x]
            check("speelritme: het advies noemt de beste en de slechtste groep", bool(adv) and beste in adv[0] and slechtste in adv[0], True)
            check("speelritme: niet 'kort op elkaar' als de kortste pauze niet de beste is", any('kort op elkaar' in x for x in adv) and beste != 'binnen 3 dagen', False)
        else:
            check("speelritme: de testdata heeft een duidelijk verschil", groepen, 'twee groepen met ≥ 1.5 verschil')
        waar = ' '.join(secties.get('Waar verlies je je slagen?', []))
        m = re.search(r'\((\d+)% vóór de green\)', waar)
        if m:
            pct = int(m.group(1))
            verreweg = any(x.startswith('Verreweg de meeste slagen') for x in aanbev)
            meeste = any(x.startswith('De meeste slagen') for x in aanbev)
            print('    vóór de green:', pct, '%')
            check(f"bij {pct}% vóór de green: 'Verreweg' alleen vanaf 75 %", verreweg, pct >= 75)
            check(f"bij {pct}% vóór de green: 'De meeste' tussen 50 en 75 %", meeste, 50 < pct < 75)
        else:
            check("waar verlies je je slagen: het percentage staat erbij", waar[:80], '(NN% vóór de green)')
        # het analysevenster op 360 px: de knop 'AI-prompt' op één regel, de datums in het overzicht heel
        await pg.set_viewport_size({'width': 360, 'height': 740})
        v = await pg.evaluate("""() => { nav('stat'); openGameAnalysis(); const k = document.getElementById('analysisCopyBtn'), r = document.createRange(); r.selectNodeContents(k);
            const regels = new Set([...r.getClientRects()].filter(x => x.width > 1).map(x => Math.round(x.top))).size;
            const datums = [...document.querySelectorAll('#analysisModal .bijeen')].filter(e => /\\d+-\\d+-\\d{4}/.test(e.textContent));
            const uit = [k.textContent.trim(), regels, datums.length >= 2 && datums.every(e => e.getClientRects().length === 1)];
            document.getElementById('analysisModal').classList.add('hidden'); return uit; }""")
        check("analysevenster 360 px: 'AI-prompt' op één regel, de datums in het overzicht heel", v, ['AI-prompt', 1, True])
        # Opruimen: '1 ronde' bij één, 'rondes' bij meer
        een = await pg.evaluate("""() => { const s = loadSavedRounds(); const p = startPlayerName();
            s.forEach(r => { r.qualifying = true; r.player = p; }); s[0].qualifying = false; s[1].player = 'Medespeler';
            setRoundsAndMark(JSON.stringify(s)); updateStorageSettingsUI(); updateOtherPlayerCleanupUI();
            const t = id => document.getElementById(id).parentElement.textContent.replace(/\\s+/g, ' ').trim();
            return [t('nonQCount'), t('otherPlayerCount')]; }""")
        check("bij één: '1 niet-qualifying ronde' en '1 ronde van andere spelers'", [een[0].startswith('Je hebt 1 niet-qualifying ronde, oefenrondes meegeteld.'), 'Je hebt 1 ronde van andere spelers' in een[1]], [True, True])
        print('   ', een)
        twee = await pg.evaluate("""() => { const s = loadSavedRounds(); s[2].qualifying = false; setRoundsAndMark(JSON.stringify(s)); updateStorageSettingsUI();
            return document.getElementById('nonQCount').parentElement.textContent.replace(/\\s+/g, ' ').trim(); }""")
        check("bij twee: 'rondes'", twee.startswith('Je hebt 2 niet-qualifying rondes, oefenrondes meegeteld.'), True)
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
