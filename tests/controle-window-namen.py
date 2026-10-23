"""Gebruiken de tests de toestand van de app onder de goede naam? (1352898-024)

Sinds 024 zijn de meeste losse waarden van de app gewone variabelen (let bovenaan hun
sectie), geen window._…-eigenschappen meer. Een test die toch window._x = … schrijft,
maakt dan stil een aparte waarde waar de app niet naar kijkt, en test daarmee niets.

Deze controle faalt als een test window._x gebruikt terwijl _x in de app een gewone
variabele is (schrijf dan: _x).

Sinds 031 ook: een naam die de app helemaal niet kent, mag alleen als hulpwaarde van de
test zelf — dan zet en gebruikt hetzelfde bestand hem. Wordt hij alleen gelezen, of alleen
gezet, dan is het vrijwel zeker een oude of verkeerd gespelde naam van de app: de test
leest dan altijd niets, of zet iets waar niemand naar kijkt. Zo vond hij
window._stipVoorTabwissel (test-backup-scenarios, altijd null) en window._allesClubsDicht
(test-langindrukken, een reset die niets deed).

Bij het invoeren vond hij er al één: test-corrigeren.py las window._corrigeerScores, dat al
langer een gewone variabele was; de controle 'er blijft niets hangen' was daardoor altijd waar.
"""
import os, re, sys, glob
HIER = os.path.dirname(os.path.abspath(__file__))
app = open(os.path.join(HIER, '..', 'golf-score.html'), encoding='utf-8').read()

op_window = set(re.findall(r"window\.(_[A-Za-z0-9][A-Za-z0-9_]*)", app))
# dynamisch op window: de inklapgroepen (inklapKop('_groep', …), archiefInklapKop(…, '_groep'))
op_window |= set(re.findall(r"'(_[A-Za-z]+Collapsed)'", app))
variabelen = set()
for m in re.finditer(r"^(?:let|const) ([^=;\n]+)", app, re.M):
    for naam in re.findall(r"\b(_[A-Za-z0-9][A-Za-z0-9_]*)\b", m.group(1)):
        variabelen.add(naam)

# Teksten die juist controleren dat een naam NIET (meer) bestaat, of hem alleen noemen.
NOEMT_ALLEEN = {('controle-filter-putts.js', '_dupIds'), ('run-alles.py', '_x')}
SCHRIJF = r"\s*(?:\[[^\]]*\]\s*)?(?:=(?!=)|\|\|=|\?\?=|&&=)"

fouten = []
for f in sorted(glob.glob(os.path.join(HIER, '*.py')) + glob.glob(os.path.join(HIER, '*.js'))):
    if os.path.basename(f) == os.path.basename(__file__): continue
    tekst = open(f, encoding='utf-8').read()
    for m in re.finditer(r"window\.(_[A-Za-z0-9][A-Za-z0-9_]*)", tekst):
        naam = m.group(1)
        regel = tekst[:m.start()].count('\n') + 1
        if naam in variabelen and naam not in op_window:
            fouten.append(f"{os.path.basename(f)}:{regel}: window.{naam} — in de app een gewone variabele, schrijf {naam}")
    for naam in sorted(set(re.findall(r"window\.(_[A-Za-z0-9][A-Za-z0-9_]*)", tekst))):
        if naam in variabelen or naam in op_window or (os.path.basename(f), naam) in NOEMT_ALLEEN: continue
        plekken = list(re.finditer(r"window\." + naam + r"\b", tekst))
        gezet = [m for m in plekken if re.match(SCHRIJF, tekst[m.end():])]
        regel = tekst[:plekken[0].start()].count('\n') + 1
        if not gezet:
            fouten.append(f"{os.path.basename(f)}:{regel}: window.{naam} — de app kent deze naam niet en de test zet hem niet: leest altijd niets")
        elif len(gezet) == len(plekken):
            fouten.append(f"{os.path.basename(f)}:{regel}: window.{naam} — de app kent deze naam niet en de test leest hem nergens: zetten doet niets")

print(f"\n  {len(op_window)} namen op window, {len(variabelen)} gewone variabelen met een _ ervoor")
for r in fouten[:20]: print('  FOUT ' + r)
print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
sys.exit(1 if fouten else 0)
