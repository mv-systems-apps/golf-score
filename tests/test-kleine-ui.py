"""Kleine verbeteringen in beeld.

1. Lege kop (niets gepland): de laatste afgeronde ronde van de speler bovenin Start, als
   titel in plaats van 'Geen geplande rondes' ('Za 3-10-2026 · 09:30', altijd met jaartal
   en met de tijd, groen en vet; 13528F3-001), en op een tweede
   regel 'Stb 38 · Hcp 31.3': alleen de handicap van nu, ook als die ronde hem veranderde
   (13528F3-001; het verloop staat op de rondekaart). Beide regels even groot als de titel
   (20 px). De kop blijft even hoog, ook in een ronde;
   met een geplande ronde verdwijnt het weer.
2. Het actieve tabblad is ook in de lichte modus goud (de regel voor de lichte modus won).
3. Rondekaart: de getallen achter Str en Stb vet; 'Pcc —' staat er niet meer als Pcc niet
   is ingevuld, een ingevulde Pcc wel.
4. Opslag onder 1 MB in kB, daarboven in MB.
5. Clubkaart: de korte naam grijs, zonder 'Kort:'.
6. Scorekaart: cijfers even breed (tabular-nums).
7. Rondekaart: een afgebroken regel springt in; 'Par … · …h' blijft bij elkaar.
8. De herstelknoppen zijn niet gedimd.
9. Het backupblok heeft een chevron en brengt je naar Gegevens.
"""
import asyncio, datetime, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

async def nieuw(b, thema='light'):
    pg = await b.new_page(viewport={'width': 360, 'height': 800}, device_scale_factor=2)
    pf = []
    pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES])
    await pg.evaluate("(t) => localStorage.setItem('golf_theme', t)", thema)
    await pg.reload(); await pg.wait_for_timeout(500)
    return pg, pf

# Wat de kop zou moeten tonen, hier los uitgerekend uit de opgeslagen rondes.
VERWACHT = """() => {
  const speler = startPlayerName();
  const af = loadSavedRounds().filter(r => r.player === speler && !r._justImported && r.date && r.holes.every(h => h.score != null));
  af.sort((a, b) => (a.date + 'T' + (a.time || '')) < (b.date + 'T' + (b.time || '')) ? 1 : -1);
  const r = af[0], d = new Date(r.date + 'T00:00:00');
  const dag = ['Zo','Ma','Di','Wo','Do','Vr','Za'][d.getDay()];
  const stb = r.holes.reduce((s, h) => s + stbFor(h), 0);
  return { regel1: dag + ' ' + d.getDate() + '-' + (d.getMonth() + 1) + '-' + d.getFullYear() + (r.time ? ' · ' + r.time : ''),
           stb: 'Stb ' + stb, hcp: whsStand(speler).nu.value.toFixed(1), id: r.id, hcpBij: r.hcp };
}"""
KOP = """() => ({ regels: [document.getElementById('hdrClubName').textContent.trim(), ...document.getElementById('hdrRoundName').innerText.split('\\n').map(x => x.trim())],
               hcp: (document.querySelector('#hdrRoundName .kop-hcp') || {dataset: {}}).dataset.hcp || '',
               pijl: !!document.querySelector('#hdrRoundName .kop-hcp svg'),
               rechts: document.getElementById('hdrHoleCount').textContent.trim(),
               hoogte: Math.round(document.querySelector('header').getBoundingClientRect().height),
               rij: (() => { const cs = getComputedStyle(document.getElementById('hdrRoundName').parentElement); return cs.position + ' ' + cs.zIndex; })() })"""

