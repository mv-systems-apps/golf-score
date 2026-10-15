"""Wat er via een bestand binnenkomt wordt gekeurd en rechtgezet voordat het wordt opgeslagen.

Een backup is invoer van buiten, ook als deze app hem zelf heeft gemaakt: hij kan met de
hand zijn bewerkt, beschadigd zijn of uit een andere versie komen. Tot 13527DA-120:
  * werd één ronde inlezen niet gekeurd (een handicap van 999 kwam erdoor);
  * werd nergens op het soort waarde gelet (een datum als getal brak de tab Rondes voorgoed);
  * bleef een getal-als-tekst tekst ("5" + "4" werd "54" in het totaal).

De regel: keuren → rechtzetten → pas dan opslaan. Een ronde die niet kan kloppen komt er
niet in, met de reden in de melding. Een ronde die alleen slordig is opgeschreven (getallen
als tekst, een ontbrekende score) wordt rechtgezet. Elk geval gaat langs twee routes: als
los bestand met één ronde, en als backup samen met twee goede rondes.
"""
import asyncio, copy, json, os, sys, tempfile
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    if not ok or os.environ.get('ALLES'): print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)
    return ok

PARS = [4, 3, 5, 4, 4, 3, 4, 5, 4]
def basis(dag=10, tijd='10:00'):
    holes = [{"id": f"H{k + 1}", "par": p, "si": k + 1, "phcp": 2 if k < 6 else 1, "ppar": p + (2 if k < 6 else 1), "score": p + 2, "putts": 2} for k, p in enumerate(PARS)]
    return {"date": f"2026-06-{dag:02d}", "time": tijd, "player": "Mark", "hcp": 30.7, "club": "Testclub", "clubShort": "TC", "track": "Baan", "gender": "Heren", "tee": "Geel",
            "CR": 35.0, "SR": 120, "PAR": 36, "chcp": 15, "qualifying": True, "pcc": 0, "sdFinal": 31.2, "holes": holes}
def met(**velden):
    r = basis(); r.update(velden); return r
def hole(k=0, **velden):
    r = basis(); r['holes'][k].update(velden); return r
def zonder_in_hole(sleutel, k=0):
    r = basis(); del r['holes'][k][sleutel]; return r

WEIGEREN = [
    ("datum als getal",                 met(date=20260726)),
    ("datum in een ander formaat",      met(date="26-07-2026")),
    ("datum die niet bestaat",          met(date="2026-13-45")),
    ("speler als getal",                met(player=12)),
    ("speler als lijst",                met(player=["Mark"])),
    ("speler leeg",                     met(player="  ")),
    ("tijd als getal",                  met(time=930)),
    ("tijd die niet bestaat",           met(time="25:99")),
    ("geslacht als getal",              met(gender=1)),
    ("tee als object",                  met(tee={"naam": "Geel"})),
    ("club als getal",                  met(club=5)),
    ("baan als lijst",                  met(track=["Baan"])),
    ("notitie als object",              met(note={"x": 1})),
    ("geen holes",                      met(holes=[])),
    ("negentien holes",                 met(holes=basis()['holes'] * 2 + basis()['holes'][:1])),
    ("een hole die geen hole is",       met(holes=basis()['holes'][:8] + [None])),
    ("hole zonder par",                 zonder_in_hole('par')),
    ("par als woord",                   hole(par="vier")),
    ("par met decimalen",               hole(par=4.5)),
    ("par 7",                           hole(par=7)),
    ("stroke index 0",                  hole(si=0)),
    ("stroke index 19",                 hole(si=19)),
    ("stroke index als woord",          hole(si="abc")),
    ("hole zonder stroke index",        zonder_in_hole('si')),
    ("score met decimalen",             hole(score=4.5)),
    ("score als woord",                 hole(score="abc")),
    ("score negatief",                  hole(score=-3)),
    ("score 99",                        hole(score=99)),
    ("score als ja/nee",                hole(score=True)),
    ("score als lijst",                 hole(score=[5])),
    ("putts negatief",                  hole(putts=-1)),
    ("putts met decimalen",             hole(putts=2.5)),
    ("slagen per hole als woord",       hole(phcp="twee")),
    ("handicap 999",                    met(hcp=999)),
    ("handicap als woord",              met(hcp="veel")),
    ("course rating 500",               met(CR=500)),
    ("slope rating 0",                  met(SR=0)),
    ("dagresultaat -50",                met(sdFinal=-50)),
    ("baanhandicap als woord",          met(chcp="x")),
    ("baanhandicap 99",                 met(chcp=99)),
    ("par van de baan als woord",       met(PAR="x")),
    ("alles tegelijk mis",              met(hcp=999, CR=500, SR=0, sdFinal=-50)),
]
def als_tekst():
    r = basis()
    for h in r['holes']:
        for k in ('par', 'si', 'phcp', 'ppar', 'score', 'putts'): h[k] = str(h[k])
    for k in ('hcp', 'CR', 'SR', 'PAR', 'chcp', 'sdFinal'): r[k] = str(r[k])
    return r
