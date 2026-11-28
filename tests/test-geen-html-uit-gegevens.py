"""Gegevens komen nooit als HTML in beeld (veiligheidsronde 22-11-2026).

Alle vier de apps delen één domein: een stukje HTML in een naam of notitie dat als HTML in
de pagina komt, kan code draaien met toegang tot de opslag van alle apps. Deze test zet in
elk vrij tekstveld (speler, club, korte naam, baan, tee, notitie, standaardnamen) een
<img> met een kenmerk en een onerror, loopt de schermen en vensters langs en eist dat er
nergens zo'n element ontstaat en dat er geen code draait. De tekst zelf mag gewoon in beeld.
"""
import asyncio, copy, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

def P(tag):
    return f'<img src=x data-xss="{tag}" onerror="(window.__xss=window.__xss||[]).push(\'{tag}\')">'

CLUB = 'Golfclub De Hoeve' + P('club'); KORT = 'De Hoeve' + P('kort'); BAAN = 'Akkerweg' + P('baan'); TEE = 'Blauw' + P('tee')
SPELER = 'Testspeler' + P('speler'); SPELER2 = 'Speler 2' + P('speler2')

def vergiftig():
    clubs = copy.deepcopy(CLUBS)
    c = clubs.pop('Golfclub De Hoeve'); c['club'] = CLUB; c['shortName'] = KORT
    c['courses'][BAAN] = c['courses'].pop('Akkerweg')
    t = c['courses'][BAAN]['tees']['Heren']; t[TEE] = t.pop('Blauw')
    clubs[CLUB] = c
    rondes = copy.deepcopy(RONDES)
    for r in rondes:
        if r['club'] == 'Golfclub De Hoeve': r['club'] = CLUB; r['clubShort'] = KORT
        if r['track'] == 'Akkerweg': r['track'] = BAAN
        if r['tee'] == 'Blauw' and r['track'] == BAAN: r['tee'] = TEE
        r['player'] = SPELER if r['player'] == 'Testspeler' else SPELER2
        r['note'] = 'notitie ' + P('notitie')
    # een koppel: ronde 84 (Speler 2) op hetzelfde moment als ronde 80
    r80 = next(r for r in rondes if r['id'] == 80); r84 = next(r for r in rondes if r['id'] == 84)
    r84['date'], r84['time'] = r80['date'], r80['time']
    return clubs, rondes

HAAK = """(() => { window.__rauw = [];
  const kijk = (waar, v) => { const t = String(v); const m = t.match(/<img src=x data-xss="([a-z0-9]+)"/g);
    if (m) window.__rauw.push(waar + ': ' + m.map(x => x.split('"')[1]).join(',')); };
  const d = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML');
  Object.defineProperty(Element.prototype, 'innerHTML', { configurable: true, get: d.get, set(v) { kijk('innerHTML', v); d.set.call(this, v); } });
  const o = Object.getOwnPropertyDescriptor(Element.prototype, 'outerHTML');
  Object.defineProperty(Element.prototype, 'outerHTML', { configurable: true, get: o.get, set(v) { kijk('outerHTML', v); o.set.call(this, v); } });
  const ia = Element.prototype.insertAdjacentHTML;
  Element.prototype.insertAdjacentHTML = function(w, v) { kijk('insertAdjacentHTML', v); return ia.call(this, w, v); };
})()"""

