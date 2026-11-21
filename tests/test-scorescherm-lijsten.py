"""Het lege scorescherm met alle geplande en gepauzeerde rondes (13528FB-001).

Per soort één kop (Geplande ronde(s), Gepauzeerde ronde(s)) en één lijst: de eerste ronde
staat open als volledige kaart, de volgende als compacte regel: icoon, datum en tijd, club ·
baan (gepauzeerd ook de gespeelde holes). Een tik klapt een regel open tot een volledige kaart
met potlood, ▶ en Op deze baan; een tik op die kaart klapt hem dicht; per soort hooguit één open. Hoeveel regels:
Instellingen > Agenda (per groep, de eerste meegeteld: standaard 5, 0 t/m 10; − en + grijs bij de grens, ook bij Min. aantal rondes); de rest via 'Nog N' naar Rondes. Op elke
volledige kaart staat boven de ▶ het potlood (hetzelfde venster als in Rondes). Een tik op een
dag met een ronde in de agendastrook: het scorescherm met die ronde open (een dag zonder ronde:
de eerstvolgende ronde erna, anders alleen het scorescherm; bovenin de kop en '+N': Rondes) en een zacht groen vlak om die dag (ook om
de dag van de eerste, zolang die open staat; alleen op het lege scorescherm).

Via de echte bediening: tikken op regels, kaarten, potlood, ▶, 'Nog N', de strook, − en +.
"""
import asyncio, os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

async def ev(pg, js, arg=None):
    try:
        return await pg.evaluate(js, arg)
    except Exception as e:
        return 'FOUT: ' + str(e).split('\n')[0][:120]

async def klik(pg, sel):
    try: await pg.locator(sel).first.click(timeout=2000); await pg.wait_for_timeout(250); return True
    except Exception: return False

HIER = os.path.dirname(os.path.abspath(__file__))
PLAN = open(os.path.join(HIER, 'test-op-deze-baan.py')).read().split('PLAN = """')[1].split('"""')[0]
DAGEN = (6, 9, 13, 20, 27, 34, 41)
def dag(n): return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()

