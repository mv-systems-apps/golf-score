"""Backupmelding tegen de WERKELIJKE backupinhoud, in alle situaties.

Voor elke situatie: eerst een echte backup (het bestand wordt onderschept), dan de
handeling, en dan twee dingen vergelijken:
  * wat de app meldt (geen melding, of oranje met een stip op het tandwiel);
  * wat een backup op dat moment zou bevatten, vergeleken met de laatste backup —
    op INHOUD, dus ongeacht de volgorde van rondes en velden.

Afspraken (keuzes van de gebruiker):
  * in de backup hoort elke ronde waarvan alle holes zijn ingevuld, ook als hij open
    staat, voor speler 1 en 2 gelijk;
  * niet: rondes in de categorie 'Geïmporteerd' (tot 'Sla op'), gepauzeerde, geplande;
  * de melding gaat alleen aan als die inhoud afwijkt van de laatste backup;
  * toegevoegde (geïmporteerde) afgeronde rondes tellen als nieuwe rondes;
  * vaste regel, sinds de drempels zijn vervallen: iets niet in de backup = oranje + stip.
"""
import asyncio, sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright
APP = os.environ.get('APP') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'golf-score.html')

PREP = """async (drempels) => {
  localStorage.setItem('golf_profile_name','Testspeler'); localStorage.setItem('golf_kenmerk_gevraagd','1');
  localStorage.setItem('golf_default_club','Golfclub Heelsum');
  localStorage.setItem('golf_backup_reminder_days', String(drempels[0]));
  localStorage.setItem('golf_backup_reminder_rounds', String(drempels[1]));
  window.tryWriteToExportFolder = async (f, c) => { if (f.startsWith('rondes')) window._cap = c; return true; };
  await exportAllClubs(); await exportAllRounds();
  window._backupInhoud = window._cap;
}"""
# wat zou een backup NU bevatten, zonder de backupstand te veranderen
NU = """async () => {
  const vasteVolgordeTest = v => Array.isArray(v) ? '[' + v.map(vasteVolgordeTest).join(',') + ']' : (v && typeof v === 'object') ? '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + vasteVolgordeTest(v[k])).join(',') + '}' : JSON.stringify(v);
  const keys = ['golf_last_backup_date','golf_last_backup_ts','golf_last_backup_count','golf_backup_inhoud','golf_backup_onzeker'];
  const bewaar = Object.fromEntries(keys.map(k => [k, localStorage.getItem(k)]));
  window._cap = null; await exportAllRounds(); const nu = window._cap;
  keys.forEach(k => bewaar[k] == null ? localStorage.removeItem(k) : localStorage.setItem(k, bewaar[k]));
  nav('settings'); updateLastBackupDisplay();
  const r = document.getElementById('newRoundsInfoTop');
  const lijst = loadSavedRounds(); const act = localStorage.getItem('golf_active_id');
  const oud = JSON.parse(window._backupInhoud || '[]'), nieuw = JSON.parse(nu || '[]');
  // afgeronde rondes die NIET in de laatste backup staan, gemeten los van 'actief'
  const sleutel = x => [x.date, x.time, x.player].join('|');
  const inBackup = new Set(oud.map(sleutel));
  const afMaarNietInBackup = lijst.filter(x => isRondeAf(x) && !inBackup.has(sleutel(x))).length;
  return {
    regel: r.classList.contains('hidden') ? 'geen' : (r.innerHTML.includes('--orange') ? 'ORANJE' : 'grijs'),
    stip: document.getElementById('tab-settings').classList.contains('has-dot'),
    backupZouAndersZijn: JSON.stringify(nieuw.map(vasteVolgordeTest).sort()) !== JSON.stringify(oud.map(vasteVolgordeTest).sort()),
    rondesInBackupNu: nieuw.length, rondesInLaatsteBackup: oud.length,
    afMaarNietInBackup, actiefIsAf: !!(act && isRondeAf(lijst.find(x => String(x.id) === act))),
  };
}"""

