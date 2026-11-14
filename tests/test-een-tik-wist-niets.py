"""Iets definitief verwijderen kan nooit met één tik.

De app heeft daar per knop een voorziening voor: tik twee keer, of een venster dat om
bevestiging vraagt. Dat is knop voor knop gebouwd en nergens als geheel getest.

Deze test doet het omgekeerde van een gewone test. Hij weet niet welke knoppen gevaarlijk
zijn. Hij zet de app in een gewone stand — een scherm, of een scherm met een bewerkvenster
open — en tikt dan op ALLES wat er te zien is, elk ding één keer, telkens opnieuw vanuit
die stand. Na elke tik: is er een ronde weg, een score, een puttwaarde, een notitie, een
club, een baan of een tee? Dan was dat één tik te weinig.

Een bevestigingsvenster ("Weet je het zeker?") en een knop die al één keer is aangetikt
zijn geen gewone stand: daar hoort de tweede tik juist wel te werken.

Bekende uitzondering, bewust zo gebouwd: de min-knop op het scorescherm haalt één slag
van de score af, en bij score 1 wordt de hole leeg. Dat is invoer, geen verwijderen; de
test meldt het apart.
"""
import asyncio, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}" + ('' if ok else f": {str(echt)[:900]} — verwacht {verwacht}"))
    if not ok: fouten.append(naam)

def tee(cr, sr, pars): return {"CR": cr, "SR": sr, "holes": [{"par": p, "si": i + 1} for i, p in enumerate(pars)]}
PA = [4, 3, 5, 4, 4, 3, 4, 5, 4]; PB = [5, 4, 4, 3, 4, 5, 4, 4, 4]
def ids(l, n=9): return [f"{l}{i}" for i in range(1, n + 1)]
CLUBS = {
  "Club A": {"club": "Club A", "shortName": "A", "courses": {
    "Noord": {"holeIds": ids('A'), "tees": {"Heren": {"Geel": tee(35.0, 120, PA), "Wit": tee(36.1, 127, PA)}, "Dames": {"Rood": tee(36.5, 126, PA)}}},
    "Zuid":  {"holeIds": ids('Z'), "tees": {"Heren": {"Geel": tee(33.1, 112, PB)}}},
    "Lus":   {"holeIds": ids('L'), "lus": True, "tees": {"Heren": {"Geel": tee(34.0, 117, PB)}}}}},
  "Club B": {"club": "Club B", "shortName": "B", "courses": {
    "West": {"holeIds": ids('W'), "tees": {"Heren": {"Geel": tee(38.0, 139, PB)}}}}},
}
def ronde(rid, datum, speler, gespeeld=9, qual=True, note=None):
    r = {"id": rid, "date": datum, "time": "09:00", "player": speler, "hcp": 24.0, "gender": "Heren", "track": "Zuid", "tee": "Geel",
         "club": "Club A", "clubShort": "A", "CR": 33.1, "SR": 112, "PAR": sum(PB), "chcp": 10, "qualifying": qual, "started": True,
         "holesCount": 9, "currentHole": 0, "total": 0, "totalStb": 0,
         "holes": [{"id": f"Z{i+1}", "par": p, "si": i + 1, "phcp": 1, "ppar": p + 1, "score": (p + 1 if i < gespeeld else None), **({"putts": 2} if i < gespeeld else {})} for i, p in enumerate(PB)]}
    if note: r["note"] = note
    return r
RONDES = [ronde(101, "2026-08-01", "Testspeler", note="eerste"), ronde(102, "2026-08-08", "Testspeler", note="tweede"), ronde(103, "2026-08-15", "Anna", note="van Anna"),
          ronde(104, "2026-08-22", "Testspeler", qual=False, note="oefenronde"), ronde(105, "2027-05-01", "Testspeler", gespeeld=0, note="gepland"),
          ronde(106, "2026-08-29", "Piet", note="van Piet"), ronde(107, "2026-09-05", "Testspeler", gespeeld=5, note="half")]

