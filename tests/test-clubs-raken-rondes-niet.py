"""Een baan, tee of club wijzigen of verwijderen verandert geen bestaande ronde,
tenzij je bij hernoemen 'ja' zegt.

Vaste regel (Mark, 4-10-2026). 'Bestaande ronde' is elke ronde in de opslag: afgerond,
half gespeeld, gepland, en ook de ronde die op dat moment open staat — een ronde ligt
vast vanaf de start.

Per handeling een verse app met dezelfde beginstand: de testclubs (met bij een tweede
club een baan met DEZELFDE naam), de testrondes, een geplande ronde en een lopende
ronde op de baan die gewijzigd wordt. Daarna:

  A. WIJZIGEN EN VERWIJDEREN — CR/SR, par en SI, een holenaam, tee erbij, tee weg, baan
     weg, club weg, een ander clubbestand inlezen. Na afloop is elke ronde inhoudelijk
     gelijk aan ervoor, en de lopende ronde in het geheugen ook. De test controleert
     ook dat de wijziging in de clubgegevens echt is doorgevoerd.
  B. HERNOEMEN MET 'NEE' ('Alleen nieuwe rondes') — club (lang en kort), baan, tee: de
     app stelt de vraag, en na 'nee' is elke ronde gelijk.
  C. HERNOEMEN MET 'JA' ('Alles aanpassen') — alleen de naam verandert, alleen in de
     rondes van die club, baan of tee. Par, SI, CR, SR, slagen en scores blijven; de
     gelijknamige baan bij de andere club blijft ongemoeid.
  D. MARKS EIGEN GEGEVENS — zijn clubbestand en zijn rondes: op elke baan waar hij een
     ronde heeft de CR/SR wijzigen en daarna de baan verwijderen; geen ronde verandert.

Opslaan, verwijderen en de keuze in het hernoemvenster gaan met echte tikken; de
velden in de editor worden gevuld zoals de editor ze zelf uitleest.

Bewijs dat de test kan falen:  KAPOT=1 python3 test-clubs-raken-rondes-niet.py
draait op een app die bij hernoemen niet vraagt maar altijd alle rondes aanpast, en
die bij het opslaan van een baan de CR van bestaande rondes bijwerkt.
"""
import asyncio, copy, datetime, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testdata
from testdata import app_url
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
KAPOT = os.environ.get('KAPOT') == '1'
ECHTE_CLUBLIJST = json.load(open(os.path.join(HIER, 'echte-clubs.json'), encoding='utf-8'))
ECHTE_CLUBS = {c['club']: c for c in ECHTE_CLUBLIJST}
ECHTE_RONDES = json.load(open(os.path.join(HIER, 'echte-rondes.json'), encoding='utf-8'))
for _i, _r in enumerate(ECHTE_RONDES): _r.setdefault('id', 880000 + _i)      # de backup bewaart geen id's

fouten, geteld = [], [0]
def check(naam, ok, detail=''):
    geteld[0] += 1
    if not ok:
        print(f"  FOUT {naam}" + (f": {detail}" if detail else ''))
        fouten.append(naam)

# ── beginstand ────────────────────────────────────────────────────────────────────
def clubs():
    c = copy.deepcopy(testdata.CLUBS)
    c['Papendal']['courses']['Airborne'] = copy.deepcopy(c['Golfclub Heelsum']['courses']['Airborne'])   # zelfde baannaam, andere club
    return c

def rondes():
    r = [copy.deepcopy(x) for x in testdata.RONDES]
    for i in range(4):
        x = testdata.ronde(700 + i, f'2026-06-1{i}', baan='Airborne', club='Papendal', kort='Pap', tee=('Blauw', 'Geel')[i % 2])
        r.append(x)
    morgen = (datetime.date.today() + datetime.timedelta(days=4)).isoformat()
    r.append(testdata.ronde(710, morgen, played=0))                                # gepland, Heelsum Airborne Blauw
    r.append(testdata.ronde(711, '2026-07-07', tee='Geel'))                        # Heelsum Airborne Geel
    return r

LOPEND = """() => { nav('setup'); sel.track='Airborne'; sel.gender='Heren'; sel.tee='Blauw'; sel.qualifying=true;
  document.getElementById('iName').value='Mark'; document.getElementById('iHcp').value='30.7';
  startRound(); const cb=document.getElementById('confirmModalBtn');
  if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
  nav('score'); renderScore();
  for (const h of [0, 1, 2]) { setCurrentHole(h); selectHole(h); toggleScoreButtons(h); armScoreChange(h, 5); clearScoreTap(false); }
  return game.started; }"""

