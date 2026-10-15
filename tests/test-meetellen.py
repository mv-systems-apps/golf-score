"""Alleen afgeronde, qualifying rondes tellen mee voor handicap en statistiek.

Vaste regel (Mark, 4-10-2026): er wordt gerekend met wat afgerond is en niet meer
actief. 'Afgerond' is: alle holes ingevuld én de ronde staat niet meer open. Enige
uitzondering op 'alleen qualifying': de baananalyse in het clubscherm.

Opzet: RUIS TOEVOEGEN MAG NIETS VERANDEREN. De test legt eerst vast wat de app toont
met alleen afgeronde qualifying rondes van Mark. Daarna voegt hij, soort voor soort,
rondes toe die niet mogen meetellen, en vergelijkt:

  - WHS-hcp op Start;
  - het hele Statistiek-scherm, in de drie periodes;
  - de spelanalyse (Analyseer mijn spel);
  - de export van dagresultaten;
  - de berekende handicap op elke rondekaart van de oorspronkelijke rondes.

Soorten ruis: niet-qualifying, half gespeeld, gepland, van een andere speler, ingelezen
maar nog niet opgeslagen (de groep 'Geïmporteerd'), een volle
ronde die nog open staat (nieuw gespeeld), een volle ronde van speler 2 die open staat,
en alles tegelijk. En omgekeerd: een OUDE ronde opnieuw laden haalt hem tijdelijk uit
de berekening — dat moet hetzelfde geven als wanneer die ronde er niet is.

Daarnaast, in elke stand: elke handicapberekening onderweg wordt meegeschreven. Er
mogen alleen afgeronde, qualifying, niet-open rondes van de speler bovenin Start in
zitten. En bij een open ronde staat er geen 'Verwachte/Nieuwe WHS-hcp'.

De uitzondering wordt ook bewaakt: de baananalyse in het clubscherm moet door
niet-qualifying rondes juist WEL veranderen.

Bewijs dat de test kan falen:  KAPOT=1 python3 test-meetellen.py
draait op een app waarin het filter alleen nog op de speler let. Dan moet hij falen.
"""
import asyncio, copy, datetime, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testdata
from testdata import app_url
from playwright.async_api import async_playwright

KAPOT = os.environ.get('KAPOT') == '1'
fouten, geteld = [], [0]
def check(naam, ok, detail=''):
    geteld[0] += 1
    if not ok:
        print(f"  FOUT {naam}" + (f": {detail}" if detail else ''))
        fouten.append(naam)

VANDAAG = datetime.date.today()
def dag(n): return (VANDAAG - datetime.timedelta(days=n)).isoformat()

# De basis: 30 afgeronde qualifying rondes van Mark over het afgelopen jaar, met
# uiteenlopende dagresultaten. Daar mag ruis niets aan veranderen.
def basis():
    uit = []
    for i in range(30):
        r = testdata.ronde(100 + i, dag(5 + i * 11), baan=("Airborne", "Sandr")[i % 2])
        r['time'] = '09:30'; r['sd'] = r['sdFinal'] = 26.0 + (i * 7 % 13)
        uit.append(r)
    return uit

def ruis_ronde(rid, n, **kw):
    r = testdata.ronde(rid, dag(n), **kw); r['time'] = '15:45'
    r['sd'] = r['sdFinal'] = 3.0                       # opvallend laag: telt hij mee, dan zie je het meteen
    return r

def niet_qualifying(): return [ruis_ronde(900 + i, 1 + i * 20, qual=False) for i in range(6)]
def half():            return [dict(ruis_ronde(910 + i, 2 + i * 20, played=5), sdFinal=3.0) for i in range(4)]
def gepland():         return [dict(ruis_ronde(920 + i, -3 - i, played=0), sdFinal=3.0) for i in range(3)]
def ander():           return [ruis_ronde(930 + i, 3 + i * 15, speler='Partner') for i in range(8)]
def ingelezen():       return [dict(ruis_ronde(940 + i, 4 + i * 20), _justImported=True) for i in range(5)]   # in 'Geïmporteerd', nog geen 'Sla op'