# Wat er te verliezen valt.
BEZIT = """() => { const l = JSON.parse(localStorage.getItem('golf_rounds') || '[]'), c = JSON.parse(localStorage.getItem('golf_clubs') || '{}');
  const rondes = {}; l.forEach(r => { rondes[r.id] = [r.holes.filter(h => h.score != null).length, r.holes.filter(h => h.putts != null).length, r.note ? 1 : 0, r.holes.length]; });
  const clubs = {}; Object.values(c).forEach(k => { clubs[k.club] = {}; Object.entries(k.courses || {}).forEach(([b, d]) => {
      clubs[k.club][b] = [(d.holeIds || []).length, Object.entries(d.tees || {}).flatMap(([g, m]) => Object.keys(m).map(t => g + ' ' + t)).sort().join(',')]; }); });
  return { rondes, clubs, gewapend: [...document.querySelectorAll('[data-confirm="1"], .confirm-armed')].length }; }"""

def verlies(voor, na):
    uit = []
    for rid, v in voor['rondes'].items():
        n = na['rondes'].get(rid)
        if n is None: uit.append(f"ronde {rid} weg"); continue
        for i, wat in enumerate(['scores', 'putts', 'notitie', 'holes']):
            if n[i] < v[i]: uit.append(f"ronde {rid}: {wat} {v[i]} -> {n[i]}")
    for club, banen in voor['clubs'].items():
        if club not in na['clubs']: uit.append(f"club {club} weg"); continue
        for baan, v in banen.items():
            n = na['clubs'][club].get(baan)
            if n is None: uit.append(f"baan {baan} weg")
            elif n[0] < v[0]: uit.append(f"baan {baan}: holes {v[0]} -> {n[0]}")
            elif set(v[1].split(',')) - set(n[1].split(',')): uit.append(f"baan {baan}: tee weg ({v[1]} -> {n[1]})")
    return uit

# Alles wat je kunt aantikken en dat nu echt bovenop ligt.
ALLES = "[...document.querySelectorAll('*')].filter(e => /^(BUTTON|SELECT|SUMMARY|LABEL|A)$/.test(e.tagName) || (e.tagName === 'INPUT' && /checkbox|radio/.test(e.type)) || typeof e.onclick === 'function' || typeof e.onpointerdown === 'function')"
DOELEN = """() => { const uit = []; const gezien = new Set();
  __ALLES__.forEach(e => { const r = e.getBoundingClientRect(); if (r.width < 4 || r.height < 4) return;
    if (getComputedStyle(e).visibility === 'hidden' || e.disabled) return;
    e.scrollIntoView({ block: 'center', inline: 'center' });
    const q = e.getBoundingClientRect(), x = q.left + q.width / 2, y = q.top + q.height / 2;
    if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) return;
    const top = document.elementFromPoint(x, y); if (!top || !(e === top || e.contains(top) || top.contains(e))) return;
    const naam = (e.tagName.toLowerCase() + ' "' + (e.innerText || e.getAttribute('aria-label') || e.title || '').replace(/\\s+/g, ' ').trim().slice(0, 28) + '" ' + (e.getAttribute('onclick') || e.getAttribute('onpointerdown') || e.id || '').slice(0, 70));
    if (gezien.has(naam)) return; gezien.add(naam);
    uit.push(naam); });
  return uit; }"""
TIK = """(naam) => {
  for (const e of __ALLES__) { const r0 = e.getBoundingClientRect(); if (r0.width < 4 || r0.height < 4) continue;
    const n = (e.tagName.toLowerCase() + ' "' + (e.innerText || e.getAttribute('aria-label') || e.title || '').replace(/\\s+/g, ' ').trim().slice(0, 28) + '" ' + (e.getAttribute('onclick') || e.getAttribute('onpointerdown') || e.id || '').slice(0, 70));
    if (n !== naam) continue; e.scrollIntoView({ block: 'center', inline: 'center' }); const q = e.getBoundingClientRect();
    return [q.left + q.width / 2, q.top + q.height / 2]; }
  return null; }"""

DOELEN = DOELEN.replace('__ALLES__', ALLES); TIK = TIK.replace('__ALLES__', ALLES)

