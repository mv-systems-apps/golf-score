"""
13528ED-001: een geplande ronde die je herplant en opnieuw naar de agenda exporteert, verzet
de afspraak die er al staat, in plaats van er een tweede naast te zetten. Dat kan omdat elke
export van dezelfde ronde dezelfde herkenning (UID) heeft, met een oplopend volgnummer
(SEQUENCE). Herplannen maakt een nieuwe ronde; die neemt de herkenning van de oude over in
het veld agendaUid. Proef op de telefoon (1-11-2026): de agenda werkt dan bij.

Via de knoppen: het exportvenster, de optie Agenda en OK; het deelmenu wordt opgevangen.
"""
import asyncio, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testdata
from testdata import app_url
from playwright.async_api import async_playwright

CLUBS = {
    "Golfclub Heelsum": {
        "club": "Golfclub Heelsum", "shortName": "Heelsum",
        "courses": {"Airborne": {
            "tees": {"Heren": {"Blauw": {"CR": 34.5, "SR": 120, "holes": [{"par": 4 if i % 3 else 3, "si": i + 1} for i in range(9)]}}},
            "holeIds": [i + 1 for i in range(9)]}},
    }
}

def ronde(rid, datum, tijd, extra=None):
    r = {"id": rid, "date": datum, "time": tijd, "player": "Testspeler", "hcp": 30.7,
         "club": "Golfclub Heelsum", "clubShort": "Heelsum", "track": "Airborne",
         "gender": "Heren", "tee": "Blauw", "CR": 34.5, "SR": 120, "PAR": 35, "chcp": 11,
         "qualifying": True, "total": 0, "holesCount": 9, "currentHole": 0, "started": True,
         "holes": [{"id": str(i + 1), "par": 4 if i % 3 else 3, "si": i + 1, "phcp": 1,
                    "ppar": (4 if i % 3 else 3) + 1, "score": None} for i in range(9)]}
    r.update(extra or {})
    return r

VANG = """() => {
  window.__ics = [];
  navigator.canShare = () => true;
  navigator.share = async (d) => { for (const f of (d.files || [])) window.__ics.push(await f.text()); };
}"""

async def exporteer(pg, rid):
    """Zoals een gebruiker: het exportvenster van de kaart, Agenda, OK."""
    await pg.evaluate("""(rid) => {
      const idx = loadSavedRounds().findIndex(r => String(r.id) === String(rid));
      openExportModal(idx);
      document.getElementById('exportOptAgenda').click();
      [...document.querySelectorAll('#exportModal button')].find(b => b.textContent.trim() === 'OK').click();
    }""", rid)
    await pg.wait_for_timeout(300)
    return await pg.evaluate("() => window.__ics[window.__ics.length - 1] || ''")

def veld(ics, naam):
    m = re.search(r'^' + naam + r':(.*)$', ics, re.M)
    return m.group(1).strip() if m else None