def dag(n):
    return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()

        print("\n=== 1. LEGE KOP: LAATSTE RONDE EN HANDICAP ===\n")
        pg, pf = await nieuw(b)
        v = await pg.evaluate(VERWACHT)
        k = await pg.evaluate(KOP)
        check("regel 1: de laatste ronde, met jaartal en tijd", k['regels'][0], v['regel1'])
        check("regel 2 begint met de Stb", k['regels'][1].startswith(v['stb'] + ' · Hcp '), True)
        check("regel 2: de WHS-hcp van nu", k['hcp'], v['hcp'])
        check("rechts staat niets meer", k['rechts'], '')
        # Speelde je de laatste ronde met een andere handicap dan er nu staat: toch alleen de
        # nieuwe handicap (13528F3-001). Vast gezet (0.5 lager), zodat dit niet van de testdata afhangt.
        check("de laatste ronde is qualifying (anders test dit niets)", await pg.evaluate("(id) => !!loadSavedRounds().find(r => r.id === id).qualifying", v['id']), True)
        oud = round(float(v['hcp']) - 0.5, 1)
        await pg.evaluate("(a) => { const s = loadSavedRounds(); s.find(r => r.id === a[0]).hcp = a[1]; setRoundsAndMark(JSON.stringify(s)); _legeKopSleutel = null; toonLegeKop(); }", [v['id'], oud])
        kv = await pg.evaluate(KOP)
        check("de handicap veranderde: toch alleen de nieuwe, zonder pijl en verschil (13528F3-001)", (kv['regels'][1], kv['pijl']), (f"{v['stb']} · Hcp {v['hcp']}", False))
        check("regel 1 is de titel: groen en vet, regel 2 even groot maar halfvet (13528F3-001)", await pg.evaluate("""() => { const r = getComputedStyle(document.getElementById('hdrRoundName')), t = getComputedStyle(document.getElementById('hdrClubName'));
            const g = document.createElement('span'); g.style.color = 'var(--green-light)'; document.body.appendChild(g); const groen = getComputedStyle(g).color; g.remove();
            return [r.fontSize, t.fontSize, r.fontWeight, t.fontWeight, t.color === groen, /Geen geplande rondes/.test(document.querySelector('header').textContent)]; }"""), ['20px', '20px', '600', '800', True, False])
        check("en de kop even hoog als zonder handicap in de kop", kv['hoogte'], k['hoogte'])
        check("de regel staat boven het silhouet", k['rij'], 'relative 1')
        # Speelde je met de handicap die er nu staat, dan geen verloop: alleen de hcp.
        await pg.evaluate("(id) => { const s = loadSavedRounds(); s.find(r => r.id === id).hcp = whsStand(startPlayerName()).nu.value; setRoundsAndMark(JSON.stringify(s)); _legeKopSleutel = null; toonLegeKop(); }", v['id'])
        kz = await pg.evaluate(KOP)
        check("geen verandering: alleen de hcp, zonder pijl", (kz['regels'][1], kz['pijl']), (f"{v['stb']} · Hcp {v['hcp']}", False))
        check("ook dan even hoog", kz['hoogte'], k['hoogte'])
        await pg.evaluate("(id) => { const s = loadSavedRounds(); s.find(r => r.id === id[0]).hcp = id[1]; setRoundsAndMark(JSON.stringify(s)); _legeKopSleutel = null; toonLegeKop(); }", [v['id'], v['hcpBij']])
        await pg.evaluate("""(d) => { const s = loadSavedRounds(); const b = s.find(r => isRondeAf(r));
            s.push({ ...b, id: 990001, date: d, time: '10:00', holes: b.holes.map(h => ({ ...h, score: null })) });
            setRoundsAndMark(JSON.stringify(s)); toonLegeKop(); }""", dag(4))
        kg = await pg.evaluate(KOP)
        check("met een geplande ronde: geen hcp in de kop", kg['hcp'], '')
        check("de kop blijft even hoog", kg['hoogte'], k['hoogte'])
        await pg.evaluate("() => { setRoundsAndMark(JSON.stringify(loadSavedRounds().filter(r => r.id !== 990001))); toonLegeKop(); }")
        check("weer niets gepland: weer de laatste ronde", (await pg.evaluate(KOP))['regels'][0], v['regel1'])
        # Zonder 'Handicap bijhouden' geen handicap
        await pg.evaluate("() => { const r = loadSavedRounds(); setRoundsAndMark(JSON.stringify(r)); }")
        geen = await pg.evaluate("() => { const oud = whsVolgen; window.whsVolgen = () => false; _legeKopSleutel = null; toonLegeKop(); const t = document.getElementById('hdrRoundName').innerText; window.whsVolgen = oud; _legeKopSleutel = null; toonLegeKop(); return t; }")
        check("zonder handicap bijhouden: geen Hcp, wel de Stb", ('Hcp' in geen, v['stb'] in geen), (False, True))
        # Nog geen gespeelde ronde: dan wel 'Geen geplande rondes', grijs, en de kop even hoog
        nog = await pg.evaluate("""() => { const r = loadSavedRounds(); setRoundsAndMark(JSON.stringify(r.map(x => ({...x, player: 'Iemand anders'})))); _legeKopSleutel = null; _kopLaatste = null; toonLegeKop();
            const t = document.getElementById('hdrClubName'), uit = [t.textContent, t.classList.contains('info-msg'), Math.round(document.querySelector('header').getBoundingClientRect().height)];
            setRoundsAndMark(JSON.stringify(r)); _legeKopSleutel = null; toonLegeKop(); return uit; }""")
        check("nog geen gespeelde ronde: 'Geen geplande rondes', grijs, even hoog (13528F3-001)", nog, ['Geen geplande rondes', True, k['hoogte']])
        # Een ronde starten: de kop krijgt zijn gewone regels terug, even hoog, zonder de marge.
        await pg.evaluate("nav('setup')"); await pg.click('#startRoundBtn'); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { const b = document.getElementById('confirmModalBtn'); if (b && !document.getElementById('confirmModal').classList.contains('hidden')) b.click(); }")
        await pg.wait_for_timeout(300)
        kr = await pg.evaluate("() => [!!(game && game.started), document.getElementById('hdrRoundName').style.marginBottom, !!document.querySelector('#hdrRoundName br, #hdrRoundName .kop-hcp')]")
        check("in een ronde: de marge en de tweede regel weg", kr, [True, '', False])
        check("geen paginafouten", pf, [])
        await pg.close()

        print("\n=== 2. ACTIEF TABBLAD GOUD, OOK IN DE LICHTE MODUS ===\n")
        for thema in ('light', 'dark'):
            pg, pf = await nieuw(b, thema)
            await pg.evaluate("nav('archive')"); await pg.wait_for_timeout(400)
            kl = await pg.evaluate("""() => { const t = document.createElement('span'); t.style.color = 'var(--gold)'; document.body.appendChild(t);
                const goud = getComputedStyle(t).color; t.remove();
                return [getComputedStyle(document.getElementById('tab-archive')).color === goud,
                        getComputedStyle(document.getElementById('tab-stat')).color === goud]; }""")
            check(f"{thema}: actief goud, de rest niet", kl, [True, False])
            await pg.close()

        print("\n=== 3. RONDEKAART: VETTE SCORES, GEEN 'PCC —' ===\n")
        pg, pf = await nieuw(b)
        await pg.evaluate("""() => { const s = loadSavedRounds(); const af = s.filter(r => isRondeAf(r));
            af[0].pcc = null; af[0].sdFinal = null; af[1].pcc = 1; af[1].sdFinal = null;
            setRoundsAndMark(JSON.stringify(s)); nav('archive'); }""")
        await pg.wait_for_timeout(400)
        kaart = await pg.evaluate("""() => { const s = loadSavedRounds().filter(r => isRondeAf(r));
            const alles = document.getElementById('savedList').innerText;
            const getallen = [...document.querySelectorAll('#savedList .kaart-getal')];
            return { pccLeeg: /Pcc —/.test(alles), pccIngevuld: /Pcc \\+?1/.test(alles),
                     vet: getallen.length > 0 && getallen.every(g => getComputedStyle(g).fontWeight === '800'),
                     strEnStb: /Str \\d/.test(alles) && /Stb \\d/.test(alles) && getallen.some(g => /^Str/.test(g.parentElement.textContent.trim())) }; }""")
        check("'Pcc —' nergens meer", kaart['pccLeeg'], False)
        check("een ingevulde Pcc staat er wel", kaart['pccIngevuld'], True)
        check("de getallen zijn vet (800)", kaart['vet'], True)
        check("Str en Stb staan er nog", kaart['strEnStb'], True)
        check("geen paginafouten", pf, [])
        await pg.close()

        print("\n=== 4. OPSLAG IN kB ONDER 1 MB ===\n")
        pg, pf = await nieuw(b)
        uit = []
        for usage in (317000, 2621440):
            uit.append(await pg.evaluate("""async (u) => {
                Object.defineProperty(navigator, 'storage', { configurable: true, value: {
                    persisted: async () => false, estimate: async () => ({ usage: u }), persist: async () => false } });
                await refreshStorageStatus(); return document.getElementById('storageStatusLine').textContent; }""", usage))
        check("317000 bytes", uit[0], 'Opslag beschermd: nee · 310 kB gebruikt')
        check("2,5 MiB", uit[1], 'Opslag beschermd: nee · 2.5 MB gebruikt')
        await pg.close()

        print("\n=== 5. CLUBKAART: KORTE NAAM GRIJS, ZONDER 'KORT:' ===\n")
        pg, pf = await nieuw(b)
        await pg.evaluate("nav('club')"); await pg.wait_for_timeout(400)
        c = await pg.evaluate("""() => { const k = document.querySelector('#screen-club .card'); const r = k.children[1];
            const t = document.createElement('span'); t.style.color = 'var(--muted)'; document.body.appendChild(t);
            const grijs = getComputedStyle(t).color; t.remove();
            return { kort: /Kort:/.test(document.getElementById('screen-club').innerText), grijs: getComputedStyle(r).color === grijs,
                     grootte: getComputedStyle(r).fontSize }; }""")
        check("'Kort:' staat er niet meer", c['kort'], False)
        check("de korte naam is grijs", c['grijs'], True)
        check("en even groot als de clubnaam", c['grootte'], '20px')
        await pg.close()

        print("\n=== 6. SCORECIJFERS EVEN BREED ===\n")
        pg, pf = await nieuw(b)
        check("rijen van de scorekaart: tabular-nums", await pg.evaluate("""() => { const d = document.createElement('div'); d.className = 'sum-tr';
            document.body.appendChild(d); const v = getComputedStyle(d).fontVariantNumeric; d.remove(); return v; }"""), 'tabular-nums')
        await pg.close()

        print("\n=== 7. RONDEKAART: INSPRINGEN, PAR EN HOLES BIJ ELKAAR ===\n")
        pg, pf = await nieuw(b)
        await pg.evaluate("nav('archive')"); await pg.wait_for_timeout(400)
        k = await pg.evaluate("""() => { const kaart = document.querySelector('#savedList .saved-item');
            const regels = [...kaart.querySelectorAll('.saved-meta')];
            const baan = regels.find(m => /\\d+h$/.test(m.textContent.trim()));
            const span = baan && [...baan.querySelectorAll('span')].find(x => x.style.whiteSpace === 'nowrap');
            const cs = getComputedStyle(regels[0]);
            return { inspring: regels.every(m => { const c = getComputedStyle(m); return c.textIndent === '-' + c.paddingLeft && parseFloat(c.paddingLeft) > 0; }),
                     samen: span ? /^Par \\d+ · \\d+h$/.test(span.textContent) : false }; }""")
        check("elke regel springt in als hij afbreekt", k['inspring'], True)
        check("'Par … · …h' blijft bij elkaar", k['samen'], True)
        # Afbreken werkt echt: een lange baannaam op een smal scherm
        smal = await pg.evaluate("""() => { const m = [...document.querySelectorAll('#savedList .saved-meta')].find(m => /\\d+h$/.test(m.textContent.trim()));
            m.firstChild.textContent = 'Een heel erg lange baannaam voor de proef · '; const r = m.getClientRects(); const range = document.createRange();
            range.selectNodeContents(m); const lijnen = [...range.getClientRects()]; const links = [...new Set(lijnen.map(l => Math.round(l.left)))].sort((a, b) => a - b);
            return { regels: new Set(lijnen.map(l => Math.round(l.top))).size, inspring: links.length > 1 ? links[links.length - 1] - links[0] : 0 }; }""")
        check("een lange regel breekt af en de tweede regel springt in", smal['regels'] > 1 and smal['inspring'] > 10, True)
        await pg.close()

        print("\n=== 8. HERSTELKNOPPEN NIET GEDIMD ===\n")
        pg, pf = await nieuw(b)
        check("drie herstelknoppen, alle volledig zichtbaar", await pg.evaluate("""() => ['resetHcpToComputed', 'resetChcpOverride', 'resetChcpSpeler2Override']
            .map(f => getComputedStyle(document.querySelector('button[onclick="' + f + '()"]')).opacity)"""), ['1', '1', '1'])
        await pg.close()

        print("\n=== 9. BACKUPBLOK MET CHEVRON ===\n")
        pg, pf = await nieuw(b)
        await pg.evaluate("nav('settings')"); await pg.wait_for_timeout(400)
        c = await pg.evaluate("""() => { const k = document.getElementById('backupStatusTop'), ch = document.getElementById('backupStatusChevron');
            const kr = k.getBoundingClientRect(), cr = ch ? ch.getBoundingClientRect() : null;
            return { chevron: !!ch && cr.width > 0, rechts: !!cr && kr.right - cr.right < 30, tekst: document.getElementById('lastBackupInfoTop').textContent.trim().startsWith('Backup rondes') }; }""")
        check("chevron rechts in het blok", (c['chevron'], c['rechts']), (True, True))
        check("de backupregel staat er nog", c['tekst'], True)
        await pg.evaluate("() => document.getElementById('backupStatusChevron').dispatchEvent(new MouseEvent('click', {bubbles: true}))")
        await pg.wait_for_timeout(300)
        check("een tik op de chevron gaat naar Gegevens", await pg.evaluate("() => !document.getElementById('settingsTabData').classList.contains('hidden') && getComputedStyle(document.getElementById('settingsTabData')).display !== 'none'"), True)
        check("geen paginafouten", pf, [])
        await pg.close()

        await b.close()
    print(f"\n{'GEEN FOUTEN' if not fouten else str(len(fouten)) + ' FOUT(EN): ' + ', '.join(fouten)}")
    sys.exit(1 if fouten else 0)

asyncio.run(main())