FOTO = """() => {
  const vast = v => Array.isArray(v) ? '[' + v.map(vast).join(',') + ']'
    : (v && typeof v === 'object') ? '{' + Object.keys(v).filter(k => v[k] !== undefined).sort().map(k => JSON.stringify(k) + ':' + vast(v[k])).join(',') + '}'
    : JSON.stringify(v === undefined ? null : v);
  const plat = r => { const u = {}; Object.keys(r).filter(k => r[k] !== undefined).forEach(k => u[k] = vast(r[k])); return u; };
  const rondes = {}; loadSavedRounds().forEach(r => rondes[r.id] = plat(r));
  return { rondes, spel: (game && game.started) ? plat(game) : null, clubs: JSON.stringify(CLUBS) };
}"""

# In de editor: de tee-rij met deze naam.
RIJ = "const rij = (naam) => [...document.querySelectorAll('.tee-editor-row')].find(r => (r.querySelector('.tee-name-field')?.dataset.value || '') === naam);"
ZET = "const zet = (el, v) => { el.dataset.value = String(v); el.textContent = String(v); };"

async def open_baan(pg, club, baan):
    await pg.evaluate("([c, b]) => { nav('club'); openClubEditor(c); openCourseEditor(b); }", [club, baan])
    await pg.wait_for_timeout(200)

async def bewaar_baan(pg):
    await pg.locator('[onclick="saveCourseFromEditor()"]').click(); await pg.wait_for_timeout(250)
    return (await pg.evaluate("() => { const s = document.getElementById('editorStatus'); return s ? s.textContent.trim() : ''; }"))

async def bewaar_club(pg):
    await pg.locator('[onclick="saveClubFromEditor()"]').click(); await pg.wait_for_timeout(250)
    return (await pg.evaluate("() => { const s = document.getElementById('clubEditorStatus'); return s ? s.textContent.trim() : ''; }"))

async def hernoemvraag(pg, antwoord):
    """Beantwoordt het hernoemvenster als het er staat. Geeft terug of de vraag gesteld is."""
    gesteld = 0
    for _ in range(3):
        if not await pg.evaluate("() => !document.getElementById('clubRenameModal').classList.contains('hidden')"): break
        gesteld += 1
        await pg.locator(f'[onclick="clubRenameKeuze({"true" if antwoord else "false"})"]').click(); await pg.wait_for_timeout(250)
    return gesteld

async def tweemaal_en_bevestig(pg, selector):
    k = pg.locator(selector)
    await k.click(); await pg.wait_for_timeout(120); await k.click(); await pg.wait_for_timeout(250)
    for sel in ('#dangerModalConfirmBtn', '#confirmModalBtn'):
        cb = pg.locator(sel)
        if await cb.is_visible(): await cb.click(); await pg.wait_for_timeout(300); break

# ── de handelingen ────────────────────────────────────────────────────────────────
H = 'Golfclub Heelsum'

async def h_cr_sr(pg):
    await open_baan(pg, H, 'Airborne')
    await pg.evaluate("() => {" + RIJ + ZET + " const r = rij('Blauw'); zet(r.querySelector('.cr-name-field'), '33.3'); zet(r.querySelector('.sr-name-field'), '111'); }")
    s = await bewaar_baan(pg)
    return s, await pg.evaluate("(c) => CLUBS[c].courses.Airborne.tees.Heren.Blauw.CR === 33.3 && CLUBS[c].courses.Airborne.tees.Heren.Blauw.SR === 111", H)

async def h_par_si(pg):
    await open_baan(pg, H, 'Airborne')
    voor = await pg.evaluate("(c) => JSON.stringify(CLUBS[c].courses.Airborne.tees)", H)
    await pg.evaluate("""() => { const rijen = [...document.querySelectorAll('#editorHoles tr')].filter(t => t.querySelector('.hole-id'));
        const a = rijen[0], b = rijen[1];
        const pa = a.querySelector('.par-cycle-btn'); pa.dataset.par = String((parseInt(pa.dataset.par) || 4) === 5 ? 4 : 5);
        const sa = a.querySelector('.hole-si'), sb = b.querySelector('.hole-si'); const t = sa.value; sa.value = sb.value; sb.value = t;
        if (typeof updateAllTeeParDisplays === 'function') { syncHoleTableNaarTee(); updateAllTeeParDisplays(); } }""")
    s = await bewaar_baan(pg)
    return s, await pg.evaluate("([c, voor]) => JSON.stringify(CLUBS[c].courses.Airborne.tees) !== voor", [H, voor])

