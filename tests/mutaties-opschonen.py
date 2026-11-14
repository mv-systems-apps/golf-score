"""Vangt test-opschonen.py de fouten die ertoe doen? (1352898-033)

Maakt per mutatie een kopie van de app met één bewuste fout in het opschonen, en draait
test-opschonen.py daartegen. Elke mutatie moet minstens één FOUT geven; overleeft er één,
dan test de test die eis niet.
"""
import os, sys, subprocess, tempfile
HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.environ.get('APP') or os.path.join(HIER, '..', 'golf-score.html')
bron = open(APP, encoding='utf-8').read()

MUTATIES = [
    ('zonder narekenen (alleen het jaar plus 20)',
     "        if (standVoorOpschonen(speler, rondes.filter(r => !weg.has(r.id))) === voor) break;",
     "        break;"),
    ('zonder vloer (de nieuwste N, verder niets)',
     "        chrono.slice(vanaf).forEach(c => weg.delete(c.id));",
     "        if (vanaf < 0) chrono.slice(vanaf).forEach(c => weg.delete(c.id));"),
    ('alleen de stand van nu vergelijken (de fout uit de review)',
     "                         st.lowHi, st.afgeleideLowHi().value, laatste, jaar]);",
     "                         st.lowHi, st.afgeleideLowHi().value, laatste]);"),
    ('verwijderen kan zonder archief',
     "    verwijderBtn.disabled = !klaar;",
     "    verwijderBtn.disabled = !n;"),
    ('de sleutel kijkt niet naar de inhoud',
     "      + (djb2(JSON.stringify(rondesVoorBestand(lijst))) >>> 0).toString(36) : '',",
     "      : '',"),
    ('archiefnaam zonder tijd',
     "  const bestand = `rondes_archief_${ts}_${kenmerkVoorBestandsnaam()}(${opslagCode()}).json`;",
     "  const bestand = `rondes_archief_${ts.slice(0, 8)}_${kenmerkVoorBestandsnaam()}(${opslagCode()}).json`;"),
    ('een open ronde blokkeert niet',
     "  if (openRondeIds().size) return { open: true,",
     "  if (false) return { open: true,"),
    ('archief inlezen biedt ook Vervangen',
     "        if (/^rondes_archief_/i.test(file.name)) {",
     "        if (false) {"),
    ('beschermde rondes niet beschermd',
     "  const kandidaten = rondes.filter(r => hoortInBackup(r) && !isLopendeRonde(r)).sort(archiefNieuwsteEerst);",
     "  const kandidaten = rondes.slice().sort(archiefNieuwsteEerst);"),
]

overleefd = []
map_ = tempfile.mkdtemp(prefix='mutatie-opschonen-')
for naam, oud, nieuw in MUTATIES:
    if bron.count(oud) != 1:
        print(f" FOUT  mutatie '{naam}': de regel staat niet (precies één keer) in de app"); overleefd.append(naam); continue
    pad = os.path.join(map_, 'app.html')
    open(pad, 'w', encoding='utf-8').write(bron.replace(oud, nieuw))
    uit = subprocess.run([sys.executable, os.path.join(HIER, 'test-opschonen.py')], env={**os.environ, 'APP': pad},
                         capture_output=True, text=True, timeout=900)
    gevangen = uit.returncode != 0 and ('FOUT' in uit.stdout or 'Error' in uit.stderr)
    eerste = next((r.strip() for r in uit.stdout.splitlines() if r.startswith(' FOUT')), (uit.stderr.strip().splitlines() or ['?'])[-1])
    print(f" {' ok ' if gevangen else 'FOUT'}  {naam}: {'gevangen — ' + eerste[:110] if gevangen else 'NIET gevangen'}")
    if not gevangen: overleefd.append(naam)

print('\n' + (f'{len(overleefd)} FOUT(EN)' if overleefd else 'GEEN FOUTEN'))
sys.exit(1 if overleefd else 0)
