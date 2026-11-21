"""Herplannen en corrigeren op het startscherm: de oranje regel en de gouden knop (13528FB-002).

De oranje regel zegt alleen welke ronde vervangen wordt ('De ronde van … wordt vervangen',
bij corrigeren '— je scores gaan mee'; eerst stond er 'Opnieuw plannen:' of 'Corrigeren:'
voor), en de datum breekt niet af over twee regels (vaste koppeltekens). De gouden knop heet zolang er een
ronde wordt vervangen 'Ronde herplannen' of 'Ronde corrigeren', anders 'Nieuwe ronde'; hij
doet wat hij deed: de ronde vervangen en de scorekaart openen. Na het kruisje of na het
vervangen heet hij weer 'Nieuwe ronde'. In het menu staat alleen wat kan: zonder scores geen
Vaststellen.

Via de echte bediening: het potlood, het menu, het kruisje en de gouden knop.
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
def dag(n): return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()

MENU = """() => [...document.querySelectorAll('#roundEditChoiceModal button')].filter(b => b.id && !b.classList.contains('hidden')).map(b => b.textContent.trim())"""
KNOP = "() => document.getElementById('startRoundBtn')?.textContent.trim()"
REGEL = "() => { const b = document.getElementById('herplanBanner'); return b && !b.classList.contains('hidden') ? b.querySelector('span')?.textContent : null; }"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        await ev(pg, PLAN % dag(6), [990101, 'Golfclub Heelsum', 'Airborne', 'Blauw', None])
        await ev(pg, "() => { nav('score'); verversLegeScoreKnoppen(); }"); await pg.wait_for_timeout(300)
        check("zonder herplannen: Nieuwe ronde", await ev(pg, KNOP), 'Nieuwe ronde')

        print("\n=== 1. HET MENU: ALLEEN WAT KAN ===\n")
        await klik(pg, '#scoreEmptyMsg .lege-open[data-regel="gepland:990101"] .lege-knop-bewerk')
        check("geplande ronde (vanaf het scorescherm): geen Vaststellen, wel de agenda", await ev(pg, MENU), ['Ronde herplannen', 'Ronde bewerken', 'Afspraak maken'])
        await ev(pg, "() => { sluitRoundEditChoice(); const i = loadSavedRounds().findIndex(r => gespeeldeHoles(r) > 0); openRoundEditChoice(i); }")
        check("ronde met scores: wel Vaststellen", await ev(pg, MENU), ['Corrigeren', 'Bewerken', 'Vaststellen'])
        await ev(pg, "() => { sluitRoundEditChoice(); const i = loadSavedRounds().findIndex(r => gespeeldeHoles(r) > 0); openRoundEditChoice(i, true); }")
        check("vanaf het scorescherm met scores: 'Ronde corrigeren', 'Ronde bewerken', Vaststellen", await ev(pg, MENU), ['Ronde corrigeren', 'Ronde bewerken', 'Vaststellen'])
        await ev(pg, "() => sluitRoundEditChoice()")

        print("\n=== 2. HERPLANNEN ===\n")
        await klik(pg, '#scoreEmptyMsg .lege-open[data-regel="gepland:990101"] .lege-knop-bewerk')
        await klik(pg, '#roundEditChoiceHerplan')
        regel = await ev(pg, REGEL)
        check("de oranje regel: 'De ronde van … wordt vervangen', zonder 'Herplannen' (dat staat op de knop)", isinstance(regel, str) and regel.startswith('De ronde van ') and regel.endswith('wordt vervangen'), True)
        check("de datum met vaste koppeltekens", isinstance(regel, str) and '‑' in regel and '-' not in regel.split(' om ')[0], True)
        check("de gouden knop: Ronde herplannen", await ev(pg, KNOP), 'Ronde herplannen')
        await klik(pg, '#herplanBanner button')
        check("na het kruisje: geen regel, Nieuwe ronde", [await ev(pg, REGEL), await ev(pg, KNOP)], [None, 'Nieuwe ronde'])
        check("en de ronde staat er nog", await ev(pg, "() => loadSavedRounds().some(r => r.id === 990101)"), True)

        await ev(pg, "() => nav('score')"); await pg.wait_for_timeout(200)
        await klik(pg, '#scoreEmptyMsg .lege-open[data-regel="gepland:990101"] .lege-knop-bewerk')
        await klik(pg, '#roundEditChoiceHerplan')
        await klik(pg, '#startRoundBtn')
        await ev(pg, "() => { const b = document.getElementById('confirmModalBtn'); if (b && !document.getElementById('confirmModal').classList.contains('hidden')) b.click(); }")
        await pg.wait_for_timeout(300)
        check("Ronde herplannen: de scorekaart staat open, de oude ronde is vervangen",
              await ev(pg, "() => [document.querySelector('.screen.active')?.id, !!(game && game.started), loadSavedRounds().some(r => r.id === 990101)]"), ['screen-score', True, False])
        check("daarna heet de knop weer Nieuwe ronde", await ev(pg, KNOP), 'Nieuwe ronde')
        await ev(pg, "() => { const l = document.getElementById('finishRoundLabel'); if (l && l.textContent === 'Sluiten') finishActiveRound(null); }")

        print("\n=== 3. CORRIGEREN ===\n")
        await ev(pg, "() => { const r = loadSavedRounds().find(r => gespeeldeHoles(r) > 0 && !staatInGeheugen(r)); corrigeerRonde(String(r.id)); }")
        check("de waarschuwing noemt alleen scores en herberekening, niet dat de oude ronde verdwijnt", await ev(pg, "() => { const t = document.getElementById('keuzeModalTekst')?.textContent || ''; return t.includes('opnieuw berekend') && !t.includes('verdwijnt'); }"), True)
        await klik(pg, '#keuzeModalKnop2')
        regel = await ev(pg, REGEL)
        check("de oranje regel: 'De ronde van … wordt vervangen — je scores gaan mee'", isinstance(regel, str) and regel.startswith('De ronde van ') and regel.endswith('wordt vervangen — je scores gaan mee'), True)
        check("de gouden knop: Ronde corrigeren", await ev(pg, KNOP), 'Ronde corrigeren')
        await klik(pg, '#herplanBanner button')
        check("na het kruisje: Nieuwe ronde", await ev(pg, KNOP), 'Nieuwe ronde')

        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
