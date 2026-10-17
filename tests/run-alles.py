#!/usr/bin/env python3
"""Draait alle controles en tests en geeft één samenvatting.

Gebruik:
    python3 tests/run-alles.py                 # tegen ../golf-score.html
    APP=/pad/naar/golf-score.html python3 tests/run-alles.py

Eerst de snelle statische controles (node), dan de browsertests (playwright).
Stopt nergens: je krijgt altijd het volledige beeld.
"""
import os, re, subprocess, sys, time

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.environ.get('APP') or os.path.join(os.path.dirname(HIER), 'golf-score.html')

STATISCH = [
    ('controle-diep.js',         'syntax, dode code, losse eindjes'),
    ('controle-baanmodel.js',    'par en SI horen bij de tee'),
    ('controle-breed.js',        'app-brede samenhang'),
    ('controle-herplan.js',      'opnieuw plannen'),
    ('controle-filter-putts.js', 'filters en puttregels'),
    ('controle-hernoemen.js',    'clubs/banen/tees hernoemen'),
    ('controle-inlezen.js',      'foutafvang bij inlezen', True),
    ('test-duplicaat.js',        'duplicaten en koppeling speler 2'),
    ('test-isaf.js',             '"is deze ronde af" — randgevallen'),
    ('test-afronding.js',        'afronding van de handicap en de caps, nagerekend in hele getallen'),
    ('test-whs-rekenkern.js',    'baanhandicap, Stableford, dagresultaat, ESR en index, nagerekend in hele getallen'),
    ('test-ags-volledige-baanhandicap.js', 'AGS (net double bogey) met de volledige course handicap, ook bij 85% of +/− (regel 3.1b, 2024)'),
    ('test-esr-onafgerond.js', 'uitzonderlijke score: onafgerond dagresultaat tegen de index, zonder rekenruis (regel 5.9, 2024)'),
    ('test-handicapverloop.js', 'handicapverloop (ESR, Low HI over 365 dagen, caps) nagerekend met een tweede berekening'),
    ('test-pcc-9-holes-ngf.js', 'dagresultaat 9 holes met PCC: de helft telt, nagerekend op Marks rondes tegen de NGF-app'),
    ('test-afgerond.js',         'de manieren om "afgerond" te bepalen', True),
]