async def h_holenaam(pg):
    await open_baan(pg, H, 'Airborne')
    await pg.evaluate("() => { document.querySelector('#editorHoles .hole-id').value = 'X1'; }")
    s = await bewaar_baan(pg)
    return s, await pg.evaluate("(c) => CLUBS[c].courses.Airborne.holeIds[0] === 'X1'", H)

async def h_tee_erbij(pg):
    await open_baan(pg, H, 'Airborne')
    await pg.evaluate("() => {" + ZET + """ addTeeRow(); const r = [...document.querySelectorAll('.tee-editor-row')].pop();
        zet(r.querySelector('.tee-name-field'), 'Oranje'); zet(r.querySelector('.cr-name-field'), '35.5'); zet(r.querySelector('.sr-name-field'), '125');
        if (typeof updateAllTeeParDisplays === 'function') updateAllTeeParDisplays(); }""")
    s = await bewaar_baan(pg)
    return s, await pg.evaluate("(c) => Object.values(CLUBS[c].courses.Airborne.tees).some(t => 'Oranje' in t)", H)

async def h_tee_weg(pg):
    await open_baan(pg, H, 'Airborne')
    voor = await pg.evaluate("(c) => Object.values(CLUBS[c].courses.Airborne.tees).reduce((s, t) => s + Object.keys(t).length, 0)", H)
    # de rij van Blauw (waar rondes op staan, ook de lopende) uit de editor halen
    await pg.evaluate("() => {" + RIJ + " const r = rij('Blauw'); if (editorHoleTeeRow === r) { const ander = [...document.querySelectorAll('.tee-editor-row')].find(x => x !== r); if (typeof toonTeeInHoleTabel === 'function') toonTeeInHoleTabel(ander); else editorHoleTeeRow = ander; } r.remove(); }")
    s = await bewaar_baan(pg)
    return s, await pg.evaluate("([c, voor]) => !('Blauw' in (CLUBS[c].courses.Airborne.tees.Heren || {})) && Object.values(CLUBS[c].courses.Airborne.tees).reduce((s, t) => s + Object.keys(t).length, 0) === voor - 1", [H, voor])

async def h_baan_weg(pg):
    await open_baan(pg, H, 'Airborne')
    await tweemaal_en_bevestig(pg, '[onclick="deleteCourseFromEditor(this)"]')
    return 'verwijderd', await pg.evaluate("(c) => !('Airborne' in CLUBS[c].courses)", H)

async def h_club_weg(pg):
    await pg.evaluate("(c) => { nav('club'); openClubEditor(c); }", H); await pg.wait_for_timeout(200)
    await tweemaal_en_bevestig(pg, '[onclick="deleteClubFromEditor(this)"]')
    return 'verwijderd', await pg.evaluate("(c) => !(c in CLUBS)", H)

async def h_clubbestand(pg):
    """Een ander clubbestand inlezen: Marks eigen clubbestand, met overal een andere CR en SR.
    Daarin staat ook Golfclub Heelsum met de baan Airborne, waar de testrondes op liggen."""
    c = copy.deepcopy(ECHTE_CLUBLIJST)
    for club in c:
        for baan in club['courses'].values():
            for g in baan['tees'].values():
                for t in g.values(): t['CR'] = round(t['CR'] + 1.1, 1); t['SR'] = t['SR'] + 3
    pad = os.path.join(tempfile.mkdtemp(), 'clubs_backup_test.json')
    json.dump(c, open(pad, 'w', encoding='utf-8'))
    await pg.evaluate("() => nav('settings')"); await pg.wait_for_timeout(150)
    await pg.locator('#importClubFile').set_input_files(pad); await pg.wait_for_timeout(500)
    for _ in range(4):                         # elke vraag die de app stelt bevestigen
        gedaan = False
        for sel in ('#confirmModalBtn', '#dangerModalConfirmBtn', '#keuzeModalKnop2'):
            k = pg.locator(sel)
            if await k.count() and await k.is_visible():
                await k.click(); await pg.wait_for_timeout(350); gedaan = True; break
        if not gedaan: break
    open_ = await pg.evaluate("() => [...document.querySelectorAll('[id$=Modal]:not(.hidden)')].map(m => m.id + ': ' + m.innerText.replace(/\\s+/g, ' ').trim().slice(0, 120))")
    return 'ingelezen; open vensters: ' + str(open_), await pg.evaluate("() => 'Golfclub Zeewolde' in CLUBS")

