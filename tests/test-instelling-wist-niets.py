"""Een instelling uitzetten verbergt alleen en wist niets: uit en weer aan geeft alles terug.

Vaste regel (Mark, 4-10-2026). De test vindt ZELF elke schakelaar in Instellingen; een
nieuwe schakelaar doet dus vanzelf mee. Per schakelaar, in elke stand van de app:

  1. alle schermen openen en hun tekst onthouden; de hele opslag en de lopende ronde
     in het geheugen vastleggen;
  2. de schakelaar omzetten met een echte tik (staat hij aan: uit; staat hij uit: aan);
  3. vergelijken: alleen de instelling zelf mag veranderd zijn;
  4. alle schermen openen (een scherm openen kan gegevens opnieuw wegschrijven);
  5. weer vergelijken;
  6. de schakelaar terugzetten: de opslag is exact als bij 1, en de schermen tonen
     hetzelfde als bij 1.

Standen: geen lopende ronde, een lopende ronde, twee spelers, een volle ronde die nog
open staat — met de testgegevens. En met Marks eigen gegevens: geen lopende ronde, en
een echte afgeronde ronde opnieuw geladen. Daarna 'putts bijhouden' en 'handicap
bijhouden' samen uit en weer aan.

Vergelijken gaat op INHOUD: de volgorde van de velden binnen een ronde telt niet (die
verandert bij het opslaan van een geopende ronde en is geen wijziging).

Buiten deze test: wat je zelf verandert terwijl een schakelaar uit staat (een score
verlagen met putts uit neemt de putts mee omlaag; een ronde starten met handicap uit
is niet qualifying). Dat is bewust zo gebouwd.

Bewijs dat de test kan falen:  KAPOT=1 python3 test-instelling-wist-niets.py
draait dezelfde test op een app waarin 'putts bijhouden' uitzetten de putts wist, en
waarin 'handicap bijhouden' uitzetten de qualifying-vlag weghaalt. Dan moet hij falen.
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testdata
from testdata import app_url
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
KAPOT = os.environ.get('KAPOT') == '1'

ECHTE_CLUBS = {c['club']: c for c in json.load(open(os.path.join(HIER, 'echte-clubs.json'), encoding='utf-8'))}
_STAND = next(iter(json.load(open(os.path.join(HIER, 'overstap-standen.json'), encoding='utf-8')).values()))
ECHTE_RONDES = json.loads(_STAND['opslag']['golf_rounds'])

fouten, geteld = [], [0]
def check(naam, ok, detail=''):
    geteld[0] += 1
    if not ok:
        print(f"  FOUT {naam}" + (f": {detail}" if detail else ''))
        fouten.append(naam)

# ── de app in een stand zetten ────────────────────────────────────────────────────
SEED_ECHT = """([clubs, rondes]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(clubs));
  localStorage.setItem('golf_rounds', JSON.stringify(rondes)); localStorage.setItem('golf_profile_name', 'Testspeler');
  localStorage.setItem('golf_profile_hcp', '30.8'); localStorage.setItem('golf_kenmerk_gevraagd', '1');
  localStorage.setItem('golf_home_club', 'Golfclub Heelsum'); localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
  localStorage.setItem('golf_track_putts', 'on');
  ['handicap','prestaties','banen'].forEach(g => localStorage.setItem('golf_stats_grp_' + g, 'open')); }"""

START = """(twee) => { nav('setup'); sel.track='Airborne'; sel.gender='Heren'; sel.tee='Blauw'; sel.qualifying=true;
  document.getElementById('iName').value='Mark'; document.getElementById('iHcp').value='30.7';
  if (twee) togglePlayer2(true); }"""
START2 = """(twee) => { if (twee) { document.getElementById('iName2').value='Partner'; document.getElementById('iHcp2').value='18.0';
  sel2.track='Airborne'; sel2.gender='Heren'; sel2.tee='Blauw'; sel2.qualifying=true; }
  startRound(); const cb=document.getElementById('confirmModalBtn');
  if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }"""

async def start(pg, twee=False):
    await pg.evaluate(START, twee); await pg.wait_for_timeout(200)
    await pg.evaluate(START2, twee); await pg.wait_for_timeout(250)
    await pg.evaluate("() => { nav('score'); renderScore(); }"); await pg.wait_for_timeout(100)

async def vul(pg, n, speler=None):
    if speler: await pg.evaluate("(n) => switchToPlayer(n)", speler); await pg.wait_for_timeout(120)
    for h in range(n):
        # score 5 (de app zet er zelf 2 putts bij), daarna putts op 1 of 3 zodat er iets te verliezen valt
        await pg.evaluate("""(h) => { setCurrentHole(h); selectHole(h); toggleScoreButtons(h); armScoreChange(h, 4 + (h % 3)); clearScoreTap(false); }""", h)
        await pg.wait_for_timeout(40)

async def stand_geen(pg): pass
async def stand_lopend(pg): await start(pg); await vul(pg, 4)
async def stand_twee(pg): await start(pg, True); await vul(pg, 4); await vul(pg, 3, 2); await pg.evaluate("() => switchToPlayer(1)")
async def stand_vol_open(pg): await start(pg); await vul(pg, 9)
async def stand_echt_geladen(pg):
    await pg.evaluate("""() => { const s = loadSavedRounds(); const i = s.findIndex(r => isRondeAf(r) && r.qualifying
        && (r.holes || []).some(h => h.putts != null)); loadRoundSingle(i >= 0 ? i : s.findIndex(r => isRondeAf(r))); }""")
    await pg.wait_for_timeout(250)

STANDEN = [
    ('test: geen lopende ronde',        False, stand_geen),
    ('test: lopende ronde',             False, stand_lopend),
    ('test: twee spelers',              False, stand_twee),
    ('test: volle ronde nog open',      False, stand_vol_open),
    ('eigen gegevens: geen lopende ronde',   True, stand_geen),
    ('eigen gegevens: echte ronde geladen',  True, stand_echt_geladen),
]

# ── vastleggen en vergelijken ─────────────────────────────────────────────────────
FOTO = """() => {
  const vast = v => Array.isArray(v) ? '[' + v.map(vast).join(',') + ']'
    : (v && typeof v === 'object') ? '{' + Object.keys(v).filter(k => v[k] !== undefined).sort().map(k => JSON.stringify(k) + ':' + vast(v[k])).join(',') + '}'
    : JSON.stringify(v === undefined ? null : v);
  const opslag = {};
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i), w = localStorage.getItem(k);
    let inhoud = w;
    try { const j = JSON.parse(w); if (j && typeof j === 'object') inhoud = vast(j); } catch (e) {}
    opslag[k] = inhoud;
  }
  return { opslag, geheugen: vast({ game, game2Id, activePlayer }) };
}"""

SCHERMEN = ['setup', 'score', 'archive', 'stat', 'club', 'settings']

async def schermen_langs(pg, teksten=None):
    """Tikt elk tabblad aan. Geeft de tekst per scherm terug als daarom gevraagd wordt."""
    uit = {}
    for s in SCHERMEN:
        knop = pg.locator(f'#tab-{s}')
        if await knop.is_visible():
            await knop.click()
        else:
            await pg.evaluate("(s) => nav(s)", s)
        await pg.wait_for_timeout(120)
        if teksten is not None and s != 'settings':
            uit[s] = await pg.evaluate("(s) => document.getElementById('screen-' + s).innerText", s)
    return uit

# De schakelaar in beeld brengen (juiste subtab, sectie open) en zeggen of hij te tikken is.
TOON = """(id) => {
  const cb = document.getElementById(id); if (!cb) return 'ontbreekt';
  const tab = cb.closest('#settingsTabMain, #settingsTabMain2, #settingsTabWhs, #settingsTabData');
  const knop = { settingsTabMain: 'settingsTabBtnMain', settingsTabMain2: 'settingsTabBtnMain',
                 settingsTabWhs: 'settingsTabBtnWhs', settingsTabData: 'settingsTabBtnData' }[tab && tab.id];
  if (knop) document.getElementById(knop).click();
  const body = cb.closest('.settings-section-body');
  if (body && getComputedStyle(body).display === 'none') body.previousElementSibling.click();
  const l = cb.closest('label');
  return (l && l.getClientRects().length) ? 'zichtbaar' : 'verborgen';
}"""

async def tik(pg, sid):
    """Echte tik op de schakelaar. Geeft de nieuwe stand terug, of None als hij niet te zien is."""
    await pg.locator('#tab-settings').click(); await pg.wait_for_timeout(100)
    if await pg.evaluate(TOON, sid) != 'zichtbaar':
        return None
    await pg.wait_for_timeout(60)
    await pg.locator(f'label:has(#{sid})').click()
    await pg.wait_for_timeout(200)
    return await pg.evaluate("(id) => document.getElementById(id).checked", sid)

def verschil(a, b, vrij):
    """De sleutels waarvan de inhoud verschilt, buiten de vrijgestelde."""
    return sorted(k for k in set(a) | set(b) if k not in vrij and a.get(k) != b.get(k))

def kort(a, b, k):
    x, y = str(a.get(k)), str(b.get(k))
    i = next((n for n in range(min(len(x), len(y))) if x[n] != y[n]), min(len(x), len(y)))
    return f"{k} @{i}: …{x[max(0, i-40):i+60]}… → …{y[max(0, i-40):i+60]}…"

# Opzettelijk kapot, alleen voor het bewijs dat de test kan falen.
KAPOT_JS = """() => {
  const p = window.toggleTrackPutts;
  window.toggleTrackPutts = function () { p();
    if (!trackPuttsEnabled()) { const s = loadSavedRounds(); s.forEach(r => (r.holes || []).forEach(h => { if (h.putts != null) h.putts = null; }));
      metVerwijderen(() => setRoundsAndMark(JSON.stringify(s))); } };
  const w = window.toggleWhsVolgen;
  window.toggleWhsVolgen = function () { w();
    if (!whsVolgen()) { const s = loadSavedRounds(); s.forEach(r => { r.qualifying = false; });
      metVerwijderen(() => setRoundsAndMark(JSON.stringify(s))); } };
}"""

async def doorloop(b, standnaam, echt, opzet, schakelaars):
    """Eén stand, één of meer schakelaars: omzetten, rondkijken, terugzetten."""
    naam = f"{standnaam} · {' + '.join(schakelaars)}"
    pg = await b.new_page(viewport={'width': 390, 'height': 844})
    pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
    try:
        await pg.goto(app_url())
        if echt: await pg.evaluate(SEED_ECHT, [ECHTE_CLUBS, ECHTE_RONDES])
        else:    await pg.evaluate(testdata.SEED, [testdata.CLUBS, testdata.RONDES])
        await pg.reload(); await pg.wait_for_timeout(400)
        if KAPOT: await pg.evaluate(KAPOT_JS)
        await opzet(pg)

        # in beeld brengen vóór de eerste foto: een sectie openklappen wordt onthouden
        for sid in schakelaars:
            await pg.locator('#tab-settings').click(); await pg.wait_for_timeout(80)
            await pg.evaluate(TOON, sid)
        voor_tekst = await schermen_langs(pg, {})
        f0 = await pg.evaluate(FOTO)
        begin = {sid: await pg.evaluate("(id) => document.getElementById(id).checked", sid) for sid in schakelaars}

        gedaan = []
        for sid in schakelaars:
            nu = await tik(pg, sid)
            if nu is None: continue
            check(f"{naam}: de tik zet {sid} om", nu != begin[sid])
            gedaan.append(sid)
        if not gedaan:
            return naam, 'overgeslagen'

        f1 = await pg.evaluate(FOTO)
        # Wat bij het omzetten verandert IS de instelling: dat mogen geen gegevens zijn.
        eigen = set(verschil(f0['opslag'], f1['opslag'], set()))
        gegevens = {k for k in eigen if k in ('golf_rounds', 'golf_clubs', 'golf_active_id', 'golf_game2_id')
                    or k.startswith('golf_backup') or k.startswith('golf_last_backup') or k.startswith('golf_profile')}
        check(f"{naam}: omzetten raakt geen gegevens", not gegevens,
              '; '.join(kort(f0['opslag'], f1['opslag'], k) for k in sorted(gegevens)))
        check(f"{naam}: omzetten raakt alleen de instelling zelf", len(eigen) <= len(gedaan), f"veranderd: {sorted(eigen)}")
        check(f"{naam}: de ronde in het geheugen is na het omzetten gelijk", f1['geheugen'] == f0['geheugen'])

        await schermen_langs(pg)
        f2 = await pg.evaluate(FOTO)
        d = verschil(f1['opslag'], f2['opslag'], set())
        check(f"{naam}: de schermen openen verandert niets", not d, '; '.join(kort(f1['opslag'], f2['opslag'], k) for k in d))
        check(f"{naam}: de ronde in het geheugen is na het rondkijken gelijk", f2['geheugen'] == f0['geheugen'])

        for sid in reversed(gedaan):
            nu = await tik(pg, sid)
            check(f"{naam}: {sid} staat terug zoals hij stond", nu == begin[sid], f"{nu}")
        f3 = await pg.evaluate(FOTO)
        d = verschil(f0['opslag'], f3['opslag'], eigen)
        check(f"{naam}: na terugzetten is de opslag als voorheen", not d, '; '.join(kort(f0['opslag'], f3['opslag'], k) for k in d))
        check(f"{naam}: en de ronde in het geheugen ook", f3['geheugen'] == f0['geheugen'])
        na_tekst = await schermen_langs(pg, {})
        for s in voor_tekst:
            check(f"{naam}: scherm '{s}' toont hetzelfde als voorheen", na_tekst.get(s) == voor_tekst[s])
        check(f"{naam}: geen fouten in de pagina", not pf, str(pf))
        return naam, 'gedaan'
    except Exception as e:
        check(f"{naam}: de doorloop is afgemaakt", False, str(e)[:200])
        return naam, 'afgebroken'
    finally:
        await pg.close()

async def melding_nieuwe_low(b):
    """De eenmalige regel 'Nieuwe laagste handicap' wordt niet ongezien verbruikt.

    Gevonden door deze test (4-10-2026): twee schakelaars bouwen Statistiek op de
    achtergrond op, en dat zette het 'laatst gezien'-merkje al. Sinds 10C gebeurt dat
    alleen als Statistiek in beeld is.
    """
    pg = await b.new_page(viewport={'width': 390, 'height': 844})
    await pg.goto(app_url()); await pg.evaluate(testdata.SEED, [testdata.CLUBS, testdata.RONDES])
    await pg.reload(); await pg.wait_for_timeout(400)
    await pg.locator('#tab-stat').click(); await pg.wait_for_timeout(200)
    sleutel = await pg.evaluate("() => Object.keys(localStorage).find(k => k.startsWith('golf_seen_low_hi_')) || null")
    check("melding: de app houdt een laatst geziene Low HI bij", sleutel is not None)
    if sleutel:
        echt = await pg.evaluate("(k) => localStorage.getItem(k)", sleutel)
        await pg.evaluate("(k) => localStorage.setItem(k, '54')", sleutel)     # doen alsof de vorige stand hoger was
        for sid in ('puttsStatsToggle', 'whsToggle'):
            await tik(pg, sid); await tik(pg, sid)
        check("melding: schakelaars omzetten verbruikt hem niet", await pg.evaluate("(k) => localStorage.getItem(k)", sleutel) == '54')
        await pg.locator('#tab-stat').click(); await pg.wait_for_timeout(250)
        tekst = await pg.evaluate("() => document.getElementById('screen-stat').innerText")
        check("melding: staat op Statistiek zodra je het opent", 'Nieuwe laagste handicap' in tekst)
        check("melding: en is daarna als gezien genoteerd", await pg.evaluate("(k) => localStorage.getItem(k)", sleutel) == echt)
        await pg.locator('#tab-setup').click(); await pg.wait_for_timeout(120)
        await pg.locator('#tab-stat').click(); await pg.wait_for_timeout(250)
        tekst = await pg.evaluate("() => document.getElementById('screen-stat').innerText")
        check("melding: de tweede keer staat hij er niet meer", 'Nieuwe laagste handicap' not in tekst)
    await pg.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        await pg.goto(app_url()); await pg.evaluate(testdata.SEED, [testdata.CLUBS, testdata.RONDES]); await pg.reload(); await pg.wait_for_timeout(300)
        schakelaars = await pg.evaluate("() => [...document.querySelectorAll('#screen-settings input[type=checkbox]')].map(c => c.id)")
        await pg.close()
        print(f"Schakelaars in Instellingen ({len(schakelaars)}): {', '.join(schakelaars)}")
        if KAPOT: print("LET OP: opzettelijk kapotte app — deze doorloop HOORT te falen.")
        check("de test vindt schakelaars", len(schakelaars) >= 2)
        check("putts bijhouden en handicap bijhouden zitten erbij", {'trackPuttsToggle', 'whsToggle'} <= set(schakelaars), str(schakelaars))

        werk = [(n, e, o, [s]) for s in schakelaars for (n, e, o) in STANDEN]
        werk += [(n, e, o, ['trackPuttsToggle', 'whsToggle']) for (n, e, o) in STANDEN]
        uitkomst = []
        for i in range(0, len(werk), 6):          # zes pagina's tegelijk
            uitkomst += await asyncio.gather(*[doorloop(b, *w) for w in werk[i:i + 6]])
        await melding_nieuwe_low(b)
        await b.close()

        gedaan = [n for n, u in uitkomst if u == 'gedaan']
        over = [n for n, u in uitkomst if u == 'overgeslagen']
        print(f"\n{len(gedaan)} doorlopen gedaan, {geteld[0]} controles.")
        if over:
            print(f"{len(over)} overgeslagen omdat de schakelaar in die stand niet te zien is:")
            for n in over: print("   " + n)
        # Elke schakelaar moet in minstens één stand echt zijn omgezet.
        for s in schakelaars:
            check(f"{s} is in minstens één stand omgezet", any(n.endswith('· ' + s) for n in gedaan))
        print(f"\n{len(fouten)} FOUT(EN)" if fouten else "\nGEEN FOUTEN")
        sys.exit(1 if fouten else 0)

asyncio.run(main())