BROWSER = [
    ('ijk-stats.py',            'statistieken byte-voor-byte (ijkmeting)', ['ijkmeting.json']),
    ('test-herplan-browser.py', 'opnieuw plannen, end-to-end', []),
    ('test-modals.py',          'de twee bewerkvensters', []),
    ('test-corrupt.py',         'corrupte gegevens worden niet overschreven', []),
    ('test-misvormde-opslag.py', 'leesbare maar misvormde opslag: de app start altijd en schrijft er niet overheen', []),
    ('test-keuring-bij-laden.py', 'ook een veld van het verkeerde soort laat niets vastlopen en geeft geen NaN', []),
    ('test-naam-en-lus-qualifying.py', 'naam wijzigen neemt de lopende ronde mee; qualifying komt terug na een lus', []),
    ('test-foutvanger.py',      'een onverwachte fout wordt gemeld, één keer, en raakt geen gegevens', []),
    ('test-export-mislukt.py',  'een mislukte export wordt gemeld en verschuift de backupstand niet', []),
    ('test-opslag-alleen-geheugen.py', 'kan de browser niets bewaren, dan hoor je dat vóór je gaat spelen', []),
    ('test-kleine-koppelingen.py', 'naamloze club blijft uit de opslag; kaartknoppen kloppen na een wijziging in een ander tabblad', []),
    ('test-sw-update-offline.py', 'een update bij slecht bereik breekt de app offline niet', []),
    ('test-sw-gecontroleerde-update.py', 'een nieuwe versie wacht tot je op de melding tikt; nooit vanzelf herladen, ook niet tijdens een ronde of offline', []),
    ('test-sw-actieve-cache.py', 'de updatecontrole bekijkt precies de cache van de actieve service worker', []),
    ('test-sw-afgeschermd.py', 'Golf Score onderschept alleen eigen bestanden en leest alleen uit de eigen cache, niet uit die van andere apps of een wachtende versie', []),
    ('test-sw-eigen-bestanden.py', 'alleen eigen bestanden in de cache, zonder dubbele kopieën; nooit eindeloos wachten; altijd een geldig antwoord', []),
    ('test-sw-verse-installatie.py', 'een update installeert altijd de nieuwe app (niet uit de browsercache) en laat bij mislukken niets half achter', []),
    ('test-sw-slecht-bereik.py', 'bij slecht bereik opent de app direct uit de opslag, ook via een adres met een toevoeging', []),
    ('test-sw-ronde-en-update.py', 'andere apps houden hun cache; een update of opruimactie tijdens een ronde laat de app offline bruikbaar', []),
    ('test-sw-halve-update.py', 'een mislukte update laat de draaiende cache ongemoeid: eerst alles ophalen, dan pas wegschrijven', []),
    ('test-sw-gelijk-met-buren.py', 'wat Golf Score, Trends en Events gelijk doen: cachenaam als teller, meteen melden, no-cache, grens bij installeren', []),
    ('test-afgeleide-waarden.py', 'Stableford-totaal en netto par worden uit de holes berekend, niet overgenomen', []),
    ('test-wachtende-tik.py',   'een wachtende scorewijziging blijft bij haar eigen ronde, ook als een andere ronde wordt geladen', []),
    ('test-lege-ronde-overschrijft-niet.py', 'een lege ronde overschrijft nooit een ronde met scores; de weigering komt als false terug', []),
    ('test-ags-in-beeld.py', 'overal dezelfde, juiste AGS: kaart, overzicht, deeltekst, CSV en dagresultaat', []),
    ('test-namen-per-negen-en-analyse.py', 'holenamen in de negen-tabbladen en Per negen, en baannamen in de analyse blijven tekst', []),
    ('test-percentage-en-grenzen.py', 'wedstrijdpercentage over de onafgeronde course handicap; geen grens van 54 op de baanhandicap', []),
    ('test-import-overschrijft-geen-lopende-ronde.py', 'een import overschrijft geen ronde die nog loopt', []),
    ('test-twee-vensters.py', 'twee vensters tegelijk: de stand uit de opslag gaat voor, open vensters houden vast aan de ronde', []),
    ('test-handicapvenster-en-grenzen.py', 'laatste 20 alleen met dagresultaat; dagresultaat tot 100; onbevestigde tik terug bij weggaan', []),
    ('test-caps-pas-vanaf-20.py', 'soft en hard cap pas vanaf 20 scores, overal gelijk: handicap nu, rondekaart en grafiek', []),
    ('test-esr-en-lowhi-geldende-index.py', 'uitzonderlijke score tegen de geldende index (na cap), Low HI met ESR; overal gelijk (regel 5.7/5.9, 2024)', []),
    ('test-baanhandicap-9-en-lus.py', 'baanhandicap: onafgeronde halve index bij 9 holes (R&A, regel 6.1b, zoals de NGF), naar rato bij een ander aantal, met melding', []),
    ('test-stableford-volle-chcp.py', 'wedstrijdpercentage bewaard, playing handicap (85% of −5), stableford bij 100%, Gem. Stb met volle baanhandicap', []),
    ('test-drempel-statistiek.py', 'minimum aantal rondes voor statistieken: per tee, clubs, par/SI (rondes), bovenste rij, verloop, trend en spreiding', []),
    ('test-veilige-tekst-export.py', 'namen blijven tekst: in de startmelding, als formule in de CSV en als extra regel in de agenda', []),
    ('test-mislukt-opslaan-terugdraaien.py', 'mislukt het opslaan, dan blijft alles zoals het was (nieuwe ronde, laden, naam, club)', []),
    ('test-tekst-en-herplan.py', 'datum en SI uit de opslag zijn tekst; herplannen vergeet de keuze van vóór een lus', []),
    ('test-importmeldingen.py', 'een mislukte import zegt waarom, in gewone taal; een fout in de app gaat naar de foutvanger', []),
    ('test-herstel-na-onleesbaar.py', 'na onleesbare gegevens lukt backup terugzetten, en verder niets', []),
    ('test-backupteller.py',    'backupwaarschuwing telt afgeronde rondes', []),
    ('test-tellerlag.py',       'telling klopt tijdens het spelen', []),
    ('test-paden.py',           'alle schermen en verse installatie', []),
    ('test-labels.py',          'labels bij de invoervelden', []),
    ('test-autonext.py',        'automatisch naar de volgende hole', []),
    ('test-instellingen.py',    'secties ingeklapt en backupregel bovenaan', []),
    ('test-instellingen2.py',   'tabnamen, lang indrukken, tik op de status', []),
    ('test-backupblok.py',      'backupblok bovenaan en de sprong naar Backup', []),
    ('test-backupinfo.py',      'backupstand bijgewerkt via alle acht routes', []),
    ('test-notitie-start.py',   'notitie op het startscherm en bij herplannen', []),
    ('test-cr-grenzen.py',      'CR-grenzen volgen het aantal holes', []),
    ('test-gewijzigd.py',       'gewijzigd-stempel volgt de backupinhoud', []),
    ('test-par-per-tee.py',     'par en SI per tee, van editor tot ronde', []),
    ('test-levenscyclus.py',    'baan maken, spelen, backuppen, herstellen', []),
    ('test-editor-stress.py',   'baaneditor onder druk (60 bewerkingen)', []),
    ('test-namen-met-tekens.py', 'tee- en holenamen met lastige tekens breken geen scherm en geen knop', []),
    ('test-velden-als-tekst.py', 'elk tekstveld uit een bestand is tekst: geen HTML, geen code in knoppen', []),
    ('test-herplan-startscherm.py', 'herplannen vult het startscherm volledig', []),
    ('test-rode-knoppen.py',     'wit op rood, ook pictogrammen', []),
    ('test-volgende-hole.py',    'doorspringen naar de volgende lege hole', []),
    ('test-rondeverlies.py',     'een ingevulde kaart raakt niet zoek', []),
    ('test-opslagcode.py',       'welke opslag is dit (profiel/adres)', []),
    ('test-updatebanner.py',     'versiebanner wijst de juiste kant op', []),
    ('test-langindrukken.py',    'lang indrukken is overal een toggle', []),
    ('test-clubbackup.py',       'backupherinnering voor clubs', []),
    ('test-teevolgorde.py',      'tees overal in dezelfde volgorde', []),
    ('test-rondescache.py',      'bewaarde rondelijst: snel en veilig', []),
    ('test-doorloop.py',         'hele keten met echte tikken, twee spelers', []),
    ('test-restpaden.py',        'import, 18 holes, speler 2, club tijdens ronde', []),
    ('test-importkeuring.py',    'een bestand wordt gekeurd en rechtgezet voor het wordt opgeslagen', []),
    ('test-opslagstoring.py',    'opslag weigert halverwege een ronde', []),
    ('test-opslagstoring-handelingen.py', 'bij een opslagstoring gaan afronden, wisselen en corrigeren niet door', []),
    ('test-opslagmelding.py',    'geen succesmelding als het wegschrijven van clubs of rondes mislukte', []),
    ('test-naamswijziging.py',   'naam wijzigen raakt je handicap niet stil', []),
    ('test-kopuitlijning.py',    'groepskoppen precies gelijk uitgelijnd', []),
    ('test-lijstgrens.py',       'gegroepeerde lijsten blijven begrensd', []),
    ('test-whsvolgen.py',        'handicap bijhouden aan/uit', []),
    ('test-instelling-wist-niets.py', 'een schakelaar omzetten wist niets', []),
    ('test-handicap-grenzen.py', 'handicap nooit boven 54,0 of Low HI + 5,0', []),
    ('test-handicap-alleen-speler1.py', 'handicap alleen voor de speler bovenin Start', []),
    ('test-meetellen.py',        'alleen afgerond, qualifying en niet open telt mee', []),
    ('test-slagen-per-hole.py',  'slagen per hole tellen op tot de baanhandicap', []),
    ('test-clubs-raken-rondes-niet.py', 'baan, tee of club wijzigen verandert geen ronde', []),
    ('test-honderden-rondes.py', 'elk scherm opent zonder fout bij honderden rondes', []),
    ('test-scoretik-lijst.py',   'een scoretik bouwt de rondelijst niet op; stip en lijst kloppen toch', []),
    ('test-rekenwerk-per-handeling.py', 'Statistiek en zoeken rekenen niet meer dan nodig, met dezelfde uitkomst', []),
    ('test-zelfde-baannamen.py', 'clubs met dezelfde baannamen, op elk scherm', []),
    ('test-lowhi-regel.py',      'Low HI-regel is aanklikbaar', []),
    ('test-watals.py',           'Wat als klopt met de vooruitblik', []),
    ('test-spelergroepen.py',    'geplande rondes apart per speler', []),
    ('test-wedstrijdpercentage.py','wedstrijdpercentage op de baanhandicap', []),
    ('test-actief-corrigeren.py', 'actieve ronde corrigeren zonder valse melding', []),
    ('test-notitie-behoud.py',   'notitie overleeft het hervatten', []),
    ('test-per-negen.py',        'per negen in de ronde-informatie', []),
    ('test-lowhi-per-ronde.py',  'Low HI per ronde, niet die van vandaag', []),
    ('test-wanneer-best.py',     'wanneer speel je het best (dag, maand, kwartaal)', []),
    ('test-corrigeren.py',       'gespeelde ronde corrigeren met behoud van scores', []),
    ('test-speler-wissel-corrigeren.py', 'na corrigeren staat de eigen speler er weer; een wachtende tik lekt niet naar speler 2', []),
    ('test-waarschuwingsdriehoek.py', 'driehoekje bij afgeleide waarden', []),
    ('test-backup-afronden.py', 'backupmelding volgt de drempels na afronden', []),
    ('test-backup-pauze.py',    'backupmelding stil bij starten en pauzeren', []),
    ('test-backup-scenarios.py', 'backupmelding tegen de echte backupinhoud (35 situaties)', []),
    ('test-backup-overstap.py', 'overstap vanaf 0EE/0EF met echte rondes', []),
    ('test-kop-gepland.py',     'geplande rondes in de kop', []),
    ('test-putts-langdruk.py',  'lang indrukken op + zet putts op 2', []),
    ('test-score-en-putts.py',   'score en putts horen bij elkaar, langs elke knop', []),
    ('test-notitie-tweespelers.py', 'notities bewerken met twee spelers', []),
    ('test-speler2-op-scherm.py', 'elke rondehandeling met speler 1 en met speler 2 op het scherm', []),
    ('test-herplan-onderbreken.py', 'opnieuw plannen blijft staan bij een uitstapje', []),
    ('test-wedstrijdlus.py',     'wedstrijdlus maken uit bestaande banen', []),
    ('test-wedstrijdlus-ronde.py', 'de ronde onthoudt dat hij op een wedstrijdlus is gespeeld', []),
    ('test-wedstrijdlus-bron.py', 'een verouderde wedstrijdlus tonen en bijwerken, zonder rondes te raken', []),
    ('test-startscherm-clubs.py', 'startscherm bij clubs met dezelfde baannamen', []),
    ('test-startscherm-lopende-ronde.py', 'het startscherm raakt een lopende ronde niet', []),
    ('test-lopende-ronde-andere-schermen.py', 'de andere schermen raken een lopende ronde niet', []),
    ('test-ronde-velden.py',     'geen veld van een ronde valt onderweg weg', []),
    ('test-een-tik-wist-niets.py', 'verwijderen kan nooit met één tik (alles aantikken, in elke stand)', []),
    ('test-echte-gegevens.py',   'Marks eigen clubs en rondes', []),
    ('test-clubs-heen-en-terug.py', 'clubbackup en terugzetten geeft exact dezelfde clubs; een fout bestand verandert niets', []),
    ('test-echte-knoppen.py',    'hernoemen, wedstrijdlus, herplannen en corrigeren via de echte knoppen', []),
    ('meet-prestaties.py',      'snelheid per scherm', [], True),
]

