"""Punten uit de review van dagelijks gebruik (13528FE-001).

1. De kaart met twee spelers toont de notitie van elke speler met zijn nummer ervoor
   ("1: …", "2: …"), alleen voor wie er een heeft; bij één speler zoals voorheen, zonder
   nummer. Tot 13528FD-003 stond alleen de notitie van speler 1 op de kaart.
2. Een tik op een dag in de agendastrook bovenin opent die ronde; de gouden kop Geplande
   rondes staat daarna niet half onder de vaste kop van het scherm (een strookje letters).
3. Op een open kaart in Rondes (320 px) breekt een label niet los van zijn waarde: Sd✓ 32.0,
   Pcc 0, · 09:30 en Whs 30.7→31.3 (+0.6) blijven elk op één regel.
4. Na Sluiten van een geplande ronde die niet de eerste is, staat die kaart open (review 2);
   tot dan sprong de lijst terug naar de eerstvolgende ronde.
5. Een ronde van vandaag eerder dan gepland gestart, een paar holes gespeeld en gepauzeerd:
   die staat onder Gepauzeerde rondes (niet als planning), en de kop van die groep staat
   helemaal in beeld (review 3: het scherm stond nog gescrold van het scorescherm).
Via de echte bediening (de dag in de strook), op 360 px.
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

HIER = os.path.dirname(os.path.abspath(__file__))
PLAN = open(os.path.join(HIER, 'test-op-deze-baan.py')).read().split('PLAN = """')[1].split('"""')[0]
def dag(n): return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()

NOTITIES = """(id) => { const k = document.querySelector('#scoreEmptyMsg .lege-open[data-regel^="gepland:' + id + '"]');
  return k ? [...k.querySelectorAll('.lege-knop-notitie')].map(e => e.textContent) : null; }"""
ZET = """([a, b]) => { const s = loadSavedRounds(); const x = s.find(r => r.id === 990802), y = s.find(r => r.id === 990803);
  if (a) x.note = a; else delete x.note; if (b) y.note = b; else delete y.note; setRoundsAndMark(JSON.stringify(s));
  _legeOpen.gepland = '990802,990803'; nav('score'); verversLegeScoreKnoppen(); }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 740})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        hoofd = await ev(pg, "() => startPlayerName()")
        await ev(pg, PLAN % dag(2), [990801, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', hoofd])
        await ev(pg, PLAN % dag(4), [990802, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', hoofd])
        await ev(pg, PLAN % dag(4), [990803, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', 'Medespeler'])
        for i, d in enumerate((6, 8, 10)):
            await ev(pg, PLAN % dag(d), [990810 + i, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', hoofd])

        print("\n=== 1. DE NOTITIE OP DE KAART ===\n")
        await ev(pg, "() => { const s = loadSavedRounds(); s.find(r => r.id === 990801).note = 'Alleen ik'; setRoundsAndMark(JSON.stringify(s)); _legeOpen.gepland = undefined; nav('score'); verversLegeScoreKnoppen(); }")
        await pg.wait_for_timeout(200)
        check("één speler: de notitie zoals hij is, zonder nummer", await ev(pg, NOTITIES, '990801'), ['Alleen ik'])
        await ev(pg, ZET, ['Clubcompetitie', 'Eerste keer mee']); await pg.wait_for_timeout(200)
        check("twee spelers, beide een notitie: 1: … en 2: …, elk een eigen regel", await ev(pg, NOTITIES, '990802'), ['1: Clubcompetitie', '2: Eerste keer mee'])
        check("elk op een eigen regel", await ev(pg, """() => { const n = [...document.querySelectorAll('#scoreEmptyMsg .lege-open[data-regel^="gepland:990802"] .lege-knop-notitie')];
            return n.length === 2 && n[1].getBoundingClientRect().top >= n[0].getBoundingClientRect().bottom - 1; }"""), True)
        await ev(pg, ZET, [None, 'Eerste keer mee']); await pg.wait_for_timeout(200)
        check("alleen speler 2: 2: …", await ev(pg, NOTITIES, '990802'), ['2: Eerste keer mee'])
        await ev(pg, ZET, ['Clubcompetitie', None]); await pg.wait_for_timeout(200)
        check("alleen speler 1: 1: …", await ev(pg, NOTITIES, '990802'), ['1: Clubcompetitie'])
        await ev(pg, ZET, ['Een heel lange notitie die echt niet op één regel van de kaart past, ook niet op een breed scherm', None]); await pg.wait_for_timeout(200)
        check("een lange notitie blijft één regel (afgekapt)", await ev(pg, """() => { const e = document.querySelector('#scoreEmptyMsg .lege-open[data-regel^="gepland:990802"] .lege-knop-notitie');
            return !!e && e.scrollWidth > e.clientWidth && e.getClientRects().length === 1; }"""), True)

        print("\n=== 2. EEN TIK OP EEN DAG IN DE STROOK ===\n")
        await ev(pg, "() => { _legeOpen.gepland = undefined; nav('setup'); }"); await pg.wait_for_timeout(200)
        HALF = """() => { const kop = document.querySelector('#scoreEmptyMsg .lege-kop[data-kop="gepland"]'), hdr = document.querySelector('header');
            if (!kop || !hdr) return 'niet gevonden'; const k = kop.getBoundingClientRect(), h = hdr.getBoundingClientRect().bottom;
            return k.bottom <= h + 0.5 ? 'weg' : k.top >= h - 0.5 ? 'heel' : 'half'; }"""
        for d in (4, 6, 8, 10):
            await ev(pg, "() => { nav('setup'); window.scrollTo(0, 0); }"); await pg.wait_for_timeout(150)
            dagEl = pg.locator(f'#hdrGeplandStrook .kop-dag[data-iso="{dag(d)}"]')
            try: await dagEl.first.click(timeout=2000)
            except Exception: await ev(pg, "(iso) => naarRondeOpScorescherm(iso, true)", dag(d))
            await pg.wait_for_timeout(400)
            open_ = await ev(pg, "() => [...document.querySelectorAll('#scoreEmptyMsg .lege-open[data-regel^=gepland]')].map(e => e.dataset.regel)")
            zicht = await ev(pg, """() => { const k = document.querySelector('#scoreEmptyMsg .lege-open[data-regel^=gepland]'), h = document.querySelector('header').getBoundingClientRect().bottom;
                if (!k) return null; const r = k.getBoundingClientRect(); return r.top >= h - 0.5 && r.bottom <= innerHeight - 60; }""")
            check(f"dag +{d}: die kaart open en helemaal in beeld, de gouden kop niet half", [len(open_ or []) == 1, zicht, await ev(pg, HALF) != 'half'], [True, True, True])
        print("\n=== 3. RONDES OP 320 PX: LABEL EN WAARDE BIJ ELKAAR ===\n")
        await pg.set_viewport_size({'width': 320, 'height': 740})
        await ev(pg, "() => nav('archive')"); await pg.wait_for_timeout(500)
        BIJEEN = r"""() => { const uit = {}; const pat = { Sd: /Sd[^\S\n]*[≈]?[^\S\n]*\d+\.\d/g, Pcc: /Pcc [+−-]?\d+/g, tijd: /· \d\d:\d\d/g, Whs: /Whs \d+\.\d\d+\.\d( \([+-]\d+\.\d\))?/g };
          for (const k in pat) uit[k] = { gezien: 0, los: 0 };
          for (const kaart of [...document.querySelectorAll('.saved-item')].slice(0, 12)) {
            const w = document.createTreeWalker(kaart, NodeFilter.SHOW_TEXT); const nodes = []; let t = '', n;
            while ((n = w.nextNode())) { if (!n.parentElement.offsetParent) continue; nodes.push([n, t.length]); t += n.data.replace(/\u00a0/g, ' '); }
            const top = i => { for (let j = nodes.length - 1; j >= 0; j--) if (nodes[j][1] <= i) { const r = document.createRange(); r.setStart(nodes[j][0], i - nodes[j][1]); r.setEnd(nodes[j][0], i - nodes[j][1] + 1); return r.getBoundingClientRect().top; } };
            for (const k in pat) for (const m of t.matchAll(pat[k])) { uit[k].gezien++; if (Math.abs(top(m.index) - top(m.index + m[0].length - 1)) > 4) uit[k].los++; }
          }
          return uit; }"""
        r = await ev(pg, BIJEEN)
        los = await ev(pg, r"""() => { const uit = [];
          for (const kaart of [...document.querySelectorAll('.saved-item')].slice(0, 12)) for (const el of kaart.querySelectorAll('.saved-meta, .saved-name')) {
            const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); const ch = []; let n;
            while ((n = w.nextNode())) { if (!n.parentElement.offsetParent) continue; for (let i = 0; i < n.data.length; i++) if (!/\s/.test(n.data[i])) ch.push([n, i]); }
            const top = ([x, i]) => { const r = document.createRange(); r.setStart(x, i); r.setEnd(x, i + 1); return r.getBoundingClientRect().top; };
            ch.forEach((c, j) => { if (c[0].data[c[1]] === '·' && ch[j + 1] && top(ch[j + 1]) > top(c) + 4) uit.push(el.textContent.replace(/\s+/g, ' ').trim().slice(0, 50)); });
          } return uit; }""")
        check("320 px: geen punt aan het eind van een regel op de kaarten (eindcontrole)", los, [])
        for k in ('Sd', 'Pcc', 'tijd', 'Whs'):
            v = r.get(k, {}) if isinstance(r, dict) else {}
            check(f"{k}: gevonden op de kaarten en nergens over twee regels", [v.get('gezien', 0) > 0, v.get('los')], [True, 0])
        await pg.set_viewport_size({'width': 360, 'height': 740}); await pg.wait_for_timeout(200)
        gat = await ev(pg, """() => { const n = document.querySelector('.saved-item .saved-name > span'); if (!n) return null; const w = document.createTreeWalker(n, NodeFilter.SHOW_TEXT); let t, dat = null, dot = null;
            while ((t = w.nextNode())) { if (!dat && /\\d{4}/.test(t.data)) dat = t; if (/·/.test(t.data)) { dot = t; break; } }
            if (!dat || !dot) return null; const j = dat.data.search(/\\d{4}/) + 3, i = dot.data.indexOf('·'), a = document.createRange(), d = document.createRange();
            a.setStart(dat, j); a.setEnd(dat, j + 1); d.setStart(dot, i); d.setEnd(dot, i + 1); return Math.round(d.getBoundingClientRect().left - a.getBoundingClientRect().right); }""")
        check("360 px, datum · tijd op één regel: één gewone spatie ervoor, geen dubbele (review 2)", [gat is not None and 0 < gat <= 7, gat], [True, gat])

        titel = await ev(pg, r"""() => { const i = loadSavedRounds().findIndex(r => r.time && isRondeAf(r)); openRoundEditChoice(i);
            const t = document.getElementById('roundEditChoiceTitle'), w = document.createTreeWalker(t, NodeFilter.SHOW_TEXT); let n, dot = null, eerste = null;
            while ((n = w.nextNode())) { if (!eerste) eerste = n; if (n.data.includes('·')) { dot = n; break; } }
            const top = (x, i) => { const r = document.createRange(); r.setStart(x, i); r.setEnd(x, i + 1); return Math.round(r.getBoundingClientRect().top); };
            const uit = [/^[A-Za-z]{2} \d/.test(t.textContent), !!dot && top(dot, dot.data.indexOf('·')) === top(dot, dot.data.length - 1), !!dot && !!eerste];
            sluitRoundEditChoice(); return uit; }""")
        check("360 px, titel van het potloodvenster: geen punt na de dag, '· tijd' als geheel (eindcontrole)", titel, [True, True, True])

        print("\n=== 4. NA SLUITEN DE KAART WAAR JE VANDAAN KWAM ===\n")
        await pg.set_viewport_size({'width': 360, 'height': 740})
        await ev(pg, "() => { _legeOpen.gepland = undefined; nav('score'); verversLegeScoreKnoppen(); window.scrollTo(0, 0); }"); await pg.wait_for_timeout(300)
        OPEN = "() => [...document.querySelectorAll('#scoreEmptyMsg .lege-open[data-regel^=gepland]')].map(e => e.dataset.regel)"
        try:
            # zoals de reviewer: op Start een ronde plannen die niet de eerstvolgende is, dan Sluiten
            await ev(pg, "() => { nav('setup'); window.scrollTo(0, 0); }"); await pg.wait_for_timeout(200)
            await pg.fill('#iDate', dag(3)); await pg.dispatch_event('#iDate', 'change')
            await pg.fill('input[type=time]', '10:30')
            await pg.click('#startRoundBtn'); await pg.wait_for_timeout(700)
            nieuw = await ev(pg, "() => String(storage.getItem('golf_active_id'))")
            label = await ev(pg, "() => document.getElementById('finishRoundLabel').textContent")
            await pg.locator('#finishRoundLabel').click(timeout=3000); await pg.wait_for_timeout(600)
            zicht = await ev(pg, """(id) => { const k = document.querySelector('#scoreEmptyMsg .lege-open[data-regel^="gepland:' + id + '"]'); if (!k) return false;
                const r = k.getBoundingClientRect(), h = document.querySelector('header').getBoundingClientRect().bottom; return r.top >= h - 0.5 && r.top < innerHeight - 60; }""", nieuw)
            check("Sluiten bij een net geplande latere ronde: die kaart open en in beeld", [label, await ev(pg, OPEN), zicht], ['Sluiten', ['gepland:' + nieuw], True])
        except Exception as e:
            check("Sluiten bij een net geplande latere ronde", 'FOUT: ' + str(e).split('\n')[0][:120], 'gelukt')
        print("\n=== 5. EERDER GESTART EN GEPAUZEERD ===\n")
        try:
            # een gewone gepauzeerde ronde (tijd voorbij), zonder geplande rondes erboven: na
            # Pauzeren staat de kop Gepauzeerde rondes bovenaan helemaal in beeld (het scherm
            # stond nog gescrold van het scorescherm)
            ctx2 = await b.new_context(viewport={'width': 320, 'height': 680}, has_touch=True, is_mobile=True)
            p2 = await ctx2.new_page()
            await p2.goto(app_url()); await p2.evaluate(SEED, [CLUBS, RONDES]); await p2.reload(); await p2.wait_for_timeout(500)
            await p2.fill('#iDate', dag(0)); await p2.dispatch_event('#iDate', 'change')
            await p2.fill('input[type=time]', '00:05')
            await p2.click('#startRoundBtn'); await p2.wait_for_timeout(700)
            await p2.evaluate("() => { game.holes.slice(0, 3).forEach(h => { h.score = (h.par || 4) + 1; }); saveActiveRound(); renderScore(); window.scrollTo(0, document.documentElement.scrollHeight); }"); await p2.wait_for_timeout(300)
            await p2.locator('#finishRoundBtn').click(); await p2.wait_for_timeout(150); await p2.locator('#finishRoundBtn').click(); await p2.wait_for_timeout(700)
            kopIn = await p2.evaluate("""() => { const kop = document.querySelector('#scoreEmptyMsg .lege-kop'), hdr = document.querySelector('header').getBoundingClientRect().bottom;
                return [kop ? kop.dataset.kop : null, !!kop && kop.getBoundingClientRect().top >= hdr - 0.5]; }""")
            check("na Pauzeren (geen planning erboven): de kop Gepauzeerde rondes helemaal in beeld", kopIn, ['gepauzeerd', True])
            await ctx2.close()
        except Exception as e:
            check("na Pauzeren", 'FOUT: ' + str(e).split('\n')[0][:120], 'gelukt')
        try:
            await pg.set_viewport_size({'width': 320, 'height': 740})
            await ev(pg, "() => { nav('setup'); window.scrollTo(0, 0); }"); await pg.wait_for_timeout(200)
            later = await ev(pg, "() => { const d = new Date(Date.now() + 3 * 3600e3); return d.getDate() === new Date().getDate() ? String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0') : '23:59'; }")
            await pg.fill('#iDate', dag(0)); await pg.dispatch_event('#iDate', 'change')
            await pg.fill('input[type=time]', later)
            await pg.click('#startRoundBtn'); await pg.wait_for_timeout(700)
            rid = await ev(pg, "() => String(storage.getItem('golf_active_id'))")
            await ev(pg, "() => { game.holes.slice(0, 3).forEach(h => { h.score = (h.par || 4) + 1; }); saveActiveRound(); renderScore(); window.scrollTo(0, 400); }"); await pg.wait_for_timeout(300)
            await pg.locator('#finishRoundBtn').click(); await pg.wait_for_timeout(150); await pg.locator('#finishRoundBtn').click(); await pg.wait_for_timeout(700)
            stand = await ev(pg, """(id) => { const k = legeScoreKeuzes(), kop = document.querySelector('#scoreEmptyMsg .lege-kop[data-kop="gepauzeerd"]'), hdr = document.querySelector('header').getBoundingClientRect().bottom;
                return [k.gepauzeerdAlle.some(m => m.some(r => String(r.id) === id)), k.geplandAlle.some(m => m.some(r => String(r.id) === id)), !!kop && kop.getBoundingClientRect().top >= hdr - 0.5]; }""", rid)
            check("eerder gestart en gepauzeerd: onder Gepauzeerde rondes, niet gepland, de kop helemaal in beeld", stand, [True, False, True])
        except Exception as e:
            check("eerder gestart en gepauzeerd", 'FOUT: ' + str(e).split('\n')[0][:120], 'gelukt')
        try:
            # hetzelfde met twee spelers (de medespeler nog zonder scores): de kaart staat maar
            # in één groep, Gepauzeerde rondes (review 3: hij stond in beide)
            ctx3 = await b.new_context(viewport={'width': 320, 'height': 680}, has_touch=True, is_mobile=True)
            p3 = await ctx3.new_page()
            await p3.goto(app_url()); await p3.evaluate(SEED, [CLUBS, RONDES]); await p3.reload(); await p3.wait_for_timeout(500)
            await p3.click('#addPlayer2Btn'); await p3.wait_for_timeout(200)
            await p3.fill('#iName2', 'Medespeler'); await p3.fill('#iHcp2', '20.4'); await p3.locator('#iHcp2').blur()
            await p3.fill('#iDate', dag(0)); await p3.dispatch_event('#iDate', 'change')
            await p3.fill('input[type=time]', later)
            await p3.click('#startRoundBtn'); await p3.wait_for_timeout(700)
            await p3.evaluate("() => { game.holes.slice(0, 3).forEach(h => { h.score = (h.par || 4) + 1; }); saveActiveRound(); renderScore(); }"); await p3.wait_for_timeout(300)
            await p3.locator('#finishRoundBtn').click(); await p3.wait_for_timeout(150); await p3.locator('#finishRoundBtn').click(); await p3.wait_for_timeout(700)
            groepen = await p3.evaluate("""() => { const k = legeScoreKeuzes(), ids = new Set(loadSavedRounds().filter(r => r.date === todayISO() && !isRondeAf(r)).map(r => String(r.id)));
                const in_ = lijst => lijst.filter(m => m.some(r => ids.has(String(r.id)))).length; return [in_(k.geplandAlle), in_(k.gepauzeerdAlle)]; }""")
            check("twee spelers, eerder gestart en gepauzeerd: alleen onder Gepauzeerde rondes", groepen, [0, 1])
            await ctx3.close()
        except Exception as e:
            check("twee spelers, eerder gestart", 'FOUT: ' + str(e).split('\n')[0][:120], 'gelukt')
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