WIJZIGEN = [
    ('CR en SR van een tee wijzigen', h_cr_sr),
    ('par en SI wijzigen', h_par_si),
    ('een hole hernoemen', h_holenaam),
    ('een tee toevoegen', h_tee_erbij),
    ('een tee verwijderen (met rondes erop)', h_tee_weg),
    ('een baan verwijderen (met rondes erop)', h_baan_weg),
    ('een club verwijderen (met rondes erop)', h_club_weg),
    ('een ander clubbestand inlezen', h_clubbestand),
]

async def n_club_lang(pg):
    await pg.evaluate("(c) => { nav('club'); openClubEditor(c); document.getElementById('editorClubName').value = 'GC De Heuvel'; }", H); await pg.wait_for_timeout(150)
    return await bewaar_club(pg)
async def n_club_kort(pg):
    await pg.evaluate("(c) => { nav('club'); openClubEditor(c); document.getElementById('editorShortName').value = 'HLS'; }", H); await pg.wait_for_timeout(150)
    return await bewaar_club(pg)
async def n_baan(pg):
    await open_baan(pg, H, 'Airborne')
    await pg.evaluate("() => { document.getElementById('editorCourseName').value = 'Luchtlanding'; }")
    return await bewaar_baan(pg)
async def n_tee(pg):
    await open_baan(pg, H, 'Airborne')
    await pg.evaluate("() => {" + RIJ + ZET + " zet(rij('Blauw').querySelector('.tee-name-field'), 'Azuur'); }")
    return await bewaar_baan(pg)

# naam, handeling, welke rondes horen bij 'ja' te veranderen, en welke velden
HERNOEMEN = [
    ('clubnaam (lang)',  n_club_lang, lambda r: r.get('club') == json.dumps(H),                                              {'club'}),
    ('clubnaam (kort)',  n_club_kort, lambda r: r.get('club') == json.dumps(H),                                              {'clubShort'}),
    ('baannaam',         n_baan,      lambda r: r.get('club') == json.dumps(H) and r.get('track') == '"Airborne"',           {'track'}),
    ('teenaam',          n_tee,       lambda r: r.get('club') == json.dumps(H) and r.get('track') == '"Airborne"' and r.get('tee') == '"Blauw"' and r.get('gender') == '"Heren"', {'tee'}),
]

KAPOT_JS = """() => {
  // hernoemen: nooit vragen, altijd alles aanpassen
  const v1 = window.vraagNaamWijziging;
  window.vraagNaamWijziging = function (...a) { v1(...a); naamWijzigingKeuze(true); };
  const v2 = window.vraagClubRename;
  window.vraagClubRename = function (...a) { v2(...a); clubRenameKeuze(true); };
  // opslaan van een baan: de CR van bestaande rondes op die baan bijwerken
  const a = window.applyCourseChanges;
  window.applyCourseChanges = function (v) { const uit = a(v);
    const s = loadSavedRounds(); s.forEach(r => { if (r.track === v.newCourseName) r.CR = 99; }); setRoundsAndMark(JSON.stringify(s)); return uit; };
}"""

async def pagina(b, clubdata, rondedata, lopend=True, naam='Mark'):
    pg = await b.new_page(viewport={'width': 390, 'height': 844})
    pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
    await pg.goto(app_url()); await pg.evaluate(testdata.SEED, [clubdata, rondedata])
    await pg.evaluate("(n) => { localStorage.setItem('golf_profile_name', n); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }", naam)
    await pg.reload(); await pg.wait_for_timeout(400)
    if lopend:
        gestart = await pg.evaluate(LOPEND)
        check("beginstand: de lopende ronde is gestart", gestart)
    if KAPOT: await pg.evaluate(KAPOT_JS)
    return pg, pf

def anders(voor, na):
    """{ronde-id: velden die verschillen}; een verdwenen of nieuwe ronde telt als '(ronde)'."""
    uit = {}
    for i in set(voor) | set(na):
        if i not in voor or i not in na: uit[i] = {'(ronde weg)' if i in voor else '(ronde erbij)'}; continue
        v = {k for k in set(voor[i]) | set(na[i]) if voor[i].get(k) != na[i].get(k)}
        if v: uit[i] = v
    return uit