def kop(t):
    print('\n' + t)
    print('─' * len(t))

def beoordeel(regels, crash=False):
    """(faalt, slaagt) op basis van de uitvoerregels van een test.

    Regels die met 'ok' beginnen zijn geslaagde controles en tellen niet mee als
    foutsignaal: daarin kan het woord 'fout' gewoon als waarde staan (test-isaf.js
    toont een tabel met de uitkomsten 'goed' en 'fout'). En 'afwijkingen: 0' is geen
    afwijking (test-tellerlag.py). Beide werden eerder als fout geteld.
    """
    alles = '\n'.join(regels).lower()
    signaal = '\n'.join(r for r in regels if not re.match(r'ok\b', r, re.I)).lower()
    signaal = re.sub(r'afwijkingen: 0\b', '', signaal)
    faalt = bool(crash or not regels
                 or re.search(r'\b[1-9]\d* fout\(en\)', signaal)
                 or ' fout ' in signaal or 'afwijking' in signaal
                 or 'verschil gevonden' in signaal or 'syntaxfout' in signaal
                 or 'traceback' in signaal)
    slaagt = any(w in alles for w in
                 ['geen fouten', 'geslaagd', 'identiek', "alle scenario's goed",
                  'gevallen goed', 'ongewijzigd', 'afwijkingen: 0', 'fouten onderweg: geen'])
    return faalt, slaagt

