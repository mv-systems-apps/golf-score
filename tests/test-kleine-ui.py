"""Kleine verbeteringen in beeld.

1. Lege kop (niets gepland): links grijs 'Geen geplande rondes', regel 2 en rechts leeg, en
   de agenda van 14 dagen eronder (13528F5-002; zie test-kop-gepland). De laatste ronde en
   de handicap staan niet meer in de kop. De kop blijft even hoog, ook met een geplande
   ronde en in een ronde.
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

KOP = """() => ({ regels: [document.getElementById('hdrClubName').textContent.trim(), ...document.getElementById('hdrRoundName').innerText.split('\\n').map(x => x.trim())],
               rechts: document.getElementById('hdrHoleCount').textContent.trim(),
               hoogte: Math.round(document.querySelector('header').getBoundingClientRect().height),
               rij: (() => { const cs = getComputedStyle(document.getElementById('hdrRoundName').parentElement); return cs.position + ' ' + cs.zIndex; })() })"""

def dag(n):
    return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()

        print("\n=== 1. LEGE KOP: GEEN GEPLANDE RONDES, WEL DE AGENDA ===\n")
        pg, pf = await nieuw(b)
        k = await pg.evaluate(KOP)
        check("regel 1 'Geen geplande rondes', regel 2 en rechts leeg (13528F5-002)", (k['regels'][0], k['regels'][1], k['rechts']), ('Geen geplande rondes', '', ''))
        check("geen laatste ronde of handicap in de kop (13528F5-002)", await pg.evaluate("() => /Stb|Hcp/.test(document.getElementById('hdrClubName').textContent + document.getElementById('hdrRoundName').textContent + document.getElementById('hdrTrack').textContent)"), False)
        check("regel 1 even groot als altijd, grijs (13528F5-002)", await pg.evaluate("""() => { const t = document.getElementById('hdrClubName'); return [getComputedStyle(t).fontSize, t.classList.contains('info-msg')]; }"""), ['20px', True])
        check("de regel staat boven de agenda", k['rij'], 'relative 1')
        # Een geplande ronde erbij en weer weg: de kop blijft even hoog.
        await pg.evaluate("""(d) => { const s = loadSavedRounds(); const b = s.find(r => isRondeAf(r));
            s.push({ ...b, id: 990001, date: d, time: '10:00', holes: b.holes.map(h => ({ ...h, score: null })) });
            setRoundsAndMark(JSON.stringify(s)); toonLegeKop(); }""", dag(4))
        kg = await pg.evaluate(KOP)
        check("met een geplande ronde: die in de kop", kg['regels'][0], '+4 dagen')
        check("de kop blijft even hoog", kg['hoogte'], k['hoogte'])
        await pg.evaluate("() => { setRoundsAndMark(JSON.stringify(loadSavedRounds().filter(r => r.id !== 990001))); toonLegeKop(); }")
        kw = await pg.evaluate(KOP)
        check("weer niets gepland: weer 'Geen geplande rondes', even hoog", (kw['regels'][0], kw['hoogte']), ('Geen geplande rondes', k['hoogte']))
        # Een ronde starten: de kop krijgt zijn gewone regels terug, even hoog, zonder de marge.
        await pg.evaluate("nav('setup')"); await pg.click('#startRoundBtn'); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { const b = document.getElementById('confirmModalBtn'); if (b && !document.getElementById('confirmModal').classList.contains('hidden')) b.click(); }")
        await pg.wait_for_timeout(300)
        kr = await pg.evaluate("() => [!!(game && game.started), document.getElementById('hdrRoundName').style.marginTop, document.getElementById('hdrGeplandStrook').classList.contains('hidden')]")
        check("in een ronde: de gewone regels, zonder agenda", kr, [True, '', True])
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