def zonder_score():
    r = basis(); del r['holes'][8]['score']; del r['holes'][8]['putts']; r['sdFinal'] = None; return r
def kaal():
    r = basis(); r['time'] = None; r['pcc'] = None; r['sdFinal'] = None
    for h in r['holes']: del h['putts']
    return r
def getal_ids():
    r = basis()
    for k, h in enumerate(r['holes']): h['id'] = k + 1
    return r
ACCEPTEREN = [
    ("een gewone ronde",                              basis(),                         {}),
    ("alle getallen als tekst",                       als_tekst(),                     {"totaal": 54, "soort": True}),
    ("een hole zonder score: niet gespeeld",          zonder_score(),                  {"gespeeld": 8}),
    ("zonder tijd, putts, pcc en dagresultaat",       kaal(),                          {}),
    ("een veld dat deze versie niet kent blijft staan", met(toekomst="iets nieuws"),   {"toekomst": "iets nieuws"}),
    ("holenummers als getal worden tekst",            getal_ids(),                     {"ids": True}),
    ("een ronde op een lus van drie holes (lage CR)",  met(holes=basis()['holes'][:3], PAR=12, CR=11.8, chcp=5, sdFinal=None, lus=True), {}),
    ("achttien holes",                                met(holes=[dict(h, id=f"H{i + 1}", si=i + 1) for i, h in enumerate(basis()['holes'] * 2)], PAR=72), {}),
]

def bestand(inhoud):
    pad = os.path.join(tempfile.mkdtemp(), 'in.json')
    with open(pad, 'w', encoding='utf-8') as f: json.dump(inhoud, f, ensure_ascii=False)
    return pad
VENSTER = """() => { const m = document.getElementById('confirmModal'), k = document.getElementById('keuzeModal'); const open = e => e && !e.classList.contains('hidden');
  const t = (open(k) ? k.innerText : open(m) ? m.innerText : '').replace(/\\s+/g, ' ').trim();
  document.querySelectorAll('#confirmModal:not(.hidden) button, #keuzeModal:not(.hidden) button').forEach(b => { if (/Sluiten/.test(b.textContent)) b.click(); }); return t; }"""