def draai(cmd, naam, omschrijving, meting=False):
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900,   # de test die alles aantikt duurt ruim acht minuten
                          
                           cwd=HIER, env={**os.environ, 'APP': APP})
        uitvoer = (r.stdout or '').strip()
        crash = r.returncode != 0 and 'Traceback' in (r.stderr or '')
    except subprocess.TimeoutExpired:
        uitvoer, crash = 'TIJD VERSTREKEN', True
    except Exception as e:
        uitvoer, crash = 'FOUT: ' + str(e)[:60], True

    regels = [x.strip() for x in uitvoer.split('\n') if x.strip()]
    laatste = regels[-1] if regels else '(geen uitvoer)'
    faalt, slaagt = beoordeel(regels, crash)

    # Een foutmelding weegt altijd zwaarder dan een geruststellend woord elders in de
    # uitvoer. Eerder won 'goed' zodra er ergens 'identiek' stond, ook als de test
    # daaronder '1 FOUT(EN)' meldde — dan zag je een echte fout als 'goed'.
    if meting:
        merk, oordeel = '    ', 'meting'
    elif faalt:
        merk, oordeel = ' !! ', 'PROBLEEM'
    elif slaagt:
        merk, oordeel = '    ', 'goed'
    else:
        merk, oordeel = '  ? ', 'onduidelijk'

    sec = f'{time.time() - t0:4.1f}s'
    print(f'{merk}{naam:<26}{sec}  {oordeel:<10} {omschrijving}')
    print(f'      → {laatste[:94]}')
    return meting or (slaagt and not faalt)