fouten = []
async def scenario(b, naam, actie, drempels=(1,1), verwacht=None, extra=None):
    page = await b.new_page(viewport={'width':390,'height':844})
    err = []; page.on('pageerror', lambda e: err.append(str(e)[:120]))
    await page.goto(app_url(APP)); await page.evaluate(SEED, [CLUBS, RONDES])
    await page.reload(); await page.wait_for_timeout(400)
    await page.evaluate(PREP, list(drempels))
    try:
        if callable(actie): await actie(page)
        else: await page.evaluate(actie)
        await page.wait_for_timeout(250)
        r = await page.evaluate(NU)
    except Exception as e:
        r = {'FOUT': str(e)[:200]}
    ok = 'FOUT' not in r and not err
    if ok and verwacht is not None:
        ok = (r['regel'], r['stip']) == verwacht
    # Vaste regel: geen melding  <=>  de backup zou gelijk zijn aan de laatste
    # (behalve 'nooit geback-upt', waar er geen laatste backup is).
    # Uitzondering sinds 10B: zolang een ronde OPEN staat wacht de melding, terwijl het
    # backupbestand hem wel al meeneemt. Die scenario's heten 'nog open' en geven zelf op
    # of het bestand anders zou zijn (extra={'backupZouAndersZijn': ...}).
    if ok and 'nooit' not in naam and 'nog open' not in naam:
        ok = (r['regel'] != 'geen') == r['backupZouAndersZijn']
    if ok and extra:
        for k, v in extra.items(): ok = ok and r.get(k) == v
    print(f"  {'ok  ' if ok else 'FOUT'} {naam:<52} {r.get('regel')}/{'stip' if r.get('stip') else '-'}"
          + ('' if ok else f"  {json.dumps(r, ensure_ascii=False)} verwacht {verwacht} {extra or ''}")
          + (f"  PAGINAFOUT {err}" if err else ''))
    if not ok: fouten.append(naam)
    await page.close()
    return r

START = """(twee) => { nav('setup'); sel.track='Airborne'; sel.gender='Heren'; sel.tee='Blauw'; sel.qualifying=true;
  document.getElementById('iName').value='Testspeler'; document.getElementById('iHcp').value='30.7';
  if (twee) togglePlayer2(true); }"""
START2 = """(twee) => { if (twee) { document.getElementById('iName2').value='Partner'; document.getElementById('iHcp2').value='18.0';
  sel2.track='Airborne'; sel2.gender='Heren'; sel2.tee='Blauw'; sel2.qualifying=true; }
  startRound(); const cb=document.getElementById('confirmModalBtn');
  if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }"""
async def start(page, twee=False):
    await page.evaluate(START, twee); await page.wait_for_timeout(250)
    await page.evaluate(START2, twee); await page.wait_for_timeout(300)
    await page.evaluate("() => { nav('score'); renderScore(); }"); await page.wait_for_timeout(150)
async def vul(page, n, speler=None):
    if speler: await page.evaluate("(n) => switchToPlayer(n)", speler); await page.wait_for_timeout(150)
    for h in range(n):
        await page.evaluate("(h) => { setCurrentHole(h); selectHole(h); toggleScoreButtons(h); armScoreChange(h,5); clearScoreTap(false); }", h)
        await page.wait_for_timeout(50)
async def knop(page, sel='saveAndClearActiveRound'):
    await page.evaluate("() => nav('archive')"); await page.wait_for_timeout(250)
    k = page.locator(f'button[onclick^="{sel}"]').first
    await k.click(); await page.wait_for_timeout(80); await k.click(); await page.wait_for_timeout(250)