BASIS = """() => { document.querySelectorAll('[id$=Modal], [id$=Overlay]').forEach(m => m.classList.add('hidden')); if (typeof annuleerHerplan === 'function') annuleerHerplan();
    window.tryWriteToExportFolder = async () => true; navigator.share = undefined; """
OPEN = ("document.querySelectorAll('[data-section-key]').forEach(k => { window._setSectionCollapsed[k.dataset.sectionKey] = false; }); applySettingsSections();"
        # Ook de uitklapblokken 'Meer opties': daar staan de wisknoppen in.
        " document.querySelectorAll('#screen-settings .more-full').forEach(f => { if (!f.classList.contains('open') && f.previousElementSibling) toggleMoreInfo(f.previousElementSibling); f.style.maxHeight = 'none'; });")
STANDEN = [
  ("startscherm", "nav('setup'); localStorage.setItem('golf_lussen_open', '1'); if (!player2Visible) togglePlayer2(); rebuildStartScreen();"),
  ("scorescherm, invoerpaneel open", "nav('score'); if (activePlayer !== 1) switchToPlayer(1); setCurrentHole(1); scoreButtonsRow = 1; beginInvoer(1); renderScore();"),
  ("scorescherm, speler 2", "nav('score'); if (activePlayer !== 2) switchToPlayer(2); setCurrentHole(0); scoreButtonsRow = 0; beginInvoer(0); renderScore();"),
  ("Rondes, lijst", "nav('archive'); zetGroepering(null); tekenRondelijst();"),
  ("Rondes, agenda", "nav('archive'); if (archiefGroepering !== 'gepland') toggleGroupByPlanned(); document.querySelectorAll('#savedList [onclick]').forEach(e => { if (/Later|Volgende|Deze/.test(e.innerText)) e.click(); });"),
  ("Rondes, keuzevenster van een ronde", "nav('archive'); openRoundEditChoice(leesRondes().findIndex(r => r.id === 101));"),
  ("Rondes, Ronde bewerken open", "nav('archive'); doOpenRoundInfoModal(leesRondes().findIndex(r => r.id === 102));"),
  ("Rondes, Ronde bewerken van de lopende ronde", "nav('archive'); doOpenRoundInfoModal(leesRondes().findIndex(r => String(r.id) === localStorage.getItem('golf_active_id')));"),
  ("Rondes, Vaststellen open", "nav('archive'); doOpenRoundResultModal(leesRondes().findIndex(r => r.id === 101));"),
  ("Statistiek", "['handicap','prestaties','banen'].forEach(k => localStorage.setItem('golf_stats_grp_' + k, 'open')); window._statClubCollapsed = { Club_A: false }; nav('stat'); renderPlayerStats();"),
  ("Clubs", "nav('club'); document.querySelectorAll('#screen-club .card').forEach(k => { const a = k.querySelector('.club-actions'); if (a && a.classList.contains('hidden')) toggleClubActions(null, k); const l = k.querySelector('.course-list-toggle'); if (l && l.classList.contains('hidden')) toggleCourseList(k.firstElementChild); k.querySelectorAll('[id^=courseSubGroup_]').forEach(g => { if (g.classList.contains('hidden')) toggleClubSubGroup(g.id); }); });"),
  ("Club bewerken", "nav('club'); openClubEditor('Club A'); ['9','18','overig','lus'].forEach(g => { const w = document.getElementById('clubCourseGroup' + g); if (w && w.classList.contains('hidden')) toggleClubCourseGroup(g); });"),
  ("Baan bewerken", "nav('club'); openClubEditor('Club A'); openCourseEditor('Noord'); ['tees', 'holes'].forEach(k => { const w = document.getElementById(k === 'tees' ? 'editorTeesWrap' : 'editorHolesWrap'); if (w && w.classList.contains('hidden')) toggleEditorSection(k); });"),
  ("Baan bewerken, wedstrijdlus", "nav('club'); openClubEditor('Club A'); openCourseEditor('Lus'); ['tees', 'holes'].forEach(k => { const w = document.getElementById(k === 'tees' ? 'editorTeesWrap' : 'editorHolesWrap'); if (w && w.classList.contains('hidden')) toggleEditorSection(k); });"),
  ("Nieuwe wedstrijdlus", "nav('club'); openClubEditor('Club A'); openLusMaker(); kiesLusBron('Noord'); [0,1,2].forEach(tikLusHole);"),
  ("Instellingen, Algemeen", "nav('settings'); switchSettingsTab('main'); " + OPEN),
  ("Instellingen, WHS", "nav('settings'); switchSettingsTab('whs'); " + OPEN),
  ("Instellingen, Gegevens", "nav('settings'); switchSettingsTab('data'); " + OPEN),
  ("clubzoekvenster", "nav('setup'); openClubSearchModal();"),
]