def toon(d, voor, na, n=3):
    return '; '.join(f"ronde {i}: " + ', '.join(f"{k} {voor.get(i, {}).get(k)}→{na.get(i, {}).get(k)}"[:70] for k in sorted(v)) for i, v in list(d.items())[:n])

async def wijzig(b, naam, handeling):
    pg, pf = await pagina(b, clubs(), rondes())
    try:
        f0 = await pg.evaluate(FOTO)
        status, doorgevoerd = await handeling(pg)
        gesteld = await hernoemvraag(pg, False)
        f1 = await pg.evaluate(FOTO)
        check(f"{naam}: de wijziging is in de clubgegevens doorgevoerd", doorgevoerd, f"status: '{status}'")
        check(f"{naam}: de clubgegevens zijn veranderd", f1['clubs'] != f0['clubs'])
        d = anders(f0['rondes'], f1['rondes'])
        check(f"{naam}: geen enkele van de {len(f0['rondes'])} rondes is veranderd", not d, toon(d, f0['rondes'], f1['rondes']))
        ds = anders({'spel': f0['spel']}, {'spel': f1['spel']}) if f0['spel'] and f1['spel'] else ({} if f0['spel'] == f1['spel'] else {'spel': {'(lopende ronde weg)'}})
        check(f"{naam}: de lopende ronde in het geheugen is gelijk", not ds, str(ds))
        # en na herladen nog steeds
        await pg.reload(); await pg.wait_for_timeout(400)
        f2 = await pg.evaluate(FOTO)
        d = anders(f0['rondes'], f2['rondes'])
        check(f"{naam}: ook na herladen is geen ronde veranderd", not d, toon(d, f0['rondes'], f2['rondes']))
        # (de inhoud van de lopende ronde zit al in de vergelijking van de opslag hierboven)
        check(f"{naam}: de lopende ronde loopt na herladen nog", f2['spel'] is not None)
        check(f"{naam}: geen fouten in de pagina", not pf, str(pf[:2]))
    except Exception as e:
        check(f"{naam}: de handeling is uitgevoerd", False, str(e)[:250])
    finally:
        await pg.close()

async def hernoem(b, naam, handeling, hoort, velden, ja):
    wat = f"{naam} hernoemen, '{'ja' if ja else 'nee'}'"
    pg, pf = await pagina(b, clubs(), rondes())
    try:
        f0 = await pg.evaluate(FOTO)
        status = await handeling(pg)
        gesteld = await hernoemvraag(pg, ja)
        f1 = await pg.evaluate(FOTO)
        check(f"{wat}: de naam is in de clubgegevens gewijzigd", f1['clubs'] != f0['clubs'], f"status: '{status}'")
        if not KAPOT:
            check(f"{wat}: de app stelt de vraag", gesteld >= 1)
        d = anders(f0['rondes'], f1['rondes'])
        if not ja:
            check(f"{wat}: geen enkele ronde is veranderd", not d, toon(d, f0['rondes'], f1['rondes']))
            check(f"{wat}: de lopende ronde is gelijk", f0['spel'] == f1['spel'])
        else:
            moet = {i for i, r in f0['rondes'].items() if hoort(r)}
            check(f"{wat}: er zijn rondes die het betreft", len(moet) > 0)
            teveel = {i: v for i, v in d.items() if i not in moet}
            check(f"{wat}: alleen rondes van die club, baan of tee veranderen", not teveel, toon(teveel, f0['rondes'], f1['rondes']))
            fout = {i: v for i, v in d.items() if i in moet and not v <= velden}
            check(f"{wat}: alleen de naam verandert ({', '.join(sorted(velden))})", not fout, toon(fout, f0['rondes'], f1['rondes']))
            if gesteld:
                gemist = sorted(i for i in moet if i not in d)
                check(f"{wat}: alle {len(moet)} betrokken rondes zijn aangepast", not gemist, f"{len(gemist)} niet: {gemist[:5]}")
            if f0['spel'] and f1['spel']:
                ds = {k for k in set(f0['spel']) | set(f1['spel']) if f0['spel'].get(k) != f1['spel'].get(k)}
                check(f"{wat}: in de lopende ronde verandert hooguit de naam", ds <= velden | {'clubShort'} if 'club' in velden else ds <= velden, str(ds))
        check(f"{wat}: geen fouten in de pagina", not pf, str(pf[:2]))
        return wat, gesteld
    except Exception as e:
        check(f"{wat}: de handeling is uitgevoerd", False, str(e)[:250])
        return wat, 0
    finally:
        await pg.close()