OPSLAG = "() => { try { return JSON.parse(localStorage.getItem('golf_rounds') || '[]'); } catch (e) { return 'onleesbaar'; } }"
SCHERMEN = """() => { const fout = []; for (const t of ['archive', 'stat', 'setup', 'settings', 'club']) { try { nav(t); } catch (e) { fout.push(t + ': ' + String(e).slice(0, 80)); } }
  try { const h = currentOfficialHcp ? currentOfficialHcp() : null; if (h != null && typeof h === 'object' && h.value != null && !isFinite(h.value)) fout.push('handicap ' + h.value); } catch (e) { fout.push('handicap: ' + String(e).slice(0, 80)); }
  return fout; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:120]))
        await pg.goto(app_url())
        async def leeg():
            await pg.evaluate("() => { localStorage.clear(); localStorage.setItem('golf_rounds', '[]'); localStorage.setItem('golf_profile_name', 'Mark'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }")
            await pg.reload(); await pg.wait_for_timeout(450); del pf[:]
        async def lees_in(inhoud):
            await pg.evaluate("() => nav('settings')")
            await pg.locator('#importRoundFile').set_input_files(bestand(inhoud)); await pg.wait_for_timeout(450)
            return await pg.evaluate(VENSTER)

        print(f"\n=== 1. MOET GEWEIGERD WORDEN ({len(WEIGEREN)} gevallen, elk langs twee routes) ===\n")
        goed = 0
        for naam, r in WEIGEREN:
            await leeg(); m = await lees_in(r); o = await pg.evaluate(OPSLAG)
            a = check(f"{naam} — los bestand: niets opgeslagen", o, [])
            c = check(f"{naam} — los bestand: gemeld als mislukt", 'mislukt' in m.lower() or 'ongeldig' in m.lower() or 'niet ingelezen' in m.lower(), True)
            await leeg(); m = await lees_in([basis(11, '09:00'), basis(12, '09:00'), r]); o = await pg.evaluate(OPSLAG)
            d = check(f"{naam} — in een backup: alleen de twee goede rondes opgeslagen", sorted(str(x.get('date')) for x in o) if isinstance(o, list) else o, ['2026-06-11', '2026-06-12'])
            e = check(f"{naam} — in een backup: gemeld dat er één niet is ingelezen", '1 ronde niet ingelezen' in m, True)
            s = await pg.evaluate(SCHERMEN)
            f = check(f"{naam} — daarna werken alle schermen", (s, pf[:2]), ([], []))
            goed += all([a, c, d, e, f])
        print(f"   {goed} van de {len(WEIGEREN)} gevallen goed geweigerd langs beide routes")

        print(f"\n=== 2. MOET GEACCEPTEERD EN RECHTGEZET WORDEN ({len(ACCEPTEREN)} gevallen) ===\n")
        goed = 0
        def recht(o, extra, naam):
            try: return recht_(o, extra, naam)
            except Exception as e: return check(f"{naam}: de opgeslagen ronde is in orde", f"{type(e).__name__}: {e}"[:80], 'in orde')
        def recht_(o, extra, naam):
            ok = True
            r = o[0]
            getallen = all(isinstance(h.get(k), int) or (k in ('score', 'putts') and h.get(k) is None) for h in r['holes'] for k in ('par', 'si', 'score') ) and all(isinstance(r.get(k), (int, float)) for k in ('CR', 'SR', 'PAR', 'chcp', 'total')) and 'totalStb' not in r
            ok &= check(f"{naam}: par, SI, score en de kengetallen zijn getallen", getallen, True)
            ok &= check(f"{naam}: het totaal is de som van de scores", r.get('total'), sum((h.get('score') or 0) for h in r['holes']) if all(isinstance(h.get('score'), (int, type(None))) for h in r['holes']) else 'scores zijn geen getallen')
            ok &= check(f"{naam}: holenamen zijn tekst", all(isinstance(h['id'], str) for h in r['holes']), True)
            if 'gespeeld' in extra: ok &= check(f"{naam}: acht holes gespeeld, de negende leeg", ([h['score'] is not None for h in r['holes']].count(True), r['holes'][8]['score']), (8, None))
            if 'toekomst' in extra: ok &= check(f"{naam}: het onbekende veld staat er nog", r.get('toekomst'), extra['toekomst'])
            if 'totaal' in extra: ok &= check(f"{naam}: totaal 54 en geen aan elkaar geplakte tekst", r['total'], 54)
            return ok
        for naam, r, extra in ACCEPTEREN:
            await leeg(); m = await lees_in(copy.deepcopy(r)); o = await pg.evaluate(OPSLAG)
            a = check(f"{naam} — los bestand: één ronde opgeslagen", len(o) if isinstance(o, list) else o, 1) and recht(o, extra, naam + ' — los bestand')
            s1 = await pg.evaluate(SCHERMEN)
            await leeg(); m = await lees_in([basis(11, '09:00'), basis(12, '09:00'), copy.deepcopy(r)]); o = await pg.evaluate(OPSLAG)
            c = check(f"{naam} — in een backup: drie rondes opgeslagen, niets overgeslagen", (len(o) if isinstance(o, list) else o, 'niet ingelezen' in m), (3, False))
            if c: c = recht([x for x in o if x['date'] == '2026-06-10'], extra, naam + ' — in een backup')
            s2 = await pg.evaluate(SCHERMEN)
            d = check(f"{naam} — daarna werken alle schermen", (s1, s2, pf[:2]), ([], [], []))
            goed += all([a, c, d])
        print(f"   {goed} van de {len(ACCEPTEREN)} gevallen goed geaccepteerd langs beide routes")

        print("\n=== 3. MARKS EIGEN BACKUP KOMT ER ONGEWIJZIGD DOOR ===\n")
        echt = json.load(open(os.path.join(HIER, 'echte-rondes.json'), encoding='utf-8'))
        await leeg(); m = await lees_in(copy.deepcopy(echt)); o = await pg.evaluate(OPSLAG)
        check("alle rondes ingelezen, niets overgeslagen", (len(o), 'niet ingelezen' in m), (len(echt), False))
        AFGELEID = {'id', 'total', 'totalStb', 'holesCount', 'currentHole', 'started', 'sd', 'playedCount', '_justImported'}
        sleutel = lambda r: (r['date'], r.get('time'), r['player'])
        na = {sleutel(r): r for r in o}
        anders = []
        for r in echt:
            n = na.get(sleutel(r))
            if not n: anders.append(('ontbreekt', sleutel(r))); continue
            for k in set(r) | set(n):
                if k in AFGELEID: continue
                if r.get(k) != n.get(k): anders.append((sleutel(r), k, str(r.get(k))[:40], str(n.get(k))[:40]))
        check("elk opgeslagen veld is gelijk aan het bestand", anders[:5], [])
        check("daarna werken alle schermen", (await pg.evaluate(SCHERMEN), pf[:2]), ([], []))
        print("\n=== 4. CLUBBESTANDEN ===\n")
        clubs = json.load(open(os.path.join(HIER, 'echte-clubs.json'), encoding='utf-8'))
        def club(**w):
            c = copy.deepcopy(clubs[0]); c.update(w); return c
        def baan(fn):
            c = copy.deepcopy(clubs[0]); n = next(iter(c['courses'])); fn(c, n); return c
        def tee_van(c, n): g = next(iter(c['courses'][n]['tees'])); t = next(iter(c['courses'][n]['tees'][g])); return c['courses'][n]['tees'][g], t
        def cr(c, n): m, t = tee_van(c, n); m[t]['CR'] = 500
        def sr(c, n): m, t = tee_van(c, n); m[t]['SR'] = -5
        def teenaam(c, n): m, t = tee_van(c, n); m['constructor'] = m.pop(t)
        def baannaam(c, n): c['courses']['prototype'] = c['courses'].pop(n)
        CLUBGEVALLEN = [("club heet constructor", club(club='constructor')), ("club heet prototype", club(club='prototype')), ("korte naam als getal", club(shortName=5)),
                        ("baan heet prototype", baan(baannaam)), ("tee heet constructor", baan(teenaam)), ("course rating 500", baan(cr)), ("slope rating -5", baan(sr))]
        CLUBOPSLAG = "() => localStorage.getItem('golf_clubs')"
        async def lees_club(inhoud):
            await pg.evaluate("() => nav('club')")
            await pg.locator('#importClubFile').set_input_files(bestand(inhoud)); await pg.wait_for_timeout(450)
            m = await pg.evaluate(VENSTER)
            await pg.evaluate("() => { const b = document.getElementById('confirmModalBtn'); const m = document.getElementById('confirmModal'); if (m && !m.classList.contains('hidden')) b.click(); }")
            return m
        goed = 0
        for naam, c in CLUBGEVALLEN:
            await leeg(); voor = await pg.evaluate(CLUBOPSLAG); m = await lees_club(c)
            a = check(f"{naam} — los clubbestand: niets opgeslagen", await pg.evaluate(CLUBOPSLAG), voor)
            b2 = check(f"{naam} — los clubbestand: gemeld als mislukt", 'mislukt' in m.lower() or 'ongeldig' in m.lower(), True)
            await leeg(); m = await lees_club([clubs[1], c]); na = await pg.evaluate("() => JSON.parse(localStorage.getItem('golf_clubs') || '{}')")
            c2 = check(f"{naam} — in een clubbackup: de goede club is ingelezen, de foute niet", (na.get(clubs[1]['club']) == clubs[1], na.get(c['club']) == c), (True, False))
            d = check(f"{naam} — daarna werken alle schermen", (await pg.evaluate(SCHERMEN), pf[:2]), ([], []))
            goed += all([a, b2, c2, d])
        print(f"   {goed} van de {len(CLUBGEVALLEN)} gevallen goed geweigerd langs beide routes")
        await leeg(); m = await lees_club(copy.deepcopy(clubs))
        na = await pg.evaluate("() => JSON.parse(localStorage.getItem('golf_clubs') || '{}')")
        check("Marks eigen clubbackup komt er ongewijzigd door", [na.get(c['club']) == c for c in clubs], [True] * len(clubs))
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