STAPPEN = [
    ("Start", "() => nav('setup')"),
    ("Statistiek", "() => { nav('stat'); renderPlayerStats(); }"),
    ("Analyseer mijn spel", "() => openGameAnalysis()"),
    ("Rondes", "() => { document.querySelectorAll('.modal-overlay, [id$=Modal], [id$=Overlay]').forEach(o => o.classList && o.classList.add('hidden')); nav('archive'); }"),
    *[(f"Rondes, groepering {g}", f"() => {{ zetGroepering('{g}'); tekenRondelijst(); }}") for g in ('categorie', 'club', 'speler', 'whs', 'gepland')],
    ("Rondes, zoeken", "() => { zetGroepering(null); toggleArchiefZoeken(); const z = document.getElementById('archiveSearch'); z.value = 'notitie'; z.dispatchEvent(new Event('input')); }"),
    ("Clubs", "() => { nav('club'); }"),
    ("Clubs, zoeken", "() => { const z = document.getElementById('clubSearch'); z.value = 'Golf'; z.dispatchEvent(new Event('input')); }"),
    ("Baananalyse", "() => { const b = [...document.querySelectorAll('#screen-club button[title=\"Baananalyse\"]')][0]; if (b) b.click(); }"),
    ("Club bewerken", "(c) => openClubEditor(c)"),
    ("Baan bewerken", "(c) => { openCourseEditor(Object.keys(CLUBS[c].courses)[0]); toggleEditorSection('tees'); toggleEditorSection('holes'); }"),
    ("Instellingen", "() => { document.querySelectorAll('.modal-overlay, [id$=Modal], [id$=Overlay]').forEach(o => { if (o.style) o.style.display = ''; o.classList && o.classList.add('hidden'); }); nav('settings'); switchSettingsTab('whs'); switchSettingsTab('data'); }"),
    ("Ronde bewerken", "() => { doOpenRoundInfoModal(loadSavedRounds().findIndex(isRondeAf)); }"),
    ("Ronde resultaat", "() => { closeRoundInfoModal(); openRoundResultModal(loadSavedRounds().findIndex(isRondeAf)); }"),
    ("Rondes bewerken (koppel)", "() => { const l = loadSavedRounds(); openRondesBewerken([String(l.find(r => r.id === 80).id), String(l.find(r => r.id === 84).id)]); }"),
    ("Keuzemenu bewerken", "() => { sluitRondesBewerken(); openRoundEditChoice(loadSavedRounds().findIndex(isRondeAf)); }"),
    ("Exporteren", "() => { sluitRoundEditChoice && sluitRoundEditChoice(); openExportModal(loadSavedRounds().findIndex(isRondeAf)); }"),
    ("Verwijderen (vraag)", "() => { closeExportModal(); const l = loadSavedRounds(); showDangerModal('Ronde verwijderen', tekstRondesVerwijderen([l[0], l[1]]), 'Verwijderen', () => {}); }"),
    ("Herplannen (Start)", "() => { herplanRonde(loadSavedRounds().find(r => r.id === 80).id); nav('setup'); }"),
    ("Ronde laden (Score)", "() => { annuleerHerplan(); loadRoundSingle(loadSavedRounds().findIndex(r => r.id === 80)); nav('score'); }"),
    ("Score, speler 2 gekoppeld", "() => { const l = loadSavedRounds(); loadRoundAsCouple(l.findIndex(r => r.id === 80), l.find(r => r.id === 84).id); nav('score'); }"),
    ("Leeg scorescherm met kaarten", "() => { finishActiveRound(null); nav('score'); }"),
]

async def main():
    clubs, rondes = vergiftig()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 780})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        # Elke keer dat er HTML in de pagina gaat: staat er een ongeëscapete <img> uit de gegevens
        # in? Zo is ook een naam te zien die in een attribuut (title="…") terechtkomt en daar uit
        # breekt; die geeft geen eigen element en ontsnapt anders aan de controle op [data-xss].
        await pg.add_init_script(HAAK)
        await pg.goto(app_url()); await pg.evaluate(SEED, [clubs, rondes])
        await pg.evaluate("""([s1, s2, c]) => { localStorage.setItem('golf_profile_name', s1); localStorage.setItem('golf_std_player1_name', s1);
            localStorage.setItem('golf_default_player2_name', s2); localStorage.setItem('golf_default_club', c); localStorage.setItem('golf_home_club', c); }""", [SPELER, SPELER2, CLUB])
        await pg.reload(); await pg.wait_for_timeout(600)
        mislukt = []
        for naam, js in STAPPEN:
            try:
                await pg.evaluate(js, CLUB) if '(c)' in js else await pg.evaluate(js)
            except Exception as e:
                mislukt.append(f"{naam}: {str(e)[:100]}")
            await pg.wait_for_timeout(250)
            n = await pg.evaluate("() => [...document.querySelectorAll('[data-xss]')].map(e => e.dataset.xss)")
            check(f"{naam}: geen element uit de gegevens", n, [])
        check("nergens ging een naam of notitie ongeëscapet als HTML de pagina in", await pg.evaluate("() => [...new Set(window.__rauw)]"), [])
        check("nergens is code uit de gegevens gedraaid", await pg.evaluate("() => window.__xss || []"), [])
        check("de namen staan wel als tekst in beeld (de club)", await pg.evaluate("(c) => { nav('club'); return document.getElementById('screen-club').textContent.includes(c); }", CLUB), True)
        check("alle stappen liepen", mislukt, [])
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