async def vers(pg):
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES])
    await pg.evaluate("() => { localStorage.setItem('golf_default_club', 'Club A'); localStorage.setItem('golf_home_club', 'Club A'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_actions_always_visible', 'on'); localStorage.setItem('golf_auto_next', 'off'); }")
    await pg.reload(); await pg.wait_for_timeout(350)
    await pg.evaluate("""() => { nav('setup'); sel.track = 'Noord'; sel.gender = 'Heren'; sel.tee = 'Geel'; sel._teeUserSelected = true;
        document.getElementById('iName').value = 'Testspeler'; document.getElementById('iHcp').value = '30.8';
        player2Visible = true; sel2.gender = 'Dames'; sel2.tee = 'Rood'; sel2._teeUserSelected = true;
        document.getElementById('iName2').value = 'Anna'; document.getElementById('iHcp2').value = '20';
        zetStartNote(1, 'lopend Testspeler'); zetStartNote(2, 'lopend Anna'); startRound(); }"""); await pg.wait_for_timeout(250)
    await pg.evaluate("""() => { for (let i = 0; i < 4; i++) { setCurrentHole(i); stepScore(i, +1); } switchToPlayer(2); for (let i = 0; i < 3; i++) { setCurrentHole(i); stepScore(i, +1); } switchToPlayer(1); }""")
    await pg.wait_for_timeout(100)

async def main():
    t0 = time.time()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        pg.on('dialog', lambda d: asyncio.ensure_future(d.dismiss()))
        await vers(pg)
        bezit0 = await pg.evaluate(BEZIT)
        check("uitgangspunt: negen rondes, twee clubs, vier banen", (len(bezit0['rondes']), len(bezit0['clubs']), sum(len(v) for v in bezit0['clubs'].values())), (9, 2, 4))
        totaal = 0; invoer = []
        for naam, js in STANDEN:
            await pg.evaluate(BASIS + js + " }"); await pg.wait_for_timeout(200)
            doelen = await pg.evaluate(DOELEN)
            verloren = []
            for d in doelen:
                await pg.evaluate(BASIS + js + " }"); await pg.wait_for_timeout(60)
                plek = await pg.evaluate(TIK, d)
                if not plek: continue
                try:
                    await pg.mouse.click(plek[0], plek[1]); await pg.wait_for_timeout(90)
                    await pg.wait_for_load_state('domcontentloaded')
                    na = await pg.evaluate(BEZIT)
                except Exception:
                    await pg.wait_for_timeout(500); na = await pg.evaluate(BEZIT)
                totaal += 1
                v = verlies(bezit0, na)
                if v:
                    # De min-knop op het scorescherm is invoer: één slag eraf, en bij 1 leeg.
                    (invoer if 'minusDown' in d else verloren).append(f"{d} => {'; '.join(v)}")
                if v or na['gewapend'] or na != bezit0:
                    await vers(pg)                        # schone lei: niets gewapend, alles terug
                    bezit0 = await pg.evaluate(BEZIT)     # de lopende rondes hebben na een verse start een nieuw nummer
            check(f"{naam}: {len(doelen)} dingen aangetikt, niets kwijt", verloren, [])
        print(f"\n   {totaal} tikken in {len(STANDEN)} standen, {int(time.time() - t0)} seconden")
        print(f"   invoer met de min-knop (geen verwijderen): {len(invoer)} keer" + (f", bv. {invoer[0][:150]}" if invoer else ""))
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