async def open_nieuw(pg):
    """Een nieuwe ronde starten en alle holes invullen; hij blijft open staan."""
    await pg.evaluate("""() => { nav('setup'); sel.track='Airborne'; sel.gender='Heren'; sel.tee='Blauw'; sel.qualifying=true;
        document.getElementById('iName').value='Mark'; document.getElementById('iHcp').value='30.7'; }""")
    await pg.wait_for_timeout(200)
    await pg.evaluate("""() => { startRound(); const cb=document.getElementById('confirmModalBtn');
        if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
    await pg.wait_for_timeout(300)
    await pg.evaluate("() => { nav('score'); renderScore(); }")
    for h in range(9):
        await pg.evaluate("(h) => { setCurrentHole(h); selectHole(h); toggleScoreButtons(h); armScoreChange(h, 2); clearScoreTap(false); }", h)
        await pg.wait_for_timeout(40)

async def open_twee(pg):
    await pg.evaluate("""() => { nav('setup'); sel.track='Airborne'; sel.gender='Heren'; sel.tee='Blauw'; sel.qualifying=true;
        document.getElementById('iName').value='Mark'; document.getElementById('iHcp').value='30.7'; togglePlayer2(true); }""")
    await pg.wait_for_timeout(200)
    await pg.evaluate("""() => { document.getElementById('iName2').value='Partner'; document.getElementById('iHcp2').value='18.0';
        sel2.track='Airborne'; sel2.gender='Heren'; sel2.tee='Blauw'; sel2.qualifying=true;
        startRound(); const cb=document.getElementById('confirmModalBtn');
        if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
    await pg.wait_for_timeout(300)
    await pg.evaluate("() => { nav('score'); renderScore(); }")
    for speler in (1, 2):
        await pg.evaluate("(n) => switchToPlayer(n)", speler); await pg.wait_for_timeout(120)
        for h in range(9):
            await pg.evaluate("(h) => { setCurrentHole(h); selectHole(h); toggleScoreButtons(h); armScoreChange(h, 2); clearScoreTap(false); }", h)
            await pg.wait_for_timeout(40)
    await pg.evaluate("() => switchToPlayer(1)"); await pg.wait_for_timeout(120)

MEESCHRIJVEN = """(kapot) => {
  window._in = [];
  if (kapot) window.meetelFilter = (player) => (r => !!r && r.player === player);
  const whs = window.whsHandicap;
  window.whsHandicap = function (rounds, low = null, esr = null) {
    const open = new Set([localStorage.getItem('golf_active_id'), localStorage.getItem('golf_game2_id')].filter(Boolean).map(String));
    const boven = document.getElementById('iName').value.trim();
    (rounds || []).forEach(r => {
      if (String(r.id).startsWith('__')) return;              // proefrondes van 'Wat als?' en de vooruitblik
      const waarom = !r.qualifying ? 'niet qualifying' : r._justImported ? 'ingelezen, niet opgeslagen' : !isRondeAf(r) ? 'niet alle holes' : open.has(String(r.id)) ? 'staat open'
                   : r.player !== boven ? 'andere speler' : null;
      if (waarom) window._in.push(r.id + ' (' + waarom + ')');
    });
    window._n = (window._n || 0) + 1;
    return whs(rounds, low, esr);
  };
}"""

BEELD = """async () => {
  const uit = {};
  nav('setup'); updateComputedHcp();
  uit.start = document.getElementById('computedHcpVal').textContent.trim();
  // de export van dagresultaten, zonder iets weg te schrijven
  const oud = window.tryWriteToExportFolder; let tekst = null;
  window.tryWriteToExportFolder = async (naam, t) => { tekst = t; return true; };
  try { await exportDagresultaten(); } finally { window.tryWriteToExportFolder = oud; }
  uit.export = tekst;
  uit.analyse = (() => { try { const a = buildGameAnalysis(); return typeof a === 'string' ? a : JSON.stringify(a); } catch (e) { return 'FOUT ' + e.message; } })();
  return uit;
}"""

KAARTEN = """() => { const uit = {};
  [...document.querySelectorAll('#screen-archive .saved-item')].forEach(k => {
    const t = k.innerText; const kop = (t.split('\\n')[0] || '').trim();
    const m = t.match(/Whs\\s*(-?\\d+\\.\\d)\\s*(-?\\d+\\.\\d)?[^\\n]*/);
    if (/09:30/.test(kop) && /(^|\\n)\\s*Mark\\b/.test(t)) uit[kop] = m ? m[0].trim() : '(geen)';
  });
  return uit; }"""

GETAL = r'(-?\d+\.\d)'

async def meet(b, naam, rondes, na_laden=None, weg=None):
    """Zet de app op met deze rondes en geeft terug wat hij toont."""
    pg = await b.new_page(viewport={'width': 390, 'height': 844})
    pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
    await pg.goto(app_url()); await pg.evaluate(testdata.SEED, [testdata.CLUBS, rondes])
    await pg.evaluate("() => localStorage.setItem('golf_stats_grp_clubs', 'open')")
    await pg.reload(); await pg.wait_for_timeout(400)
    await pg.evaluate(MEESCHRIJVEN, KAPOT)
    if na_laden: await na_laden(pg)
    open_ronde = await pg.evaluate("() => !!localStorage.getItem('golf_active_id')")
    uit = await pg.evaluate(BEELD)
    uit['open'] = open_ronde
    uit['stat'] = {}
    await pg.locator('#tab-stat').click(); await pg.wait_for_timeout(250)
    if open_ronde:
        uit['ronde_info'] = await pg.evaluate("() => document.getElementById('screen-stat').innerText")
    else:
        for periode in ('Laatste 20', '12 maanden', 'Alles'):
            k = pg.get_by_text(periode, exact=True).first
            if await k.count() and await k.is_visible():
                await k.click(); await pg.wait_for_timeout(200)
            uit['stat'][periode] = await pg.evaluate("() => document.getElementById('playerStats').innerText")
    await pg.locator('#tab-archive').click(); await pg.wait_for_timeout(300)
    # De lijst toont standaard hooguit vijftig kaarten; voor de vergelijking moeten ze er allemaal staan.
    await pg.evaluate("() => { window._flatListLimit = 1000; loadSaved(); }"); await pg.wait_for_timeout(250)
    uit['kaarten'] = await pg.evaluate(KAARTEN)
    await pg.locator('#tab-club').click(); await pg.wait_for_timeout(300)
    uit['baan'] = await pg.evaluate("() => JSON.stringify(courseAnalysisData('Golfclub Heelsum', 'Airborne'))")
    uit['driehoek'] = await pg.evaluate("() => [loadSavedRounds().filter(roundHasWarning).length, openStaandeMeldingen().filter(m => m.filter === 'warn').length]")
    uit['in'] = sorted(set(await pg.evaluate("() => window._in")))
    uit['n'] = await pg.evaluate("() => window._n || 0")
    uit['pf'] = pf
    await pg.close()
    return naam, uit

def vergelijk(naam, basis_, nu, kaarten_weg=()):
    check(f"{naam}: WHS-hcp op Start blijft {basis_['start']}", nu['start'] == basis_['start'], nu['start'])
    check(f"{naam}: de export van dagresultaten is gelijk", nu['export'] == basis_['export'],
          f"{len(nu['export'] or '')} tekens tegen {len(basis_['export'] or '')}")
    check(f"{naam}: de spelanalyse is gelijk", nu['analyse'] == basis_['analyse'])
    if nu['open']:
        check(f"{naam}: bij de open ronde staat geen Verwachte/Nieuwe WHS-hcp",
              not re.search(r'WHS-hcp', nu.get('ronde_info', ''), re.I))
    else:
        for periode, tekst in basis_['stat'].items():
            a, c = tekst.split('\n'), nu['stat'].get(periode, '').split('\n')
            i = next((k for k in range(min(len(a), len(c))) if a[k] != c[k]), None)
            check(f"{naam}: Statistiek ({periode}) is gelijk", tekst == nu['stat'].get(periode),
                  '' if i is None else f"regel {i}: '{a[i][:50]}' → '{c[i][:50]}'")
    check(f"{naam}: driehoekjes en de teller 'zonder dagresultaat' zijn gelijk (ook een volle open ronde krijgt er nog geen)",
          nu['driehoek'] == basis_['driehoek'], f"{basis_['driehoek']} → {nu['driehoek']}")
    anders = {k: (v, nu['kaarten'].get(k)) for k, v in basis_['kaarten'].items()
              if k not in kaarten_weg and nu['kaarten'].get(k) != v}
    check(f"{naam}: de handicap op de {len(basis_['kaarten'])} oorspronkelijke rondekaarten is gelijk", not anders,
          str(list(anders.items())[:2]))

STAND_INLEZEN = """() => { nav('setup'); updateComputedHcp(); const lijst = loadSavedRounds();
    return { hcp: document.getElementById('computedHcpVal').textContent.trim(), ingelezen: lijst.filter(r => r._justImported).length, aantal: lijst.length,
             driehoek: lijst.filter(roundHasWarning).length, teller: openStaandeMeldingen().filter(m => m.filter === 'warn').length,
             kaartDriehoek: (() => { nav('archive'); window._flatListLimit = 1000; loadSaved();
                 return [...document.querySelectorAll('#screen-archive .saved-item')].filter(k => /07:07/.test(k.innerText))
                   .map(k => [...k.querySelectorAll('svg')].filter(s => (s.getAttribute('stroke') || '').includes('--orange') && s.querySelector('path[d^="M10.29"]')).length); })() }; }"""

async def inlezen_en_opslaan(b, B, basis_):
    """De routes zelf, met echte tikken.

    EEN BESTAND MET ÉÉN RONDE is importeren: de ronde komt in 'Geïmporteerd' en telt pas mee
    na 'Sla op' — voor de handicap, en ook voor het driehoekje en 'N zonder dagresultaat'.
    Overschrijft die ene ronde een BESTAANDE ronde (zelfde datum, tijd en speler), dan vraagt
    de app het, en na 'Opslaan' staat de nieuwe er meteen als opgeslagen: geen tussenstop.
    EEN BESTAND MET MEER RONDES is een backup terugzetten (Marks keuze): na 'Toevoegen' zijn
    de rondes meteen opgeslagen en tellen ze direct mee; er komt niets in 'Geïmporteerd'.
    """
    import tempfile
    def bestand(rondes):
        pad = os.path.join(tempfile.mkdtemp(), 'rondes.json'); json.dump(rondes, open(pad, 'w', encoding='utf-8')); return pad
    def ronde(speler, sd, tijd='07:07', n=1):
        x = copy.deepcopy(B[0]); x.pop('id'); x['date'] = dag(n); x['time'] = tijd; x['player'] = speler; x['sd'] = x['sdFinal'] = sd; return x
    async def pagina():
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(testdata.SEED, [testdata.CLUBS, B]); await pg.reload(); await pg.wait_for_timeout(400)
        return pg, pf
    async def lees_in(pg, pad, toevoegen=False):
        await pg.evaluate("() => nav('settings')")
        await pg.locator('#importRoundFile').set_input_files(pad); await pg.wait_for_timeout(500)
        if toevoegen: await pg.get_by_text('Toevoegen', exact=True).first.click(); await pg.wait_for_timeout(500)
        await pg.evaluate("() => document.querySelectorAll('[id$=Modal]:not(.hidden)').forEach(m => m.classList.add('hidden'))")
    async def sla_op(pg):
        await pg.locator('#tab-archive').click(); await pg.wait_for_timeout(300)
        k = pg.locator('#screen-archive [onclick*="archiveImportedRound("]').first
        if not (await k.count() and await k.is_visible()): return False
        await k.click(); await pg.wait_for_timeout(120); await k.click(); await pg.wait_for_timeout(400)
        return True

    # 1. Eén ronde van Mark, met dagresultaat
    pg, pf = await pagina()
    await lees_in(pg, bestand([ronde('Mark', 2.0)]))
    check("inlezen: de ronde staat in 'Geïmporteerd'", await pg.evaluate("() => loadSavedRounds().filter(r => r._justImported).length") == 1)
    u = await pg.evaluate(BEELD)
    check(f"inlezen: WHS-hcp op Start blijft {basis_['start']}", u['start'] == basis_['start'], u['start'])
    check("inlezen: de export van dagresultaten is gelijk", u['export'] == basis_['export'])
    check("inlezen: de spelanalyse is gelijk", u['analyse'] == basis_['analyse'])
    check("inlezen: de knop 'Sla op' staat bij de ronde", await sla_op(pg))
    check("Sla op: de ronde is niet meer 'Geïmporteerd'", await pg.evaluate("() => loadSavedRounds().filter(r => r._justImported).length") == 0)
    u2 = await pg.evaluate(BEELD)
    check("Sla op: nu telt de ronde mee (de WHS-hcp op Start verandert)", u2['start'] != basis_['start'], u2['start'])
    check("Sla op: en hij staat in de export", u2['export'] != basis_['export'])
    check("inlezen en opslaan: geen fouten in de pagina", not pf, str(pf[:3])); await pg.close()

    # 2. Eén ronde van Mark ZONDER dagresultaat: het driehoekje en de teller wachten ook op 'Sla op'
    pg, pf = await pagina()
    s0 = await pg.evaluate(STAND_INLEZEN)
    await lees_in(pg, bestand([ronde('Mark', None)]))
    s1 = await pg.evaluate(STAND_INLEZEN)
    check("zonder dagresultaat ingelezen: staat in 'Geïmporteerd'", s1['ingelezen'] == 1)
    check("zonder dagresultaat ingelezen: de handicap is gelijk", s1['hcp'] == s0['hcp'], f"{s0['hcp']} → {s1['hcp']}")
    check("zonder dagresultaat ingelezen: nog geen driehoekje", s1['driehoek'] == s0['driehoek'] and s1['kaartDriehoek'] == [0], f"{s1['driehoek']}, kaart {s1['kaartDriehoek']}")
    check("zonder dagresultaat ingelezen: de teller 'zonder dagresultaat' telt hem nog niet", s1['teller'] == s0['teller'], str(s1['teller']))
    await sla_op(pg)
    s2 = await pg.evaluate(STAND_INLEZEN)
    check("na Sla op: nu wel het driehoekje, in de functie en op de kaart", s2['driehoek'] == s0['driehoek'] + 1 and s2['kaartDriehoek'] == [1], f"{s2['driehoek']}, kaart {s2['kaartDriehoek']}")
    check("na Sla op: en de teller telt hem", s2['teller'] == s0['teller'] + 1, str(s2['teller']))
    check("na Sla op: en hij telt mee voor de handicap (met de schatting)", s2['hcp'] != s0['hcp'], s2['hcp'])
    check("zonder dagresultaat: geen fouten in de pagina", not pf, str(pf[:3])); await pg.close()

    # 3. Eén ronde van speler 2, met en zonder dagresultaat: nooit iets voor de handicap of de waarschuwing
    for sd in (2.0, None):
        wat = f"ronde van een ander ingelezen ({'met' if sd else 'zonder'} dagresultaat)"
        pg, pf = await pagina()
        s0 = await pg.evaluate(STAND_INLEZEN)
        await lees_in(pg, bestand([ronde('Partner', sd)]))
        s1 = await pg.evaluate(STAND_INLEZEN)
        check(f"{wat}: staat in 'Geïmporteerd'", s1['ingelezen'] == 1)
        check(f"{wat}: handicap, driehoekje en teller gelijk", (s1['hcp'], s1['driehoek'], s1['teller'], s1['kaartDriehoek']) == (s0['hcp'], s0['driehoek'], s0['teller'], [0]), str(s1))
        await sla_op(pg)
        s2 = await pg.evaluate(STAND_INLEZEN)
        check(f"{wat}: ook na Sla op gelijk", (s2['hcp'], s2['driehoek'], s2['teller'], s2['kaartDriehoek']) == (s0['hcp'], s0['driehoek'], s0['teller'], [0]), str(s2))
        check(f"{wat}: geen fouten in de pagina", not pf, str(pf[:3])); await pg.close()

    # 5. Eén ronde die een BESTAANDE ronde overschrijft: na 'Opslaan' in het venster is hij meteen opgeslagen
    pg, pf = await pagina()
    doel = sorted(B, key=lambda r: r['date'])[-1]
    s0 = await pg.evaluate(STAND_INLEZEN)
    telt0 = await pg.evaluate("() => loadSavedRounds().filter(meetelFilter('Mark')).length")
    x = copy.deepcopy(doel); x.pop('id'); x['sd'] = x['sdFinal'] = 2.0
    await pg.evaluate("() => nav('settings')")
    await pg.locator('#importRoundFile').set_input_files(bestand([x])); await pg.wait_for_timeout(500)
    vraag = await pg.evaluate("() => document.getElementById('confirmModal').classList.contains('hidden') ? '' : document.getElementById('confirmModal').innerText.replace(/\\s+/g, ' ')")
    check("overschrijven: de app vraagt het eerst ('Ronde bestaat al')", 'bestaat al' in vraag.lower() and 'overschrijven' in vraag.lower(), vraag[:120])
    tussen = await pg.evaluate("() => loadSavedRounds().filter(meetelFilter('Mark')).length")
    check("overschrijven: zolang je niet kiest verandert er niets", tussen == telt0)
    await pg.locator('#confirmModalBtn').click(); await pg.wait_for_timeout(400)
    await pg.evaluate("() => document.querySelectorAll('[id$=Modal]:not(.hidden)').forEach(m => m.classList.add('hidden'))")
    s1 = await pg.evaluate(STAND_INLEZEN)
    telt1 = await pg.evaluate("() => loadSavedRounds().filter(meetelFilter('Mark')).length")
    nieuw = await pg.evaluate("([d, t]) => loadSavedRounds().filter(r => r.date === d && r.time === t).map(r => [r.sdFinal, !!r._justImported])", [doel['date'], doel['time']])
    check("overschrijven: er staat nog precies één ronde op die datum en tijd, de nieuwe", nieuw == [[2.0, False]], str(nieuw))
    check("overschrijven: het aantal rondes is gelijk gebleven", s1['aantal'] == s0['aantal'], f"{s0['aantal']} → {s1['aantal']}")
    check("overschrijven: er staat niets in 'Geïmporteerd'", s1['ingelezen'] == 0, str(s1['ingelezen']))
    check("overschrijven: er tellen meteen weer evenveel rondes mee", telt1 == telt0, f"{telt0} → {telt1}")
    check("overschrijven: de nieuwe versie telt meteen mee voor de handicap", s1['hcp'] != s0['hcp'], f"{s0['hcp']} → {s1['hcp']}")
    check("overschrijven: geen fouten in de pagina", not pf, str(pf[:3])); await pg.close()

    # 5b. Annuleren in dat venster: alles blijft zoals het was
    pg, pf = await pagina()
    voor = await pg.evaluate("() => JSON.stringify(loadSavedRounds())")
    await pg.evaluate("() => nav('settings')")
    await pg.locator('#importRoundFile').set_input_files(bestand([x])); await pg.wait_for_timeout(500)
    await pg.locator('#confirmModal').get_by_text('Annuleren', exact=True).click(); await pg.wait_for_timeout(300)
    check("overschrijven, Annuleren: geen enkele ronde is veranderd", await pg.evaluate("() => JSON.stringify(loadSavedRounds())") == voor)
    check("overschrijven, Annuleren: geen fouten in de pagina", not pf, str(pf[:3])); await pg.close()

    # 4. Een bestand met MEER rondes: dat is een backup terugzetten, geen importeren
    pg, pf = await pagina()
    s0 = await pg.evaluate(STAND_INLEZEN)
    await lees_in(pg, bestand([ronde('Mark', 2.0, '07:07', 1), ronde('Mark', 3.0, '08:08', 2), ronde('Partner', 2.0, '09:09', 3)]), toevoegen=True)
    s1 = await pg.evaluate(STAND_INLEZEN)
    check("meer rondes in één bestand, 'Toevoegen': alle drie staan erbij", s1['aantal'] == s0['aantal'] + 3, f"{s0['aantal']} → {s1['aantal']}")
    check("meer rondes: er komt niets in 'Geïmporteerd'", s1['ingelezen'] == 0, str(s1['ingelezen']))
    check("meer rondes: de rondes van Mark tellen meteen mee", s1['hcp'] != s0['hcp'], s1['hcp'])
    check("meer rondes: geen fouten in de pagina", not pf, str(pf[:3])); await pg.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        if KAPOT: print("LET OP: opzettelijk kapotte app — deze doorloop HOORT te falen.")
        B = basis()
        oud = B[0]                                   # de oude ronde die opnieuw geladen wordt: de nieuwste, en een van de beste acht
        async def laad_oud(pg):
            await pg.evaluate("(id) => { const s = loadSavedRounds(); loadRoundSingle(s.findIndex(r => r.id === id)); }", oud['id'])
            await pg.wait_for_timeout(300)

        werk = [
            ('basis',                               B, None),
            ('niet-qualifying erbij',               B + niet_qualifying(), None),
            ('half gespeeld erbij',                 B + half(), None),
            ('gepland erbij',                       B + gepland(), None),
            ('rondes van een ander erbij',          B + ander(), None),
            ('ingelezen, nog niet opgeslagen',      B + ingelezen(), None),
            ('nieuwe volle ronde, nog open',        B, open_nieuw),
            ('twee spelers vol, nog open',          B + ander(), open_twee),
            ('alles tegelijk',                      B + niet_qualifying() + half() + gepland() + ander() + ingelezen(), open_twee),
            ('zonder de oude ronde',                [r for r in B if r['id'] != oud['id']], None),
            ('oude ronde opnieuw geladen',          B, laad_oud),
        ]
        uit = dict(await asyncio.gather(*[meet(b, *w) for w in werk]))
        await inlezen_en_opslaan(b, B, uit['basis'])
        # Het driehoekje komt bij het opslaan: een nieuwe volle ronde heeft geen vastgesteld dagresultaat.
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        await pg.goto(app_url()); await pg.evaluate(testdata.SEED, [testdata.CLUBS, B]); await pg.reload(); await pg.wait_for_timeout(400)
        D = "() => { nav('archive'); loadSaved(); const k = [...document.querySelectorAll('#screen-archive .saved-item')][0]; return [loadSavedRounds().filter(roundHasWarning).length, openStaandeMeldingen().filter(m => m.filter === 'warn').length, k ? [...k.querySelectorAll('svg')].filter(s => (s.getAttribute('stroke') || '').includes('--orange') && s.querySelector('path[d^=\"M10.29\"]')).length : null]; }"
        d0 = await pg.evaluate(D)
        await open_nieuw(pg)
        d1 = await pg.evaluate(D)
        check("volle ronde, nog open: geen driehoekje, niet in de teller en niet op de kaart", d1[:2] == d0[:2] and d1[2] == 0, f"{d0} → {d1}")
        await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(250)
        k = pg.locator('button[onclick^="saveAndClearActiveRound"]').first
        await k.click(); await pg.wait_for_timeout(100); await k.click(); await pg.wait_for_timeout(400)
        d2 = await pg.evaluate(D)
        check("na opslaan: het driehoekje staat er, in de teller en op de kaart", d2 == [d0[0] + 1, d0[1] + 1, 1], f"{d0} → {d2}")
        await pg.close()
        await b.close()

        basis_ = uit['basis']
        check("basis: er is een handicap", re.fullmatch(GETAL, basis_['start']) is not None, basis_['start'])
        check("basis: alle 30 rondekaarten tonen een berekende handicap",
              len(basis_['kaarten']) == 30 and all(v != '(geen)' for v in basis_['kaarten'].values()),
              f"{len(basis_['kaarten'])} kaarten, {sum(1 for v in basis_['kaarten'].values() if v == '(geen)')} zonder")
        check("basis: de export bevat dagresultaten", bool(basis_['export']) and basis_['export'].count(':') >= 30)
        check("basis: de spelanalyse is opgebouwd", bool(basis_['analyse']) and not basis_['analyse'].startswith('FOUT'), str(basis_['analyse'])[:80])

        for naam in ('niet-qualifying erbij', 'half gespeeld erbij', 'gepland erbij', 'rondes van een ander erbij', 'ingelezen, nog niet opgeslagen',
                     'nieuwe volle ronde, nog open', 'twee spelers vol, nog open', 'alles tegelijk'):
            vergelijk(naam, basis_, uit[naam])

        # Een oude ronde opnieuw geladen: zolang hij open staat hetzelfde als zonder die ronde.
        zonder, geladen = uit['zonder de oude ronde'], uit['oude ronde opnieuw geladen']
        kop_oud = next((k for k in basis_['kaarten'] if k not in zonder['kaarten']), None)
        check("oude ronde opnieuw geladen: WHS-hcp op Start is als zonder die ronde", geladen['start'] == zonder['start'],
              f"{geladen['start']} tegen {zonder['start']}")
        check("oude ronde opnieuw geladen: de export is als zonder die ronde", geladen['export'] == zonder['export'])
        anders = {k: (v, geladen['kaarten'].get(k)) for k, v in zonder['kaarten'].items() if geladen['kaarten'].get(k) != v}
        check("oude ronde opnieuw geladen: de handicap op de andere kaarten is als zonder die ronde", not anders, str(list(anders.items())[:2]))
        check("oude ronde opnieuw geladen: geen Verwachte/Nieuwe WHS-hcp bij de open ronde",
              not re.search(r'WHS-hcp', geladen.get('ronde_info', ''), re.I))
        if not KAPOT:
            check("zonder de oude ronde: dat verandert de handicap of een kaart echt (de test meet iets)",
                  zonder['start'] != basis_['start'] or any(zonder['kaarten'].get(k) != v for k, v in basis_['kaarten'].items() if k != kop_oud))

        # Elke berekening onderweg, in elke stand
        for naam, u in uit.items():
            check(f"{naam}: er is onderweg gerekend", u['n'] > 0, str(u['n']))
            check(f"{naam}: in geen enkele berekening zit een ronde die niet mag meetellen", not u['in'], ', '.join(u['in'][:6]))
            check(f"{naam}: geen fouten in de pagina", not u['pf'], str(u['pf']))
            geteld[0] += u['n']

        # De uitzondering: de baananalyse in het clubscherm neemt niet-qualifying rondes WEL mee.
        check("uitzondering: de baananalyse is opgebouwd", bool(basis_['baan']) and basis_['baan'] != 'null', str(basis_['baan'])[:60])
        check("uitzondering: de baananalyse in het clubscherm verandert door niet-qualifying rondes",
              uit['niet-qualifying erbij']['baan'] != basis_['baan'])
        for naam in ('half gespeeld erbij', 'gepland erbij', 'rondes van een ander erbij', 'ingelezen, nog niet opgeslagen', 'nieuwe volle ronde, nog open', 'twee spelers vol, nog open'):
            check(f"uitzondering: de baananalyse verandert niet door '{naam}'", uit[naam]['baan'] == basis_['baan'])
        check("uitzondering: een opnieuw geladen oude ronde telt ook daar tijdelijk niet mee", geladen['baan'] == zonder['baan'])

        print(f"  WHS-hcp op Start: basis {basis_['start']}, zonder de oude ronde {zonder['start']}, oude ronde geladen {geladen['start']}")
        print(f"\n{geteld[0]} controles.")
        print(f"{len(fouten)} FOUT(EN)" if fouten else "GEEN FOUTEN")
        sys.exit(1 if fouten else 0)

asyncio.run(main())