# een afgeronde ronde laden (Laad-knop), zoals in het archief
LAAD_AF = """() => { const s = loadSavedRounds(); const i = s.findIndex(r => isRondeAf(r) && r.player==='Testspeler'); loadRoundSingle(i); return i; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        S = scenario
        print("--- rondes spelen")
        await S(b, "A1 niets doen na backup", "() => 0", verwacht=('geen', False))
        async def a2(pg): await start(pg)
        await S(b, "A2 ronde starten", a2, verwacht=('geen', False))
        async def a3(pg): await start(pg); await vul(pg, 3)
        await S(b, "A3 3 holes invullen (actief)", a3, verwacht=('geen', False))
        async def a4(pg): await start(pg); await vul(pg, 9)
        await S(b, "A4 alle holes ingevuld, nog open", a4, verwacht=('geen', False), extra={'backupZouAndersZijn': True, 'afMaarNietInBackup': 1})
        async def a5(pg): await start(pg); await vul(pg, 3); await knop(pg)
        await S(b, "A5 pauzeren", a5, verwacht=('geen', False))
        async def a6(pg): await start(pg); await vul(pg, 9); await knop(pg)
        await S(b, "A6 afronden (Gereed)", a6, verwacht=('ORANJE', True))
        async def a6b(pg): await start(pg); await vul(pg, 9); await pg.evaluate("() => finishActiveRound(null)")
        await S(b, "A6b afronden (finishActiveRound)", a6b, verwacht=('ORANJE', True))
        async def a7(pg):
            await start(pg); await vul(pg, 3); await knop(pg)
            await pg.evaluate("() => { const s=loadSavedRounds(); const i=s.findIndex(r=>!isRondeAf(r) && gespeeldeHoles(r)>0); loadRoundSingle(i); }")
            await pg.wait_for_timeout(200); await pg.evaluate("() => { nav('score'); renderScore(); }")
            await pg.evaluate("() => { setCurrentHole(3); selectHole(3); toggleScoreButtons(3); armScoreChange(3,5); clearScoreTap(false); }")
            await knop(pg)
        await S(b, "A7 gepauzeerde hervatten, hole erbij, pauzeren", a7, verwacht=('geen', False))
        print("--- twee spelers")
        async def b1(pg): await start(pg, True); await vul(pg, 9); await vul(pg, 9, 2)
        await S(b, "B1 beide spelers alles ingevuld, nog open", b1, verwacht=('geen', False), extra={'backupZouAndersZijn': True, 'afMaarNietInBackup': 2})
        async def b2(pg): await start(pg, True); await vul(pg, 9); await vul(pg, 3, 2); await pg.evaluate("() => switchToPlayer(1)"); await knop(pg)
        await S(b, "B2 P1 af, P2 half, sluiten", b2, verwacht=('ORANJE', True))
        async def b3(pg): await start(pg, True); await vul(pg, 3); await vul(pg, 9, 2)
        await S(b, "B3 P1 half, P2 alles ingevuld, nog open", b3, verwacht=('geen', False), extra={'backupZouAndersZijn': True, 'afMaarNietInBackup': 1})
        async def b4(pg): await start(pg, True); await vul(pg, 9); await vul(pg, 9, 2); await pg.evaluate("() => switchToPlayer(1)"); await knop(pg)
        await S(b, "B4 beide spelers alles ingevuld, sluiten", b4, verwacht=('ORANJE', True))
        print("--- afgeronde ronde openen")
        async def c1(pg): await pg.evaluate(LAAD_AF)
        await S(b, "C1 afgeronde ronde laden (Laad), niets wijzigen", c1, verwacht=('geen', False))
        async def c2(pg): await pg.evaluate(LAAD_AF); await pg.wait_for_timeout(200); await knop(pg)
        await S(b, "C2 laden en weer sluiten (Gereed), niets gewijzigd", c2, verwacht=('geen', False))
        async def c3(pg):
            await pg.evaluate(LAAD_AF); await pg.wait_for_timeout(200)
            await pg.evaluate("() => { nav('score'); renderScore(); setCurrentHole(0); selectHole(0); toggleScoreButtons(0); armScoreChange(0, (game.holes[0].score||4)+1); clearScoreTap(false); }")
            await knop(pg)
        await S(b, "C3 laden, score wijzigen, sluiten", c3, verwacht=('ORANJE', True))
        async def c3b(pg):
            await pg.evaluate(LAAD_AF); await pg.wait_for_timeout(200)
            await pg.evaluate("() => { nav('score'); renderScore(); setCurrentHole(0); selectHole(0); toggleScoreButtons(0); armScoreChange(0, (game.holes[0].score||4)+1); clearScoreTap(false); }")
        await S(b, "C3b laden, score wijzigen, nog open", c3b, verwacht=('geen', False), extra={'backupZouAndersZijn': True})
        async def c3c(pg):
            await pg.evaluate(LAAD_AF); await pg.wait_for_timeout(200)
            await pg.evaluate("() => { nav('score'); renderScore(); setCurrentHole(0); selectHole(0); toggleScoreButtons(0); armScoreChange(0, null); clearScoreTap(false); }")
        await S(b, "C3c laden, een score wissen (ronde niet meer vol), nog open", c3c, verwacht=('geen', False))
        async def c5(pg):
            await start(pg); await vul(pg, 9)
            await pg.evaluate(PREP, [1,1])   # backup terwijl de volle NIEUWE ronde open staat
            await knop(pg)
        await S(b, "C5 backup maken terwijl volle nieuwe ronde open staat, dan sluiten", c5, verwacht=('geen', False), extra={'afMaarNietInBackup': 0, 'rondesInLaatsteBackup': 74})
        async def c4(pg):
            await pg.evaluate(LAAD_AF); await pg.wait_for_timeout(200)
            await pg.evaluate(PREP, [1,1])   # nieuwe backup terwijl hij open staat
            await knop(pg)
        await S(b, "C4 backup maken terwijl afgeronde ronde open staat", c4, verwacht=('geen', False), extra={'afMaarNietInBackup': 0, 'rondesInLaatsteBackup': 73})
        print("--- bewerken in archief")
        await S(b, "D1 dagresultaat vaststellen (andere SD)", "() => { const s=loadSavedRounds(); const i=s.findIndex(r=>isRondeAf(r)); doOpenRoundResultModal(i); document.getElementById('editSdInput').value='12.3'; confirmRoundResult(); }", verwacht=('ORANJE', True))
        await S(b, "D2 vaststellen zonder iets te wijzigen", "() => { const s=loadSavedRounds(); const i=s.findIndex(r=>isRondeAf(r)); doOpenRoundResultModal(i); confirmRoundResult(); }", verwacht=('geen', False))
        await S(b, "D3 afgeronde ronde verwijderen", "() => { const s=loadSavedRounds(); const i=s.findIndex(r=>isRondeAf(r)); performDeleteRound(i); }", verwacht=('ORANJE', True))
        await S(b, "D4 ronde plannen (toekomst, geen scores)", """() => { const s=loadSavedRounds(); const b=s.find(r=>isRondeAf(r)); const d=new Date(); d.setDate(d.getDate()+5);
            s.unshift({...b, id: 777001, date: new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10), holes: b.holes.map(h=>({...h, score:null}))}); setRoundsAndMark(JSON.stringify(s)); }""", verwacht=('geen', False))
        await S(b, "D5 geplande ronde verwijderen", """() => { const s=loadSavedRounds(); const b=s.find(r=>isRondeAf(r)); const d=new Date(); d.setDate(d.getDate()+5);
            s.unshift({...b, id: 777001, date: new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10), holes: b.holes.map(h=>({...h, score:null}))}); setRoundsAndMark(JSON.stringify(s));
            localStorage.setItem('golf_last_backup_ts', new Date().toISOString());  /* planning valt buiten */
            const i = loadSavedRounds().findIndex(r=>r.id===777001); performDeleteRound(i); }""", verwacht=('geen', False))
        print("--- importeren / herstellen")
        await S(b, "E1 losse ronde importeren (Geïmporteerd)", """() => { const s=loadSavedRounds(); const b=JSON.parse(JSON.stringify(s.find(r=>isRondeAf(r)))); b.date='2019-05-05'; b.time='10:00'; doImportRound(b, s); }""", verwacht=('geen', False))
        await S(b, "E2 idem en daarna 'Sla op'", """() => { const s=loadSavedRounds(); const b=JSON.parse(JSON.stringify(s.find(r=>isRondeAf(r)))); b.date='2019-05-05'; b.time='10:00'; doImportRound(b, s);
            const t=loadSavedRounds(); const i=t.findIndex(r=>r._justImported); const btn=document.createElement('button'); btn.dataset.confirm='1'; document.body.appendChild(btn); archiveImportedRound(i, btn); }""", verwacht=('ORANJE', True))
        await S(b, "E3 toevoegen-import (bulk) van 2 nieuwe rondes", """() => { const s=loadSavedRounds(); const b=s.filter(r=>isRondeAf(r)).slice(0,2).map(r=>({...JSON.parse(JSON.stringify(r)), date:'2019-06-0'+(1+s.indexOf(r)%8), time:'11:0'+(s.indexOf(r)%9)}));
            doAdditiveImport(b); }""", verwacht=('ORANJE', True))
        await S(b, "E4 volledig herstellen uit de laatste backup", "() => doFullRestoreImport(JSON.parse(window._backupInhoud))", verwacht=('geen', False))
        print("--- instellingen / drempels")
        async def f1(pg): await start(pg); await vul(pg, 9); await knop(pg)
        await S(b, "F1 afronden, met oude drempelwaarden 7/3 in de opslag", f1, drempels=(7,3), verwacht=('ORANJE', True))
        await S(b, "F2 bewerking, met oude drempelwaarden 7/3", "() => { const s=loadSavedRounds(); const i=s.findIndex(r=>isRondeAf(r)); doOpenRoundResultModal(i); document.getElementById('editSdInput').value='12.3'; confirmRoundResult(); }", drempels=(7,3), verwacht=('ORANJE', True))
        await S(b, "F3 bewerking, backup 8 dagen oud, drempels 7/3", """() => { const d=new Date(); d.setDate(d.getDate()-8); localStorage.setItem('golf_last_backup_date', new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)); localStorage.setItem('golf_last_backup_ts', d.toISOString());
            const s=loadSavedRounds(); const i=s.findIndex(r=>isRondeAf(r)); doOpenRoundResultModal(i); document.getElementById('editSdInput').value='12.3'; confirmRoundResult(); }""", drempels=(7,3), verwacht=('ORANJE', True))
        await S(b, "F4 nooit geback-upt (1/1)", "() => { ['golf_last_backup_date','golf_last_backup_ts','golf_last_backup_count'].forEach(k=>localStorage.removeItem(k)); }", verwacht=('ORANJE', True))
        async def f6(pg):
            await pg.evaluate("() => { metVerwijderen(() => setRoundsAndMark('[]')); ['golf_last_backup_date','golf_last_backup_ts','golf_last_backup_count','golf_backup_inhoud'].forEach(k=>localStorage.removeItem(k)); }")
            await start(pg); await vul(pg, 9)
        await S(b, "F6 nooit geback-upt, enige volle ronde staat nog open", f6, verwacht=('geen', False))
        async def f7(pg): await f6(pg); await knop(pg)
        await S(b, "F7 nooit geback-upt, die ronde gesloten", f7, verwacht=('ORANJE', True))
        await S(b, "F5 nooit geback-upt, drempel rondes 50", "() => { ['golf_last_backup_date','golf_last_backup_ts','golf_last_backup_count'].forEach(k=>localStorage.removeItem(k)); }", drempels=(1,50), verwacht=('ORANJE', True))
        await S(b, "F6 klok achteruit: wijziging 'vóór' backup-tijd", """() => { localStorage.setItem('golf_last_backup_ts', new Date(Date.now()+3600e3).toISOString());
            const s=loadSavedRounds(); const i=s.findIndex(r=>isRondeAf(r)); doOpenRoundResultModal(i); document.getElementById('editSdInput').value='12.3'; confirmRoundResult(); }""", verwacht=('ORANJE', True))
        print("--- namen / clubs / opruimen")
        await S(b, "G1 ronde-limiet: oudste valt weg", """() => { localStorage.setItem('golf_round_limit', String(loadSavedRounds().length)); const s=loadSavedRounds(); const b=s.find(r=>isRondeAf(r));
            const d = new Date(); d.setDate(d.getDate()+9); s.unshift({...b, id: 777002, date: new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10), holes: b.holes.map(h=>({...h, score:null}))}); setRoundsAndMark(JSON.stringify(trimRondes(s))); }""", verwacht=('geen', False))
        print("--- nieuw sinds de controle")
        await S(b, "E3b toevoegen-import telt als 2 nieuwe rondes (drempel 30/2)", """() => { const s=loadSavedRounds(); const b=s.filter(r=>isRondeAf(r)).slice(0,2).map((r,k)=>({...JSON.parse(JSON.stringify(r)), date:'2019-06-0'+(k+1), time:'11:0'+k}));
            doAdditiveImport(b); }""", drempels=(30,2), verwacht=('ORANJE', True))
        await S(b, "H1 wijziging en weer terugdraaien", """() => { const s=loadSavedRounds(); const i=s.findIndex(r=>isRondeAf(r)); const oud=s[i].sdFinal;
            doOpenRoundResultModal(i); document.getElementById('editSdInput').value='12.3'; confirmRoundResult();
            doOpenRoundResultModal(i); document.getElementById('editSdInput').value = oud == null ? '' : String(oud); confirmRoundResult(); }""", verwacht=('geen', False))
        await S(b, "H2 twee bewerkte rondes tellen als twee (drempel 30/2)", """() => { const s=loadSavedRounds(); const af=s.filter(r=>isRondeAf(r)).slice(0,2);
            af.forEach((r,k) => r.note = 'bewerkt ' + k); setRoundsAndMark(JSON.stringify(s)); }""", drempels=(30,2), verwacht=('ORANJE', True))
        await S(b, "H2b één bewerkte ronde: oranje (geen drempels meer)", """() => { const s=loadSavedRounds(); const af=s.find(r=>isRondeAf(r));
            af.note = 'bewerkt'; setRoundsAndMark(JSON.stringify(s)); }""", drempels=(30,2), verwacht=('ORANJE', True))
        await b.close()
    print()
    print('GEEN FOUTEN' if not fouten else f'{len(fouten)} FOUT(EN)')
asyncio.run(main())
