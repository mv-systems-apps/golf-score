"""De notitie in de bewerkvensters werkt met een potlood, zoals op het startscherm (13528FD-001).

Ronde bewerken (één speler: het potlood naast Q, 13528FD-002) en Ronde bewerken met twee spelers
(per speler een potlood naast Q):
  - geen notitie: het veld is niet zichtbaar; het potlood opent een leeg veld om te typen;
    nog een tik op een leeg veld laat het weer verdwijnen;
  - wel een notitie: het venster opent in leesstand (zichtbaar, niet te wijzigen, gedimd);
    het potlood maakt hem bewerkbaar en kleurt dan goud; nog een tik zet hem terug in
    leesstand, wat je typte blijft staan;
  - opslaan bewaart wat er staat, ook in leesstand;
  - het startscherm werkt nog zoals voorheen (dezelfde functies).
Via de echte knoppen.
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
    try: await pg.locator(sel).first.click(timeout=2000); await pg.wait_for_timeout(150); return True
    except Exception: return False

async def typ(pg, sel, tekst):
    try: await pg.locator(sel).first.fill(tekst, timeout=2000); return True
    except Exception: return False

HIER = os.path.dirname(os.path.abspath(__file__))
PLAN = open(os.path.join(HIER, 'test-op-deze-baan.py')).read().split('PLAN = """')[1].split('"""')[0]
def dag(n): return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()

# stand van een notitie: [zichtbaar, alleen-lezen, gedimd, potlood goud]
STAND = """([veld, knop]) => { const v = document.getElementById(veld), k = document.getElementById(knop); if (!v) return null;
  const goud = !!k && getComputedStyle(k).color === getComputedStyle(document.querySelector('.goud-kop')).color;
  return [!!v.offsetParent, v.readOnly, getComputedStyle(v).opacity === '0.75', goud]; }"""
NOTITIE = "(id) => (loadSavedRounds().find(r => r.id === id) || {}).note || null"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        hoofd = await ev(pg, "() => startPlayerName()")
        await ev(pg, PLAN % dag(6), [990701, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', hoofd])
        await ev(pg, PLAN % dag(7), [990702, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', hoofd])
        await ev(pg, "() => { const s = loadSavedRounds(); s.find(r => r.id === 990702).note = 'Clubcompetitie'; setRoundsAndMark(JSON.stringify(s)); }")
        OPEN1 = "(id) => doOpenRoundInfoModal(loadSavedRounds().findIndex(r => r.id === id))"

        print("\n=== 1. ÉÉN SPELER, GEEN NOTITIE ===\n")
        await ev(pg, OPEN1, 990701); await pg.wait_for_timeout(200)
        # Naast Q (13528FD-002): naast de titel scrolde het uit beeld
        NAAST_Q = "() => { const k = document.getElementById('editNoteBtn'), q = document.getElementById('editQualifyToggle').closest('.switch'); return !!k && !!k.offsetParent && Math.abs(k.getBoundingClientRect().top + k.offsetHeight / 2 - (q.getBoundingClientRect().top + q.offsetHeight / 2)) < 6 && k.getBoundingClientRect().left > q.getBoundingClientRect().right; }"
        check("het potlood staat rechts naast Q", await ev(pg, NAAST_Q), True)
        check("vlak boven de notitie (niet naast de titel)", await ev(pg, "() => { const k = document.getElementById('editNoteBtn'), w = document.getElementById('editNoteWrap'); return !!k && !!w && k.compareDocumentPosition(w) === Node.DOCUMENT_POSITION_FOLLOWING && k.closest('#roundInfoModal > div > div') !== document.querySelector('#roundInfoModal h2')?.parentElement; }"), True)
        # Afstanden gelijk aan Speler → Datum & tijd (13528FD-002; waren 20)
        check("14 px boven en onder de regels Oefenronde en Q met potlood", await ev(pg, """() => { const r = s => document.querySelector(s).getBoundingClientRect();
            if (!document.getElementById('editNoteWrap')) return null; document.getElementById('editNoteWrap').classList.remove('hidden');   // eerst tonen: het venster staat in het midden en schuift mee
            const rij = document.getElementById('editNoteBtn').parentElement.getBoundingClientRect();
            /* sinds 1352901-001 staat de regel Oefenronde tussen Datum & tijd en de regel met Q */
            const oefen = document.getElementById('editOefenToggle').closest('.switch').parentElement.getBoundingClientRect();
            const uit = [Math.round(r('label[for=editDateInput]').top - r('#editPlayerInput').bottom), Math.round(oefen.top - r('#editDateInput').bottom),
              Math.round(rij.top - oefen.bottom), Math.round(r('#editNoteInput').top - rij.bottom)];
            document.getElementById('editNoteWrap').classList.add('hidden'); return uit; }"""), [14, 14, 14, 14])
        await ev(pg, "() => { closeRoundInfoModal(); storage.setItem('golf_whs_volgen', 'off'); pasWhsWeergaveToe(); }")
        await ev(pg, OPEN1, 990701); await pg.wait_for_timeout(200)
        check("zonder Handicap bijhouden: Q weg, het potlood blijft, rechts", await ev(pg, "() => { const k = document.getElementById('editNoteBtn'), m = document.querySelector('#roundInfoModal > div'); return [!!document.getElementById('editQualRow')?.offsetParent, !!k && !!k.offsetParent, !!k && Math.abs(k.getBoundingClientRect().right - (m.getBoundingClientRect().right - parseFloat(getComputedStyle(m).paddingRight) - parseFloat(getComputedStyle(m).borderRightWidth))) < 2]; }"), [False, True, True])
        await ev(pg, "() => { closeRoundInfoModal(); storage.setItem('golf_whs_volgen', 'on'); pasWhsWeergaveToe(); }")
        await ev(pg, OPEN1, 990701); await pg.wait_for_timeout(200)
        check("geen label 'Notitie' meer", await ev(pg, "() => !document.querySelector('#roundInfoModal label[for=editNoteInput]')"), True)
        check("het veld is niet zichtbaar", (await ev(pg, STAND, ['editNoteInput', 'editNoteBtn']) or [None])[0], False)
        await klik(pg, '#editNoteBtn')
        check("potlood: leeg veld om te typen, cursor erin, potlood goud",
              [await ev(pg, STAND, ['editNoteInput', 'editNoteBtn']), await ev(pg, "() => document.activeElement && document.activeElement.id")], [[True, False, False, True], 'editNoteInput'])
        await klik(pg, '#editNoteBtn')
        check("nog een tik op een leeg veld: weer weg", (await ev(pg, STAND, ['editNoteInput', 'editNoteBtn']) or [None])[0], False)
        await klik(pg, '#editNoteBtn'); await typ(pg, '#editNoteInput', 'Nieuw genoteerd')
        await klik(pg, '#editNoteBtn')
        check("gevuld, nog een tik: leesstand, tekst blijft", [await ev(pg, STAND, ['editNoteInput', 'editNoteBtn']), await ev(pg, "() => document.getElementById('editNoteInput').value")], [[True, True, True, False], 'Nieuw genoteerd'])
        await klik(pg, 'button[onclick="confirmRoundInfo()"]'); await pg.wait_for_timeout(200)
        await ev(pg, "() => document.getElementById('confirmModal').classList.add('hidden')")
        check("opslaan in leesstand bewaart de notitie", await ev(pg, NOTITIE, 990701), 'Nieuw genoteerd')

        print("\n=== 2. ÉÉN SPELER, MET NOTITIE ===\n")
        await ev(pg, OPEN1, 990702); await pg.wait_for_timeout(200)
        check("opent in leesstand", await ev(pg, STAND, ['editNoteInput', 'editNoteBtn']), [True, True, True, False])
        check("niet te wijzigen zonder potlood", await typ(pg, '#editNoteInput', 'per ongeluk'), False)
        await klik(pg, '#editNoteBtn')
        check("potlood: bewerkbaar en goud", await ev(pg, STAND, ['editNoteInput', 'editNoteBtn']), [True, False, False, True])
        await typ(pg, '#editNoteInput', 'Clubcompetitie, ronde 2')
        await klik(pg, 'button[onclick="confirmRoundInfo()"]'); await pg.wait_for_timeout(200)
        await ev(pg, "() => document.getElementById('confirmModal').classList.add('hidden')")
        check("opgeslagen", await ev(pg, NOTITIE, 990702), 'Clubcompetitie, ronde 2')
        await ev(pg, OPEN1, 990701); await pg.wait_for_timeout(200)
        check("opnieuw openen: weer leesstand (niet onthouden)", await ev(pg, STAND, ['editNoteInput', 'editNoteBtn']), [True, True, True, False])
        await ev(pg, "() => closeRoundInfoModal()")

        print("\n=== 3. TWEE SPELERS ===\n")
        await ev(pg, PLAN % dag(10), [990801, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', hoofd])
        await ev(pg, PLAN % dag(10), [990802, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', 'Medespeler'])
        await ev(pg, "() => { const s = loadSavedRounds(); s.find(r => r.id === 990801).note = 'Met Anna'; setRoundsAndMark(JSON.stringify(s)); nav('score'); openRondesBewerken(['990801', '990802']); }"); await pg.wait_for_timeout(250)
        check("per speler een potlood in de regel van de speler", await ev(pg, """() => [1, 2].map(n => { const k = document.getElementById('rbNotBtn' + n), q = document.getElementById('rbQ' + n);
            return !!k && Math.abs(k.getBoundingClientRect().top + k.offsetHeight / 2 - (q.closest('.switch').getBoundingClientRect().top + q.closest('.switch').offsetHeight / 2)) < 6; })"""), [True, True])
        check("speler 1 (notitie) leesstand, speler 2 (geen) niet zichtbaar",
              [await ev(pg, STAND, ['rbNotitie1', 'rbNotBtn1']), (await ev(pg, STAND, ['rbNotitie2', 'rbNotBtn2']) or [None])[0]], [[True, True, True, False], False])
        await klik(pg, '#rbNotBtn2')
        check("potlood speler 2: leeg veld, cursor erin", [await ev(pg, STAND, ['rbNotitie2', 'rbNotBtn2']), await ev(pg, "() => document.activeElement && document.activeElement.id")], [[True, False, False, True], 'rbNotitie2'])
        await typ(pg, '#rbNotitie2', 'Met Bram')
        await klik(pg, 'button[onclick="bevestigRondesBewerken()"]'); await pg.wait_for_timeout(250)
        check("opslaan: beide notities", [await ev(pg, NOTITIE, 990801), await ev(pg, NOTITIE, 990802)], ['Met Anna', 'Met Bram'])

        print("\n=== 4. HET STARTSCHERM WERKT NOG ZOALS VOORHEEN ===\n")
        await ev(pg, "() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); nav('setup'); wisStartNotes(); }"); await pg.wait_for_timeout(200)
        await klik(pg, '#noteBtn1'); await typ(pg, '#startNote1', 'Start')
        check("start: potlood opent, typen kan, goud", await ev(pg, STAND, ['startNote1', 'noteBtn1']), [True, False, False, True])
        await klik(pg, '#noteBtn1')
        check("start: tweede tik leesstand", await ev(pg, STAND, ['startNote1', 'noteBtn1']), [True, True, True, False])
        await ev(pg, "() => zetStartNote(2, 'Meegekomen')")
        check("start: zetStartNote opent in leesstand", await ev(pg, "() => [document.getElementById('startNote2').readOnly, document.getElementById('noteWrap2').classList.contains('hidden')]"), [True, False])
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
