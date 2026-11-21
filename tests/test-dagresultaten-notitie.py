"""
13528A7-001: de export van Dagresultaten (voor Trends) neemt de notitie van een ronde mee.
13528F3-001: in het tekstformaat dat Trends leest: één regel per ronde,
DjjjjmmddTuumm;waarde of DjjjjmmddTuumm;waarde;notitie. Een notitie is één regel zonder
puntkomma: een regeleinde wordt een spatie, een puntkomma een komma. Een lange notitie gaat
heel mee. Daarnaast: alle notitievelden staan op 250 tekens.
"""
import asyncio, json, os, sys, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testdata
from testdata import CLUBS, app_url
from playwright.async_api import async_playwright

LANG = 'x' * 300

def rondes():
    r = copy.deepcopy(testdata.RONDES)
    for x in r:
        if x['id'] == 1: x['note'] = 'Clubcompetitie, veel wind'
        if x['id'] == 2: x['note'] = 'Eerste regel\nTweede regel; derde'
        if x['id'] == 3: x['note'] = LANG
        if x['id'] == 81: x['note'] = 'niet-qualifying, hoort er niet in'
    return r

EXPORT = """async () => {
  const oud = window.tryWriteToExportFolder; let tekst = null, naam = null;
  window.tryWriteToExportFolder = async (n, t) => { naam = n; tekst = t; return true; };
  try { await exportDagresultaten(); } finally { window.tryWriteToExportFolder = oud; }
  return [naam, tekst];
}"""

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
        await pg.goto(app_url()); await pg.evaluate(testdata.SEED, [CLUBS, rondes()])
        await pg.reload(); await pg.wait_for_timeout(500)
        naam, tekst = await pg.evaluate(EXPORT)
        regels = tekst.split('\n')
        eis('het bestand eindigt met een regeleinde, geen lege regels ertussen', [regels[-1], '' in regels[:-1]], ['', False])
        obj = {r.split(';')[0]: r.split(';')[1:] for r in regels[:-1]}
        per_id = {r['id']: r for r in rondes()}
        def sleutel(r): return 'D' + r['date'].replace('-', '') + 'T' + r['time'].replace(':', '')
        eis('bestandsnaam: .txt (13528F3-001)', naam, 'Dagresultaat_Testspeler.txt')
        w1 = obj.get(sleutel(per_id[1]))
        eis('een ronde met notitie: waarde en notitie', len(w1 or []), 2)
        eis('de notitie zoals in de ronde', w1[1] if w1 else None, 'Clubcompetitie, veel wind')
        import re
        eis('de waarde is het dagresultaat op 1 decimaal', bool(w1 and re.fullmatch(r'-?\d+\.\d', w1[0])), True)
        w2 = obj.get(sleutel(per_id[2]))
        eis('meer regels en een puntkomma: één regel, een spatie en een komma', w2[1] if w2 and len(w2) == 2 else w2, 'Eerste regel Tweede regel, derde')
        w3 = obj.get(sleutel(per_id[3]))
        eis('een notitie van 300 tekens gaat heel mee', len(w3[1]) if w3 and len(w3) == 2 else None, 300)
        w4 = obj.get(sleutel(per_id[4]))
        eis('een ronde zonder notitie: alleen de waarde, geen puntkomma aan het eind', [len(w4 or []), any(r.endswith(';') for r in regels)], [1, False])
        eis('alle sleutels met een tijd', all(re.fullmatch(r'D\d{8}T\d{4}', k) for k in obj), True)
        eis('gesorteerd op sleutel', list(obj) == sorted(obj), True)
        eis('een niet-qualifying ronde komt er nog steeds niet in, ook niet met notitie', 'niet-qualifying, hoort er niet in' in tekst, False)
        lengtes = await pg.evaluate("() => ['startNote1', 'startNote2', 'editNoteInput', 'resultNoteInput'].map(id => document.getElementById(id).getAttribute('maxlength'))")
        eis('alle vier de notitievelden: 250 tekens', lengtes, ['250', '250', '250', '250'])
        eis('geen paginafouten', pf, [])
        await b.close()
    print('\nGEEN FOUTEN' if not fouten else f'\n{len(fouten)} FOUT(EN)')
    sys.exit(1 if fouten else 0)

asyncio.run(main())