def main():
    if not os.path.exists(APP):
        print('App niet gevonden: ' + APP)
        print('Geef het pad mee met APP=/pad/naar/golf-score.html')
        sys.exit(1)
    print('App: ' + APP)
    goed = []

    kop('STATISCHE CONTROLES')
    for regel in STATISCH:
        naam, oms = regel[0], regel[1]
        meting = len(regel) > 2 and regel[2]
        if os.path.exists(os.path.join(HIER, naam)):
            goed.append(draai(['node', naam], naam, oms, meting))

    kop('BROWSERTESTS')
    for regel in BROWSER:
        naam, oms, extra = regel[0], regel[1], regel[2]
        meting = len(regel) > 3 and regel[3]
        if os.path.exists(os.path.join(HIER, naam)):
            goed.append(draai(['python3', naam] + ([APP] + extra if extra else []), naam, oms, meting))

    if os.path.exists(os.path.join(HIER, 'rondes_backup.json')):
        kop('MET JE EIGEN BACKUP')
        goed.append(draai(['python3', 'test-herstel.py'], 'test-herstel.py',
                          'backup terugzetten en vergelijken'))

    kop('SAMENVATTING')
    aantal = len([g for g in goed if g is not None])
    print(f'  {sum(1 for g in goed if g)} van de {aantal} onderdelen goed of gemeten')
    if not all(goed):
        print('  Kijk hierboven bij de regels met !! of ?')
    else:
        print('  Alles in orde.')
    # De doorloop zegt of de bestaande regels nog gelden. Of de WIJZIGING goed is afgedekt
    # staat er niet in: daarvoor zijn de zes vragen.
    print()
    print('  Bij de levering: de zes vragen uit CONTROLELIJST.md, elk met een antwoord.')
    sys.exit(0 if all(goed) else 1)

if __name__ == '__main__':
    main()
