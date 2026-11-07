import asyncio, os, json, hashlib
from playwright.async_api import async_playwright
from testdata import CLUBS, RONDES, APP, app_url, SEED

BACKUP = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rondes_backup.json'), encoding='utf-8').read()
# Clubs, banen en tees afleiden uit de backup zelf, zodat er geen tussenbestand nodig is.
def uitBackup(tekst):
    ruw = json.loads(tekst)
    rondes = ruw if isinstance(ruw, list) else (ruw.get('rounds') or ruw.get('rondes') or [])
    clubs = {}
    for i, r in enumerate(rondes, 1):
        r.setdefault('id', 100000 + i)
        r.setdefault('started', True)
        c, kort, baan = r.get('club'), r.get('clubShort'), r.get('track')
        tee, g = r.get('tee'), r.get('gender', 'Heren')
        if not c or not baan:
            continue
        club = clubs.setdefault(c, {'club': c, 'shortName': kort or c[:6], 'courses': {}})
        course = club['courses'].setdefault(baan, {'tees': {}, 'holes': []})
        course['tees'].setdefault(g, {})[tee] = {'PAR': r.get('PAR', 35), 'CR': r.get('CR', 34.5), 'SR': r.get('SR', 120)}
        if not course['holes']:
            course['holes'] = [{'id': h.get('id', k + 1), 'par': h.get('par', 4), 'si': h.get('si', k + 1)}
                               for k, h in enumerate(r.get('holes', []))]
    return {'clubs': clubs, 'rondes': rondes}

DATA = uitBackup(BACKUP)
SPELER = (DATA['rondes'][0].get('player') if DATA['rondes'] else 'Testspeler')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        fouten = []
        page.on('pageerror', lambda e: fouten.append(str(e)[:120]))

        # 1. Uitgangssituatie: app met jouw rondes erin
        await page.goto(app_url())
        await page.evaluate("""([clubs, rondes, speler]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rondes));
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_home_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', speler);
        }""", [DATA['clubs'], DATA['rondes'], SPELER])
        await page.reload(); await page.wait_for_timeout(800)
        voor = await page.evaluate("""(speler) => {
            const alle = loadSavedRounds();
            const l20 = last20Qualifying(speler, alle);
            const whs = whsHandicap(l20, effectiveLowHi(speler, alle), esrMapFor(speler, alle));
            return { rondes: alle.length, handicap: whs ? whs.value : null,
                     sds: alle.map(r => (effectiveSD(r) || {}).value ?? null).join(','),
                     datums: alle.map(r => r.date + (r.time ? ' ' + r.time : '')).join('|'),
                     banen: [...new Set(alle.map(r => r.track))].sort().join(','),
                     putts: alle.reduce((s,r) => s + (r.holes||[]).filter(h => h.putts != null).length, 0),
                     notities: alle.filter(r => r.note).length };
        }""", SPELER)
        print('1. VÓÓR — de app met je 32 rondes')
        print(f"   rondes {voor['rondes']}, handicap {voor['handicap']}, banen: {voor['banen']}")
        print(f"   holes met putts: {voor['putts']}, rondes met notitie: {voor['notities']}")

        # 2. Totale wisser: alsof je telefoon leeg is
        await page.evaluate("() => localStorage.clear()")
        await page.reload(); await page.wait_for_timeout(700)
        leeg = await page.evaluate("() => loadSavedRounds().length")
        print(f'\n2. NA WISSEN — rondes in de app: {leeg}')

        # 3. Herstellen uit het backupbestand, via het echte importpad
        await page.evaluate("""([clubs, speler]) => {
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', speler);
        }""", [DATA['clubs'], SPELER])
        await page.reload(); await page.wait_for_timeout(600)

        na = await page.evaluate("""([tekst, speler]) => {
            const ruw = JSON.parse(tekst);
            const lijst = Array.isArray(ruw) ? ruw : (ruw.rounds || ruw.rondes || []);
            const gebruikt = new Set();
            const entries = lijst.map(r => buildImportEntry(r, gebruikt, true));
            setRoundsAndMark(JSON.stringify(entries));
            const alle = loadSavedRounds();
            const l20 = last20Qualifying(speler, alle);
            const whs = whsHandicap(l20, effectiveLowHi(speler, alle), esrMapFor(speler, alle));
            return { rondes: alle.length, handicap: whs ? whs.value : null,
                     sds: alle.map(r => (effectiveSD(r) || {}).value ?? null).join(','),
                     datums: alle.map(r => r.date + (r.time ? ' ' + r.time : '')).join('|'),
                     banen: [...new Set(alle.map(r => r.track))].sort().join(','),
                     putts: alle.reduce((s,r) => s + (r.holes||[]).filter(h => h.putts != null).length, 0),
                     notities: alle.filter(r => r.note).length };
        }""", [BACKUP, SPELER])
        print('\n3. NA HERSTEL uit het backupbestand')
        print(f"   rondes {na['rondes']}, handicap {na['handicap']}, banen: {na['banen']}")
        print(f"   holes met putts: {na['putts']}, rondes met notitie: {na['notities']}")

        print('\n4. VERGELIJKING')
        for veld in ['rondes', 'handicap', 'banen', 'putts', 'notities', 'sds', 'datums']:
            gelijk = voor[veld] == na[veld]
            toon = '' if veld in ('sds','datums') else f"   ({voor[veld]})"
            print(('   ok   ' if gelijk else ' VERSCHIL ') + veld.ljust(12) + toon)
            if not gelijk and veld in ('sds','datums'):
                a, c = str(voor[veld]).split('|' if veld=='datums' else ','), str(na[veld]).split('|' if veld=='datums' else ',')
                mist = [x for x in a if x not in c][:4]
                extra = [x for x in c if x not in a][:4]
                if mist: print('        ontbreekt na herstel: ' + ', '.join(mist))
                if extra: print('        extra na herstel: ' + ', '.join(extra))
        alles_gelijk = all(voor[v] == na[v] for v in ['rondes','handicap','banen','putts','notities','sds','datums'])
        print()
        print('GEEN FOUTEN — de backup komt volledig terug' if alles_gelijk and not fouten
              else '1 FOUT(EN) — zie de vergelijking hierboven')
        await b.close()

asyncio.run(main())