STAAT = """() => { const m = document.getElementById('scoreEmptyMsg'); if (!m) return null;
  return { koppen: [...m.querySelectorAll('.lege-kop')].map(k => (k.querySelector('.lege-kop-titel') || k).textContent),
           regels: [...m.querySelectorAll('.lege-regel')].map(r => r.dataset.soort + ':' + r.dataset.ids),
           open: [...m.querySelectorAll('.lege-open')].map(o => o.dataset.regel),
           meer: [...m.querySelectorAll('.lege-meer')].map(b => b.textContent.trim()) }; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 900})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        for i, d in enumerate(DAGEN):
            await ev(pg, PLAN % dag(d), [990101 + i, 'Golfclub Heelsum', 'Airborne', 'Blauw', None])
        await ev(pg, "() => { nav('score'); verversLegeScoreKnoppen(); _legeKopSleutel = null; toonLegeKop(); }"); await pg.wait_for_timeout(300)
        gepauzeerd = await ev(pg, "() => legeScoreKeuzes().gepauzeerdAlle.length")

        print("\n=== 1. DE LIJSTEN ===\n")
        st = await ev(pg, STAAT)
        check("koppen: geplande, gepauzeerde, andere ronde", st and st['koppen'], ['Geplande rondes', 'Gepauzeerde rondes' if isinstance(gepauzeerd, int) and gepauzeerd > 1 else 'Gepauzeerde ronde', 'Andere ronde'])
        check("de eerste van elke soort staat open", st and st['open'], ['gepland:990101'] + (['gepauzeerd:' + str(await ev(pg, "() => legeScoreKeuzes().gepauzeerdAlle[0].map(r => r.id).join(',')"))] if gepauzeerd else []))
        gepl = [r for r in (st or {}).get('regels', []) if r.startswith('gepland:')]
        # standaard 5 per groep, de eerste meegeteld (sinds 13528FC-005; eerder 5 ná de eerste)
        check("standaard: vijf, de eerste open en vier als regel", gepl, [f'gepland:{990102 + i}' for i in range(4)])
        check("'Nog 2' voor de zesde en zevende", (st or {}).get('meer', [])[:1], ['Nog 2'])
        # de rest van deze test met zes per groep, zoals hij geschreven is
        await ev(pg, "() => { localStorage.setItem('golf_lege_lijst_n', '6'); verversLegeScoreKnoppen(); }"); await pg.wait_for_timeout(200)
        st = await ev(pg, STAAT)
        check("zes: de eerste open en vijf als regel, 'Nog 1'", [[r for r in st['regels'] if r.startswith('gepland:')], st['meer'][:1]], [[f'gepland:{990102 + i}' for i in range(5)], ['Nog 1']])
        r = await ev(pg, """() => { const r = document.querySelector('#scoreEmptyMsg .lege-regel[data-soort="gepland"]');
            return [r.querySelector('.lege-regel-wanneer').textContent, r.querySelector('.lege-regel-wat').textContent.replace(/\u00a0/g, ' '), !!r.querySelector('.agenda-status'), !!r.querySelector('.lege-regel-pijl svg'),
                    r.textContent.includes('Testspeler')]; }""")
        check("een regel: datum en tijd, club · baan, agenda-icoon, pijltje, geen speler", r and [r[1], r[2], r[3], r[4]], ['Heelsum · Airborne', True, True, False])
        if isinstance(gepauzeerd, int) and gepauzeerd > 1:
            pz = await ev(pg, """() => { const r = document.querySelector('#scoreEmptyMsg .lege-regel[data-soort="gepauzeerd"]'); if (!r) return null;
                return [/\\d+\\/\\d+$/.test(r.querySelector('.lege-regel-wat').textContent), !!r.querySelector('.lege-regel-pauze'), !r.querySelector('.agenda-status')]; }""")
            check("gepauzeerd als regel: gespeelde holes, pauzeteken, geen agenda-icoon", pz, [True, True, True])
        else:
            print('    (de testgegevens hebben maar één gepauzeerde ronde)')

        uitlijning = await ev(pg, """() => { const m = e => { if (!e) return null; const r = e.getBoundingClientRect(); return [(r.left + r.right) / 2, r.left]; };
            const odb = m([...(document.querySelector('#scoreEmptyMsg .lege-open[data-regel^=gepland] .odb-kop')?.querySelectorAll('svg') || [])].pop());
            const pijl = m(document.querySelector('#scoreEmptyMsg .lege-regel[data-soort=gepland] .lege-regel-pijl svg'));
            const ki = m(document.querySelector('#scoreEmptyMsg .lege-open[data-regel^=gepland] .agenda-status')), ri = m(document.querySelector('#scoreEmptyMsg .lege-regel[data-soort=gepland] .agenda-status'));
            return odb && pijl && ki && ri ? [Math.abs(odb[0] - pijl[0]) < 0.6, Math.abs(ki[1] - ri[1]) < 0.6] : null; }""")
        check("de gouden pijltjes recht onder elkaar (regel en Op deze baan), de iconen ook", uitlijning, [True, True])

        print("\n=== 2. OPEN- EN DICHTKLAPPEN ===\n")
        await klik(pg, '#scoreEmptyMsg .lege-regel[data-ids="990103"]')
        st = await ev(pg, STAAT)
        check("tik op een regel: die staat open als kaart, de eerste dicht", st and [o for o in st['open'] if o.startswith('gepland:')], ['gepland:990103'])
        kaart = await ev(pg, """() => { const o = document.querySelector('#scoreEmptyMsg .lege-open'); if (!o) return null;
            return [!!o.querySelector('.lege-knop-bewerk'), !!o.querySelector('.lege-knop-actie'), !!o.querySelector('.odb-kop'), o.querySelector('.lege-knop').getAttribute('aria-expanded')]; }""")
        check("open: potlood, ▶, Op deze baan", kaart, [True, True, True, 'true'])
        check("de dag in de strook is gekozen", await ev(pg, f"() => document.querySelector('#hdrGeplandStrook .kop-dag[data-iso=\"{dag(13)}\"]')?.classList.contains('kop-open')"), True)
        check("de dag: een groen vlak (niet het goud van .gekozen), geen rand", await ev(pg, f"() => {{ const d = document.querySelector('#hdrGeplandStrook .kop-dag[data-iso=\"{dag(13)}\"]'); if (!d) return null; const c = getComputedStyle(d); const t = document.createElement('div'); t.style.background = 'color-mix(in srgb, var(--green-light) 30%, transparent)'; document.body.appendChild(t); const v = getComputedStyle(t).backgroundColor; t.remove(); return [c.backgroundColor === v, c.boxShadow === 'none']; }}"), [True, True])
        await klik(pg, '#scoreEmptyMsg .lege-regel[data-ids="990105"]')
        check("een andere regel open: de vorige klapt dicht", [o for o in (await ev(pg, STAAT))['open'] if o.startswith('gepland:')], ['gepland:990105'])
        check("gekozen dag verhuist mee", await ev(pg, f"() => [...document.querySelectorAll('#hdrGeplandStrook .kop-dag.kop-open')].map(d => d.dataset.iso)"), [dag(27)] if (datetime.date.fromisoformat(dag(27)) - datetime.date.today()).days < 14 else [])
        # Waar je op de open kaart tikt: bovenin (tot net boven de club) klapt dicht, het
        # agenda-icoon heeft daar een ruimer vlak, de rest gaat naar die ronde in Rondes.
        async def tik_op(sel, dx=0.5, dy=0.5, absx=None):
            box = await ev(pg, f"() => {{ const e = document.querySelector('{sel}'); if (!e) return null; e.scrollIntoView({{block: 'center'}}); const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }}")
            if not isinstance(box, list): return False
            await pg.mouse.click(absx if absx is not None else box[0] + box[2] * dx, box[1] + box[3] * dy); await pg.wait_for_timeout(300); return True
        KAART = '#scoreEmptyMsg .lege-open[data-regel="gepland:990105"]'
        # op de spelersnaam (onder de datum, boven de club): dicht
        await tik_op(KAART + ' .lege-knop-namen', 0.3, 0.5)
        check("tik op de naam (boven de club): klapt dicht", [o for o in (await ev(pg, STAAT))['open'] if o.startswith('gepland:')], [])
        check("en geen gekozen dag meer", await ev(pg, "() => document.querySelectorAll('#hdrGeplandStrook .kop-dag.kop-open').length"), 0)

        await klik(pg, '#scoreEmptyMsg .lege-regel[data-ids="990103"]')
        KAART = '#scoreEmptyMsg .lege-open[data-regel="gepland:990103"]'
        # op het agenda-icoon (alleen de stand, sinds 13528FC-003): klapt dicht, exporteert niet
        await ev(pg, "() => { window.__exp = []; window.__echtExp = window.exportRoundIcs; window.exportRoundIcs = id => window.__exp.push(String(id)); return true; }")
        await tik_op(KAART + ' .agenda-status', 0.5, 0.5)
        check("tik op het agenda-icoon van de open kaart: klapt dicht, exporteert niet",
              [await ev(pg, "() => { const l = window.__exp; window.exportRoundIcs = window.__echtExp; return l; }"), [o for o in (await ev(pg, STAAT))['open'] if o.startswith('gepland:')]], [[], []])
        await klik(pg, '#scoreEmptyMsg .lege-regel[data-ids="990103"]')
        # op de club: naar die ronde in Rondes (agenda), de kaart licht op
        await tik_op(KAART + ' .lege-knop-waar', 0.3, 0.5)
        await pg.wait_for_timeout(150)
        check("tik op de club: Rondes in de agendaweergave, deze ronde in beeld en oplichtend",
              await ev(pg, "() => [document.querySelector('.screen.active')?.id, archiefGroepering, !!document.querySelector('#round-full-990103.round-flash'), (() => { const k = document.getElementById('round-full-990103'); if (!k) return false; const r = k.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; })()]"),
              ['screen-archive', 'gepland', True, True])
        await ev(pg, "() => nav('score')"); await pg.wait_for_timeout(250)
        # met het toetsenbord (Enter op de kaart): in- en uitklappen
        await ev(pg, f"() => document.querySelector('{KAART} .lege-knop')?.focus()")
        await pg.keyboard.press('Enter'); await pg.wait_for_timeout(250)
        check("Enter op de open kaart: klapt dicht", [o for o in (await ev(pg, STAAT))['open'] if o.startswith('gepland:')], [])
        # een gepauzeerde kaart: tik onder de datum (op de club) gaat naar Rondes, Gepauzeerd open
        pz = await ev(pg, "() => (legeScoreKeuzes().gepauzeerdAlle[0] || [])[0]?.id ?? null")
        if pz is not None:
            await tik_op('#scoreEmptyMsg .lege-open[data-regel^="gepauzeerd"] .lege-knop-waar', 0.3, 0.5)
            await pg.wait_for_timeout(150)
            check("gepauzeerde kaart, tik op de club: Rondes per categorie, deze ronde oplichtend",
                  await ev(pg, f"() => [document.querySelector('.screen.active')?.id, archiefGroepering, !!document.querySelector('#round-full-{pz}.round-flash')]"), ['screen-archive', 'categorie', True])
            await ev(pg, "() => nav('score')"); await pg.wait_for_timeout(250)

        print("\n=== 3. ICOON, POTLOOD, ▶, NOG ===\n")
        r = await ev(pg, """async () => { const a = document.querySelector('#scoreEmptyMsg .lege-regel[data-ids="990104"] .agenda-status'); if (!a) return null;
            const echt = { cs: navigator.canShare, sh: navigator.share }; let gedeeld = 0;
            try { navigator.canShare = () => true; navigator.share = async () => { gedeeld++; }; a.click(); await new Promise(r => setTimeout(r, 150)); }
            finally { navigator.canShare = echt.cs; navigator.share = echt.sh; }
            const nu = document.querySelector('#scoreEmptyMsg .lege-regel[data-ids="990104"] .agenda-status, #scoreEmptyMsg .lege-open[data-regel="gepland:990104"] .agenda-status');
            return [gedeeld, document.querySelectorAll('#scoreEmptyMsg .lege-open[data-regel="gepland:990104"]').length, nu ? [...nu.classList].find(c => c.startsWith('agenda-') && c !== 'agenda-status') : null]; }""")
        # Sinds 13528FC-003 toont het icoon in een compacte regel alleen de status: een tik klapt de regel open
        check("agenda-icoon in een regel: exporteert niet, klapt de regel open", r and r[:2], [0, 1])
        check("het icoon in de regel is geen knop (geen role, niet focusbaar)", await ev(pg, "() => { const a = document.querySelector('#scoreEmptyMsg .lege-regel[data-soort=gepland] .agenda-status'); return a ? [a.getAttribute('role'), a.tabIndex] : 'geen regel'; }"), [None, -1])
        await klik(pg, '#scoreEmptyMsg .lege-regel[data-ids="990101"]')
        maat = await ev(pg, """() => { const k = document.querySelector('#scoreEmptyMsg .lege-knop[data-soort="gepland"]'); const c = k.getBoundingClientRect();
            const p = k.querySelector('.lege-knop-bewerk').getBoundingClientRect(), s = k.querySelector('.lege-knop-actie').getBoundingClientRect(), bw = parseFloat(getComputedStyle(k).borderTopWidth) || 0;
            const ruimte = [p.top - c.top - bw, s.top - p.bottom, c.bottom - bw - s.bottom];
            return [[Math.round(p.width), Math.round(p.height)], [Math.round(s.width), Math.round(s.height)], p.top < s.top, Math.max(...ruimte) - Math.min(...ruimte) <= 1]; }""")
        check("open kaart: potlood boven de ▶, beide 46×39, gelijke ruimte", maat, [[46, 39], [46, 39], True, True])
        await klik(pg, '#scoreEmptyMsg .lege-knop[data-soort="gepland"] .lege-knop-bewerk')
        v = await ev(pg, "() => [!document.getElementById('roundEditChoiceModal')?.classList.contains('hidden'), document.getElementById('roundEditChoiceTitle')?.textContent]")
        check("potlood: het venster van Rondes, voor deze ronde", isinstance(v, list) and v[0] and dag(6)[8:10].lstrip('0') in (v[1] or ''), True)
        print('    (', v, ')')
        await ev(pg, "() => { try { sluitRoundEditChoice(); } catch (e) {} }")
        await klik(pg, '#scoreEmptyMsg .lege-regel[data-ids="990102"]')
        await klik(pg, '#scoreEmptyMsg .lege-open[data-regel="gepland:990102"] .lege-knop-actie')
        check("▶ in een open kaart start die ronde", await ev(pg, "() => [!!(game && game.started), String(game.id)]"), [True, '990102'])
        await ev(pg, "() => document.getElementById('finishRoundBtn').click()"); await pg.wait_for_timeout(400)
        await ev(pg, "() => nav('score')"); await pg.wait_for_timeout(200)
        await klik(pg, '#scoreEmptyMsg .lege-meer')
        check("'Nog 1': naar Rondes", await ev(pg, "() => document.querySelector('.screen.active')?.id"), 'screen-archive')

        print("\n=== 4. DE AGENDASTROOK ===\n")
        await ev(pg, "() => nav('setup')"); await pg.wait_for_timeout(200)
        await klik(pg, f'#hdrGeplandStrook .kop-dag[data-iso="{dag(9)}"]')
        check("tik op een dag: het scorescherm met die ronde open", [await ev(pg, "() => document.querySelector('.screen.active')?.id"), [o for o in (await ev(pg, STAAT))['open'] if o.startswith('gepland:')]], ['screen-score', ['gepland:990102']])
        await klik(pg, f'#hdrGeplandStrook .kop-dag[data-iso="{dag(6)}"]')
        check("tik op de dag van de eerste ronde: de eerste open, met groen vlak", [[o for o in (await ev(pg, STAAT))['open'] if o.startswith('gepland:')], await ev(pg, "() => [...document.querySelectorAll('#hdrGeplandStrook .kop-dag.kop-open')].map(d => d.dataset.iso)")], [['gepland:990101'], [dag(6)]])
        await ev(pg, "() => nav('setup')"); await pg.wait_for_timeout(200)
        check("op een ander scherm geen groen vlak", await ev(pg, "() => document.querySelectorAll('#hdrGeplandStrook .kop-dag.kop-open').length"), 0)
        await ev(pg, "() => nav('score')"); await pg.wait_for_timeout(200)
        check("terug op het scorescherm: het groene vlak om de open ronde", await ev(pg, "() => [...document.querySelectorAll('#hdrGeplandStrook .kop-dag.kop-open')].map(d => d.dataset.iso)"), [dag(6)])
        # Een dag zonder ronde: de eerstvolgende ronde ná die dag open (anders alleen het scorescherm);
        # de ruimte tussen de dagen hoort bij de dag rechts ervan. '+N' en de kop erboven: Rondes.
        OPEN = "() => [document.querySelector('.screen.active')?.id, [...document.querySelectorAll('#scoreEmptyMsg .lege-open[data-regel^=gepland]')].map(e => e.dataset.regel), [...document.querySelectorAll('#hdrGeplandStrook .kop-dag.kop-open')].map(d => d.dataset.iso)]"
        await ev(pg, "() => nav('setup')"); await pg.wait_for_timeout(200)
        await klik(pg, '#hdrGeplandStrook .kop-dag.vandaag')
        check("tik op vandaag (zonder ronde): het scorescherm met de eerstvolgende open", await ev(pg, OPEN), ['screen-score', ['gepland:990101'], [dag(6)]])
        await klik(pg, f'#hdrGeplandStrook .kop-dag[data-iso="{dag(7)}"]')
        check("tik op een lege dag tussen twee rondes: de ronde erna open", await ev(pg, OPEN), ['screen-score', ['gepland:990102'], [dag(9)]])
        # de ruimte tussen dag 10 en 11: hoort bij 11, dus de ronde van dag 13 (aangeroepen met een tik-positie)
        r = await ev(pg, f"""() => {{ const d = document.querySelector('#hdrGeplandStrook .kop-dag[data-iso="{dag(11)}"]'); if (!d) return null;
            kopTik({{ target: document.getElementById('hdrGeplandStrook'), clientX: d.getBoundingClientRect().left - 0.5 }}); return true; }}""")
        await pg.wait_for_timeout(200)
        check("tik in de ruimte voor dag 11: telt als dag 11, de ronde van dag 13 open", await ev(pg, OPEN), ['screen-score', ['gepland:990103'], [dag(13)]])
        await klik(pg, '#hdrGeplandStrook .kop-later')
        check("tik op het aantal daarna (+N): Rondes", await ev(pg, "() => document.querySelector('.screen.active')?.id"), 'screen-archive')
        await ev(pg, "() => nav('score')"); await pg.wait_for_timeout(200)
        kop = await ev(pg, "() => { const r = document.querySelector('header').getBoundingClientRect(); return [r.left + 60, r.top + 14]; }")
        if isinstance(kop, list): await pg.mouse.click(kop[0], kop[1]); await pg.wait_for_timeout(250)
        check("tik bovenin de kop, boven de strook: Rondes", await ev(pg, "() => document.querySelector('.screen.active')?.id"), 'screen-archive')

        print("\n=== 5. DE INSTELLING ===\n")
        await ev(pg, "() => { nav('settings'); switchSettingsTab('main'); openSectie('settingsTabMain|Agenda ()'); }"); await pg.wait_for_timeout(300)
        await ev(pg, "() => { localStorage.removeItem('golf_lege_lijst_n'); nav('settings'); }"); await pg.wait_for_timeout(200)
        check("standaard 5", await ev(pg, "() => legeLijstNVal.textContent"), '5')
        check("de tekst", await ev(pg, "() => legeLijstNVal.parentElement.querySelector('span').textContent"), 'Aantal gepland en aantal gepauzeerd')
        for _ in range(3): await klik(pg, '[onclick="wijzigLegeLijstN(-1)"]')
        await ev(pg, "() => nav('score')"); await pg.wait_for_timeout(200)
        st = await ev(pg, STAAT)
        check("2: twee rondes (de eerste open, één regel), 'Nog 5'", [len([r for r in st['regels'] if r.startswith('gepland:')]), st['meer'][:1]], [1, ['Nog 5']])
        await ev(pg, "() => { nav('settings'); }")
        await klik(pg, '[onclick="wijzigLegeLijstN(-1)"]')
        check("1: − en + allebei aan", await ev(pg, "() => ['wijzigLegeLijstN(-1)', 'wijzigLegeLijstN(1)'].map(o => [...document.querySelectorAll('button')].find(b => b.getAttribute('onclick') === o)?.disabled)"), [False, False])
        await ev(pg, "() => nav('score')"); await pg.wait_for_timeout(200)
        st = await ev(pg, STAAT)
        check("1: alleen de eerste, open, en 'Nog 6'", [[r for r in st['regels'] if r.startswith('gepland:')], [o for o in st['open'] if o.startswith('gepland:')], st['meer'][:1]], [[], ['gepland:990101'], ['Nog 6']])
        await ev(pg, "() => { nav('settings'); }")
        await klik(pg, '[onclick="wijzigLegeLijstN(-1)"]')
        check("0: − grijs, + niet", await ev(pg, "() => ['wijzigLegeLijstN(-1)', 'wijzigLegeLijstN(1)'].map(o => [...document.querySelectorAll('button')].find(b => b.getAttribute('onclick') === o)?.disabled)"), [True, False])
        await ev(pg, "() => wijzigLegeLijstN(-1)")
        check("niet onder 0", await ev(pg, "() => [legeLijstNVal.textContent, localStorage.getItem('golf_lege_lijst_n')]"), ['0', '0'])
        await ev(pg, "() => nav('score')"); await pg.wait_for_timeout(200)
        st = await ev(pg, STAAT)
        check("0: geen kaart en geen regel, wel de kop met het aantal en 'Nog 7'", [[r for r in st['regels'] if r.startswith('gepland:')], [o for o in st['open'] if o.startswith('gepland:')], st['meer'][:1], await ev(pg, "() => document.querySelector('#scoreEmptyMsg .lege-kop[data-kop=gepland] .lege-kop-aantal')?.textContent")], [[], [], ['Nog 7'], '7'])
        await klik(pg, f'#hdrGeplandStrook .kop-dag[data-iso="{dag(6)}"]')
        check("0: tik op een dag met een ronde: naar Rondes (hij staat niet in de lijst)", await ev(pg, "() => document.querySelector('.screen.active')?.id"), 'screen-archive')
        await ev(pg, "() => { nav('settings'); }")
        for _ in range(10): await klik(pg, '[onclick="wijzigLegeLijstN(1)"]')
        check("10: + grijs, − niet", await ev(pg, "() => ['wijzigLegeLijstN(-1)', 'wijzigLegeLijstN(1)'].map(o => [...document.querySelectorAll('button')].find(b => b.getAttribute('onclick') === o)?.disabled)"), [False, True])
        await ev(pg, "() => wijzigLegeLijstN(1)")
        check("niet boven 10", await ev(pg, "() => legeLijstNVal.textContent"), '10')
        # Min. aantal rondes (1 t/m 10) werkt net zo
        await ev(pg, "() => { localStorage.setItem('golf_min_rounds_stat', '2'); nav('settings'); }")
        check("min. aantal rondes 2: geen van beide grijs", await ev(pg, "() => ['adjustMinRoundsStat(-1)', 'adjustMinRoundsStat(1)'].map(o => [...document.querySelectorAll('button')].find(b => b.getAttribute('onclick') === o)?.disabled)"), [False, False])
        await ev(pg, "() => adjustMinRoundsStat(-1)")   # staat in een ander, dichtgeklapt blok
        check("min. aantal rondes 1: − grijs", [await ev(pg, "() => minRoundsStatVal.textContent"), await ev(pg, "() => ['adjustMinRoundsStat(-1)', 'adjustMinRoundsStat(1)'].map(o => [...document.querySelectorAll('button')].find(b => b.getAttribute('onclick') === o)?.disabled)")], ['1', [True, False]])
        await ev(pg, "() => { localStorage.setItem('golf_min_rounds_stat', '10'); nav('settings'); }")
        check("min. aantal rondes 10: + grijs", await ev(pg, "() => ['adjustMinRoundsStat(-1)', 'adjustMinRoundsStat(1)'].map(o => [...document.querySelectorAll('button')].find(b => b.getAttribute('onclick') === o)?.disabled)"), [False, True])
        check("de instelling gaat mee in de export", await ev(pg, "() => INSTELLINGEN_EXPORT.some(d => d.k === 'golf_lege_lijst_n') && OPSLAGSLEUTELS.golf_lege_lijst_n === 'wissen'"), True)

        print("\n=== 6. EEN LANGE CLUBNAAM ===\n")
        await ev(pg, "() => { const s = loadSavedRounds(); s.forEach(r => { if (r.id === 990103) { r.clubShort = 'Golfclub De Hooge Bergsche Bosch'; r.track = 'Lange Duinen'; } }); setRoundsAndMark(JSON.stringify(s)); nav('score'); verversLegeScoreKnoppen(); }")
        r = await ev(pg, """() => { const r = document.querySelector('#scoreEmptyMsg .lege-regel[data-ids="990103"]'); const w = r.querySelector('.lege-regel-wat'), d = r.querySelector('.lege-regel-wanneer');
            return [w.scrollWidth > w.clientWidth, getComputedStyle(w).textOverflow, d.scrollWidth <= d.clientWidth + 1, r.getBoundingClientRect().right <= innerWidth]; }""")
        check("lange naam: afgekapt met …, datum heel, regel past", r, [True, 'ellipsis', True, True])
        print("\n=== 7. DE GOUDEN KOPPEN: NORMAAL OF VERKORT ===\n")
        # Zoals de kop in de handicapweergave van Rondes: een tik wisselt de hele groep.
        await ev(pg, "() => { localStorage.removeItem('golf_lege_verkort'); _legeOpen.gepland = undefined; _legeOpen.gepauzeerd = undefined; nav('score'); verversLegeScoreKnoppen(); }"); await pg.wait_for_timeout(250)
        KOP = """() => [...document.querySelectorAll('#scoreEmptyMsg .lege-kop')].map(k => [(k.querySelector('.lege-kop-titel') || k).textContent, k.querySelector('.lege-kop-aantal')?.textContent ?? null, k.getAttribute('aria-expanded')])"""
        koppen = await ev(pg, KOP)
        check("koppen met aantal (niet bij Andere ronde) en open", koppen and [[t, a is not None, e] for t, a, e in koppen], [['Geplande rondes', True, 'true'], ['Gepauzeerde rondes' if isinstance(gepauzeerd, int) and gepauzeerd > 1 else 'Gepauzeerde ronde', True, 'true'], ['Andere ronde', False, 'true']])
        await klik(pg, '#scoreEmptyMsg .lege-kop[data-kop="gepland"]')
        st = await ev(pg, STAAT)
        check("tik op Geplande rondes: verkort, alles als regel, niets open", [[o for o in st['open'] if o.startswith('gepland:')], len([r for r in st['regels'] if r.startswith('gepland:')]) >= 2, await ev(pg, "() => document.querySelector('#scoreEmptyMsg .lege-kop[data-kop=gepland]').getAttribute('aria-expanded')")], [[], True, 'false'])
        check("Gepauzeerd blijft zoals het was", [o for o in st['open'] if o.startswith('gepauzeerd:')] != [], True)
        check("de stand is bewaard", await ev(pg, "() => localStorage.getItem('golf_lege_verkort')"), 'gepland')
        await klik(pg, '#scoreEmptyMsg .lege-regel[data-soort="gepland"]')
        check("verkort: één regel openklappen kan nog", len([o for o in (await ev(pg, STAAT))['open'] if o.startswith('gepland:')]), 1)
        await ev(pg, "() => { nav('setup'); nav('score'); }"); await pg.wait_for_timeout(200)
        await pg.reload(); await pg.wait_for_timeout(500); await ev(pg, "() => nav('score')"); await pg.wait_for_timeout(250)
        check("na herladen nog verkort", [[o for o in (await ev(pg, STAAT))['open'] if o.startswith('gepland:')], await ev(pg, "() => document.querySelector('#scoreEmptyMsg .lege-kop[data-kop=gepland]')?.getAttribute('aria-expanded')")], [[], 'false'])
        # een tik op een dag in de strook opent die ronde, ook verkort (ook de eerstvolgende)
        await klik(pg, f'#hdrGeplandStrook .kop-dag[data-iso="{dag(6)}"]')
        check("verkort, tik op de dag van de eerste ronde: die staat open", [o for o in (await ev(pg, STAAT))['open'] if o.startswith('gepland:')], ['gepland:990101'])
        # Sinds 13528FD-003 volgt het pijltje wat je ziet: met een open kaart ▼, dus een tik klapt in
        await klik(pg, '#scoreEmptyMsg .lege-kop[data-kop="gepland"]')
        check("tik op de kop met een open kaart: alles compact, blijft verkort", [[o for o in (await ev(pg, STAAT))['open'] if o.startswith('gepland:')], await ev(pg, "() => localStorage.getItem('golf_lege_verkort')")], [[], 'gepland'])
        await klik(pg, '#scoreEmptyMsg .lege-kop[data-kop="gepland"]')
        check("nog een tik op de kop: normaal, de eerste open", [[o for o in (await ev(pg, STAAT))['open'] if o.startswith('gepland:')], await ev(pg, "() => localStorage.getItem('golf_lege_verkort')")], [['gepland:990101'], None])
        # Gepauzeerde rondes: ingeklapt is echt ingeklapt, alleen de kop
        await klik(pg, '#scoreEmptyMsg .lege-kop[data-kop="gepauzeerd"]')
        check("tik op Gepauzeerde rondes: alleen de kop, geen kaart of regel", [await ev(pg, "() => document.querySelectorAll('#scoreEmptyMsg [data-soort=gepauzeerd]').length"), await ev(pg, "() => !!document.querySelector('#scoreEmptyMsg .lege-kop[data-kop=gepauzeerd]')")], [0, True])
        await klik(pg, '#scoreEmptyMsg .lege-kop[data-kop="gepauzeerd"]')
        check("nog een tik: de gepauzeerde rondes terug, de eerste open", [o for o in (await ev(pg, STAAT))['open'] if o.startswith('gepauzeerd:')] != [], True)
        # Andere ronde: de knoppen weg en terug
        await klik(pg, '#scoreEmptyMsg .lege-kop[data-kop="andere"]')
        check("tik op Andere ronde: de knoppen weg", await ev(pg, "() => [...document.querySelectorAll('#scoreEmptyMsg button')].some(b => b.textContent.includes('Nieuwe ronde'))"), False)
        await ev(pg, "() => document.querySelector('#scoreEmptyMsg .lege-kop[data-kop=andere]').focus()")
        await pg.keyboard.press('Enter'); await pg.wait_for_timeout(250)
        check("Enter op de kop: de knoppen terug", await ev(pg, "() => [...document.querySelectorAll('#scoreEmptyMsg button')].some(b => b.textContent.includes('Nieuwe ronde'))"), True)
        check("register: golf_lege_verkort", await ev(pg, "() => OPSLAGSLEUTELS.golf_lege_verkort"), 'wissen')

        print("\n=== 8. ZONDER GEPLANDE RONDES ===\n")
        await ev(pg, "() => { const s = loadSavedRounds().filter(r => !(r.id >= 990101 && r.id <= 990199)); metVerwijderen(() => setRoundsAndMark(JSON.stringify(s))); nav('setup'); _legeKopSleutel = null; toonLegeKop(); }"); await pg.wait_for_timeout(300)
        geen = await ev(pg, "() => geplandeMomenten().length")
        await klik(pg, f'#hdrGeplandStrook .kop-dag[data-iso="{dag(2)}"]')
        check("niets gepland: een tik op een dag gaat alleen naar het scorescherm", [geen, await ev(pg, "() => document.querySelector('.screen.active')?.id")], [0, 'screen-score'])
        await ev(pg, "() => nav('setup')"); await pg.wait_for_timeout(200)
        kop = await ev(pg, "() => { const r = document.querySelector('header').getBoundingClientRect(); return [r.left + 60, r.top + 14]; }")
        if isinstance(kop, list): await pg.mouse.click(kop[0], kop[1]); await pg.wait_for_timeout(250)
        check("niets gepland: de kop zelf doet niets", await ev(pg, "() => document.querySelector('.screen.active')?.id"), 'screen-setup')
        check("geen paginafouten", pf, [])
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN): {', '.join(fouten)}" if fouten else "\nGEEN FOUTEN")
    sys.exit(1 if fouten else 0)

asyncio.run(main())