async def main():
    fouten = []
    def eis(naam, kreeg, verwacht):
        ok = kreeg == verwacht
        print(('  OK   ' if ok else '  FOUT ') + naam + ('' if ok else f'  — kreeg {kreeg!r}, verwacht {verwacht!r}'))
        if not ok: fouten.append(naam)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url())
        await pg.evaluate("""([clubs, rondes]) => { localStorage.clear();
          localStorage.setItem('golf_clubs', JSON.stringify(clubs)); localStorage.setItem('golf_rounds', JSON.stringify(rondes));
          localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_player_name', 'Testspeler');
          localStorage.setItem('golf_player_hcp', '30.7'); }""", [CLUBS, [ronde(7001, '2027-05-01', '09:00')]])
        await pg.reload(); await pg.wait_for_timeout(500)
        await pg.evaluate(VANG)

        ics1 = await exporteer(pg, 7001)
        eis('de eerste export: de herkenning is vast per ronde (geen tijdstip van exporteren erin)', veld(ics1, 'UID'), 'golfscore-7001@golf-score.local')
        seq1 = int(veld(ics1, 'SEQUENCE') or -1)
        eis('met een volgnummer dat bij elke export hoger is', seq1 > 0, True)
        await pg.wait_for_timeout(1100)
        ics1b = await exporteer(pg, 7001)
        eis('nog eens exporteren: dezelfde herkenning, een hoger volgnummer', [veld(ics1b, 'UID'), int(veld(ics1b, 'SEQUENCE') or -1) > seq1], ['golfscore-7001@golf-score.local', True])

        # herplannen: naar 13:00, en starten zoals Start dat doet
        log = await pg.evaluate("""() => {
          herplanRonde('7001');
          const t = document.getElementById('iTime'); t.value = '13:00'; t.dispatchEvent(new Event('change', { bubbles: true }));
          startRound();
          const cb = document.getElementById('confirmModalBtn');
          if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
          const rs = JSON.parse(localStorage.getItem('golf_rounds') || '[]');
          return rs.map(r => [String(r.id), r.time, r.agendaUid || null]);
        }""")
        await pg.wait_for_timeout(300)
        nieuw = [r for r in log if r[1] == '13:00']
        eis('na herplannen: één ronde om 13:00, de oude is weg', [len(nieuw), any(r[0] == '7001' for r in log)], [1, False])
        eis('de herplande ronde draagt de herkenning van de oude', nieuw[0][2] if nieuw else None, 'golfscore-7001')
        # 13528FA-001: het agenda-icoon. De oude ronde was geëxporteerd; de herplande ronde neemt
        # dat over en is dus 'gewijzigd' (de agenda heeft nog 09:00). Na de export weer 'erin'.
        st = await pg.evaluate("(id) => { try { const r = loadSavedRounds().find(x => String(x.id) === id); return r ? [agendaStatus(r), typeof r.agendaExport === 'string' && r.agendaExport.includes('|09:00|')] : null; } catch (e) { return 'FOUT: ' + e.message; } }", nieuw[0][0]) if nieuw else None
        eis('de herplande ronde: agenda-icoon goud, met de export van de oude ronde (09:00)', st, ['gewijzigd', True])
        await pg.wait_for_timeout(1100)
        ics2 = await exporteer(pg, nieuw[0][0]) if nieuw else ''
        eis('de export van de herplande ronde: dezelfde herkenning, dus de agenda verzet de afspraak',
            veld(ics2, 'UID'), 'golfscore-7001@golf-score.local')
        st2 = await pg.evaluate("(id) => { try { return agendaStatus(loadSavedRounds().find(x => String(x.id) === id)); } catch (e) { return 'FOUT: ' + e.message; } }", nieuw[0][0]) if nieuw else None
        eis('na de export van de herplande ronde: agenda-icoon weer grijs ✓', st2, 'erin')
        eis('met een hoger volgnummer en de nieuwe tijd', [int(veld(ics2, 'SEQUENCE') or -1) > int(veld(ics1b, 'SEQUENCE') or 0), (veld(ics2, 'DTSTART') or '')[9:13]],
            [True, '1100'])   # 13:00 in mei (zomertijd) is 11:00 UTC

        # nog een keer herplannen: de herkenning blijft die van de eerste ronde
        await pg.evaluate("""() => {
          const r = JSON.parse(localStorage.getItem('golf_rounds')).find(x => x.time === '13:00');
          herplanRonde(String(r.id));
          const t = document.getElementById('iTime'); t.value = '14:30'; t.dispatchEvent(new Event('change', { bubbles: true }));
          startRound();
          const cb = document.getElementById('confirmModalBtn');
          if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
        }""")
        await pg.wait_for_timeout(300)
        twee = await pg.evaluate("() => JSON.parse(localStorage.getItem('golf_rounds')).filter(r => r.time === '14:30').map(r => r.agendaUid || null)")
        eis('twee keer herplannen: nog steeds de herkenning van de eerste ronde', twee, ['golfscore-7001'])

        # een backup terugzetten en de keuring: het veld gaat mee, een verkeerd soort waarde niet
        keur = await pg.evaluate("""() => [keurRonde(zetRondeRecht(JSON.parse(JSON.stringify(Object.assign(JSON.parse(localStorage.getItem('golf_rounds'))[0], { agendaUid: 'golfscore-7001' }))))),
                                          keurRonde(zetRondeRecht(Object.assign(JSON.parse(localStorage.getItem('golf_rounds'))[0], { agendaUid: 5 })))]""")
        eis('de keuring: een herkenning als tekst is goed, een getal niet', keur, [None, 'agendaherkenning is geen tekst'])
        eis('geen paginafouten', pf, [])
        await b.close()
    print('\nGEEN FOUTEN' if not fouten else f'\n{len(fouten)} FOUT(EN)')
    sys.exit(1 if fouten else 0)

asyncio.run(main())
