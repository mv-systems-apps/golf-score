"""Opnieuw plannen of corrigeren blijft staan als je het startscherm verlaat.

Aanleiding (melding van de gebruiker: notitie bij de maanwedstrijd kwijt). Je tikte op 'Opnieuw
plannen', ging naar Instellingen om het clubbestand met de nieuwe baan in te lezen, en
de app brak het opnieuw plannen stil af: melding en notitie weg, de rest bleef ingevuld.
Starten gaf 'Dubbele datum & tijd'; wie daarna de oude ronde verwijderde was zijn
notitie kwijt.

Nu blijft het staan tot je het zelf annuleert of de ronde start. Het vervalt alleen als
de oude ronde er niet meer is of intussen is veranderd. Bij corrigeren gaan de scores
mee zoals ze op het moment van STARTEN zijn.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt}" + ('' if ok else f" — verwacht {verwacht}"))
    if not ok: fouten.append(naam)

N = "(naam) => { const r = leesRondes().filter(r => r.player === 'Proef'); return r.map(x => [x.track, x.date, x.note ?? null, x.holes.filter(h=>h.score!=null).length]); }"

async def schoon(pg):
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES])
    await pg.reload(); await pg.wait_for_timeout(400)

async def start(pg, note, dagen=0, track='Airborne'):
    await pg.evaluate("""([note, dagen, track]) => { nav('setup'); sel.track = track; sel.gender = 'Heren'; sel.tee = 'Blauw';
       document.getElementById('iName').value = 'Proef'; document.getElementById('iHcp').value = '30.8';
       if (dagen) { const d = new Date(); d.setDate(d.getDate()+dagen); const iso = d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
          document.getElementById('iDate').value = iso; document.getElementById('iTime').value = '10:00'; sel.date = iso; sel.time = '10:00'; sel.dateTimeEdited = true; }
       zetStartNote(1, note || ''); }""", [note, dagen, track])
    await klik_start(pg)

async def klik_start(pg):
    await pg.evaluate("""() => { startRound(); const cb = document.getElementById('confirmModalBtn');
       if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
    await pg.wait_for_timeout(300)

async def vul(pg, n=99):
    await pg.evaluate("(n) => { for (let i = 0; i < Math.min(n, game.holes.length); i++) { setCurrentHole(i); stepScore(i, +1); } }", n)

IDX = "leesRondes().findIndex(r => r.player === 'Proef')"
async def info(pg, tekst=None):
    await pg.evaluate("(t) => { doOpenRoundInfoModal(%s); if (t !== null) document.getElementById('editNoteInput').value = t; confirmRoundInfo(); }" % IDX, tekst)
    await pg.wait_for_timeout(150)
async def res(pg, tekst=None):
    await pg.evaluate("(t) => { doOpenRoundResultModal(%s); if (t !== null) document.getElementById('resultNoteInput').value = t; confirmRoundResult(); }" % IDX, tekst)
    await pg.wait_for_timeout(150)
async def herlaad(pg):
    await pg.reload(); await pg.wait_for_timeout(400)
async def kies_baan(pg, naam):
    await pg.evaluate("(n) => { [...document.querySelectorAll('#trackList button')].find(b => b.textContent.includes(n)).click(); }", naam)
    await pg.wait_for_timeout(150)
async def toon(pg, wat):
    print(f"  {wat:58}", await pg.evaluate(N, 'x'))


KEUZE = "() => document.getElementById('keuzeModal').classList.contains('hidden') ? [] : [...document.querySelectorAll('#keuzeModal button')].filter(b => !b.classList.contains('hidden')).map(b => b.textContent.trim())"
ST = "() => ({ banner: !document.getElementById('herplanBanner').classList.contains('hidden'), notitie: document.getElementById('startNote1').value })"
MODAL = "() => [...document.querySelectorAll('[id$=Modal]:not(.hidden)')].length"
# Zelfde stappen als het inlezen van een clubbestand: club vervangen, opzoeklijsten en
# startscherm opnieuw opbouwen, opslaan.
NIEUWE_BAAN = """() => { const c = JSON.parse(JSON.stringify(CLUBS['Golfclub Heelsum']));
  c.courses['Maanwedstrijd'] = JSON.parse(JSON.stringify(c.courses['Sandr']));
  CLUBS['Golfclub Heelsum'] = c; rebuildCourseLookup(); rebuildAll(); saveClubsToStorage(); }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:120]))

        print("\n=== 1. DE SITUATIE VAN DE GEBRUIKER: OPNIEUW PLANNEN, CLUBBESTAND INLEZEN, STARTEN ===\n")
        await schoon(pg); await start(pg, 'Maanwedstrijd met de club', dagen=3)
        await pg.evaluate("() => finishActiveRound(null)")
        await pg.evaluate("() => herplanRonde(leesRondes()[%s].id)" % IDX); await pg.wait_for_timeout(300)
        check("startscherm gevuld", await pg.evaluate(ST), {'banner': True, 'notitie': 'Maanwedstrijd met de club'})
        for scherm in ['settings', 'club', 'archive', 'stat']:
            await pg.evaluate("(s) => nav(s)", scherm); await pg.wait_for_timeout(100)
        await pg.evaluate("() => nav('settings')"); await pg.evaluate(NIEUWE_BAAN)
        await pg.evaluate("() => nav('setup')"); await pg.wait_for_timeout(200)
        check("na het uitstapje: melding en notitie staan er nog", await pg.evaluate(ST), {'banner': True, 'notitie': 'Maanwedstrijd met de club'})
        await kies_baan(pg, 'Maanwedstrijd'); await klik_start(pg)
        # Je bent weggeweest: Start vraagt eerst of de oude ronde vervangen moet worden.
        check("starten vraagt om bevestiging", await pg.evaluate(KEUZE), ['Annuleren', 'Vervangen', 'Oude ronde laten staan'])
        await pg.locator('#keuzeModal button', has_text='Annuleren').click(); await pg.wait_for_timeout(200)
        check("Annuleren: niets gebeurd, alles staat er nog", (await pg.evaluate(ST), [(x[0], x[2]) for x in await pg.evaluate(N, 'x')]),
              ({'banner': True, 'notitie': 'Maanwedstrijd met de club'}, [('Airborne', 'Maanwedstrijd met de club')]))
        await klik_start(pg); await pg.locator('#keuzeModal button', has_text='Vervangen').click(); await pg.wait_for_timeout(350)
        check("na Vervangen: geen verdere melding", await pg.evaluate(MODAL), 0)
        r = await pg.evaluate(N, 'x')
        check("één ronde, op de nieuwe baan, met de notitie", [(x[0], x[2]) for x in r], [('Maanwedstrijd', 'Maanwedstrijd met de club')])
        check("daarna is het startscherm weer leeg", await pg.evaluate(ST), {'banner': False, 'notitie': ''})

        print("\n=== 2. ZELF ANNULEREN MET HET KRUISJE ===\n")
        await schoon(pg); await start(pg, 'N2', dagen=3); await pg.evaluate("() => finishActiveRound(null)")
        await pg.evaluate("() => herplanRonde(leesRondes()[%s].id)" % IDX); await pg.wait_for_timeout(300)
        await pg.locator('#herplanBanner button').click()
        check("melding en notitieveld weg", await pg.evaluate(ST), {'banner': False, 'notitie': ''})
        check("de oude ronde staat er nog, met notitie", [(x[0], x[2]) for x in await pg.evaluate(N, 'x')], [('Airborne', 'N2')])

        print("\n=== 3. DE OUDE RONDE IS INTUSSEN VERWIJDERD: VERVALT ===\n")
        await schoon(pg); await start(pg, 'N3', dagen=3); await pg.evaluate("() => finishActiveRound(null)")
        await pg.evaluate("() => herplanRonde(leesRondes()[%s].id)" % IDX); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { nav('archive'); metVerwijderen(() => setRoundsAndMark(JSON.stringify(loadSavedRounds().filter(r => r.player !== 'Proef')))); nav('setup'); }")
        check("melding weg", (await pg.evaluate(ST))['banner'], False)

        print("\n=== 4. IN DE OUDE RONDE IS INTUSSEN GESPEELD: VERVALT, RONDE BLIJFT ===\n")
        await schoon(pg); await start(pg, 'N4', dagen=3)
        await pg.evaluate("() => herplanRonde(leesRondes()[%s].id)" % IDX); await pg.wait_for_timeout(300)
        await pg.evaluate("() => nav('score')"); await vul(pg, 2)
        await pg.evaluate("() => nav('setup')"); await pg.wait_for_timeout(150)
        check("melding weg", (await pg.evaluate(ST))['banner'], False)
        await klik_start(pg)
        check("starten vervangt de gespeelde ronde niet", [(x[2], x[3]) for x in await pg.evaluate(N, 'x')], [('N4', 2)])

        print("\n=== 5. CORRIGEREN: SCORES VAN HET MOMENT VAN STARTEN ===\n")
        await schoon(pg); await start(pg, 'N5'); await vul(pg, 4)
        await pg.evaluate("() => herplanRonde(leesRondes()[%s].id, true)" % IDX); await pg.wait_for_timeout(300)
        await pg.evaluate("() => nav('score')"); await vul(pg, 6)        # twee scores erbij
        await pg.evaluate("() => nav('setup')"); await pg.wait_for_timeout(150)
        check("melding staat er nog", await pg.evaluate(ST), {'banner': True, 'notitie': 'N5'})
        await kies_baan(pg, 'Sandr'); await klik_start(pg)
        await pg.locator('#keuzeModal button', has_text='Vervangen').click(); await pg.wait_for_timeout(350)
        check("alle zes scores en de notitie zijn mee", await pg.evaluate(N, 'x'), [['Sandr', await pg.evaluate("() => todayISO()"), 'N5', 6]])

        print("\n=== 6. ZONDER UITSTAPJE KOMT ER GEEN VRAAG ===\n")
        await schoon(pg); await start(pg, 'N6', dagen=3); await pg.evaluate("() => finishActiveRound(null)")
        await pg.evaluate("() => herplanRonde(leesRondes()[%s].id)" % IDX); await pg.wait_for_timeout(300)
        await kies_baan(pg, 'Sandr'); await klik_start(pg)
        check("meteen gestart", (await pg.evaluate(KEUZE), [(x[0], x[2]) for x in await pg.evaluate(N, 'x')]), ([], [('Sandr', 'N6')]))

        print("\n=== 7. 'OUDE RONDE LATEN STAAN' ===\n")
        await schoon(pg); await start(pg, 'N7', dagen=3); await pg.evaluate("() => finishActiveRound(null)")
        await pg.evaluate("() => herplanRonde(leesRondes()[%s].id)" % IDX); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { nav('archive'); nav('setup'); }"); await pg.wait_for_timeout(200)
        await klik_start(pg)
        await pg.locator('#keuzeModal button', has_text='Oude ronde laten staan').click(); await pg.wait_for_timeout(250)
        check("opnieuw plannen is afgebroken, de notitie staat nog in het veld", await pg.evaluate(ST), {'banner': False, 'notitie': 'N7'})
        check("de oude ronde staat er nog, er is niets gestart", [(x[0], x[2]) for x in await pg.evaluate(N, 'x')], [('Airborne', 'N7')])
        await pg.evaluate("() => { document.getElementById('iTime').value = '15:45'; sel.time = '15:45'; }")
        await klik_start(pg)
        check("met een andere tijd start er een tweede ronde naast, met de notitie", sorted([(x[0], x[2]) for x in await pg.evaluate(N, 'x')]), [('Airborne', 'N7'), ('Airborne', 'N7')])

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