async def eigen(b):
    """Marks eigen clubs en rondes: per baan met rondes de CR/SR wijzigen, daarna de baan verwijderen."""
    banen = sorted({(r['club'], r['track']) for r in ECHTE_RONDES if r['club'] in ECHTE_CLUBS and r['track'] in ECHTE_CLUBS[r['club']]['courses']})
    pg, pf = await pagina(b, ECHTE_CLUBS, ECHTE_RONDES, lopend=False, naam='Testspeler')
    f0 = await pg.evaluate(FOTO)
    check("eigen gegevens: alle rondes zijn ingelezen", len(f0['rondes']) == len(ECHTE_RONDES), f"{len(f0['rondes'])} van {len(ECHTE_RONDES)}")
    for club, baan in banen:
        naam = f"eigen gegevens · {club} · {baan}"
        try:
            await open_baan(pg, club, baan)
            await pg.evaluate("() => {" + ZET + " document.querySelectorAll('.tee-editor-row').forEach(r => { zet(r.querySelector('.cr-name-field'), '30.1'); zet(r.querySelector('.sr-name-field'), '101'); }); }")
            s = await bewaar_baan(pg); await hernoemvraag(pg, False)
            ok = await pg.evaluate("([c, b]) => Object.values(CLUBS[c].courses[b].tees).every(g => Object.values(g).every(t => t.CR === 30.1 && t.SR === 101))", [club, baan])
            check(f"{naam}: CR en SR zijn gewijzigd", ok, f"status: '{s}'")
            f1 = await pg.evaluate(FOTO); d = anders(f0['rondes'], f1['rondes'])
            check(f"{naam}: CR/SR wijzigen verandert geen ronde", not d, toon(d, f0['rondes'], f1['rondes']))
            await tweemaal_en_bevestig(pg, '[onclick="deleteCourseFromEditor(this)"]')
            check(f"{naam}: de baan is verwijderd", await pg.evaluate("([c, b]) => !(b in CLUBS[c].courses)", [club, baan]))
            f2 = await pg.evaluate(FOTO); d = anders(f0['rondes'], f2['rondes'])
            check(f"{naam}: de baan verwijderen verandert geen ronde", not d, toon(d, f0['rondes'], f2['rondes']))
            await pg.evaluate("() => { document.getElementById('courseEditorOverlay')?.classList.add('hidden'); document.getElementById('clubEditorOverlay')?.classList.add('hidden'); }")
        except Exception as e:
            check(f"{naam}: de handeling is uitgevoerd", False, str(e)[:250])
    await pg.reload(); await pg.wait_for_timeout(400)
    f3 = await pg.evaluate(FOTO); d = anders(f0['rondes'], f3['rondes'])
    check("eigen gegevens: na herladen is geen van Marks rondes veranderd", not d, toon(d, f0['rondes'], f3['rondes']))
    check("eigen gegevens: geen fouten in de pagina", not pf, str(pf[:2]))
    await pg.close()
    return len(banen), len(f0['rondes'])

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        if KAPOT: print("LET OP: opzettelijk kapotte app — deze doorloop HOORT te falen.")
        print("=== A. WIJZIGEN EN VERWIJDEREN ===")
        await asyncio.gather(*[wijzig(b, n, h) for n, h in WIJZIGEN])
        print("=== B en C. HERNOEMEN ===")
        uit = await asyncio.gather(*[hernoem(b, n, h, hoort, velden, ja) for (n, h, hoort, velden) in HERNOEMEN for ja in (False, True)])
        for wat, gesteld in uit: print(f"  {wat:<40} vraag gesteld: {'ja' if gesteld else 'NEE'}")
        print("=== D. MARKS EIGEN GEGEVENS ===")
        nb, nr = await eigen(b)
        print(f"  {nb} banen met rondes gewijzigd en verwijderd, {nr} rondes vergeleken")
        await b.close()
        print(f"\n{geteld[0]} controles.")
        print(f"{len(fouten)} FOUT(EN)" if fouten else "GEEN FOUTEN")
        sys.exit(1 if fouten else 0)

asyncio.run(main())
